# tkts

Tkts is a comprehensive ticket tracking system with pluggable backends.

It is easy for both humans and agents to use via CLI or via it's embedded MCP service.

The module is located in this directory, should be installable via pyconfig.toml, and tkts/README.md has a beginning description.

requirements
- Provide a Python API and an embedded MCP interface for ticket access.
- Support pluggable backends (e.g., Jira, Trello) with a default on-disk engine.
- Default CLI verb is `todo` (alias `list`), which lists current tickets.
- `new` creates a ticket with the remainder of the command as the Subject.
- `edit` allows interactive editing of a ticket (default storage engine may shell out to `$EDITOR`).
- Default storage engine root is `$HOME/.tkts`, configurable via `.tkts/config` or `TKTS_ROOT`.
- Ticket files use Internet Message Format-like headers (e.g., `Subject`, `Assignee`) with a body for details, supporting multiple documents.
- pyproject.toml for cli
- tkts mcp launches a mcp server using https://github.com/modelcontextprotocol/python-sdk
done
- implemented local file storage and retrieval with tags plus basic `tkts list` and `tkts new` CLI support
- documented README requirements in PRD
- added `tkts edit` to open tickets in $EDITOR and persist updated timestamps
- handled multi-word todo intake when the first argument is not a verb
- added `.tkts/config` discovery to configure storage root (supports `root=` or `TKTS_ROOT=` values)
