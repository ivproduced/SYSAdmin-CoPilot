## Summary

Describe the user-visible outcome and why the change is needed.

## Security impact

Describe any change to tools, permissions, validation, logging, network exposure,
or SDK capabilities. Write “None” if there is no impact.

## Verification

- [ ] `python -m pip check`
- [ ] `python -m compileall -q .`
- [ ] `ruff check .` and `ruff format --check .`
- [ ] `python -m pytest`
- [ ] Documentation updated when behavior or configuration changed
