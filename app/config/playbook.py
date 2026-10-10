from functools import lru_cache
from pathlib import Path

PLAYBOOK_PATH = Path(__file__).parent.parent.parent / "prompts" / "playbook.md"


@lru_cache
def _load_sections() -> dict[str, str]:
    text = PLAYBOOK_PATH.read_text()
    sections: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines).strip()
            current_name = line[3:].strip()
            current_lines = []
        elif current_name is not None:
            current_lines.append(line)
    if current_name is not None:
        sections[current_name] = "\n".join(current_lines).strip()
    return sections


def load_playbook_sections(names: list[str]) -> str:
    sections = _load_sections()
    missing = [name for name in names if name not in sections]
    if missing:
        raise KeyError(
            f"playbook sections not found: {missing}, available: {sorted(sections)}"
        )
    return "\n\n".join(f"## {name}\n{sections[name]}" for name in names)


def load_full_playbook() -> str:
    sections = _load_sections()
    return "\n\n".join(f"## {name}\n{body}" for name, body in sections.items())
