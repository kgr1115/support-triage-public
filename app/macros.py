"""Macro loader. Same JSONL pattern as KB articles."""

from pathlib import Path

from app.schemas import Macro


def load_macros(path: str | Path) -> list[Macro]:
    """Load macros from a JSONL file. Each non-empty line is a Macro JSON object."""
    path = Path(path)
    macros: list[Macro] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                macros.append(Macro.model_validate_json(line))
            except Exception as e:
                raise ValueError(f"Failed to parse {path}:{lineno}: {e}") from e
    return macros
