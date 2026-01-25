# 🚀 Copilot SDK Control Plane

**Agent-Native Infrastructure Management via GitHub Copilot SDK**

Give Copilot hands to manage your infrastructure. Ask questions in natural language, get real system data back. Built for the GitHub Copilot SDK Mini Hackathon.

---

## 🎯 What Is This?

An AI-powered control plane where GitHub Copilot acts as the reasoning engine, orchestrating real system operations through secure tool gateways. 

**Not a chatbot with AI features. An agent-native system where Copilot is the brain.**

### Example Queries:
- *"What's my system status?"* → Gets CPU, RAM, disk usage, uptime
- *"Show me running processes"* → Lists processes with CPU/memory usage
- *"Check disk space"* → Reports disk usage across partitions
- *"What's my network status?"* → Shows interface stats and traffic

---

## 🏗️ Architecture

```
┌─────────────────┐
│  Web Interface  │  ← You interact here (browser/mobile)
└────────┬────────┘
         │
┌────────▼────────┐
│ Copilot Agent   │  ← GitHub Copilot SDK (planning & reasoning)
└────────┬────────┘
         │
┌────────▼────────┐
│  Tool Gateway   │  ← Security layer (permissions, validation, audit)
└────────┬────────┘
         │
┌────────▼────────┐
│  System Tools   │  ← Your custom tools (API calls, DB queries, etc.)
└─────────────────┘
```

### Clean Separation:
1. **Interface Layer**: Pure UI - no logic, just displays results
2. **Agent Layer**: Copilot SDK handles all reasoning and planning
3. **Gateway Layer**: Security boundary with permission checks and audit logging
4. **Tool Layer**: Small, deterministic operations (yours to customize!)

---

## ⚡ Quick Start

### 1. Install Dependencies

```bash
pip install github-copilot-sdk fastapi uvicorn psutil aiofiles sse-starlette aiohttp
```

### 2. Copy Example Config

```bash
cp config.example.py config.py
```

### 3. Start the Server

```bash
python server.py
```

### 4. Open the Interface

Visit **http://localhost:8000** in your browser!

---

## 🛠️ Customization

### Adding Your Own Tools

1. **Create a tool file** (e.g., `my_tools.py`):

```python
async def check_api_health(params: dict, context: dict) -> str:
    """Check if my API is healthy"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get("https://myapi.com/health") as resp:
            if resp.status == 200:
                return "✅ API is healthy!"
            return f"❌ API returned {resp.status}"
```

2. **Register in `config.py`**:

```python
from my_tools import check_api_health

TOOLS = [
    check_api_health,
    # ... other tools
]
```

3. **Restart the server** - Copilot now knows about your tool!

### Tool Signature

All tools must follow this signature:

```python
async def tool_name(params: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Tool description - Copilot sees this!
    
    Permission: READ or WRITE or ADMIN
    Parameters:
        param_name (type): Description
    """
    # Your code here
    return "Result string that Copilot will see"
```

---

## 🔐 Security

### Tool Gateway

Every tool call goes through the security gateway which:
- ✅ Validates permissions (READ/WRITE/ADMIN)
- ✅ Checks input schemas
- ✅ Logs all executions
- ✅ Handles errors gracefully

### Audit Logs

All tool executions are logged to `~/.copilot-ops/logs/audit_YYYYMMDD.jsonl`:

```json
{
  "timestamp": "2026-01-25T07:00:00.123456",
  "tool_name": "get_system_info",
  "params": {},
  "success": true,
  "duration_ms": 45.2,
  "output": "🖥️ System Status..."
}
```

---

## 📁 Project Structure

```
sysadmin-copilot/
├── server.py              # FastAPI web server
├── copilot_agent.py       # Copilot SDK integration
├── tool_gateway.py        # Security layer
├── system_tools.py        # Example system monitoring tools
├── config.example.py      # Configuration template
├── config.py             # Your config (gitignored)
├── .internal/            # Your private tools (gitignored)
├── README.md             # This file
└── REDDIT_POST.md        # Hackathon submission details
```

---

## 🎮 Example Use Cases

### DevOps Automation
```
"Restart the nginx service"
"Check if port 8080 is open"
"Show me the last 50 lines of error logs"
```

### Database Management
```
"How many users are in the database?"
"Show me slow queries from today"
"Check database connection pool status"
```

### Infrastructure Monitoring  
```
"Which servers have high CPU?"
"Show me Docker containers that are down"
"Check GPU utilization across the fleet"
```

### Custom APIs
```
"Get the status of my microservices"
"Check if the payment API is responding"
"Show me today's API error rate"
```

---

## 🧠 How It Works

### 1. You Ask a Question
*"What's my system doing?"*

### 2. Copilot Plans
The SDK analyzes your question and decides which tools to use:
- `get_system_info` - get CPU/RAM/disk
- `list_processes` - show running processes

### 3. Tools Execute  
Gateway validates permissions and runs the tools.

### 4. Copilot Synthesizes
SDK combines results into a human-readable response:

> *"Your system is running well! CPU at 23%, 16GB RAM used (42%), disk 65% full. Top processes: Chrome (8%), Python (3%), Docker (2%)..."*

---

## 🔧 Advanced Configuration

### Permissions

Control what Copilot can do by setting tool permissions:

```python
from tool_gateway import ToolPermission

# Read-only (safe)
permission=ToolPermission.READ

# Can modify data (use carefully)
permission=ToolPermission.WRITE  

# System administration (dangerous!)
permission=ToolPermission.ADMIN
```

### Streaming Responses

The server uses Server-Sent Events (SSE) for real-time streaming. Copilot's thinking appears as it happens!

### Multiple Tool Calls

Copilot can chain multiple tools to answer complex questions. It handles this automatically based on your tool descriptions.

---

## 📊 Built With

- **GitHub Copilot SDK** (v0.1.18) - Agent framework
- **FastAPI** - Async web framework  
- **Python 3.11+** - Async/await throughout
- **psutil** - System monitoring
- **aiohttp** - Async HTTP client

---

## 🎥 Demo

[Video coming soon - will show natural language queries, real-time monitoring, and multi-tool reasoning]

---

## 🚧 Roadmap

- [ ] Voice interface integration
- [ ] Proactive monitoring (agent alerts you)
- [ ] Write operations with confirmation prompts
- [ ] Multi-agent orchestration
- [ ] Mobile app with push notifications
- [ ] Docker deployment

---

## 🤝 Contributing

This started as a hackathon project but there's so much potential! Ideas welcome:

- More example tools
- Better error handling
- UI improvements
- Documentation

---

## 📝 License

MIT License - see LICENSE file

---

## 🙏 Acknowledgments

Built for the GitHub Copilot SDK Mini Hackathon. Thanks to the Copilot team for an amazing SDK!

Special thanks to the community for inspiration and support.

---

## ❓ FAQ

**Q: Is this safe to use?**  
A: Yes, with proper permissions! Start with READ-only tools. Add WRITE/ADMIN tools carefully and review audit logs.

**Q: Can I use this in production?**  
A: It's hackathon-quality code, but the architecture is solid. Add authentication, rate limiting, and hardening for production.

**Q: Does it work on Windows/Mac/Linux?**  
A: Yes! System tools use cross-platform libraries (psutil).

**Q: Can I connect to external APIs?**  
A: Absolutely! Write async functions that call any API, database, or service.

**Q: How do I secure this?**  
A: Use Tailscale for network security, implement authentication, review tool permissions, monitor audit logs.

---

**Questions? Open an issue or reach out!** 🚀
