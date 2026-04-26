"""KB article loader — JSONL one article per line, sorted-key for byte-stable diffs."""

from pathlib import Path

from app.schemas import KBArticle


def load_articles(path: str | Path) -> list[KBArticle]:
    """Load KB articles from a JSONL file. Each non-empty line is a KBArticle JSON object."""
    path = Path(path)
    articles: list[KBArticle] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                articles.append(KBArticle.model_validate_json(line))
            except Exception as e:
                raise ValueError(f"Failed to parse {path}:{lineno}: {e}") from e
    return articles
