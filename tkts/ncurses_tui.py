from __future__ import annotations

import curses
from curses import textpad
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from tkts.backends import Backend, get_backend_from_env
from tkts.models import Ticket


STATUS_ORDER = ["in-progress", "in-review", "todo", "blocked", "done"]
STATUS_RANK = {status: idx for idx, status in enumerate(STATUS_ORDER)}
SORT_MODES = ["status", "updated", "created", "subject"]


@dataclass
class Row:
    kind: str
    ticket: Optional[Ticket] = None
    group: Optional[str] = None
    counts: Optional[Dict[str, int]] = None


@dataclass
class FormField:
    key: str
    label: str
    value: str
    multiline: bool = False


class TuiApp:
    def __init__(self, backend: Backend, *, watch: Optional[float] = None) -> None:
        self.backend = backend
        self.tickets: List[Ticket] = []
        self.rows: List[Row] = []
        self.selected_idx = 0
        self.scroll = 0
        self.selection: Dict[str, bool] = {}
        self.sort_mode = "status"
        self.group_view = False
        self.collapsed_groups: Dict[str, bool] = {}

        self.filter_statuses: Dict[str, bool] = {}
        self.filter_tags: Dict[str, bool] = {}
        self.search_query = ""

        self.mode = "list"
        self.detail_ticket: Optional[Ticket] = None

        self.form_fields: List[FormField] = []
        self.form_index = 0
        self.form_dirty = False
        self.form_confirm_discard = False
        self.form_context = ""

        self.filter_items: List[Tuple[str, str, str]] = []
        self.filter_index = 0

        self.bulk_index = 0

        self.message = ""
        self.message_time: Optional[float] = None

        self.watch_interval = 5.0
        self.watch_enabled = False
        if watch is not None:
            self.watch_interval = max(0.1, float(watch))
            self.watch_enabled = True

    def set_message(self, message: str) -> None:
        self.message = message

    def clear_message(self) -> None:
        self.message = ""

    def refresh_tickets(self) -> None:
        focused_id: Optional[str] = None
        if self.mode == "detail" and self.detail_ticket:
            focused_id = self.detail_ticket.ticket_id
        elif self.mode == "list":
            row = self._current_row()
            if row and row.kind == "ticket" and row.ticket:
                focused_id = row.ticket.ticket_id

        self.tickets = self.backend.list_tickets()
        valid_ids = {ticket.ticket_id for ticket in self.tickets}
        self.selection = {tid: True for tid in self.selection if tid in valid_ids}
        self.apply_filters()
        if focused_id:
            for idx, row in enumerate(self.rows):
                if row.kind == "ticket" and row.ticket and row.ticket.ticket_id == focused_id:
                    self.selected_idx = idx
                    break

    def apply_filters(self) -> None:
        filtered = [ticket for ticket in self.tickets if self._match_filters(ticket)]
        filtered = self._sort_tickets(filtered)
        self.rows = self._build_rows(filtered)
        if self.selected_idx >= len(self.rows):
            self.selected_idx = max(0, len(self.rows) - 1)
        if self.scroll > self.selected_idx:
            self.scroll = self.selected_idx

    def _match_filters(self, ticket: Ticket) -> bool:
        if self.filter_statuses:
            if (ticket.status or "") not in self.filter_statuses:
                return False
        if self.filter_tags:
            if not ticket.tags:
                return False
            if not any(tag in self.filter_tags for tag in ticket.tags):
                return False
        if self.search_query:
            needle = self.search_query.lower()
            hay = f"{ticket.subject}\n{ticket.body}".lower()
            if needle not in hay:
                return False
        return True

    def _sort_tickets(self, tickets: List[Ticket]) -> List[Ticket]:
        if self.sort_mode == "subject":
            return sorted(tickets, key=lambda t: (t.subject or "").lower())
        if self.sort_mode == "created":
            return sorted(tickets, key=lambda t: self._timestamp(t.created_at), reverse=True)
        if self.sort_mode == "updated":
            return sorted(tickets, key=lambda t: self._timestamp(t.updated_at), reverse=True)
        if self.sort_mode == "status":
            return sorted(
                tickets,
                key=lambda t: (
                    STATUS_RANK.get(t.status or "", len(STATUS_RANK)),
                    -self._timestamp(t.updated_at),
                    (t.subject or "").lower(),
                ),
            )
        return tickets

    def _build_rows(self, tickets: List[Ticket]) -> List[Row]:
        if not self.group_view:
            return [Row(kind="ticket", ticket=ticket) for ticket in tickets]
        grouped: Dict[str, List[Ticket]] = {}
        for ticket in tickets:
            group = (ticket.tags[0] if ticket.tags else "untagged")
            grouped.setdefault(group, []).append(ticket)
        rows: List[Row] = []
        for group in sorted(grouped.keys()):
            counts: Dict[str, int] = {}
            for ticket in grouped[group]:
                status = ticket.status or "unknown"
                counts[status] = counts.get(status, 0) + 1
            rows.append(Row(kind="group", group=group, counts=counts))
            if self.collapsed_groups.get(group):
                continue
            for ticket in grouped[group]:
                rows.append(Row(kind="ticket", ticket=ticket))
        return rows

    def _timestamp(self, value: Optional[str]) -> float:
        if not value:
            return 0.0
        try:
            return datetime.fromisoformat(value).timestamp()
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).timestamp()
            except ValueError:
                continue
        return 0.0

    def run(self, stdscr: "curses._CursesWindow") -> int:
        curses.curs_set(0)
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)
        if not self._monochrome():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
            curses.init_pair(2, curses.COLOR_YELLOW, -1)
            curses.init_pair(3, curses.COLOR_GREEN, -1)
            curses.init_pair(4, curses.COLOR_RED, -1)
            curses.init_pair(5, curses.COLOR_BLUE, -1)

        self.refresh_tickets()
        while True:
            self._apply_watch_timeout(stdscr)
            stdscr.erase()
            if self.mode == "list":
                self._render_list(stdscr)
            elif self.mode == "detail":
                self._render_detail(stdscr)
            elif self.mode in {"edit", "create"}:
                self._render_form(stdscr)
            elif self.mode == "filter":
                self._render_filter(stdscr)
            elif self.mode == "bulk":
                self._render_bulk(stdscr)
            elif self.mode == "help":
                self._render_help(stdscr)
            stdscr.refresh()

            key = stdscr.getch()
            if key == -1:
                if self.watch_enabled and self.mode == "list":
                    try:
                        self.refresh_tickets()
                    except Exception as exc:
                        self.set_message(f"Refresh failed: {exc}")
                    continue
            if self.mode == "list":
                if self._handle_list_key(stdscr, key):
                    return 0
            elif self.mode == "detail":
                if self._handle_detail_key(key):
                    return 0
            elif self.mode in {"edit", "create"}:
                if self._handle_form_key(stdscr, key):
                    return 0
            elif self.mode == "filter":
                if self._handle_filter_key(key):
                    return 0
            elif self.mode == "bulk":
                if self._handle_bulk_key(key):
                    return 0
            elif self.mode == "help":
                if key in {ord("q"), 27, ord("?")}:  # esc
                    self.mode = "list"

    def _monochrome(self) -> bool:
        return bool(int(__import__("os").environ.get("TKTS_TUI_MONO", "0")))

    def _apply_watch_timeout(self, stdscr: "curses._CursesWindow") -> None:
        if self.watch_enabled and self.mode == "list":
            stdscr.timeout(max(1, int(self.watch_interval * 1000)))
        else:
            stdscr.timeout(-1)

    def _render_list(self, stdscr: "curses._CursesWindow") -> None:
        height, width = stdscr.getmaxyx()
        header = "tkts TUI"
        stdscr.addstr(0, 0, header[: width - 1], curses.A_BOLD)

        columns = self._compute_columns(width)
        header_line = (
            f"{columns['id']:<5} {columns['subject']:<{columns['subject_w']}} "
            f"{columns['status']:<{columns['status_w']}} {columns['tags']:<{columns['tags_w']}} "
            f"{columns['updated']:<{columns['updated_w']}}"
        )
        stdscr.addstr(1, 0, header_line[: width - 1], curses.A_DIM)

        max_rows = max(0, height - 4)
        if self.selected_idx < self.scroll:
            self.scroll = self.selected_idx
        if self.selected_idx >= self.scroll + max_rows:
            self.scroll = self.selected_idx - max_rows + 1

        visible = self.rows[self.scroll : self.scroll + max_rows]
        for idx, row in enumerate(visible):
            line_no = 2 + idx
            attr = curses.A_NORMAL
            if self.scroll + idx == self.selected_idx:
                attr = curses.A_REVERSE
            if row.kind == "group":
                group = row.group or "untagged"
                collapsed = self.collapsed_groups.get(group)
                prefix = "[+]" if collapsed else "[-]"
                counts = row.counts or {}
                summary = ", ".join(
                    f"{status}:{counts.get(status, 0)}" for status in STATUS_ORDER if counts.get(status)
                )
                label = f"{prefix} {group}"
                if summary:
                    label = f"{label} ({summary})"
                stdscr.addstr(line_no, 0, label[: width - 1], attr | curses.A_BOLD)
                continue
            ticket = row.ticket
            if not ticket:
                continue
            short_id = ticket.ticket_id[:5]
            if self.selection.get(ticket.ticket_id):
                short_id = "*" + short_id[1:]
            subject = self._truncate(ticket.subject or "", columns["subject_w"])
            status = ticket.status or "unknown"
            tags = ",".join(ticket.tags or [])
            tags = self._truncate(tags, columns["tags_w"])
            updated = self._format_time(ticket.updated_at or ticket.created_at)
            line = (
                f"{short_id:<5} {subject:<{columns['subject_w']}} "
                f"{status:<{columns['status_w']}} {tags:<{columns['tags_w']}} "
                f"{updated:<{columns['updated_w']}}"
            )
            stdscr.addstr(line_no, 0, line[: width - 1], attr)

        self._render_status_bar(stdscr, "list")

    def _compute_columns(self, width: int) -> Dict[str, int | str]:
        id_w = 5
        status_w = 12
        updated_w = 16
        tags_w = 20
        fixed = id_w + status_w + updated_w + tags_w + 4
        subject_w = max(10, width - fixed)
        if subject_w < 10:
            subject_w = 10
        if width < fixed + 10:
            tags_w = max(10, tags_w - 5)
            fixed = id_w + status_w + updated_w + tags_w + 4
            subject_w = max(10, width - fixed)
        if width < fixed + 10:
            updated_w = max(8, updated_w - 4)
            fixed = id_w + status_w + updated_w + tags_w + 4
            subject_w = max(10, width - fixed)
        return {
            "id": "ID",
            "subject": "Subject",
            "status": "Status",
            "tags": "Tags",
            "updated": "Updated",
            "subject_w": subject_w,
            "status_w": status_w,
            "tags_w": tags_w,
            "updated_w": updated_w,
        }

    def _render_status_bar(self, stdscr: "curses._CursesWindow", view: str) -> None:
        height, width = stdscr.getmaxyx()
        status_line = f"View: {view}"
        if self.sort_mode:
            status_line += f" | Sort: {self.sort_mode}"
        if self.watch_enabled:
            status_line += f" | Watch: {self.watch_interval:g}s"
        if self.group_view:
            status_line += " | Grouped"
        if self.selection:
            status_line += f" | Selected: {len(self.selection)}"
        filters = []
        if self.filter_statuses:
            filters.append("status")
        if self.filter_tags:
            filters.append("tags")
        if self.search_query:
            filters.append("search")
        if filters:
            status_line += " | Filters: " + ",".join(filters)
        else:
            status_line += " | Filters: none"
        hint_line = "Keys: ? help  / search  f filter  s sort  t group  w watch  c create  b bulk  r refresh  q quit"
        message_line = self.message
        stdscr.addstr(height - 2, 0, self._truncate(message_line, width - 1))
        combined = f"{status_line} | {hint_line}"
        stdscr.addstr(height - 1, 0, " " * (width - 1))
        stdscr.addstr(height - 1, 0, self._truncate(combined, width - 1), curses.A_BOLD)

    def _render_detail(self, stdscr: "curses._CursesWindow") -> None:
        height, width = stdscr.getmaxyx()
        ticket = self.detail_ticket
        if not ticket:
            self.mode = "list"
            return
        stdscr.addstr(0, 0, f"Ticket {ticket.ticket_id}"[: width - 1], curses.A_BOLD)
        fields = [
            ("Subject", ticket.subject),
            ("Status", ticket.status or "unknown"),
            ("Tags", ", ".join(ticket.tags or [])),
            ("Assignee", ticket.assignee or ""),
            ("Created", ticket.created_at or ""),
            ("Updated", ticket.updated_at or ""),
        ]
        line = 2
        for label, value in fields:
            if line >= height - 4:
                break
            stdscr.addstr(line, 2, f"{label}:", curses.A_BOLD)
            stdscr.addstr(line, 14, self._truncate(value, width - 16))
            line += 1
        line += 1
        stdscr.addstr(line, 2, "Body:", curses.A_BOLD)
        line += 1
        body_lines = self._wrap_text(ticket.body or "", width - 4)
        for body_line in body_lines:
            if line >= height - 2:
                break
            stdscr.addstr(line, 4, self._truncate(body_line, width - 6))
            line += 1

        stdscr.addstr(height - 2, 0, "e edit  q back", curses.A_DIM)

    def _render_form(self, stdscr: "curses._CursesWindow") -> None:
        height, width = stdscr.getmaxyx()
        title = "Edit Ticket" if self.mode == "edit" else "Create Ticket"
        stdscr.addstr(0, 0, title[: width - 1], curses.A_BOLD)
        for idx, field in enumerate(self.form_fields):
            line = 2 + idx
            if line >= height - 4:
                break
            label = f"{field.label}:"
            value = field.value
            attr = curses.A_NORMAL
            if idx == self.form_index:
                attr = curses.A_REVERSE
            display = self._truncate(value.replace("\n", " "), width - 16)
            stdscr.addstr(line, 2, label, curses.A_BOLD)
            stdscr.addstr(line, 14, display, attr)
        hint = "Tab next  Enter edit  s save  q cancel"
        if any(field.multiline for field in self.form_fields):
            hint += "  (Ctrl+G to save multiline)"
        stdscr.addstr(height - 2, 0, self._truncate(hint, width - 1), curses.A_DIM)

    def _render_filter(self, stdscr: "curses._CursesWindow") -> None:
        height, width = stdscr.getmaxyx()
        stdscr.addstr(0, 0, "Filters"[: width - 1], curses.A_BOLD)
        for idx, (_, _, label) in enumerate(self.filter_items):
            line = 2 + idx
            if line >= height - 3:
                break
            attr = curses.A_NORMAL
            if idx == self.filter_index:
                attr = curses.A_REVERSE
            stdscr.addstr(line, 2, label[: width - 4], attr)
        stdscr.addstr(height - 2, 0, "Space toggle  Enter done  Esc cancel", curses.A_DIM)

    def _render_bulk(self, stdscr: "curses._CursesWindow") -> None:
        height, width = stdscr.getmaxyx()
        stdscr.addstr(0, 0, "Bulk Status"[: width - 1], curses.A_BOLD)
        for idx, status in enumerate(STATUS_ORDER):
            line = 2 + idx
            if line >= height - 3:
                break
            attr = curses.A_NORMAL
            if idx == self.bulk_index:
                attr = curses.A_REVERSE
            stdscr.addstr(line, 2, status, attr)
        stdscr.addstr(height - 2, 0, "Enter apply  Esc cancel", curses.A_DIM)

    def _render_help(self, stdscr: "curses._CursesWindow") -> None:
        height, width = stdscr.getmaxyx()
        lines = [
            "Keybindings",
            "Global: ? help, q quit/back, r refresh",
            "List: j/k move, g/G top/bottom, / search, f filter, s sort, t group",
            "List: w watch toggle, W set interval",
            "List: Space select, b bulk status, Enter detail, c create",
            "Detail: e edit, q back",
            "Edit/Create: Tab next, Enter edit field, s save, q cancel",
        ]
        for idx, line in enumerate(lines):
            if idx >= height - 2:
                break
            attr = curses.A_BOLD if idx == 0 else curses.A_NORMAL
            stdscr.addstr(idx, 0, self._truncate(line, width - 1), attr)

    def _handle_list_key(self, stdscr: "curses._CursesWindow", key: int) -> bool:
        if key in {ord("q")}:
            return True
        if key in {ord("j"), curses.KEY_DOWN}:
            self._move_selection(1)
        elif key in {ord("k"), curses.KEY_UP}:
            self._move_selection(-1)
        elif key in {ord("g")}:  # top
            self.selected_idx = 0
        elif key in {ord("G")}:  # bottom
            self.selected_idx = max(0, len(self.rows) - 1)
        elif key in {curses.KEY_NPAGE}:
            self._move_selection(10)
        elif key in {curses.KEY_PPAGE}:
            self._move_selection(-10)
        elif key in {ord("r")}:  # refresh
            self.refresh_tickets()
        elif key in {ord("w")}:  # watch toggle
            self.watch_enabled = not self.watch_enabled
            if self.watch_enabled:
                self.set_message(f"Watch enabled ({self.watch_interval:g}s).")
            else:
                self.set_message("Watch disabled.")
        elif key in {ord("W")}:  # set watch interval
            raw = self._prompt_input(stdscr, "Watch seconds: ", f"{self.watch_interval:g}")
            if raw is not None:
                try:
                    seconds = float(raw.strip())
                except ValueError:
                    self.set_message("Invalid number.")
                else:
                    if seconds <= 0:
                        self.set_message("Watch must be > 0 seconds.")
                    else:
                        self.watch_interval = seconds
                        self.watch_enabled = True
                        self.set_message(f"Watch enabled ({self.watch_interval:g}s).")
        elif key in {ord("s")}:  # sort
            self._cycle_sort()
        elif key in {ord("t")}:  # group
            self.group_view = not self.group_view
            self.apply_filters()
        elif key in {ord("/")}:  # search
            query = self._prompt_input(stdscr, "Search: ", self.search_query)
            if query is not None:
                self.search_query = query.strip()
                self.apply_filters()
        elif key in {ord("f")}:  # filter
            self._open_filter_panel()
            self.mode = "filter"
        elif key in {ord("c")}:  # create
            self._open_create_form()
        elif key in {ord("?")}:  # help
            self.mode = "help"
        elif key in {ord("b")}:  # bulk
            if not self.selection:
                self.set_message("No tickets selected.")
            else:
                self.mode = "bulk"
                self.bulk_index = 0
        elif key in {ord(" ")}:  # select
            row = self._current_row()
            if row and row.kind == "ticket" and row.ticket:
                ticket_id = row.ticket.ticket_id
                if self.selection.get(ticket_id):
                    self.selection.pop(ticket_id, None)
                else:
                    self.selection[ticket_id] = True
        elif key in {curses.KEY_ENTER, 10, 13}:
            row = self._current_row()
            if row and row.kind == "group" and row.group:
                self.collapsed_groups[row.group] = not self.collapsed_groups.get(row.group)
                self.apply_filters()
            elif row and row.kind == "ticket" and row.ticket:
                self.detail_ticket = row.ticket
                self.mode = "detail"
        elif key in {ord("e")}:
            row = self._current_row()
            if row and row.kind == "ticket" and row.ticket:
                self._open_edit_form(row.ticket)
        elif key in {ord("d")}:
            self.set_message("Delete not supported by backend.")
        elif key == 27:  # esc
            if self.filter_statuses or self.filter_tags or self.search_query:
                self.filter_statuses.clear()
                self.filter_tags.clear()
                self.search_query = ""
                self.apply_filters()
            else:
                self.set_message("Press q to quit.")
        return False

    def _handle_detail_key(self, key: int) -> bool:
        if key in {ord("q"), 27}:
            self.mode = "list"
        elif key in {ord("e")}:
            if self.detail_ticket:
                self._open_edit_form(self.detail_ticket)
        return False

    def _handle_form_key(self, stdscr: "curses._CursesWindow", key: int) -> bool:
        if key in {ord("q"), 27}:
            if self.form_dirty and not self.form_confirm_discard:
                self.form_confirm_discard = True
                self.set_message("Unsaved changes. Press q again to discard.")
                return False
            self.mode = "detail" if self.form_context == "detail" else "list"
            return False
        if key in {ord("\t"), 9}:
            self.form_index = (self.form_index + 1) % len(self.form_fields)
        elif key in {curses.KEY_BTAB}:
            self.form_index = (self.form_index - 1) % len(self.form_fields)
        elif key in {curses.KEY_ENTER, 10, 13}:
            field = self.form_fields[self.form_index]
            if field.multiline:
                updated = self._prompt_multiline(stdscr, field.label, field.value)
            else:
                updated = self._prompt_input(stdscr, f"{field.label}: ", field.value)
            if updated is not None:
                field.value = updated
                self.form_dirty = True
                self.form_confirm_discard = False
        elif key in {ord("s")}:
            if self.mode == "create":
                if not self._save_create():
                    return False
            else:
                if not self._save_edit():
                    return False
            self.mode = "list"
        return False

    def _handle_filter_key(self, key: int) -> bool:
        if key in {27, ord("q")}:  # esc
            self.mode = "list"
            return False
        if key in {ord("j"), curses.KEY_DOWN}:
            self.filter_index = min(len(self.filter_items) - 1, self.filter_index + 1)
        elif key in {ord("k"), curses.KEY_UP}:
            self.filter_index = max(0, self.filter_index - 1)
        elif key in {ord(" ")}:  # toggle
            kind, value, _ = self.filter_items[self.filter_index]
            if kind == "status":
                if value in self.filter_statuses:
                    self.filter_statuses.pop(value, None)
                else:
                    self.filter_statuses[value] = True
            elif kind == "tag":
                if value in self.filter_tags:
                    self.filter_tags.pop(value, None)
                else:
                    self.filter_tags[value] = True
            self.apply_filters()
        elif key in {curses.KEY_ENTER, 10, 13}:
            self.mode = "list"
        return False

    def _handle_bulk_key(self, key: int) -> bool:
        if key in {27, ord("q")}:  # esc
            self.mode = "list"
            return False
        if key in {ord("j"), curses.KEY_DOWN}:
            self.bulk_index = min(len(STATUS_ORDER) - 1, self.bulk_index + 1)
        elif key in {ord("k"), curses.KEY_UP}:
            self.bulk_index = max(0, self.bulk_index - 1)
        elif key in {curses.KEY_ENTER, 10, 13}:
            status = STATUS_ORDER[self.bulk_index]
            for ticket_id in list(self.selection.keys()):
                try:
                    self.backend.update_ticket(ticket_id, status=status)
                except Exception:
                    self.set_message(f"Failed to update {ticket_id}.")
            self.selection.clear()
            self.refresh_tickets()
            self.mode = "list"
        return False

    def _move_selection(self, delta: int) -> None:
        if not self.rows:
            return
        self.selected_idx = max(0, min(len(self.rows) - 1, self.selected_idx + delta))

    def _cycle_sort(self) -> None:
        idx = SORT_MODES.index(self.sort_mode)
        idx = (idx + 1) % len(SORT_MODES)
        self.sort_mode = SORT_MODES[idx]
        self.apply_filters()

    def _current_row(self) -> Optional[Row]:
        if not self.rows:
            return None
        return self.rows[self.selected_idx]

    def _open_edit_form(self, ticket: Ticket) -> None:
        self.form_fields = [
            FormField("subject", "Subject", ticket.subject or ""),
            FormField("status", "Status", ticket.status or ""),
            FormField("tags", "Tags", ",".join(ticket.tags or [])),
            FormField("assignee", "Assignee", ticket.assignee or ""),
            FormField("body", "Body", ticket.body or "", multiline=True),
        ]
        self.form_index = 0
        self.form_dirty = False
        self.form_confirm_discard = False
        self.form_context = "detail"
        self.detail_ticket = ticket
        self.mode = "edit"

    def _open_create_form(self) -> None:
        self.form_fields = [
            FormField("subject", "Subject", ""),
            FormField("status", "Status", "todo"),
            FormField("tags", "Tags", ""),
            FormField("assignee", "Assignee", ""),
            FormField("body", "Body", "", multiline=True),
        ]
        self.form_index = 0
        self.form_dirty = False
        self.form_confirm_discard = False
        self.form_context = "create"
        self.mode = "create"

    def _open_filter_panel(self) -> None:
        items: List[Tuple[str, str, str]] = []
        for status in STATUS_ORDER:
            flag = "[x]" if status in self.filter_statuses else "[ ]"
            items.append(("status", status, f"{flag} status: {status}"))
        all_tags = sorted({tag for ticket in self.tickets for tag in (ticket.tags or [])})
        for tag in all_tags:
            flag = "[x]" if tag in self.filter_tags else "[ ]"
            items.append(("tag", tag, f"{flag} tag: {tag}"))
        self.filter_items = items
        self.filter_index = 0

    def _save_edit(self) -> bool:
        if not self.detail_ticket:
            return False
        data = {field.key: field.value for field in self.form_fields}
        tags = [tag.strip() for tag in data.get("tags", "").split(",") if tag.strip()]
        status = data.get("status", "").strip() or None
        subject = data.get("subject", "").strip()
        body = data.get("body", "")
        assignee = data.get("assignee", "").strip() or None
        try:
            ticket = self.backend.update_ticket(
                self.detail_ticket.ticket_id,
                subject=subject or None,
                body=body,
                assignee=assignee,
                tags=tags,
                status=status,
            )
        except Exception as exc:
            self.set_message(f"Save failed: {exc}")
            return False
        self.detail_ticket = ticket
        self.refresh_tickets()
        return True

    def _save_create(self) -> bool:
        data = {field.key: field.value for field in self.form_fields}
        subject = data.get("subject", "").strip()
        body = data.get("body", "").strip()
        if not subject or not body:
            self.set_message("Subject and body are required.")
            return False
        tags = [tag.strip() for tag in data.get("tags", "").split(",") if tag.strip()]
        status = data.get("status", "").strip() or None
        assignee = data.get("assignee", "").strip() or None
        try:
            ticket = self.backend.create_ticket(
                subject=subject,
                body=body,
                assignee=assignee,
                tags=tags,
                status=status,
            )
        except Exception as exc:
            self.set_message(f"Create failed: {exc}")
            return False
        self.refresh_tickets()
        for idx, row in enumerate(self.rows):
            if row.ticket and row.ticket.ticket_id == ticket.ticket_id:
                self.selected_idx = idx
                break
        return True

    def _prompt_input(
        self, stdscr: "curses._CursesWindow", prompt: str, initial: str
    ) -> Optional[str]:
        height, width = stdscr.getmaxyx()
        prompt_y = height - 2
        stdscr.move(prompt_y, 0)
        stdscr.clrtoeol()
        stdscr.addstr(prompt_y, 0, prompt)
        win_w = max(10, width - len(prompt) - 1)
        edit_win = curses.newwin(1, win_w, prompt_y, len(prompt))
        edit_win.addstr(0, 0, initial)
        curses.curs_set(1)
        cancelled = {"value": False}

        def validator(ch: int) -> int:
            if ch in {10, 13}:
                return 7  # ctrl+g to finish
            if ch == 27:
                cancelled["value"] = True
                return 7
            return ch

        box = textpad.Textbox(edit_win)
        text = box.edit(validator).strip()
        curses.curs_set(0)
        if cancelled["value"]:
            return None
        return text or ""

    def _prompt_multiline(
        self, stdscr: "curses._CursesWindow", label: str, initial: str
    ) -> Optional[str]:
        height, width = stdscr.getmaxyx()
        win_h = max(6, height - 6)
        win_w = max(20, width - 6)
        win_y = 3
        win_x = 3
        win = curses.newwin(win_h, win_w, win_y, win_x)
        win.border()
        win.addstr(0, 2, f" {label} ")
        edit_win = curses.newwin(win_h - 2, win_w - 2, win_y + 1, win_x + 1)
        edit_win.addstr(0, 0, initial)
        box = textpad.Textbox(edit_win)
        curses.curs_set(1)
        stdscr.addstr(height - 2, 0, "Ctrl+G to save", curses.A_DIM)
        stdscr.refresh()
        text = box.edit().strip()
        curses.curs_set(0)
        return text

    def _format_time(self, value: Optional[str]) -> str:
        if not value:
            return ""
        return value[:16]

    def _truncate(self, value: str, width: int) -> str:
        if len(value) <= width:
            return value
        if width <= 3:
            return value[:width]
        return value[: max(0, width - 3)] + "..."

    def _wrap_text(self, text: str, width: int) -> List[str]:
        if not text:
            return []
        lines: List[str] = []
        for paragraph in text.splitlines() or [""]:
            line = ""
            for word in paragraph.split(" "):
                if not line:
                    line = word
                elif len(line) + 1 + len(word) <= width:
                    line = f"{line} {word}"
                else:
                    lines.append(line)
                    line = word
            if line:
                lines.append(line)
        return lines


def run_tui(*, watch: Optional[float] = None) -> int:
    backend = get_backend_from_env()
    app = TuiApp(backend, watch=watch)
    return curses.wrapper(app.run)
