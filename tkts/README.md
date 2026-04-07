# tkts

tkts is a comprehensive ticket tracking system with pluggable backends.

It can be backed by Jira, Trello, or other engines, and defaults to a stock on-disk engine. The interface is available over a Python API or an MCP.

## CLI

`tkts` is also available as a command-line program. It accepts verbs, which decide what action is taken. `todo` or `list` is the default verb, and it will return your present list of tickets even if no verb is provided.

If a phrase of words is provided that doesn't match a verb, it is interpreted as a todo item and added to the intake list.

## Engines

### tkts engine

The default `tkts` engine is a file-based storage system. It defaults to a root of `$HOME/.tkts`, but can be configured by in-directory `.tkts/config` files or the `TKTS_ROOT` environment variable.

Ticket files are stored in a format that is parsable as the Internet Message Format. It can define `Subject`, `Assignee`, and other fields as headers (like in RFC 5322). The body can be used to detail the ticket, including support of multiple documents.
