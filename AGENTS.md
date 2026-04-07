# Agent Instructions: tkts MCP Service

This repo uses the `tkts` MCP service for ticket management. 
Use MCP tools/resources to track progress, rather than direct filesystem edits.

## MCP Capabilities

Available tools:
- `mcp__tkts__list_tickets`
- `mcp__tkts__get_ticket`
- `mcp__tkts__create_ticket`

Available resources:
- `tkts://tickets` (list of tickets)
- `tkts://tickets/{ticket_id}` (single ticket)

## Creating Tickets

Create small, single-task tickets with clear outcomes.

Example tool call:
- `mcp__tkts__create_ticket` with fields:
  - `subject`: short, specific task title
  - `body`: crisp acceptance criteria or context
  - `tags`: list of grouping tags (e.g., `feature:auth`, `request:api`, `area:mcp`)
  - `status`: `todo` | `in-progress` | `in-review` | `blocked` | `done`

## Marking Done

When a ticket is complete, set `Status: done`. If you need human input, set `Status: blocked` and describe what is needed in the body.

## Grouping Tickets

Group tickets by feature or request using tags:
- Use a consistent prefix like `feature:<name>` or `request:<name>`.
- Apply the same group tag to all related tickets.
- Prefer finishing a whole group before starting a new group when possible.

## Looping

Continue iterating until the ticket queue is complete.
- Always pull the latest queue (`tkts://tickets` or `mcp__tkts__list_tickets`).
- Prioritize finishing whole groups of tickets (by shared tags) before moving to other work.
- Stop only when all tickets are `done` or `blocked` with clear next steps.
