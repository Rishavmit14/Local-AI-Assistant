"""Small typed records shared across stabilized components."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: tuple[str, ...]
    cwd: Path
    return_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class GitTransactionSummary:
    outcome: str
    repository: Path
    original_branch: str | None = None
    agent_branch: str | None = None
    starting_commit: str | None = None
    resulting_commit: str | None = None
    rolled_back: bool = False
    failed_branch_kept: bool = False
