# Copilot Ops Control Plane

Natural-language, read-only system inspection powered by the GitHub Copilot SDK.
Copilot plans the request, a validated gateway executes a small set of explicit
tools, and the browser receives the response as a live event stream.

> **Project status:** v0.2 is a stabilization release. It is suitable for local
> evaluation and development, but it does not yet include user authentication.
> Keep it bound to localhost unless you place it behind an authenticated proxy.

## What it can do

- Report CPU, memory, disk, uptime, and platform information.
- List and filter running processes.
- Inspect mounted filesystems and network interfaces.
- Summarize recent tool audit entries.
- Stream assistant text and tool activity to the included web interface.
- Load additional validated tools from a local `config.py` file.

All bundled tools are read-only. WRITE and ADMIN tool definitions are denied by
the agent until an authenticated approval workflow is implemented.

## Architecture

```text
Browser/API
    │  Server-Sent Events
    ▼
FastAPI application
    │
    ▼
Copilot SDK session (empty/isolated mode)
    │  custom tools only
    ▼
Tool gateway
    ├── permission enforcement
    ├── JSON Schema validation
    └── JSONL audit logging
    │
    ▼
Read-only system tools (psutil)
```

The SDK runs in `mode="empty"`, with only registered custom tools allowlisted.
Built-in shell, filesystem, network, MCP, plugin, skill, memory, and host-context
capabilities are not exposed to the model.

## Requirements

- Python 3.11 or newer
- A GitHub account with access to GitHub Copilot
- macOS, Linux, or Windows

## Quick start

```bash
git clone https://github.com/ivproduced/SYSAdmin-CoPilot.git
cd SYSAdmin-CoPilot

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

Pre-download the Copilot runtime so startup does not need to download it lazily:

```bash
python -m copilot download-runtime
```

Start the service:

```bash
python server.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

The SDK uses your existing GitHub Copilot authentication. Follow the error shown
at startup if the Copilot runtime requires you to sign in.

## Configuration

Runtime settings use environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `COPILOT_OPS_HOST` | `127.0.0.1` | HTTP bind address |
| `COPILOT_OPS_PORT` | `8000` | HTTP port |
| `COPILOT_OPS_MODEL` | `auto` | Copilot model selection |
| `COPILOT_OPS_REQUEST_TIMEOUT_SECONDS` | `60` | Maximum agent request duration |
| `COPILOT_OPS_MAX_MESSAGE_LENGTH` | `10000` | Maximum prompt length |
| `COPILOT_OPS_AUDIT_LOGGING` | `true` | Enable JSONL tool auditing |
| `COPILOT_OPS_LOG_DIRECTORY` | `~/.copilot-ops/logs` | Audit log directory |
| `COPILOT_OPS_COPILOT_DIRECTORY` | `~/.copilot-ops/copilot` | Isolated SDK state directory |
| `COPILOT_OPS_CORS_ORIGINS` | empty | Comma-separated allowed browser origins |

For example:

```bash
COPILOT_OPS_MODEL=gpt-5 python server.py
```

Do not set `COPILOT_OPS_HOST=0.0.0.0` until authentication has been added or an
authenticated reverse proxy restricts access.

## Adding a tool

Copy the example configuration:

```bash
cp config.example.py config.py
```

Create a `ToolDefinition` and add it to `config.py`:

```python
from typing import Any

from system_tools import SYSTEM_TOOLS
from tool_gateway import ToolDefinition, ToolPermission


def get_service_status(params: dict[str, Any], context: dict[str, Any]) -> str:
    service = params["service"]
    # Replace this with a deterministic read-only lookup.
    return f"{service}: healthy"


SERVICE_STATUS = ToolDefinition(
    name="get_service_status",
    description="Get the current status of a named service.",
    permission=ToolPermission.READ,
    input_schema={
        "type": "object",
        "properties": {
            "service": {"type": "string", "minLength": 1, "maxLength": 100},
        },
        "required": ["service"],
        "additionalProperties": False,
    },
    callback=get_service_status,
    category="services",
)

TOOLS = [*SYSTEM_TOOLS, SERVICE_STATUS]
```

Callbacks may be synchronous or asynchronous. Synchronous callbacks run in a
worker thread so they do not block the API event loop. Raise an exception when a
tool fails; the gateway will mark the audit entry and SDK result as failed.

## API

| Endpoint | Description |
| --- | --- |
| `GET /` | Web interface |
| `GET /health` | Readiness and agent state |
| `GET /api/tools` | Registered tool metadata |
| `GET /api/stats` | Agent and gateway counters |
| `POST /api/chat` | SSE stream for a chat message |
| `GET /api/logs?limit=50` | Recent audit records |

`POST /api/chat` accepts:

```json
{"message": "What is using the most memory?"}
```

The stream can contain `message_delta`, `tool_call`, `tool_result`, `complete`,
and `error` events.

## Security model

v0.2 adds several hard boundaries:

- The server binds to localhost by default.
- Copilot starts in isolated empty mode.
- Only registered custom tools are visible to the model.
- Only READ tools receive SDK permission approval.
- The gateway independently defaults each execution to READ permission.
- Inputs are validated with JSON Schema before callbacks run.
- Tool failures are recorded as failures rather than successful error strings.
- Audit files are created with restrictive permissions where the OS supports it.

Known limitations:

- There is no user authentication or per-user session isolation yet.
- One SDK conversation is serialized across requests.
- Audit records can contain sensitive system metadata and tool output.
- Logs are local JSONL files, not tamper-resistant centralized audit storage.

See [SECURITY.md](SECURITY.md) before reporting a vulnerability.

## Development

Install the development dependencies and run the suite:

```bash
python -m pip install -r requirements-dev.txt
python -m pip check
ruff check .
ruff format --check .
python -m pytest
```

CI runs the same checks on Python 3.11–3.14 and on Linux, macOS, and Windows.

## Roadmap

- Authenticated identities and per-user Copilot sessions
- Interactive approval for WRITE and ADMIN tools
- Rate limiting and request cancellation on disconnect
- Redaction and retention policies for audit data
- Container deployment behind an authenticated proxy
- Additional read-only integrations for containers and cloud platforms

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and focused tool additions are
welcome, but new write-capable tools must include an authorization design and tests.

## License

MIT License. See [LICENSE](LICENSE).

Originally created for the GitHub Copilot SDK Mini Hackathon.
