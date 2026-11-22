"""Local tool configuration example.

Copy this file to ``config.py``. Runtime settings such as the host, port, model,
and log directory are configured with ``COPILOT_OPS_*`` environment variables.
"""

from system_tools import SYSTEM_TOOLS

# Add or remove ToolDefinition objects here. See system_tools.py for examples.
TOOLS = [*SYSTEM_TOOLS]
