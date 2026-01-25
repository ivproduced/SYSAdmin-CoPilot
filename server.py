"""
Web API Server
FastAPI backend with streaming support for the Copilot Ops system
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import Optional
import asyncio
import json

from tool_gateway import ToolGateway
from system_tools import SYSTEM_TOOLS
from copilot_agent import CopilotAgent

# Try to load internal tools if they exist
try:
    import sys
    from pathlib import Path
    internal_path = Path(__file__).parent / ".internal"
    if internal_path.exists():
        sys.path.insert(0, str(internal_path))
        from tima_tools import TIMA_TOOLS
        ALL_TOOLS = SYSTEM_TOOLS + TIMA_TOOLS
        print("[Server] Loaded system tools + internal TIMA tools")
    else:
        ALL_TOOLS = SYSTEM_TOOLS
        print("[Server] Loaded system tools only (no .internal directory)")
except ImportError as e:
    ALL_TOOLS = SYSTEM_TOOLS
    print(f"[Server] Loaded system tools only (internal tools not available: {e})")


# Initialize components
tool_gateway = ToolGateway()
for tool in ALL_TOOLS:
    tool_gateway.register_tool(tool)

agent = CopilotAgent(tool_gateway)


# FastAPI app
app = FastAPI(
    title="Copilot Ops Control Plane",
    description="AI-native system operations via GitHub Copilot SDK",
    version="0.1.0"
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request models
class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None


# Initialize agent on startup
@app.on_event("startup")
async def startup():
    print("🚀 Starting Copilot Ops Control Plane...")
    await agent.initialize()
    print("✅ System ready")


@app.on_event("shutdown")
async def shutdown():
    print("🛑 Shutting down...")
    await agent.cleanup()


# API Endpoints

@app.get("/")
async def root():
    """Root endpoint - returns web interface"""
    return HTMLResponse(
        content=get_web_interface(),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent": agent.get_stats()
    }


@app.get("/api/tools")
async def list_tools():
    """List all registered tools"""
    tools = []
    for tool_name, tool_def in tool_gateway.tools.items():
        tools.append({
            "name": tool_def.name,
            "description": tool_def.description,
            "permission": tool_def.permission.value,
            "category": tool_def.category
        })
    return {"tools": tools}


@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    return {
        "agent": agent.get_stats(),
        "gateway": tool_gateway.get_stats()
    }


@app.post("/api/chat")
async def chat(message: ChatMessage):
    """
    Chat endpoint with Server-Sent Events streaming
    
    Returns a stream of events as the agent processes the message
    """
    async def event_generator():
        try:
            async for response in agent.process_message(message.message):
                # Format as SSE event
                data = {
                    "type": response.type,
                    "content": response.content,
                    "tool_name": response.tool_name,
                    "tool_output": response.tool_output,
                    "error": response.error
                }
                
                yield {
                    "event": response.type,
                    "data": json.dumps(data)
                }
                
                # Small delay to allow client to process
                await asyncio.sleep(0.01)
        
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }
    
    return EventSourceResponse(event_generator())


@app.get("/api/logs")
async def get_logs(limit: int = 50):
    """Get recent audit logs"""
    logs = tool_gateway.audit_logger.get_recent_logs(limit)
    return {
        "logs": [log.to_dict() for log in logs]
    }


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
        console.log('Script loaded!');
        const chat = document.getElementById('chat');
        const input = document.getElementById('input');
        const sendBtn = document.getElementById('send');
        const thinking = document.getElementById('thinking');
        
        console.log('Elements:', { chat, input, sendBtn, thinking });
        
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
        sendBtn.addEventListener('click', function(e) {
            console.log('Button clicked!');
            sendMessage();
        });
        
        async function sendMessage() {
            console.log('sendMessage called');
            const message = input.value.trim();
            console.log('Message:', message);
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
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let assistantMsg = null;
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const text = decoder.decode(value);
                    const lines = text.split('\n');
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                
                                if (data.type === 'complete' && data.content) {
                                    assistantMsg = addMessage('assistant', data.content);
                                }
                                else if (data.type === 'error') {
                                    assistantMsg = addMessage('assistant', '❌ ' + (data.error || 'An error occurred'), true);
                                }
                            } catch (e) {
                                console.error('Parse error:', e);
                            }
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
    
    print("\n" + "="*60)
    print("🚀 Copilot Ops Control Plane")
    print("="*60)
    print("\nStarting server...")
    print("\n📍 Access via:")
    print("   • Local:     http://localhost:8000")
    print("   • Tailscale: http://<tailscale-ip>:8000")
    print("\n" + "="*60 + "\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",  # Listen on all interfaces (required for Tailscale)
        port=8000,
        log_level="info"
    )
