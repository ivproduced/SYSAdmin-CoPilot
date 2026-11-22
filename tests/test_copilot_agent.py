from __future__ import annotations

from types import SimpleNamespace

import pytest
from copilot import ToolInvocation
from copilot.rpc import PermissionDecisionApproveOnce, PermissionDecisionReject
from copilot.session_events import (
    AssistantMessageData,
    AssistantMessageDeltaData,
    PermissionRequestCustomTool,
    SessionIdleData,
)

from copilot_agent import CopilotAgent
from tool_gateway import ToolDefinition, ToolGateway, ToolPermission


class FakeSession:
    def __init__(self, events=None):
        self.events = events or []
        self.handlers = set()
        self.unsubscribe_count = 0
        self.disconnected = False

    def on(self, handler):
        self.handlers.add(handler)

        def unsubscribe():
            self.handlers.discard(handler)
            self.unsubscribe_count += 1

        return unsubscribe

    async def send(self, message):
        for data in self.events:
            event = SimpleNamespace(data=data, agent_id=None)
            for handler in list(self.handlers):
                handler(event)

    async def disconnect(self):
        self.disconnected = True
        self.handlers.clear()


class FakeClient:
    def __init__(self, *, session, **options):
        self.session = session
        self.options = options
        self.started = False
        self.stopped = False
        self.create_options = None

    async def start(self):
        self.started = True

    async def create_session(self, **options):
        self.create_options = options
        return self.session

    async def stop(self):
        self.stopped = True


def make_agent(tmp_path, *, events=None, timeout=1):
    gateway = ToolGateway(tmp_path / "logs")
    gateway.register_tool(
        ToolDefinition(
            name="echo",
            description="Echo a value",
            permission=ToolPermission.READ,
            input_schema={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            },
            callback=lambda params, context: params["value"],
        )
    )
    session = FakeSession(events)
    client = FakeClient(session=session)
    agent = CopilotAgent(
        gateway,
        base_directory=tmp_path / "copilot",
        request_timeout_seconds=timeout,
        client_factory=lambda **options: _configure_fake_client(client, options),
    )
    return agent, client, session


def _configure_fake_client(client, options):
    client.options = options
    return client


@pytest.mark.asyncio
async def test_initializes_in_empty_mode_with_only_custom_tools(tmp_path):
    agent, client, _ = make_agent(tmp_path)

    await agent.initialize()

    assert client.options["mode"] == "empty"
    assert client.started is True
    assert client.create_options["streaming"] is True
    assert client.create_options["available_tools"].to_list() == ["custom:*"]
    assert [tool.name for tool in client.create_options["tools"]] == ["echo"]


@pytest.mark.asyncio
async def test_streams_deltas_and_unsubscribes_after_completion(tmp_path):
    events = [
        AssistantMessageDeltaData(delta_content="Hel", message_id="message-1"),
        AssistantMessageDeltaData(delta_content="lo", message_id="message-1"),
        AssistantMessageData(content="Hello", message_id="message-1"),
        SessionIdleData(),
    ]
    agent, _, session = make_agent(tmp_path, events=events)

    responses = [response async for response in agent.process_message("Say hello")]

    assert [response.type for response in responses] == [
        "message_delta",
        "message_delta",
        "complete",
    ]
    assert responses[-1].content == "Hello"
    assert session.unsubscribe_count == 1


@pytest.mark.asyncio
async def test_sdk_tool_handler_returns_typed_success_result(tmp_path):
    agent, client, _ = make_agent(tmp_path)
    await agent.initialize()
    [tool] = client.create_options["tools"]

    result = await tool.handler(
        ToolInvocation(
            session_id="session-1",
            tool_call_id="call-1",
            tool_name="echo",
            arguments={"value": "hello"},
        )
    )

    assert result.result_type == "success"
    assert result.text_result_for_llm == "hello"


@pytest.mark.asyncio
async def test_timeout_discards_the_session(tmp_path):
    agent, _, session = make_agent(tmp_path, timeout=0.01)

    responses = [
        response async for response in agent.process_message("Never completes")
    ]

    assert responses[-1].type == "error"
    assert "timed out" in responses[-1].error
    assert session.disconnected is True
    assert agent.session is None


def test_permission_handler_approves_read_tools_and_rejects_other_capabilities(
    tmp_path,
):
    agent, _, _ = make_agent(tmp_path)
    request = PermissionRequestCustomTool(
        tool_description="Echo a value",
        tool_name="echo",
        args={"value": "hello"},
    )

    assert isinstance(
        agent._handle_permission_request(request, {}), PermissionDecisionApproveOnce
    )
    assert isinstance(
        agent._handle_permission_request(SimpleNamespace(), {}),
        PermissionDecisionReject,
    )
