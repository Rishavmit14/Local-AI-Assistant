"""Promotion-readiness gate for the exact reviewed and validated worktree state."""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .errors import PromotionError
from .gitops import ensure_no_git_filters, git_argv, safe_git_environment
from .models import WorktreeIdentity, WorktreeState


@dataclass(frozen=True, slots=True)
class PromotionEvidence:
    plan_hash: str
    reviewed_diff_hash: str
    validated_diff_hash: str
    current_diff_hash: str
    commit: str | None = None


def worktree_diff_bytes(repository: Path, starting_commit: str) -> bytes:
    result = subprocess.run(
        ["git", "diff", "--binary", "--full-index", starting_commit],
        cwd=repository,
        capture_output=True,
    )
    if result.returncode:
        raise PromotionError("Cannot inspect worktree promotion diff")
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=repository,
        capture_output=True,
    )
    if untracked.returncode:
        raise PromotionError("Cannot inspect untracked promotion files")
    # An untracked inventory is part of identity; content must be staged before commit.
    return result.stdout + b"\0UNTRACKED\0" + untracked.stdout


def diff_hash(repository: Path, starting_commit: str) -> str:
    repository = repository.resolve(strict=True)
    try:
        ensure_no_git_filters(repository, starting_commit)
    except Exception as exc:
        raise PromotionError(str(exc)) from exc
    with tempfile.NamedTemporaryFile(prefix="friday-index-", delete=False) as stream:
        index_path = Path(stream.name)
    try:
        source_index = subprocess.run(
            ["git", "rev-parse", "--git-path", "index"],
            cwd=repository,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        source_path = Path(source_index)
        if not source_path.is_absolute():
            source_path = repository / source_path
        index_path.write_bytes(source_path.read_bytes())
        environment = safe_git_environment({"GIT_INDEX_FILE": str(index_path)})
        subprocess.run(
            git_argv("add", "-A"), cwd=repository, env=environment, check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        tree = subprocess.run(
            git_argv("write-tree"), cwd=repository, env=environment, check=True,
            text=True, capture_output=True,
        ).stdout.strip()
        return hashlib.sha256(f"{starting_commit}\0{tree}".encode()).hexdigest()
    except (OSError, subprocess.SubprocessError) as exc:
        raise PromotionError(f"Cannot calculate promotion state identity: {exc}") from exc
    finally:
        index_path.unlink(missing_ok=True)


def verify_promotion(
    identity: WorktreeIdentity,
    reviewed_diff_hash: str,
    validated_diff_hash: str,
    *,
    canonical_head: str,
) -> PromotionEvidence:
    if identity.state not in {WorktreeState.VALIDATING, WorktreeState.PROMOTION_READY}:
        raise PromotionError("Worktree is not in a promotable lifecycle state")
    if canonical_head != identity.starting_commit:
        raise PromotionError("Canonical repository advanced; revalidation/reapproval is required")
    current = diff_hash(Path(identity.worktree), identity.starting_commit)
    if not current or len({current, reviewed_diff_hash, validated_diff_hash}) != 1:
        raise PromotionError("Reviewed, validated, and current diff identities do not match")
    return PromotionEvidence(identity.plan_hash, reviewed_diff_hash, validated_diff_hash, current)


def commit_exact(
    identity: WorktreeIdentity,
    evidence: PromotionEvidence,
    message: str,
) -> PromotionEvidence:
    repository = Path(identity.worktree)
    if diff_hash(repository, identity.starting_commit) != evidence.current_diff_hash:
        raise PromotionError("Worktree changed after promotion review")
    try:
        ensure_no_git_filters(repository, identity.starting_commit)
    except Exception as exc:
        raise PromotionError(str(exc)) from exc
    environment = safe_git_environment()
    add = subprocess.run(git_argv("add", "-A"), cwd=repository, env=environment, capture_output=True)
    if add.returncode:
        raise PromotionError("Cannot stage promotion candidate")
    commit = subprocess.run(
        git_argv("commit", "-m", message),
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
    )
    if commit.returncode:
        subprocess.run(
            git_argv("restore", "--staged", "."), cwd=repository, env=environment, capture_output=True
        )
        raise PromotionError("Cannot commit promotion candidate: " + commit.stderr.strip())
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True, capture_output=True
    ).stdout.strip()
    committed_tree = subprocess.run(
        ["git", "rev-parse", f"{head}^{{tree}}"], cwd=repository,
        text=True, capture_output=True,
    ).stdout.strip()
    committed_hash = hashlib.sha256(
        f"{identity.starting_commit}\0{committed_tree}".encode()
    ).hexdigest()
    if committed_hash != evidence.current_diff_hash:
        raise PromotionError("Committed content differs from reviewed promotion evidence")
    return PromotionEvidence(
        evidence.plan_hash,
        evidence.reviewed_diff_hash,
        evidence.validated_diff_hash,
        evidence.current_diff_hash,
        head,
    )
