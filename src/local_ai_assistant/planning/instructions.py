"""Project instruction discovery with root-to-leaf precedence."""

from __future__ import annotations

from pathlib import Path


def load_project_instructions(repository: Path, paths: tuple[str, ...], limit: int = 12_000) -> str:
    repository = repository.resolve()
    directories = {repository}
    for value in paths:
        candidate = (repository / value).resolve()
        if repository == candidate or repository in candidate.parents:
            current = candidate.parent if candidate.suffix else candidate
            while repository == current or repository in current.parents:
                directories.add(current)
                if current == repository:
                    break
                current = current.parent
    sections = []
    for directory in sorted(directories, key=lambda item: (len(item.relative_to(repository).parts), str(item))):
        normal = directory / "AGENTS.md"
        override = directory / "AGENTS.override.md"
        chosen = override if override.is_file() else normal
        if chosen.is_file():
            relative = chosen.relative_to(repository).as_posix()
            sections.append(f"[{relative}]\n{chosen.read_text(encoding='utf-8', errors='replace')}")
    return "\n\n".join(sections)[:limit]
