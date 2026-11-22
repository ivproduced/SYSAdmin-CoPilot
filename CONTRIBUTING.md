# Contributing

Thanks for helping improve Copilot Ops. Small, testable changes are easiest to
review, especially while the project is establishing its security model.

## Development setup

```bash
git clone https://github.com/ivproduced/SYSAdmin-CoPilot.git
cd SYSAdmin-CoPilot
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements-dev.txt
python -m pytest
```

The automated suite does not start the Copilot runtime or require Copilot
credentials. SDK behavior is exercised through typed test doubles.

## Before opening a pull request

1. Open or reference an issue for substantial behavior changes.
2. Keep unrelated formatting and refactors out of the change.
3. Add tests for new behavior and failure paths.
4. Run:

   ```bash
   python -m pip check
   python -m compileall -q .
   ruff check .
   ruff format --check .
   python -m pytest
   ```

5. Update the README when setup, configuration, API behavior, or security
   assumptions change.

## Tool contributions

Every tool must be a `ToolDefinition` with:

- A narrowly scoped name and description.
- The least-privileged `ToolPermission` classification.
- A JSON Schema that rejects unknown fields and constrains sizes and ranges.
- Deterministic output and explicit exceptions on failure.
- Tests for valid input, invalid input, and callback failure.

READ tools must not modify state. WRITE and ADMIN tools are not currently
approved by the agent; proposals for them must include an authentication and
human-approval design.

Never include secrets, tokens, private infrastructure names, production data,
or personal audit logs in fixtures, screenshots, issues, or commits.

## Reporting security issues

Do not open a public issue for a vulnerability. Follow [SECURITY.md](SECURITY.md).

## Pull requests

Use a clear summary and explain both the user-visible result and the verification
performed. CI must pass on every supported Python version and operating system.

By contributing, you agree that your contribution is licensed under the MIT
License used by this repository.
