# PRD: Trello Backend for `tkts`

## Summary
Implement a Trello-backed engine for the `tkts` ticket system so users and agents can manage tickets stored as Trello cards via:
- `tkts` CLI verbs (`list`, `show`, `new`, `edit`, `update`, `done`, etc.)
- the embedded `tkts mcp` server

The backend must implement the contract in `tkts/BACKENDS.md` and register as `trello` via `tkts.backends.register_backend(...)`.

## Goals
- Make Trello a first-class storage backend for `tkts` (`TKTS_BACKEND=trello`).
- Preserve a clean, low-friction workflow: Trello is the system of record; `tkts` is the interface.
- Map `tkts` concepts (status/tags/assignee/body/changelog) onto Trello primitives in a predictable way.
- Support use via both CLI and MCP with good error messages and safe defaults.

## Non-Goals
- Full Trello “power-up” feature parity (custom fields, checklists, attachments, automations).
- Complex two-way sync or offline-first caching; default behavior can be “live API calls”.
- Supporting every Trello workspace/board structure; focus on one board per backend instance/config.

## Users / Personas
- Engineers: want `tkts` CLI/MCP but prefer Trello as the canonical tracker.
- Project leads: want tickets visible on a Trello board while still enabling agentic workflows.
- Agents: need deterministic mapping and id semantics for reliable automation.

## Terminology
- **Board**: Trello board that contains ticket cards.
- **List**: Trello column (e.g. “todo”, “in-progress”).
- **Card**: Trello card; maps to a `tkts` ticket.
- **Label**: Trello label; maps to `tkts` tags.
- **Member**: Trello member; maps to `tkts` assignee (single primary assignee for MVP).

## MVP Scope
MVP implements the `Backend` protocol operations using Trello cards on a single board:
- list tickets (cards) and show ticket detail
- create/update tickets
- map status to list movement
- map tags to labels
- map assignee to a single member assignment
- append/comment support via Trello card comments
- changelog tail implemented via recent card actions/comments (best-effort)

## Out of Scope (MVP)
- Multi-board aggregation.
- Multi-assignee support in `tkts` (Trello supports multiple members per card; `tkts` model uses one `assignee`).
- Attachments/documents mapping beyond basic description/comments.
- Deletion semantics (archive vs delete) unless the existing CLI expects it.

## User Stories
1. As a user, I can run `TKTS_BACKEND=trello tkts list` to see open tickets from a Trello board.
2. As a user, I can run `tkts show <id>` to view a card’s title/description/tags/assignee/status.
3. As a user, I can run `tkts new "Fix login"` and it creates a Trello card in the correct list.
4. As a user, I can run `tkts update <id> --status in-progress` and the card moves to the right Trello list.
5. As a user, I can run `tkts update <id> --tags feature:auth bug` and labels are updated.
6. As an agent, I can call MCP `update_ticket(..., comment=...)` and see the comment on the Trello card.
7. As a user, I can run `tkts done <id>` and the card ends up in the “done” list.

## Data Model Mapping

### Ticket ID
Requirements:
- Must be stable and unique for the life of a Trello card.
- Must be easy to paste/share.
- Prefer short IDs because `tkts` supports prefix matching in local backend.

Proposal (MVP):
- Use Trello card `shortLink` as `ticket_id`.
  - Store the Trello card’s full `id` in `extra_headers` (or backend-internal mapping) as needed.
  - Support prefix matching on `ticket_id` (shortLink prefix) for user convenience.

### Subject
- `tkts.subject` ⇄ Trello card `name`.

### Body
- `tkts.body` ⇄ Trello card `desc`.
- `append_body` and/or `comment` should become Trello card comments (see below).

### Status
`tkts.status` values: `todo`, `in-progress`, `in-review`, `blocked`, `done`.

Mapping (MVP):
- Map `tkts.status` ⇄ Trello **list name** (case-insensitive).
  - Default list-name convention: lists named exactly like status values.
  - If a board uses different list names (e.g. “Doing”), allow explicit mapping via config.
- When listing tickets, derive `status` from the card’s current list.
- When updating status, move the card to the target list.

### Tags
- `tkts.tags` ⇄ Trello labels by label name.
- On create/update:
  - If a label exists on the board, attach it.
  - If a label does not exist:
    - MVP option A (default): create the label on the board (color optional/auto).
    - MVP option B: fail fast with actionable error listing missing labels.
  - Choose one behavior and document it; prefer a config flag to switch behavior.

### Assignee
- `tkts.assignee` ⇄ Trello card `idMembers`.
- MVP chooses a single “primary” assignee:
  - If multiple members are on the card, pick the first one as `assignee`.
  - On update, set membership to the named member (by id or username) depending on config.

### Created/Updated Times
- `updated_at` should map to Trello card’s last activity time (best available).
- `created_at` is best-effort (if not available cheaply, it may be omitted for MVP).

### Changelog
`tail_ticket_changelog(limit=10)` should return readable, chronological entries.
MVP approach (best-effort):
- Pull recent actions/comments for the card and summarize.
- At minimum, include comment timestamps and author names where available.

## Functional Requirements (Backend Contract)
Implement all methods specified in `tkts/BACKENDS.md`:

