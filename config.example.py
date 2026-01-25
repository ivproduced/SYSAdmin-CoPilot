"""
Example Tools Configuration
Define your own tools here by importing from your tool modules
"""

# Example: Import your custom tools
# from my_tools import check_server_status, list_databases, get_logs

# For the demo, we'll use simple system monitoring tools
from system_tools import (
    get_system_info,
    list_processes,
    check_disk_space,
    get_network_stats
)

# Define which tools to register
# Each tool should be an async function with signature: async def tool_name(params: dict, context: dict) -> str
TOOLS = [
    get_system_info,
    list_processes,
    check_disk_space,
    get_network_stats
]

# Tool Gateway Configuration
TOOL_GATEWAY_CONFIG = {
    "enable_audit_logging": True,
    "log_directory": "~/.copilot-ops/logs",
    "enable_permission_checks": True
}
