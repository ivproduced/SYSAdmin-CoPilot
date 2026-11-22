"""Load optional local tool configuration."""

from __future__ import annotations

import importlib
from collections.abc import Iterable

from system_tools import SYSTEM_TOOLS
from tool_gateway import ToolDefinition


def load_tool_definitions(module_name: str = "config") -> list[ToolDefinition]:
    """Load ``TOOLS`` from a local config module or use the built-in tools."""

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            return list(SYSTEM_TOOLS)
        raise

    configured_tools = getattr(module, "TOOLS", None)
    if not isinstance(configured_tools, Iterable) or isinstance(
        configured_tools, (str, bytes)
    ):
        raise TypeError(
            f"{module_name}.TOOLS must be an iterable of ToolDefinition objects"
        )

    tools = list(configured_tools)
    invalid_tools = [tool for tool in tools if not isinstance(tool, ToolDefinition)]
    if invalid_tools:
        raise TypeError(f"{module_name}.TOOLS must contain only ToolDefinition objects")
    return tools
