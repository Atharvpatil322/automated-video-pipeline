import re
from datetime import datetime
from pathlib import Path

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9-]+")


def slugify(topic: str, max_length: int = 50) -> str:
    slug = topic.strip().lower().replace(" ", "-")
    slug = _SLUG_STRIP_RE.sub("", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:max_length] or "untitled"


def create_run_dir(topic: str, base_dir: Path | None = None) -> Path:
    base_dir = base_dir or Path("output")
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    run_dir = base_dir / f"{timestamp}-{slugify(topic)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir
