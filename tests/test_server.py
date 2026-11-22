from __future__ import annotations

from fastapi.testclient import TestClient

from copilot_agent import AgentResponse
from server import create_app
from settings import AppSettings
from tool_gateway import ToolDefinition, ToolPermission


class FakeAgent:
    def __init__(self):
        self.initialized = False
        self.cleaned_up = False

    async def initialize(self):
        self.initialized = True

    async def cleanup(self):
        self.cleaned_up = True

    def get_stats(self):
        return {"initialized": self.initialized}

    async def process_message(self, message):
        yield AgentResponse(type="message_delta", content="Hello")
        yield AgentResponse(type="complete", content="Hello")


class FailingAgent(FakeAgent):
    async def initialize(self):
        raise RuntimeError("Copilot is unavailable")


def build_test_app(tmp_path, *, max_message_length=100):
    settings = AppSettings(
        max_message_length=max_message_length,
        log_directory=tmp_path / "logs",
        copilot_base_directory=tmp_path / "copilot",
    )
    tool = ToolDefinition(
        name="status",
        description="Get status",
        permission=ToolPermission.READ,
        input_schema={"type": "object", "properties": {}},
        callback=lambda params, context: "ok",
        category="system",
    )
    agent = FakeAgent()
    return create_app(
        settings=settings, tool_definitions=[tool], agent_instance=agent
    ), agent


def test_health_tools_and_lifespan(tmp_path):
    app, agent = build_test_app(tmp_path)

    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "healthy"
        [tool] = client.get("/api/tools").json()["tools"]
        assert tool == {
            "name": "status",
            "description": "Get status",
            "permission": "read",
            "category": "system",
        }

    assert agent.cleaned_up is True


def test_chat_returns_streaming_events(tmp_path):
    app, _ = build_test_app(tmp_path)

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "Hello"})

    assert response.status_code == 200
    assert "event: message_delta" in response.text
    assert '"type": "complete"' in response.text


def test_chat_and_log_limits_are_validated(tmp_path):
    app, _ = build_test_app(tmp_path, max_message_length=5)

    with TestClient(app) as client:
        assert client.post("/api/chat", json={"message": "too long"}).status_code == 422
        assert client.post("/api/chat", json={"message": ""}).status_code == 422
        assert client.get("/api/logs?limit=0").status_code == 422
        assert client.get("/api/logs?limit=201").status_code == 422


def test_startup_failure_keeps_diagnostics_available(tmp_path):
    settings = AppSettings(
        log_directory=tmp_path / "logs",
        copilot_base_directory=tmp_path / "copilot",
    )
    agent = FailingAgent()
    app = create_app(settings=settings, tool_definitions=[], agent_instance=agent)

    with TestClient(app) as client:
        health = client.get("/health")

    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert health.json()["error"] == "Copilot is unavailable"
