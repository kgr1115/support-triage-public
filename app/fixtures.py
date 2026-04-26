import json
from pathlib import Path

from app.schemas import Ticket


def load_tickets(path: str | Path) -> list[Ticket]:
    """Load labeled tickets from a JSONL file. Each non-empty line is a Ticket JSON object."""
    path = Path(path)
    tickets: list[Ticket] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                tickets.append(Ticket.model_validate_json(line))
            except Exception as e:
                raise ValueError(f"Failed to parse {path}:{lineno}: {e}") from e
    return tickets


def write_tickets(tickets: list[Ticket], path: str | Path) -> None:
    """Write tickets to a JSONL file (one Ticket per line, sorted-key JSON for determinism)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for t in tickets:
            fh.write(json.dumps(t.model_dump(mode="json"), sort_keys=True))
            fh.write("\n")
