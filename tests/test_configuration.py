from __future__ import annotations

import sys
from types import ModuleType

import pytest

from configuration import load_tool_definitions
from tool_gateway import ToolDefinition, ToolPermission


def test_missing_config_uses_system_tools():
    tools = load_tool_definitions("config_module_that_does_not_exist")
    assert {tool.name for tool in tools} >= {"get_system_info", "list_processes"}


def test_config_must_contain_tool_definitions(monkeypatch):
    module = ModuleType("bad_test_config")
    module.TOOLS = [lambda: None]
    monkeypatch.setitem(sys.modules, module.__name__, module)

    with pytest.raises(TypeError, match="ToolDefinition"):
        load_tool_definitions(module.__name__)


def test_loads_custom_tool_definitions(monkeypatch):
    definition = ToolDefinition(
        name="custom",
        description="Custom test tool",
        permission=ToolPermission.READ,
        input_schema={"type": "object", "properties": {}},
        callback=lambda params, context: "ok",
    )
    module = ModuleType("good_test_config")
    module.TOOLS = [definition]
    monkeypatch.setitem(sys.modules, module.__name__, module)

    assert load_tool_definitions(module.__name__) == [definition]
