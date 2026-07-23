from __future__ import annotations

from pathlib import Path

from career_os.records.models import AUTHORITY_DIRECTORIES


def initialize_data_root(data_root: Path, seeds_root: Path | None = None) -> list[Path]:
    created: list[Path] = []
    data_root.mkdir(parents=True, exist_ok=True)
    selected_seeds = seeds_root or Path(__file__).resolve().parents[2] / "seeds"
    home = data_root / "README.md"
    if not home.exists():
        home.write_text(
            _required_seed_text(selected_seeds, "data-root-readme.md"),
            encoding="utf-8",
            newline="\n",
        )
        created.append(home)
    for directory in AUTHORITY_DIRECTORIES.values():
        authority_root = data_root / directory
        authority_root.mkdir(parents=True, exist_ok=True)
        readme = authority_root / "README.md"
        if not readme.exists():
            readme.write_text(
                _required_seed_text(selected_seeds, f"authorities/{directory}.md"),
                encoding="utf-8",
                newline="\n",
            )
            created.append(readme)
    inbox = data_root / "10-career-evidence/_inbox/README.md"
    if not inbox.exists():
        inbox.parent.mkdir(parents=True, exist_ok=True)
        inbox.write_text(
            _seed_text(
                selected_seeds,
                "evidence-inbox-readme.md",
                "# Career Evidence Inbox\n\nRaw, unapproved captures live here.\n",
            ),
            encoding="utf-8",
            newline="\n",
        )
        created.append(inbox)
    return created


def _seed_text(seeds_root: Path | None, name: str, fallback: str) -> str:
    if seeds_root is None:
        return fallback
    path = seeds_root / name
    return path.read_text(encoding="utf-8") if path.is_file() else fallback


def _required_seed_text(seeds_root: Path, name: str) -> str:
    path = seeds_root.joinpath(*Path(name).parts)
    if not path.is_file():
        raise FileNotFoundError(f"required initialization seed is missing: {path}")
    return path.read_text(encoding="utf-8")
