"""Conservative changed-content security and dependency checks."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from .models import ReviewFinding, ReviewSeverity

PATTERNS = (
    ("private_key", ReviewSeverity.CRITICAL, re.compile(r"-----BEGIN [^-\n]*PRIVATE KEY-----"), "Private key material in changed content."),
    ("credential", ReviewSeverity.CRITICAL, re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\s*=\s*['\"][^'\"\n]{8,}['\"]"), "Hard-coded credential-like value."),
    ("unsafe_eval", ReviewSeverity.HIGH, re.compile(r"\b(eval|exec)\s*\("), "Dynamic code execution introduced."),
    ("shell_true", ReviewSeverity.HIGH, re.compile(r"subprocess\.[A-Za-z_]+\([^\n]*shell\s*=\s*True"), "Subprocess shell execution introduced."),
    ("unsafe_deserialization", ReviewSeverity.HIGH, re.compile(r"\b(pickle\.loads?|yaml\.load)\s*\("), "Potentially unsafe deserialization."),
    ("sql_concatenation", ReviewSeverity.HIGH, re.compile(r"(?i)(?:(select|insert|update|delete).{0,80}(\+|\.format\(|\{)|f['\"][^\n]*(select|insert|update|delete))"), "SQL appears dynamically concatenated."),
    ("path_traversal", ReviewSeverity.MEDIUM, re.compile(r"(?:\.\./|\.\.\\\\|Path\([^\n]+\)\s*/\s*request)"), "Potential user-controlled path traversal."),
    ("weak_crypto", ReviewSeverity.MEDIUM, re.compile(r"\b(hashlib\.)?(md5|sha1)\s*\("), "Weak cryptographic primitive introduced."),
    ("insecure_temp", ReviewSeverity.MEDIUM, re.compile(r"tempfile\.mktemp\s*\("), "Race-prone temporary filename creation."),
    ("debug_backdoor", ReviewSeverity.HIGH, re.compile(r"(?i)(admin|debug).{0,40}(bypass|backdoor|allow_all|true)"), "Possible privileged debug bypass."),
    ("auth_bypass", ReviewSeverity.CRITICAL, re.compile(r"(?i)(authorize|permission|verify_token|is_admin).{0,50}(return\s+True|bypass|disabled)"), "Possible authorization bypass."),
)

SOLIDITY_PATTERNS = (
    ("solidity_tx_origin", ReviewSeverity.HIGH, r"\btx\.origin\b", "tx.origin authorization is unsafe."),
    ("solidity_delegatecall", ReviewSeverity.CRITICAL, r"\.delegatecall\s*\(", "delegatecall changes require critical review."),
    ("solidity_selfdestruct", ReviewSeverity.CRITICAL, r"\bselfdestruct\s*\(", "selfdestruct is irreversible."),
    ("solidity_unchecked_call", ReviewSeverity.HIGH, r"\.call\s*\{[^}]*value", "Value-transferring external call requires reentrancy review."),
    ("solidity_unrestricted_transfer", ReviewSeverity.CRITICAL, r"\b(payable\([^)]*\)\.transfer|\.send\s*\()", "Value transfer requires authorization and return-value review."),
    ("solidity_unchecked", ReviewSeverity.MEDIUM, r"\bunchecked\s*\{", "Unchecked arithmetic assumptions require review."),
)


def scan_changed_content(diff: str) -> tuple[ReviewFinding, ...]:
    findings: list[ReviewFinding] = []
    path = None
    new_line = 0
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            continue
        hunk = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)", line)
        if hunk:
            new_line = int(hunk.group(1))
            continue
        if not line.startswith("+") or line.startswith("+++"):
            if line and not line.startswith("-"):
                new_line += 1
            continue
        content = line[1:]
        findings.extend(_scan_line(path, new_line, content))
        new_line += 1
    findings.extend(scan_dependency_changes(diff))
    return tuple(findings)


def scan_dependency_changes(diff: str) -> tuple[ReviewFinding, ...]:
    findings = []
    path = None
    manifests = {"pyproject.toml", "package.json", "Cargo.toml", "requirements.txt", "foundry.toml"}
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif path and PurePosixPath(path).name in manifests and line.startswith("+") and not line.startswith("+++"):
            content = line[1:].strip()
            severity = None
            reason = ""
            if re.search(r"(?:git\+|https?://|github:|path\s*=|file:)", content, re.I):
                severity, reason = ReviewSeverity.HIGH, "Direct URL, VCS, or local-path dependency introduced."
            elif _looks_unpinned(content):
                severity, reason = ReviewSeverity.MEDIUM, "Potentially unpinned dependency introduced."
            if severity:
                findings.append(_finding("dependency_security", severity, path, None, content, reason))
    return tuple(findings)


def enhanced_auth_review(diff: str, affected_files: tuple[str, ...]) -> tuple[ReviewFinding, ...]:
    text = " ".join(affected_files).lower() + " " + diff.lower()
    if not any(word in text for word in ("auth", "login", "token", "permission", "password", "session", "role")):
        return ()
    findings = []
    for regex, reason in (
        (r"compare_digest[^\n]*^-", "Timing-safe secret comparison appears removed."),
        (r"verify[^\n]*^-", "Authentication verification code appears removed."),
        (r"(?i)^\+.*password\s*=\s*[^h\n]+$", "Password handling may store plaintext."),
    ):
        if re.search(regex, diff, re.MULTILINE):
            findings.append(_finding("auth_permission", ReviewSeverity.HIGH, None, None, "[redacted auth change]", reason))
    if not findings:
        findings.append(_finding("auth_permission", ReviewSeverity.INFO, None, None, "Auth-sensitive scope detected.", "Enhanced human/model review is required.", False))
    return tuple(findings)


def _scan_line(path, line, content):
    findings = []
    for name, severity, pattern, rationale in PATTERNS:
        if pattern.search(content):
            evidence = "[REDACTED SECRET MATCH]" if name in {"private_key", "credential"} else content[:200]
            findings.append(_finding(name, severity, path, line, evidence, rationale))
    if path and path.endswith(".sol"):
        for name, severity, pattern, rationale in SOLIDITY_PATTERNS:
            if re.search(pattern, content):
                findings.append(_finding(name, severity, path, line, content[:200], rationale))
    return findings


def _finding(category, severity, path, line, evidence, rationale, blocking=None):
    return ReviewFinding(category, severity, path, None, line, line, evidence, rationale, "deterministic", severity in {ReviewSeverity.HIGH, ReviewSeverity.CRITICAL} if blocking is None else blocking, "security.scan")


def _looks_unpinned(content: str) -> bool:
    if not content or content.startswith(("#", "[", "{")):
        return False
    return bool(re.match(r"[A-Za-z0-9_.-]+\s*(?:$|[=:]\s*['\"]?[*^~]?[\s'\"]*$)", content))