### `list_tickets()`
- Returns cards from the configured board.
- Defaults to “open” cards only (not archived).
- Must populate: `ticket_id`, `subject`, `status`, `tags`, `assignee`, `updated_at` (where available).
- Must be resilient to partial/missing fields (e.g., labels disabled).

### `get_ticket(ticket_id)`
- Accepts a `shortLink` or a unique prefix of it (MVP).
- Returns `None` when not found; otherwise returns a full `Ticket`.

### `create_ticket(subject, body, assignee, tags, status)`
- Creates a new Trello card in the appropriate list:
  - If `status` is provided, use mapped list for that status.
  - Else default to `todo` list (or configured default list).
- Sets `desc` from `body`.
- Applies labels and assignee if provided.
- Validates `status` against allowed values and fails with a clear error for invalid.

### `edit_ticket(ticket_id)`
- For non-file backends, `edit_ticket` may:
  - open the Trello card URL in a browser (optional), or
  - fall back to a structured update flow, or
  - be a no-op that returns the ticket as-is.
- MVP requirement: behave consistently and document the behavior.

### `update_ticket(ticket_id, ...)`
- Supports updating:
  - `subject` (card name)
  - `body` (card desc)
  - `status` (move list)
  - `tags` (labels)
  - `assignee` (member assignment)
- Supports narrative updates:
  - `append_body`: add a new Trello card comment prefixed with something like “Append:” (configurable)
  - `comment`: add a Trello card comment as-is
  - `log_message`: add a Trello card comment or action annotation (best-effort)

### `tail_ticket_changelog(ticket_id, limit)`
- Returns the last `limit` entries in chronological order (oldest → newest).
- Best-effort mapping from Trello actions/comments to text entries.

## Configuration and Credentials

### Backend Selection
- `TKTS_BACKEND=trello` activates this backend.

### Required Credentials (ENV)
Use environment variables for authentication:
- `TRELLO_API_KEY`
- `TRELLO_API_TOKEN`

### Required Target (ENV or config)
Backend needs a target board context:
- `TRELLO_BOARD_ID` (or shortLink), or an equivalent config entry.

### Optional Configuration
- `TRELLO_BASE_URL` (default Trello API base URL; mainly for testing)
- `TRELLO_DEFAULT_STATUS` (default: `todo`)
- `TRELLO_STATUS_TO_LIST` (mapping string/JSON; e.g. `todo:To Do,in-progress:Doing,...`)
- `TRELLO_CREATE_MISSING_LABELS` (`true|false`)
- `TRELLO_INCLUDE_DONE` (`true|false`) for `list_tickets` default behavior

Notes:
- If `.tkts/config` supports backend-specific keys, mirror these names there as well.
- Do not print secrets in logs or exception messages.

## UX / CLI Expectations
- Error messages must clearly indicate:
  - which env var is missing (e.g., `TRELLO_API_TOKEN`)
  - which Trello resource is misconfigured (board/list/label/member)
  - next steps to fix configuration
- Prefix matching must be safe:
  - if a prefix matches multiple cards, return a disambiguation error.

## Reliability, Performance, and Rate Limits
- Avoid N+1 API call patterns in `list_tickets`:
  - fetch cards with the fields needed for list view in one request where possible.
- For changelog/actions, prefer lazy fetching only when requested.
- Implement basic retry/backoff for transient failures where reasonable.

## Security
- Credentials are read from environment variables only (MVP).
- Never write tokens to disk.
- Avoid including credentials in URLs, logs, or raised exceptions.

## Testing Strategy
- Unit tests should mock HTTP calls and cover:
  - status/list mapping
  - label creation/assignment behavior
  - id prefix resolution and ambiguity errors
  - update behavior for comment/append/log_message
- Optional integration test mode guarded by env vars (skipped by default).

## Milestones
1. Backend skeleton + registration (`trello`), config/env validation.
2. Implement `list_tickets` + `get_ticket` with id semantics.
3. Implement `create_ticket` with status/list mapping.
4. Implement `update_ticket` (fields + comments) and `done` workflow.
5. Implement `tail_ticket_changelog` best-effort.
6. Documentation updates: `tkts/README.md` backend usage examples.

## Acceptance Criteria
- With `TRELLO_API_KEY`, `TRELLO_API_TOKEN`, and `TRELLO_BOARD_ID` set:
  - `TKTS_BACKEND=trello tkts list` shows tickets from the Trello board.
  - `tkts show <id>` returns the expected card data.
  - `tkts new "Subject" --body "..."` creates a card in `todo` list by default.
  - `tkts update <id> --status in-progress` moves the card to the mapped list.
  - `tkts update <id> --tags a b` updates labels per documented behavior.
  - MCP tool calls operate against the same backend and return `Ticket` objects.
- Backend does not leak secrets in output/logs.

## Open Questions
- How should `edit_ticket` behave for Trello (no-op vs open URL vs in-terminal editor)?
- Should missing labels be auto-created by default, or require explicit opt-in?
- Should “done” tickets be excluded from `list_tickets` by default for Trello backend?
- How to map Trello members to `tkts.assignee` (username vs full name vs id)?
- Should archived cards map to `done` or be hidden unless explicitly requested?
