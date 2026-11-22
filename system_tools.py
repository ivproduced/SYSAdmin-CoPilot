"""Cross-platform, read-only system inspection tools."""

from __future__ import annotations

import platform
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

from tool_gateway import AuditLogger, ToolDefinition, ToolPermission


def get_system_info(params: dict[str, Any], context: dict[str, Any]) -> str:
    """Get CPU, memory, disk, uptime, and platform information."""

    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    memory = psutil.virtual_memory()
    root_path = Path.home().anchor or "/"
    disk = psutil.disk_usage(root_path)
    try:
        uptime_text = str(
            datetime.now(UTC) - datetime.fromtimestamp(psutil.boot_time(), tz=UTC)
        ).split(".")[0]
    except (PermissionError, OSError):
        uptime_text = "Unavailable"
    try:
        process_count: str | int = len(psutil.pids())
    except (PermissionError, OSError):
        process_count = "Unavailable"

    try:
        load_average = psutil.getloadavg()
        load_text = (
            f"\n  • Load average: {load_average[0]:.2f}, "
            f"{load_average[1]:.2f}, {load_average[2]:.2f}"
        )
    except (AttributeError, OSError):
        load_text = ""

    return f"""🖥️ System Status

💻 Platform: {platform.system()} {platform.release()}
🏗️ Architecture: {platform.machine()}
⏰ Uptime: {uptime_text}

⚙️ CPU
  • Cores: {cpu_count}
  • Usage: {cpu_percent}%{load_text}

🧠 Memory
  • Total: {memory.total / (1024**3):.1f} GB
  • Used: {memory.used / (1024**3):.1f} GB ({memory.percent}%)
  • Available: {memory.available / (1024**3):.1f} GB

💾 Disk ({root_path})
  • Total: {disk.total / (1024**3):.1f} GB
  • Used: {disk.used / (1024**3):.1f} GB ({disk.percent}%)
  • Free: {disk.free / (1024**3):.1f} GB

🔄 Processes: {process_count}"""


def check_disk_space(params: dict[str, Any], context: dict[str, Any]) -> str:
    """Check disk usage for a path or every mounted partition."""

    path = params.get("path")
    detailed = params.get("detailed", False)
    if path:
        disk = psutil.disk_usage(path)
        return f"""💾 Disk Usage: {path}

Total: {disk.total / (1024**3):.2f} GB
Used: {disk.used / (1024**3):.2f} GB ({disk.percent}%)
Free: {disk.free / (1024**3):.2f} GB"""

    output = ["💾 Disk Usage - All Partitions", ""]
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except (PermissionError, OSError):
            output.extend([f"📁 {partition.mountpoint} (access denied)", ""])
            continue

        output.append(f"📁 {partition.mountpoint}")
        if detailed:
            output.append(f"   Device: {partition.device}")
            output.append(f"   Type: {partition.fstype}")
        output.extend(
            [
                f"   Total: {usage.total / (1024**3):.2f} GB",
                f"   Used: {usage.used / (1024**3):.2f} GB ({usage.percent}%)",
                f"   Free: {usage.free / (1024**3):.2f} GB",
                "",
            ]
        )
    return "\n".join(output).strip()


def read_logs(params: dict[str, Any], context: dict[str, Any]) -> str:
    """Read gateway audit entries or summarize the busiest processes."""

    log_type = params.get("log_type", "audit")
    limit = params.get("limit", 20)

    if log_type == "audit":
        audit_logger = context.get("audit_logger")
        if not isinstance(audit_logger, AuditLogger):
            raise RuntimeError("Audit logger is not available")
        logs = audit_logger.get_recent_logs(limit)
        if not logs:
            return "📜 No audit logs found for today"

        output = [f"📜 Audit Logs (last {len(logs)} entries)", ""]
        for entry in logs:
            timestamp = entry.timestamp.split("T", maxsplit=1)[-1].split(
                ".", maxsplit=1
            )[0]
            status = "✅" if entry.success else "❌"
            output.append(
                f"[{timestamp}] {status} {entry.tool_name} ({entry.duration_ms:.0f}ms)"
            )
            if not entry.success and entry.error:
                output.append(f"   Error: {entry.error}")
        return "\n".join(output)

    processes = _collect_processes()
    processes.sort(key=lambda process: process["cpu_percent"], reverse=True)
    output = ["🖥️ System Process Info (Top 10 by CPU)", ""]
    output.extend(_format_process(process) for process in processes[:10])
    return "\n".join(output)


