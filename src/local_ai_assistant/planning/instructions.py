"""Project instruction discovery with root-to-leaf precedence."""

from __future__ import annotations

from pathlib import Path

from local_ai_assistant.common.repository_files import read_repo_file_bounded


MAX_INSTRUCTION_FILE_BYTES = 1024 * 1024
MAX_INSTRUCTION_PATHS = 256


def discover_project_instructions(
    repository: Path, paths: tuple[str, ...], limit: int = 12_000
) -> tuple[str, tuple[str, ...], bool]:
    repository = repository.resolve()
    paths_truncated = len(paths) > MAX_INSTRUCTION_PATHS
    bounded_paths = paths[:MAX_INSTRUCTION_PATHS]
    directories = {repository}
    for value in bounded_paths:
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
        candidates = (directory / "AGENTS.override.md", directory / "AGENTS.md")
        chosen = None
        content = None
        for candidate in candidates:
            result = read_repo_file_bounded(
                repository,
                candidate,
                max_bytes=MAX_INSTRUCTION_FILE_BYTES,
            )
            if result.readable:
                chosen, content = candidate, result.text
                break
        if chosen is not None and content is not None:
            relative = chosen.relative_to(repository).as_posix()
            sections.append(
                (
                    relative,
                    f"[{relative}]\n{content}",
                )
            )
    full_content = "\n\n".join(content for _, content in sections)
    if len(full_content) <= limit:
        return (
            full_content,
            tuple(source for source, _ in sections),
            paths_truncated,
        )

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
