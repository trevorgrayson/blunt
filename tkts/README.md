# tkts

tkts is a comprehensive ticket tracking system with pluggable backends.

It can be backed by Jira, Trello, or other engines, and defaults to a stock on-disk engine. The interface is available over a Python API or an MCP.

## Getting Started

1. Install from this repo: `python -m pip install -e .`
2. List tickets: `tkts` (or `tkts list`)
3. Create a ticket: `tkts new "Replace printer toner"`
4. Edit a ticket: `tkts edit <ticket-id>`

By default, tickets are stored in `$HOME/.tkts`. You can override the root with `TKTS_ROOT` or a `.tkts/config` file in your working directory.

## CLI

`tkts` is also available as a command-line program. It accepts verbs, which decide what action is taken. 



If a phrase of words is provided that doesn't match a verb, it is interpreted as a todo item and added to the intake list.

### verbs

The first argument will be tested as a tkts "verb" and be used choose the action.

`todo` (or `list`) is the default verb. It will return your present list of tickets even if no verb is provided.
`new` will take the remainder of the text and create a tkt with that Subject.
Use `--status` to attach a status header (e.g., `tkts new "Fix CI flake" --status in-progress`).
`edit` will allow interactive editing of the tkt. For the default storage engine, this may shell out to $EDITOR.
`update` will apply structured updates to a ticket (status, subject, body, comments).
`done` marks a ticket complete (sets status to `done`).
`show` prints a ticket by id (prefixes are accepted if unambiguous).
`tail` prints recent change log entries for a ticket.
`plan` will open a PRD file for refinement until actionable, with `--exec` to walk tasks.
`mcp` launches an MCP server for Agents to interact with. the `--read-only` option will prevent writes.


## Engines

### tkts engine

The default `tkts` engine is a file-based storage system. It defaults to a root of `$HOME/.tkts`, but can be configured by in-directory `.tkts/config` files or the `TKTS_ROOT` environment variable.

Ticket files are stored in a format that is parsable as the Internet Message Format. It can define `Subject`, `Assignee`, and other fields as headers (like in RFC 5322). The body can be used to detail the ticket, including support of multiple documents.

### Status

Tickets can include a `Status` header. Status values are validated on create, with these recommended values:

- `todo`: use when a ticket is ready to be picked up.
- `in-progress`: use when work is actively underway.
- `in-review`: use when work is ready for review.
- `blocked`: use when a ticket requires human feedback or external input before progressing.
- `done`: use when a ticket is complete.

## Updates

- 2025-09-19: Added a Getting Started section with install + basic CLI usage.
- 2025-09-19: Added multi-document support in ticket parsing/serialization using text/plain MIME parts.
- 2026-04-07: Added model round-trip tests and fixed multi-document attachment handling.
