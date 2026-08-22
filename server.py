"""FastAPI interface for the Copilot system-operations agent."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from configuration import load_tool_definitions
from copilot_agent import CopilotAgent
from settings import AppSettings
from tool_gateway import ToolDefinition, ToolGateway

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    message: str = Field(min_length=1)
    # Reserved for the authenticated, per-user session manager milestone.
    session_id: str | None = None


def create_app(
    *,
    settings: AppSettings | None = None,
    tool_definitions: Sequence[ToolDefinition] | None = None,
    agent_instance: Any | None = None,
) -> FastAPI:
    """Create an application with injectable components for reliable tests."""

    runtime_settings = settings or AppSettings.from_env()
    runtime_settings.validate()
    gateway = ToolGateway(
        runtime_settings.log_directory,
        audit_logging=runtime_settings.audit_logging,
    )
    selected_tools = (
        load_tool_definitions() if tool_definitions is None else tool_definitions
    )
    for tool in selected_tools:
        gateway.register_tool(tool)

    runtime_agent = agent_instance or CopilotAgent(
        gateway,
        base_directory=runtime_settings.copilot_base_directory,
        model=runtime_settings.model,
        request_timeout_seconds=runtime_settings.request_timeout_seconds,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        logger.info("Starting Copilot Ops Control Plane")
        application.state.startup_error = None
        try:
            await application.state.agent.initialize()
        except Exception as exc:
            application.state.startup_error = str(exc)
            logger.exception("Copilot agent was unavailable during startup")
        try:
            yield
        finally:
            await application.state.agent.cleanup()

    application = FastAPI(
        title="Copilot Ops Control Plane",
        description="AI-native, read-only system operations via GitHub Copilot SDK",
        version="0.2.0",
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    application.state.tool_gateway = gateway
    application.state.agent = runtime_agent

    if runtime_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(runtime_settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "Authorization"],
        )

    @application.get("/")
    async def root() -> HTMLResponse:
        return HTMLResponse(
            content=get_web_interface(),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @application.get("/health")
    async def health_check(request: Request) -> dict[str, Any]:
        stats = request.app.state.agent.get_stats()
        return {
            "status": "healthy" if stats.get("initialized") else "degraded",
            "agent": stats,
            "error": request.app.state.startup_error,
        }

    @application.get("/api/tools")
    async def list_tools(request: Request) -> dict[str, Any]:
        tools = [
            {
                "name": definition.name,
                "description": definition.description,
                "permission": definition.permission.value,
                "category": definition.category,
            }
            for definition in request.app.state.tool_gateway.tools.values()
        ]
        return {"tools": tools}

    @application.get("/api/stats")
    async def get_stats(request: Request) -> dict[str, Any]:
        return {
            "agent": request.app.state.agent.get_stats(),
            "gateway": request.app.state.tool_gateway.get_stats(),
        }

    @application.post("/api/chat")
    async def chat(message: ChatMessage, request: Request) -> EventSourceResponse:
        if len(message.message) > request.app.state.settings.max_message_length:
            raise HTTPException(status_code=422, detail="Message is too long")

        async def event_generator():
            try:
                async for response in request.app.state.agent.process_message(
                    message.message
                ):
                    if await request.is_disconnected():
                        break
                    data = {
                        "type": response.type,
                        "content": response.content,
                        "tool_name": response.tool_name,
                        "tool_input": response.tool_input,
                        "tool_output": response.tool_output,
                        "error": response.error,
                    }
                    yield {"event": response.type, "data": json.dumps(data)}
            except Exception as exc:
                logger.exception("Chat stream failed")
                yield {
                    "event": "error",
                    "data": json.dumps({"type": "error", "error": str(exc)}),
                }

        return EventSourceResponse(event_generator())

    @application.get("/api/logs")
    async def get_logs(
        request: Request,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        logs = request.app.state.tool_gateway.audit_logger.get_recent_logs(limit)
        return {"logs": [log.to_dict() for log in logs]}

    return application


app = create_app()


def get_web_interface() -> str:
    """Generate the web interface HTML"""
    return r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Copilot Ops - Control Plane</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .header {
            background: #161b22;
            border-bottom: 1px solid #30363d;
            padding: 16px 20px;
            flex-shrink: 0;
        }
        
        .header h1 {
            font-size: 20px;
            font-weight: 600;
            color: #58a6ff;
            margin: 0;
        }
        
        .status {
            display: inline-block;
            margin-left: 12px;
            font-size: 12px;
            color: #7ee787;
        }
        
        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        
        .message {
            display: flex;
            flex-direction: column;
            max-width: 85%;
            animation: slideIn 0.2s ease-out;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .message.user {
            align-self: flex-end;
        }
        
        .message.assistant {
            align-self: flex-start;
        }
        
        .message-content {
            padding: 12px 16px;
            border-radius: 12px;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        .user .message-content {
            background: #1f6feb;
            color: white;
        }
        
        .assistant .message-content {
            background: #21262d;
            border: 1px solid #30363d;
        }
        
        .message-meta {
            font-size: 11px;
            color: #8b949e;
            margin-top: 4px;
            padding: 0 4px;
        }
        
        .input-container {
            padding: 16px 20px;
            background: #161b22;
            border-top: 1px solid #30363d;
            flex-shrink: 0;
        }
        
        .input-wrapper {
            display: flex;
            gap: 12px;
            align-items: flex-end;
        }
        
        textarea {
            flex: 1;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 12px;
            color: #c9d1d9;
            font-family: inherit;
            font-size: 14px;
            resize: none;
            min-height: 44px;
            max-height: 120px;
            line-height: 1.5;
        }
        
        textarea:focus {
            outline: none;
            border-color: #58a6ff;
        }
        
        button {
            background: #238636;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 20px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
            height: 44px;
        }
        
        button:hover:not(:disabled) {
            background: #2ea043;
        }
        
        button:disabled {
            background: #21262d;
            color: #8b949e;
            cursor: not-allowed;
        }
        
        .thinking {
            display: none;
            align-items: center;
            gap: 8px;
            padding: 12px 16px;
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 12px;
            max-width: 85%;
            align-self: flex-start;
        }
        
        .thinking.active {
            display: flex;
        }
        
        .spinner {
            width: 16px;
            height: 16px;
            border: 2px solid #30363d;
            border-top-color: #58a6ff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .error {
            color: #f85149;
        }
        
        @media (max-width: 768px) {
            .message {
                max-width: 90%;
            }
            
            .header h1 {
                font-size: 18px;
            }
            
            .input-wrapper {
                gap: 8px;
            }
            
            button {
                padding: 12px 16px;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🧠 Copilot Ops <span class="status">● Ready</span></h1>
    </div>
    
    <div class="chat-container" id="chat">
        <div class="message assistant">
            <div class="message-content">
                Welcome to Copilot Ops Control Plane.
                
I can help you monitor and manage your system. Try:
• "What's the system status?"
• "Check disk usage"
• "Show me running processes"
• "Read recent audit logs"
            </div>
        </div>
        
        <div class="thinking" id="thinking">
            <div class="spinner"></div>
            <span>Thinking...</span>
        </div>
    </div>
    
    <div class="input-container">
        <div class="input-wrapper">
            <textarea id="input" placeholder="Ask me anything..." rows="1"></textarea>
            <button id="send">Send</button>
        </div>
    </div>
    
    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('input');
        const sendBtn = document.getElementById('send');
        const thinking = document.getElementById('thinking');
        
        // Auto-resize textarea
        input.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
        
        // Send on Enter (Shift+Enter for new line)
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        // Send button click
        sendBtn.addEventListener('click', function() {
            sendMessage();
        });
        
        async function sendMessage() {
            const message = input.value.trim();
            if (!message) return;
            
            // Add user message
            addMessage('user', message);
            input.value = '';
            input.style.height = 'auto';
            
            // Disable input
            sendBtn.disabled = true;
            input.disabled = true;
            thinking.classList.add('active');
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message })
                });
                if (!response.ok || !response.body) {
                    throw new Error(`Request failed with HTTP ${response.status}`);
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let assistantMsg = null;
                let buffer = '';
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const eventBlocks = buffer.split(/\r?\n\r?\n/);
                    buffer = eventBlocks.pop() || '';

                    for (const eventBlock of eventBlocks) {
                        const payload = eventBlock
                            .split(/\r?\n/)
                            .filter(line => line.startsWith('data:'))
                            .map(line => line.slice(5).trimStart())
                            .join('\n');
                        if (!payload) continue;

                        const data = JSON.parse(payload);
                        if (data.type === 'message_delta' && data.content) {
                            if (!assistantMsg) assistantMsg = addMessage('assistant', '');
                            assistantMsg.querySelector('.message-content').textContent += data.content;
                            chat.scrollTop = chat.scrollHeight;
                        }
                        else if (data.type === 'complete' && data.content) {
                            if (!assistantMsg) assistantMsg = addMessage('assistant', data.content);
                            else assistantMsg.querySelector('.message-content').textContent = data.content;
                        }
                        else if (data.type === 'tool_call' && data.tool_name) {
                            thinking.querySelector('span').textContent = `Running ${data.tool_name}...`;
                        }
                        else if (data.type === 'tool_result') {
                            thinking.querySelector('span').textContent = 'Thinking...';
                        }
                        else if (data.type === 'error') {
                            assistantMsg = addMessage('assistant', '❌ ' + (data.error || 'An error occurred'), true);
                        }
                    }
                }
                
                if (!assistantMsg) {
                    addMessage('assistant', '❌ No response received', true);
                }
                
            } catch (error) {
                console.error('Error:', error);
                addMessage('assistant', '❌ Network error: ' + error.message, true);
            } finally {
                // Re-enable input
                sendBtn.disabled = false;
                input.disabled = false;
                thinking.classList.remove('active');
                thinking.querySelector('span').textContent = 'Thinking...';
                input.focus();
            }
        }
        
        function addMessage(role, content, isError = false) {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${role}`;
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            if (isError) contentDiv.classList.add('error');
            contentDiv.textContent = content;
            
            const metaDiv = document.createElement('div');
            metaDiv.className = 'message-meta';
            metaDiv.textContent = new Date().toLocaleTimeString();
            
            msgDiv.appendChild(contentDiv);
            msgDiv.appendChild(metaDiv);
            
            // Insert before thinking indicator
            chat.insertBefore(msgDiv, thinking);
            chat.scrollTop = chat.scrollHeight;
            
            return msgDiv;
        }
        
        // Focus input on load
        input.focus();
    </script>
</body>
</html>
    """


if __name__ == "__main__":
    import uvicorn

    runtime_settings = AppSettings.from_env()
    logging.basicConfig(level=logging.INFO)
    logger.info(
        "Serving Copilot Ops at http://%s:%d",
        runtime_settings.host,
        runtime_settings.port,
    )
    uvicorn.run(
        app,
        host=runtime_settings.host,
        port=runtime_settings.port,
        log_level="info",
    )
