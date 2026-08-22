# Security Policy

## Supported versions

Security fixes are applied to the latest release line. The original hackathon
version (`0.1.x`) is not supported for network-exposed use.

| Version | Supported |
| --- | --- |
| `0.2.x` | Yes |
| `0.1.x` | No |

## Reporting a vulnerability

Use GitHub's private vulnerability reporting form:

<https://github.com/ivproduced/SYSAdmin-CoPilot/security/advisories/new>

If private reporting is unavailable, open a public issue that asks the maintainer
to establish private contact. Do not include exploit steps, credentials, host
details, log contents, or other sensitive information in that issue.

Please include the affected version, impact, reproduction conditions, and any
suggested mitigation in the private report. Avoid accessing data that is not
yours, changing system state, or testing against deployments without permission.

This project currently has no application-level authentication. Keep it bound to
localhost or behind an authenticated reverse proxy.
