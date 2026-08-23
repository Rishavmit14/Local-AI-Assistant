"""Project instruction discovery with root-to-leaf precedence."""

from __future__ import annotations

from pathlib import Path


def discover_project_instructions(
    repository: Path, paths: tuple[str, ...], limit: int = 12_000
) -> tuple[str, tuple[str, ...], bool]:
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
    sections: list[tuple[str, str]] = []
    for directory in sorted(directories, key=lambda item: (len(item.relative_to(repository).parts), str(item))):
        normal = directory / "AGENTS.md"
        override = directory / "AGENTS.override.md"
        chosen = override if override.is_file() else normal
        if chosen.is_file():
            relative = chosen.relative_to(repository).as_posix()
            sections.append(
                (
                    relative,
                    f"[{relative}]\n{chosen.read_text(encoding='utf-8', errors='replace')}",
                )
            )
    full_content = "\n\n".join(content for _, content in sections)
    if len(full_content) <= limit:
        return full_content, tuple(source for source, _ in sections), False

    # Deeper files have higher precedence, so preserve them first when bounded.
    selected: list[tuple[str, str]] = []
    remaining = limit
    for source, content in reversed(sections):
        separator_size = 2 if selected else 0
        available = remaining - separator_size
        if available <= 0:
            break
        selected.append((source, content[:available]))
        remaining -= min(len(content), available) + separator_size
        if len(content) > available:
            break
    selected.reverse()
    return (
        "\n\n".join(content for _, content in selected),
        tuple(source for source, _ in selected),
        True,
    )


def load_project_instructions(repository: Path, paths: tuple[str, ...], limit: int = 12_000) -> str:
    """Compatibility wrapper returning only assembled instruction text."""
    return discover_project_instructions(repository, paths, limit)[0]
