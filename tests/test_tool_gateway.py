from __future__ import annotations

import pytest

from tool_gateway import (
    ToolAuthorizationError,
    ToolDefinition,
    ToolExecutionError,
    ToolGateway,
    ToolPermission,
    ToolValidationError,
)


def make_tool(callback, *, permission=ToolPermission.READ) -> ToolDefinition:
    return ToolDefinition(
        name="example",
        description="Example tool",
        permission=permission,
        input_schema={
            "type": "object",
            "properties": {
                "value": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            "required": ["value"],
            "additionalProperties": False,
        },
        callback=callback,
    )


@pytest.mark.asyncio
async def test_executes_and_audits_a_valid_sync_tool(tmp_path):
    gateway = ToolGateway(tmp_path)
    gateway.register_tool(make_tool(lambda params, context: params["value"] * 2))

    result = await gateway.execute_tool("example", {"value": 3})

    assert result == "6"
    [execution] = gateway.audit_logger.get_recent_logs()
    assert execution.success is True
    assert execution.output == "6"
    assert gateway.get_stats()["successful_executions"] == 1


@pytest.mark.asyncio
async def test_rejects_invalid_arguments_and_audits_the_failure(tmp_path):
    gateway = ToolGateway(tmp_path)
    gateway.register_tool(make_tool(lambda params, context: "unused"))

    with pytest.raises(ToolValidationError, match="maximum of 5"):
        await gateway.execute_tool("example", {"value": 9})

    [execution] = gateway.audit_logger.get_recent_logs()
    assert execution.success is False
    assert "ToolValidationError" in execution.error


@pytest.mark.asyncio
async def test_read_only_is_the_default_authorized_permission(tmp_path):
    gateway = ToolGateway(tmp_path)
    gateway.register_tool(
        make_tool(lambda params, context: "changed", permission=ToolPermission.WRITE)
    )

    with pytest.raises(ToolAuthorizationError, match="not authorized"):
        await gateway.execute_tool("example", {"value": 1})

    result = await gateway.execute_tool(
        "example",
        {"value": 1},
        {"allowed_permissions": {ToolPermission.WRITE}},
    )
    assert result == "changed"

    result = await gateway.execute_tool(
        "example", {"value": 1}, {"allowed_permissions": "write"}
    )
    assert result == "changed"


@pytest.mark.asyncio
async def test_callback_exceptions_are_failures_not_success_strings(tmp_path):
    def broken_tool(params, context):
        raise OSError("sensor unavailable")

    gateway = ToolGateway(tmp_path)
    gateway.register_tool(make_tool(broken_tool))

    with pytest.raises(ToolExecutionError, match="sensor unavailable"):
        await gateway.execute_tool("example", {"value": 1})

    [execution] = gateway.audit_logger.get_recent_logs()
    assert execution.success is False
    assert execution.output is None
    assert gateway.get_stats()["failed_executions"] == 1


def test_rejects_duplicate_names_and_invalid_schemas(tmp_path):
    gateway = ToolGateway(tmp_path)
    tool = make_tool(lambda params, context: "ok")
    gateway.register_tool(tool)

    with pytest.raises(ValueError, match="already registered"):
        gateway.register_tool(tool)

    invalid = ToolDefinition(
        name="invalid",
        description="Invalid schema",
        permission=ToolPermission.READ,
        input_schema={"type": "not-a-json-schema-type"},
        callback=lambda params, context: "ok",
    )
    with pytest.raises(ValueError, match="Invalid schema"):
        gateway.register_tool(invalid)
