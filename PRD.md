# tkts

Tkts is a comprehensive ticket tracking system with pluggable backends.

It is easy for both humans and agents to use via CLI or via it's embedded MCP service.

The module is located in this directory, should be installable via pyconfig.toml, and tkts/README.md has a beginning description.

## change management in tkts MCP

Use the tkts MCP service to:

- break down work,
- track and close progress,
- prioritize tasks.

Look for updates on your projects from stakeholders in tkts.

## requirements
- Provide a Python API and an embedded MCP interface for ticket access.
- Support pluggable backends (e.g., Jira, Trello) with a default on-disk engine.
- Default CLI verb is `todo` (alias `list`), which lists current tickets.
- `new` creates a ticket with the remainder of the command as the Subject.
- `edit` allows interactive editing of a ticket (default storage engine may shell out to `$EDITOR`).
- Default storage engine root is `$HOME/.tkts`, configurable via `.tkts/config` or `TKTS_ROOT`.
- Ticket files use Internet Message Format-like headers (e.g., `Subject`, `Assignee`) with a body for details, supporting multiple documents.
- pyproject.toml for cli
- `tkts mcp` launches a mcp server using https://github.com/modelcontextprotocol/python-sdk
- ensure the readme is kept up to date. include getting
  - 2025-09-19: Added a Getting Started section to tkts/README.md with install + basic CLI usage.
  - 2025-09-19: Added multi-document support in ticket parsing/serialization using text/plain MIME parts.
  - 2026-04-07: Added model round-trip tests and fixed multi-document attachment handling.
- `tkts plan` will accept a filename to be iterated on until it's an actionable PRD. 
  - the `--exec` flag will prompt breaking the PRD down into units of work and executing them one-by-one.