# Contributing to Copilot SDK Control Plane

Thanks for your interest! This project welcomes contributions of all kinds.

## Ways to Contribute

### 1. **Add Example Tools**
Share tools you've built! Categories we'd love to see:
- Database tools (PostgreSQL, MongoDB, Redis, etc.)
- Cloud provider tools (AWS, GCP, Azure)
- Container orchestration (Kubernetes, Docker Swarm)
- CI/CD integrations (GitHub Actions, Jenkins)
- Monitoring integrations (Prometheus, Datadog, New Relic)

### 2. **Improve Documentation**
- Add tutorials
- Create video walkthroughs
- Improve code comments
- Add architecture diagrams

### 3. **Report Bugs**
Open an issue with:
- Description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, etc.)

### 4. **Suggest Features**
Have an idea? Open an issue to discuss:
- What problem does it solve?
- How would it work?
- Would it break existing functionality?

### 5. **Submit Pull Requests**

#### Before You Start:
1. Open an issue to discuss your idea
2. Fork the repository
3. Create a feature branch: `git checkout -b feature/your-feature`

#### Code Guidelines:
- Follow existing code style
- Add docstrings to functions
- Keep functions small and focused
- Use async/await for I/O operations
- Add type hints where possible

#### Testing:
- Test your changes locally
- Ensure existing tools still work
- Add examples of tool usage

#### Submitting:
1. Commit with clear messages: `git commit -m "Add PostgreSQL health check tool"`
2. Push to your fork: `git push origin feature/your-feature`
3. Open a Pull Request with:
   - Description of changes
   - Why it's useful
   - Examples/screenshots if applicable

## Example Tool Contribution

Here's a template for a new tool:

```python
async def check_api_status(params: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Check if an API endpoint is responding
    
    Permission: READ
    Parameters:
        url (required): The API endpoint to check
        timeout (optional): Request timeout in seconds (default: 5)
    """
    import aiohttp
    
    url = params.get("url")
    if not url:
        return "❌ URL parameter required"
    
    timeout = params.get("timeout", 5)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as resp:
                status = resp.status
                time_ms = resp.headers.get("X-Response-Time", "N/A")
                
                if status == 200:
                    return f"✅ {url} is healthy (HTTP {status}, {time_ms}ms)"
                else:
                    return f"⚠️ {url} returned HTTP {status}"
    except asyncio.TimeoutError:
        return f"❌ {url} timed out after {timeout}s"
    except Exception as e:
        return f"❌ Error checking {url}: {str(e)}"
```

Then add it to `config.py`:
```python
from my_tools import check_api_status

TOOLS = [
    check_api_status,
    # ... other tools
]
```

## Development Setup

1. Clone the repo:
```bash
git clone https://github.com/yourusername/sysadmin-copilot.git
cd sysadmin-copilot
```

2. Create virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy config:
```bash
cp config.example.py config.py
```

5. Run server:
```bash
python server.py
```

## Project Structure

- `server.py` - FastAPI web server with SSE streaming
- `copilot_agent.py` - Copilot SDK integration layer
- `tool_gateway.py` - Security gateway with permissions and audit logging
- `system_tools.py` - Example tools (CPU, memory, disk, network, processes)
- `config.example.py` - Configuration template

## Code of Conduct

- Be respectful and constructive
- Welcome newcomers
- Help others learn
- Keep discussions on-topic

## Questions?

Open an issue or reach out! We're happy to help.

---

Thanks for contributing! 🚀
