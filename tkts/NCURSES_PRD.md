# PRD: ncurses Interface for tkts

## Summary
Create a terminal UI (TUI) for `tkts` using `ncurses` to manage tickets quickly from the command line. The interface should be fast, keyboard-driven, and focused on high-throughput ticket triage and editing.

## Goals
- Provide a highly efficient, keyboard-first workflow for listing, filtering, viewing, and editing tickets.
- Reduce context switching by enabling common operations without leaving the terminal.
- Maintain a clear mental model of ticket state, grouping, and progress.
- Work reliably over SSH and in low-resource environments.

## Non-Goals
- Replace all CLI workflows; the TUI complements existing `tkts` CLI and MCP usage.
- Provide a mouse-first or graphical interface.
- Implement external integrations beyond tkts data sources.

## Users
- Engineers managing multiple concurrent tickets.
- Support/ops staff triaging and updating ticket statuses.
- Project leads reviewing progress across groups/tags.

## User Stories
1. As a user, I can view a scrollable list of tickets with key fields so I can triage quickly.
2. As a user, I can filter and search by status, tags, and free-text queries.
3. As a user, I can open a ticket detail view to read and edit fields.
4. As a user, I can bulk-update status for a selected set of tickets.
5. As a user, I can create a new ticket from within the TUI.
6. As a user, I can see grouped tickets by shared tags to finish groups efficiently.

## Functional Requirements
### 1) Ticket List View
- Default landing view shows a list of tickets.
- Columns (configurable width):
  - ID
  - Subject
  - Status
  - Tags (comma-separated, truncated)
  - Updated/Created time (if available)
- Sorting:
  - Default: status priority (in-progress, in-review, todo, blocked, done), then updated desc.
  - Toggle sort by: updated, created, subject, status.
- Navigation:
  - `j/k` or arrow keys to move selection.
  - `g/G` to jump to top/bottom.
  - `PageUp/PageDown` for paging.
- Actions:
  - `Enter` opens ticket detail.
  - `c` create ticket.
  - `e` edit selected ticket.
  - `d` delete ticket (if supported by backend) with confirm.
  - `s` cycle sort mode.
  - `r` refresh.

### 2) Filters and Search
- Quick filter bar (toggleable):
  - Status filter (one or more)
  - Tag filter (one or more)
  - Text search across subject/body
- Filter UX:
  - `/` enters search mode.
  - `f` opens filter selection panel.
  - `Esc` clears search/filter input.
- Persist filters while navigating between list and detail.
- Visual indicator when filters are active.

### 3) Ticket Detail View
- Read-only display with optional edit mode.
- Fields:
  - Subject
  - Status
  - Tags
  - Body (multi-line)
  - Assignee (if supported)
  - Created/Updated times (if available)
- Keyboard actions:
  - `e` toggle edit mode.
  - `s` save changes.
  - `q` back to list.
  - `Tab` move between fields in edit mode.
  - `Ctrl+S` save (optional).
- Unsaved changes confirmation on exit.

### 4) Create Ticket Flow
- Modal or dedicated view for creation.
- Required fields: Subject, Body.
- Optional fields: Tags, Assignee, Status.
- Validate required fields; show inline error states.
- On save, return to list with new ticket selected.

### 5) Bulk Actions
- Multi-select in list view using `Space` to toggle selection.
- Bulk status update (`b`) with a status picker.
- Bulk tag add/remove (optional).

### 6) Grouping by Tag
- Toggle grouped view (`t`): list is organized by primary tag group.
- Collapsible groups with counts.
- Group headers show status summary (e.g., 3 todo, 1 blocked).

### 7) Status and Notifications
- Status bar at bottom shows:
  - Current view
  - Active filters
  - Key hints
  - Sync status
- Non-blocking notifications for save success/error.

## Information Architecture
- Views:
  - Ticket List
  - Ticket Detail
  - Create Ticket
  - Filter/Sort Panel
  - Help/Keybindings
- Navigation hierarchy:
  - List is the hub; detail/create are modal or full-screen overlays.

## Keybindings (Proposed)
- Global:
  - `?` help
  - `q` back/quit
  - `r` refresh
- List:
  - `j/k` move
  - `g/G` top/bottom
  - `/` search
  - `f` filter
  - `s` sort
  - `t` toggle group view
  - `Space` select
  - `b` bulk action
  - `Enter` open detail
  - `c` create ticket
- Detail:
  - `e` edit
  - `s` save
  - `Tab` next field
  - `Shift+Tab` previous field

## Data & Backend
- Data source: tkts MCP service.
- Required operations:
  - list tickets
  - get ticket
  - create ticket
  - update ticket
  - delete ticket (optional)
- Refresh model: on-demand (`r`) + optional auto-refresh interval (configurable).
- Error handling: timeouts, network failures, validation errors.

## UX Requirements
- Must run in 80x24 terminals; supports resize.
- Avoid flicker, use minimal redraw.
- Clear visual focus for selected row/field.
- Respect terminal color limitations; provide a monochrome mode.
- Support low-latency SSH usage.

## Accessibility
- Keyboard-only operation.
- High-contrast color palette option.
- No reliance on color alone for state.

## Performance
- Initial list load under 200ms for up to 1k tickets.
- Smooth scrolling at 60fps on typical terminals.
- Incremental search/filter updates in under 100ms.

## Telemetry (Optional)
- Local-only usage stats (no external tracking).
- Track actions: open, edit, create, bulk change.

## Risks and Mitigations
- Risk: ncurses complexity and state management.
  - Mitigation: use a clear MVC-ish separation and a view-state reducer.
- Risk: large ticket lists cause slow redraws.
  - Mitigation: virtualized list rendering and minimal repaint regions.
- Risk: inconsistent backend responses.
  - Mitigation: robust validation and defensive parsing.

## Milestones
1. Prototype list view with navigation.
2. Add detail view and edit flow.
3. Add filters/search.
4. Add create + bulk actions.
5. Polish UX, keybindings, and help overlay.

## Open Questions
- Should deletion be supported? If so, is it soft delete or hard delete?
- What is the exact schema for tickets (fields, types, required)?
- Should auto-refresh be on by default?
- Should grouping prefer first tag or a user-selected tag?
- Any constraints on color themes or branding?
