"""
Tool Gateway Layer
Handles tool registration, validation, execution, and audit logging.
"""

import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class ToolPermission(Enum):
    """Tool permission levels"""
    READ = "read"      # Read-only operations
    WRITE = "write"    # Can modify system
    ADMIN = "admin"    # Full system access


@dataclass
class ToolDefinition:
    """Tool definition with schema and metadata"""
    name: str
    description: str
    permission: ToolPermission
    input_schema: Dict[str, Any]
    callback: Callable
    category: str = "general"
    
    def to_copilot_format(self) -> Dict[str, Any]:
        """Convert to Copilot SDK tool format"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "callback": self.callback
        }


@dataclass
class ToolExecution:
    """Record of tool execution"""
    tool_name: str
    timestamp: str
    permission_level: str
    input_params: Dict[str, Any]
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AuditLogger:
    """Audit logger for tool executions"""
    
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
    
    def log(self, execution: ToolExecution):
        """Log a tool execution"""
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(execution.to_dict()) + '\n')
    
    def get_recent_logs(self, limit: int = 50) -> List[ToolExecution]:
        """Get recent audit logs"""
        logs = []
        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    try:
                        data = json.loads(line)
                        logs.append(ToolExecution(**data))
                    except:
                        pass
        return logs


class ToolGateway:
    """
    Tool Gateway - Core security and execution layer
    
    Responsibilities:
    - Tool registration and validation
    - Permission checking
    - Input schema validation
    - Execution with error handling
    - Audit logging
    """
    
    def __init__(self, log_dir: Optional[Path] = None):
        self.tools: Dict[str, ToolDefinition] = {}
        self.audit_logger = AuditLogger(log_dir or Path.home() / ".copilot-ops" / "logs")
        self._execution_count = 0
    
    def register_tool(self, tool: ToolDefinition):
        """Register a tool in the gateway"""
        if tool.name in self.tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        
        # Validate tool definition
        self._validate_tool_definition(tool)
        
        self.tools[tool.name] = tool
        print(f"[ToolGateway] Registered tool: {tool.name} ({tool.permission.value})")
    
    def _validate_tool_definition(self, tool: ToolDefinition):
        """Validate tool definition"""
        if not tool.name:
            raise ValueError("Tool name is required")
        if not tool.description:
            raise ValueError("Tool description is required")
        if not tool.input_schema:
            raise ValueError("Tool input_schema is required")
        if not callable(tool.callback):
            raise ValueError("Tool callback must be callable")
    
    def _validate_input(self, tool: ToolDefinition, params: Dict[str, Any]) -> bool:
        """Validate input parameters against schema"""
        schema = tool.input_schema
        
        # Check required parameters
        required = schema.get("required", [])
        for param in required:
            if param not in params:
                raise ValueError(f"Missing required parameter: {param}")
        
        # Check parameter types (basic validation)
        properties = schema.get("properties", {})
        for param, value in params.items():
            if param in properties:
                expected_type = properties[param].get("type")
                if expected_type == "string" and not isinstance(value, str):
                    raise TypeError(f"Parameter '{param}' must be a string")
                elif expected_type == "integer" and not isinstance(value, int):
                    raise TypeError(f"Parameter '{param}' must be an integer")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    raise TypeError(f"Parameter '{param}' must be a boolean")
        
        return True
    
    async def execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Execute a tool with full validation and audit logging
        
        Returns:
            Tool output as string
        """
        start_time = datetime.now()
        
        # Get tool
        if tool_name not in self.tools:
            error = f"Tool '{tool_name}' not found"
            self._log_execution(tool_name, params, False, error=error, duration=0)
            return f"❌ {error}"
        
        tool = self.tools[tool_name]
        
        try:
            # Validate input
            self._validate_input(tool, params)
            
            # Execute tool
            if asyncio.iscoroutinefunction(tool.callback):
                result = await tool.callback(params, context or {})
            else:
                result = tool.callback(params, context or {})
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            # Debug logging
            print(f"[ToolGateway] Tool '{tool_name}' result: {str(result)[:200]}")
            
            # Log success
            self._log_execution(
                tool_name,
                params,
                True,
                output=str(result),
                duration=duration,
                permission=tool.permission.value
            )
            
            self._execution_count += 1
            
            return str(result)
        
        except Exception as e:
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            # Log failure
            error_msg = f"{type(e).__name__}: {str(e)}"
            self._log_execution(
                tool_name,
                params,
                False,
                error=error_msg,
                duration=duration,
                permission=tool.permission.value
            )
            
            return f"❌ Tool execution failed: {error_msg}"
    
    def _log_execution(
        self,
        tool_name: str,
        params: Dict[str, Any],
        success: bool,
        output: Optional[str] = None,
        error: Optional[str] = None,
        duration: float = 0.0,
        permission: str = "unknown"
    ):
        """Log tool execution to audit log"""
        execution = ToolExecution(
            tool_name=tool_name,
            timestamp=datetime.now().isoformat(),
            permission_level=permission,
            input_params=params,
            success=success,
            output=output,
            error=error,
            duration_ms=duration
        )
        
        self.audit_logger.log(execution)
    
    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get all tool definitions"""
        return list(self.tools.values())
    
    def get_tool_definitions_for_copilot(self) -> List[Dict[str, Any]]:
        """Get tool definitions in Copilot SDK format"""
        return [tool.to_copilot_format() for tool in self.tools.values()]
    
    def get_tools_by_permission(self, permission: ToolPermission) -> List[ToolDefinition]:
        """Get tools by permission level"""
        return [t for t in self.tools.values() if t.permission == permission]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get gateway statistics"""
        return {
            "registered_tools": len(self.tools),
            "executions": self._execution_count,
            "tools_by_permission": {
                "read": len(self.get_tools_by_permission(ToolPermission.READ)),
                "write": len(self.get_tools_by_permission(ToolPermission.WRITE)),
                "admin": len(self.get_tools_by_permission(ToolPermission.ADMIN))
            }
        }
