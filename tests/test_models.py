from tkts.models import Ticket


def _strip(value: str) -> str:
    return value.strip()


def test_ticket_round_trip_single_document() -> None:
    ticket = Ticket(
        ticket_id="abc123",
        subject="Replace printer toner",
        body="Order black toner",
        assignee="ops",
        tags=["supplies", "printer"],
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-02T00:00:00Z",
        extra_headers={"X-Source": "helpdesk"},
    )

    raw = ticket.to_string()
    parsed = Ticket.from_string(raw)

    assert parsed.ticket_id == ticket.ticket_id
    assert parsed.subject == ticket.subject
    assert _strip(parsed.body) == ticket.body
    assert parsed.assignee == ticket.assignee
    assert parsed.tags == ticket.tags
    assert parsed.created_at == ticket.created_at
    assert parsed.updated_at == ticket.updated_at
    assert parsed.extra_headers.get("X-Source") == "helpdesk"


def test_ticket_round_trip_multi_document() -> None:
    ticket = Ticket(
        ticket_id="multi123",
        subject="Incident summary",
        body="Primary body",
        documents=["Doc one", "Doc two"],
    )

    raw = ticket.to_string()
    parsed = Ticket.from_string(raw)

    assert _strip(parsed.body) == "Doc one"
    assert [_strip(doc) for doc in parsed.documents] == ["Doc one", "Doc two"]
