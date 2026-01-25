"""
System Tools - Core operations tools as defined in the plan
"""

import psutil
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


async def get_system_info(params: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Get system information including CPU, memory, disk, and uptime
    
    Permission: READ
    """
    try:
        # CPU info
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory info
        memory = psutil.virtual_memory()
        memory_gb = memory.total / (1024**3)
        memory_used_gb = memory.used / (1024**3)
        memory_percent = memory.percent
        
        # Disk info
        disk = psutil.disk_usage('/')
        disk_total_gb = disk.total / (1024**3)
        disk_used_gb = disk.used / (1024**3)
        disk_percent = disk.percent
        
        # System info
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        uptime_str = str(uptime).split('.')[0]  # Remove microseconds
        
        # Load average (Unix-like systems)
        try:
            load_avg = psutil.getloadavg()
            load_str = f"\n📊 Load Average: {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}"
        except:
            load_str = ""
        
        status = f"""🖥️ System Status
        
💻 Platform: {platform.system()} {platform.release()}
🏗️ Architecture: {platform.machine()}
⏰ Uptime: {uptime_str}

⚙️ CPU
  • Cores: {cpu_count}
  • Usage: {cpu_percent}%{load_str}

🧠 Memory
  • Total: {memory_gb:.1f} GB
  • Used: {memory_used_gb:.1f} GB ({memory_percent}%)
  • Available: {memory.available / (1024**3):.1f} GB

💾 Disk (/)
  • Total: {disk_total_gb:.1f} GB
  • Used: {disk_used_gb:.1f} GB ({disk_percent}%)
  • Free: {disk.free / (1024**3):.1f} GB

🔄 Processes: {len(psutil.pids())} running
"""
        
        return status.strip()
    
    except Exception as e:
        return f"❌ Error getting system status: {str(e)}"


async def check_disk_space(params: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Check disk usage for a specific path or all mounted partitions
    
    Permission: READ
    Parameters:
        path (optional): Specific path to check
        detailed (optional): Show detailed partition info
    """
    try:
        path = params.get("path")
        detailed = params.get("detailed", False)
        
        if path:
            # Check specific path
            disk = psutil.disk_usage(path)
            total_gb = disk.total / (1024**3)
            used_gb = disk.used / (1024**3)
            free_gb = disk.free / (1024**3)
            
            return f"""💾 Disk Usage: {path}

Total: {total_gb:.2f} GB
Used: {used_gb:.2f} GB ({disk.percent}%)
Free: {free_gb:.2f} GB
"""
        
        # Check all partitions
        partitions = psutil.disk_partitions()
        output = ["💾 Disk Usage - All Partitions\n"]
        
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                total_gb = usage.total / (1024**3)
                used_gb = usage.used / (1024**3)
                free_gb = usage.free / (1024**3)
                
                output.append(f"📁 {partition.mountpoint}")
                if detailed:
                    output.append(f"   Device: {partition.device}")
                    output.append(f"   Type: {partition.fstype}")
                output.append(f"   Total: {total_gb:.2f} GB")
                output.append(f"   Used: {used_gb:.2f} GB ({usage.percent}%)")
                output.append(f"   Free: {free_gb:.2f} GB")
                output.append("")
            except PermissionError:
                output.append(f"📁 {partition.mountpoint} (access denied)")
                output.append("")
        
        return "\n".join(output).strip()
    
    except Exception as e:
        return f"❌ Error checking disk: {str(e)}"


async def read_logs(params: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Read audit logs or system logs
    
    Permission: READ
    Parameters:
        log_type: "audit" or "system" (default: audit)
        limit: Number of lines to return (default: 20)
    """
    try:
        log_type = params.get("log_type", "audit")
        limit = params.get("limit", 20)
        
        if log_type == "audit":
            # Read audit logs from tool gateway
            log_dir = Path.home() / ".copilot-ops" / "logs"
            log_file = log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
            
            if not log_file.exists():
                return "📜 No audit logs found for today"
            
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            # Get last N lines
            recent_lines = lines[-limit:]
            
            output = [f"📜 Audit Logs (last {len(recent_lines)} entries)\n"]
            
            for line in recent_lines:
                try:
                    import json
                    entry = json.loads(line)
                    timestamp = entry['timestamp'].split('T')[1].split('.')[0]  # HH:MM:SS
                    tool = entry['tool_name']
                    success = "✅" if entry['success'] else "❌"
                    duration = f"{entry['duration_ms']:.0f}ms"
                    
                    output.append(f"[{timestamp}] {success} {tool} ({duration})")
                    
                    # Show error if failed
                    if not entry['success'] and entry.get('error'):
                        output.append(f"   Error: {entry['error']}")
                except:
                    pass
            
            return "\n".join(output)
        
        elif log_type == "system":
            # Read system logs (this would vary by OS)
            # For now, just return process information
            output = ["🖥️ System Process Info (Top 10 by CPU)\n"]
            
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    pinfo = proc.info
                    processes.append(pinfo)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Sort by CPU usage
            processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
            
            for proc in processes[:10]:
                pid = proc['pid']
                name = proc['name'][:30]  # Truncate long names
                cpu = proc['cpu_percent']
                mem = proc['memory_percent']
                output.append(f"PID {pid:5d} | {name:30s} | CPU: {cpu:5.1f}% | MEM: {mem:5.1f}%")
            
            return "\n".join(output)
        
        else:
            return f"❌ Unknown log type: {log_type}. Use 'audit' or 'system'"
    
    except Exception as e:
        return f"❌ Error reading logs: {str(e)}"


async def list_processes(params: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    List running processes with optional filtering
    
    Permission: READ
    Parameters:
        filter (optional): Filter by process name
        sort_by: "cpu" or "memory" (default: cpu)
        limit: Number of processes to show (default: 15)
    """
    try:
        filter_name = params.get("filter", "").lower()
        sort_by = params.get("sort_by", "cpu")
        limit = params.get("limit", 15)
        
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
            try:
                pinfo = proc.info
                
                # Apply filter if specified
                if filter_name and filter_name not in pinfo['name'].lower():
                    continue
                
                processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort
        if sort_by == "memory":
            processes.sort(key=lambda x: x.get('memory_percent', 0), reverse=True)
        else:
            processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
        
        # Build output
        filter_str = f" (filtered by '{filter_name}')" if filter_name else ""
        output = [f"🔄 Running Processes{filter_str} (sorted by {sort_by})\n"]
        
        for proc in processes[:limit]:
            pid = proc['pid']
            name = proc['name'][:35]
            cpu = proc['cpu_percent']
            mem = proc['memory_percent']
            status = proc['status']
            
            output.append(f"PID {pid:6d} | {name:35s} | CPU: {cpu:5.1f}% | MEM: {mem:5.1f}% | {status}")
        
        if len(processes) > limit:
            output.append(f"\n... and {len(processes) - limit} more processes")
        
        return "\n".join(output)
    
    except Exception as e:
        return f"❌ Error listing processes: {str(e)}"


async def get_network_stats(params: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Get network interface statistics
    
    Permission: READ
    Parameters:
        detailed (optional): Show detailed per-interface stats
    """
    try:
        detailed = params.get("detailed", False)
        
        # Get network interfaces
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        io_counters = psutil.net_io_counters(pernic=True)
        
        output = ["🌐 Network Interfaces\n"]
        
        for iface_name in sorted(addrs.keys()):
            # Skip loopback unless detailed
            if not detailed and ('lo' in iface_name.lower() or iface_name == '127.0.0.1'):
                continue
            
            output.append(f"📡 {iface_name}")
            
            # Show addresses
            for addr in addrs[iface_name]:
                if addr.family == 2:  # AF_INET (IPv4)
                    output.append(f"   IPv4: {addr.address}")
                elif addr.family == 10:  # AF_INET6 (IPv6)
                    if detailed:
                        output.append(f"   IPv6: {addr.address}")
            
            # Show stats
            if iface_name in stats:
                stat = stats[iface_name]
                status = "UP" if stat.isup else "DOWN"
                speed = f"{stat.speed} Mbps" if stat.speed > 0 else "Unknown"
                output.append(f"   Status: {status}, Speed: {speed}")
            
            # Show I/O counters if available
            if iface_name in io_counters:
                io = io_counters[iface_name]
                sent_mb = io.bytes_sent / (1024**2)
                recv_mb = io.bytes_recv / (1024**2)
                output.append(f"   Traffic: ↑{sent_mb:.1f} MB ↓{recv_mb:.1f} MB")
            
            output.append("")
        
        return "\n".join(output).strip()
        
    except Exception as e:
        return f"❌ Error getting network stats: {str(e)}"


# Tool definitions for registration
from tool_gateway import ToolDefinition, ToolPermission

SYSTEM_TOOLS = [
    ToolDefinition(
        name="get_system_info",
        description="Get comprehensive system information including CPU, memory, disk usage, and uptime. Use this to check overall system health.",
        permission=ToolPermission.READ,
        input_schema={
            "type": "object",
            "properties": {},
            "required": []
        },
        callback=get_system_info,
        category="system"
    ),
    ToolDefinition(
        name="check_disk_space",
        description="Check disk usage for specific path or all partitions. Use this to monitor disk space.",
        permission=ToolPermission.READ,
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Optional path to check (e.g., '/', '/home'). If not specified, shows all partitions."
                },
                "detailed": {
                    "type": "boolean",
                    "description": "Show detailed partition information including device and filesystem type.",
                    "default": False
                }
            },
            "required": []
        },
        callback=check_disk_space,
        category="system"
    ),
    ToolDefinition(
        name="read_logs",
        description="Read audit logs (tool executions) or system logs (process info). Use this to check what operations have been performed or system activity.",
        permission=ToolPermission.READ,
        input_schema={
            "type": "object",
            "properties": {
                "log_type": {
                    "type": "string",
                    "description": "Type of logs to read: 'audit' for tool execution logs, 'system' for process information.",
                    "default": "audit"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of log entries to return.",
                    "default": 20
                }
            },
            "required": []
        },
        callback=read_logs,
        category="monitoring"
    ),
    ToolDefinition(
        name="list_processes",
        description="List running processes with filtering and sorting options. Use this to see what's running on the system.",
        permission=ToolPermission.READ,
        input_schema={
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "Filter processes by name (case-insensitive partial match)."
                },
                "sort_by": {
                    "type": "string",
                    "description": "Sort by 'cpu' or 'memory'. Default is 'cpu'.",
                    "default": "cpu"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of processes to show.",
                    "default": 15
                }
            },
            "required": []
        },
        callback=list_processes,
        category="system"
    ),
    ToolDefinition(
        name="get_network_stats",
        description="Get network interface information and statistics. Use this to check network connectivity and traffic.",
        permission=ToolPermission.READ,
        input_schema={
            "type": "object",
            "properties": {
                "detailed": {
                    "type": "boolean",
                    "description": "Show detailed information including IPv6 addresses and loopback interfaces.",
                    "default": False
                }
            },
            "required": []
        },
        callback=get_network_stats,
        category="network"
    )
]