def list_processes(params: dict[str, Any], context: dict[str, Any]) -> str:
    """List running processes with optional filtering and sorting."""

    filter_name = params.get("filter", "").lower()
    sort_by = params.get("sort_by", "cpu")
    limit = params.get("limit", 15)
    processes = [
        process
        for process in _collect_processes(include_status=True)
        if not filter_name or filter_name in process["name"].lower()
    ]
    sort_key = "memory_percent" if sort_by == "memory" else "cpu_percent"
    processes.sort(key=lambda process: process[sort_key], reverse=True)

    filter_text = f" (filtered by '{filter_name}')" if filter_name else ""
    output = [f"🔄 Running Processes{filter_text} (sorted by {sort_by})", ""]
    output.extend(
        _format_process(process, include_status=True) for process in processes[:limit]
    )
    if len(processes) > limit:
        output.append(f"\n... and {len(processes) - limit} more processes")
    return "\n".join(output)


def _collect_processes(*, include_status: bool = False) -> list[dict[str, Any]]:
    attributes = ["pid", "name", "cpu_percent", "memory_percent"]
    if include_status:
        attributes.append("status")

    processes: list[dict[str, Any]] = []
    try:
        for process in psutil.process_iter(attributes):
            try:
                info = process.info
                info["name"] = str(info.get("name") or "unknown")
                info["cpu_percent"] = float(info.get("cpu_percent") or 0)
                info["memory_percent"] = float(info.get("memory_percent") or 0)
                info["status"] = str(info.get("status") or "unknown")
                processes.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except (PermissionError, OSError):
        pass
    return processes


def _format_process(process: dict[str, Any], *, include_status: bool = False) -> str:
    text = (
        f"PID {process['pid']:6d} | {process['name'][:35]:35s} | "
        f"CPU: {process['cpu_percent']:5.1f}% | MEM: {process['memory_percent']:5.1f}%"
    )
    if include_status:
        text += f" | {process['status']}"
    return text


def get_network_stats(params: dict[str, Any], context: dict[str, Any]) -> str:
    """Get network interface addresses and traffic counters."""

    detailed = params.get("detailed", False)
    addresses = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    counters = psutil.net_io_counters(pernic=True)
    output = ["🌐 Network Interfaces", ""]

    for interface_name in sorted(addresses):
        interface_addresses = addresses[interface_name]
        is_loopback = any(
            address.family == socket.AF_INET and address.address.startswith("127.")
            for address in interface_addresses
        )
        if is_loopback and not detailed:
            continue

        output.append(f"📡 {interface_name}")
        for address in interface_addresses:
            if address.family == socket.AF_INET:
                output.append(f"   IPv4: {address.address}")
            elif detailed and address.family == socket.AF_INET6:
                output.append(f"   IPv6: {address.address}")

        if interface_name in stats:
            interface_stats = stats[interface_name]
            status = "UP" if interface_stats.isup else "DOWN"
            speed = (
                f"{interface_stats.speed} Mbps"
                if interface_stats.speed > 0
                else "Unknown"
            )
            output.append(f"   Status: {status}, Speed: {speed}")
        if interface_name in counters:
            interface_counters = counters[interface_name]
            output.append(
                "   Traffic: "
                f"↑{interface_counters.bytes_sent / (1024**2):.1f} MB "
                f"↓{interface_counters.bytes_recv / (1024**2):.1f} MB"
            )
        output.append("")
    return "\n".join(output).strip()


SYSTEM_TOOLS = [
    ToolDefinition(
        name="get_system_info",
        description=(
            "Get comprehensive system information including CPU, memory, disk usage, "
            "and uptime. Use this to check overall system health."
        ),
        permission=ToolPermission.READ,
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        callback=get_system_info,
        category="system",
    ),
    ToolDefinition(
        name="check_disk_space",
        description=(
            "Check disk usage for a specific path or all mounted partitions. "
            "Use this to monitor disk space."
        ),
        permission=ToolPermission.READ,
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "minLength": 1, "maxLength": 4096},
                "detailed": {"type": "boolean", "default": False},
            },
            "additionalProperties": False,
        },
        callback=check_disk_space,
        category="system",
    ),
    ToolDefinition(
        name="read_logs",
        description="Read gateway audit entries or current process activity.",
        permission=ToolPermission.READ,
        input_schema={
            "type": "object",
            "properties": {
                "log_type": {
                    "type": "string",
                    "enum": ["audit", "system"],
                    "default": "audit",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 20,
                },
            },
            "additionalProperties": False,
        },
        callback=read_logs,
        category="monitoring",
    ),
    ToolDefinition(
        name="list_processes",
        description="List running processes with filtering and sorting options.",
        permission=ToolPermission.READ,
        input_schema={
            "type": "object",
            "properties": {
                "filter": {"type": "string", "maxLength": 100},
                "sort_by": {
                    "type": "string",
                    "enum": ["cpu", "memory"],
                    "default": "cpu",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 15,
                },
            },
            "additionalProperties": False,
        },
        callback=list_processes,
        category="system",
    ),
    ToolDefinition(
        name="get_network_stats",
        description="Get network interface information and traffic statistics.",
        permission=ToolPermission.READ,
        input_schema={
            "type": "object",
            "properties": {"detailed": {"type": "boolean", "default": False}},
            "additionalProperties": False,
        },
        callback=get_network_stats,
        category="network",
    ),
]
