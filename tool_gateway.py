"""Validation, execution, and audit boundary for agent tools."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError


class ToolPermission(Enum):
    """Declared sensitivity of a tool operation."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


@dataclass(frozen=True)
class ToolDefinition:
    """Tool metadata and callback registered with the gateway."""

    name: str
    description: str
    permission: ToolPermission
    input_schema: dict[str, Any]
    callback: Callable[[dict[str, Any], dict[str, Any]], Any]
    category: str = "general"


@dataclass
class ToolExecution:
    """Audit record for one attempted tool execution."""

    tool_name: str
    timestamp: str
    permission_level: str
    input_params: dict[str, Any]
    success: bool
    output: str | None = None
    error: str | None = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolGatewayError(RuntimeError):
    """Base class for controlled gateway failures."""


class ToolNotFoundError(ToolGatewayError):
    """Raised when a requested tool is not registered."""


class ToolValidationError(ToolGatewayError):
    """Raised when tool arguments do not match the declared schema."""


class ToolAuthorizationError(ToolGatewayError):
    """Raised when the caller is not allowed to execute a tool."""


class ToolExecutionError(ToolGatewayError):
    """Raised when a registered tool callback fails."""


class AuditLogger:
    """Append-only JSONL audit logger with daily file rotation."""

    def __init__(self, log_dir: Path, enabled: bool = True):
        self.log_dir = log_dir
        self.enabled = enabled
        self._write_lock = threading.Lock()

    def _log_file(self, timestamp: datetime | None = None) -> Path:
        timestamp = timestamp or datetime.now(UTC)
        return self.log_dir / f"audit_{timestamp.strftime('%Y%m%d')}.jsonl"

    def log(self, execution: ToolExecution) -> None:
        if not self.enabled:
            return

        payload = json.dumps(execution.to_dict(), ensure_ascii=False) + "\n"
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
        with self._write_lock:
            self.log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor = os.open(self._log_file(), flags, 0o600)
            with os.fdopen(descriptor, "a", encoding="utf-8") as log_file:
                log_file.write(payload)

    def get_recent_logs(self, limit: int = 50) -> list[ToolExecution]:
        if limit < 1:
            raise ValueError("limit must be at least 1")

        log_file = self._log_file()
        if not self.enabled or not log_file.exists():
            return []

        logs: list[ToolExecution] = []
        with log_file.open("r", encoding="utf-8") as file_handle:
            lines = deque(file_handle, maxlen=limit)

        for line in lines:
            try:
                logs.append(ToolExecution(**json.loads(line)))
            except (json.JSONDecodeError, TypeError):
                continue
        return logs


class ToolGateway:
    """Register and execute tools through a single validated audit boundary."""

    def __init__(
        self,
        log_dir: Path | None = None,
        *,
        audit_logging: bool = True,
    ):
        self.tools: dict[str, ToolDefinition] = {}
        self.audit_logger = AuditLogger(
            log_dir or Path.home() / ".copilot-ops" / "logs",
            enabled=audit_logging,
        )
        self._execution_count = 0
        self._success_count = 0
        self._failure_count = 0

    def register_tool(self, tool: ToolDefinition) -> None:
        if tool.name in self.tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._validate_tool_definition(tool)
        self.tools[tool.name] = tool

    def _validate_tool_definition(self, tool: ToolDefinition) -> None:
        if not tool.name:
            raise ValueError("Tool name is required")
        if not tool.description:
            raise ValueError("Tool description is required")
        if not isinstance(tool.permission, ToolPermission):
            raise TypeError("Tool permission must be a ToolPermission")
        if not tool.input_schema:
            raise ValueError("Tool input_schema is required")
        if not callable(tool.callback):
            raise TypeError("Tool callback must be callable")
        try:
            Draft202012Validator.check_schema(tool.input_schema)
        except SchemaError as exc:
            raise ValueError(
                f"Invalid schema for tool '{tool.name}': {exc.message}"
            ) from exc

    def _validate_input(self, tool: ToolDefinition, params: dict[str, Any]) -> None:
        if not isinstance(params, dict):
            raise ToolValidationError("Tool arguments must be a JSON object")
        try:
            Draft202012Validator(tool.input_schema).validate(params)
        except ValidationError as exc:
            location = ".".join(str(part) for part in exc.absolute_path)
            prefix = (
                f"Invalid parameter '{location}'" if location else "Invalid parameters"
            )
            raise ToolValidationError(f"{prefix}: {exc.message}") from exc

    def _authorize(self, tool: ToolDefinition, context: dict[str, Any]) -> None:
        configured = context.get("allowed_permissions", {ToolPermission.READ})
        if isinstance(configured, (str, ToolPermission)):
            configured = [configured]
        try:
            allowed_permissions = {
                permission
                if isinstance(permission, ToolPermission)
                else ToolPermission(str(permission).lower())
                for permission in configured
            }
        except (TypeError, ValueError) as exc:
            raise ToolAuthorizationError("Invalid permission context") from exc
        if tool.permission not in allowed_permissions:
            raise ToolAuthorizationError(
                f"Permission '{tool.permission.value}' is not authorized for this request"
            )

    async def execute_tool(
        self,
        tool_name: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str:
        """Validate, execute, and audit one tool call."""

        start_time = time.perf_counter()
        tool = self.tools.get(tool_name)
        if tool is None:
            error = ToolNotFoundError(f"Tool '{tool_name}' is not registered")
            self._record_execution(
                tool_name, params, False, error=str(error), start_time=start_time
            )
            raise error

        try:
            execution_context = dict(context or {})
            execution_context.setdefault("audit_logger", self.audit_logger)
            self._authorize(tool, execution_context)
            self._validate_input(tool, params)

            if asyncio.iscoroutinefunction(tool.callback):
                result = await tool.callback(params, execution_context)
            else:
                result = await asyncio.to_thread(
                    tool.callback, params, execution_context
                )

            output = str(result)
            self._record_execution(
                tool_name,
                params,
                True,
                output=output,
                permission=tool.permission.value,
                start_time=start_time,
            )
            return output
        except Exception as exc:
            self._record_execution(
                tool_name,
                params,
                False,
                error=f"{type(exc).__name__}: {exc}",
                permission=tool.permission.value,
                start_time=start_time,
            )
            if isinstance(exc, ToolGatewayError):
                raise
            raise ToolExecutionError(
                f"Tool '{tool_name}' failed: {type(exc).__name__}: {exc}"
            ) from exc

    def _record_execution(
        self,
        tool_name: str,
        params: dict[str, Any],
        success: bool,
        *,
        output: str | None = None,
        error: str | None = None,
        permission: str = "unknown",
        start_time: float,
    ) -> None:
        self._execution_count += 1
        if success:
            self._success_count += 1
        else:
            self._failure_count += 1

        self.audit_logger.log(
            ToolExecution(
                tool_name=tool_name,
                timestamp=datetime.now(UTC).isoformat(),
                permission_level=permission,
                input_params=params,
                success=success,
                output=output,
                error=error,
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )
        )

    def get_tool_definitions(self) -> list[ToolDefinition]:
        return list(self.tools.values())

    def get_tools_by_permission(
        self, permission: ToolPermission
    ) -> list[ToolDefinition]:
        return [tool for tool in self.tools.values() if tool.permission == permission]

    def get_stats(self) -> dict[str, Any]:
        return {
            "registered_tools": len(self.tools),
            "executions": self._execution_count,
            "successful_executions": self._success_count,
            "failed_executions": self._failure_count,
            "tools_by_permission": {
                permission.value: len(self.get_tools_by_permission(permission))
                for permission in ToolPermission
            },
        }
