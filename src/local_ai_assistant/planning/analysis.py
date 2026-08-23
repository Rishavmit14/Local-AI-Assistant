"""Deterministic affected-scope, risk, confidence, and policy analysis."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from local_ai_assistant.code_index.models import SymbolRecord
from local_ai_assistant.code_index.symbol_index import SymbolIndex

from .models import (
    ApprovalDecision,
    ApprovalStatus,
    ConfidenceAssessment,
    ImplementationPlan,
    RiskAssessment,
    RiskLevel,
    ScopeCandidate,
    ScopeGuardPolicy,
    ScopeRole,
    TaskCategory,
    TaskClassification,
    ValidationIssue,
)

DEPENDENCY_NAMES = {
    "pyproject.toml", "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "cargo.toml", "cargo.lock", "foundry.toml",
}
PROTECTED_PARTS = {".git", ".venv", "venv", "__pycache__", "node_modules", "var"}
SECURITY_WORDS = {
    "auth", "permission", "secret", "credential", "crypto", "token", "password",
    "shell", "subprocess", "network", "delete", "unlink", "private key", "contract",
}
CRITICAL_WORDS = {
    "drop table", "drop column", "production credential", "private key", "fund transfer",
    "payment", "irreversible", "selfdestruct",
}
HIGH_RISK_WORDS = {
    "breaking public api",
    "public api break",
    "concurrency-critical",
    "race condition",
    "thread safety",
    "deadlock",
}
MIGRATION_WORDS = {
    "migration", "migrations", "alembic", "schema", "alter table", "drop table",
    "drop column", "rename column", "django migration", "data migration",
}


def is_dependency_file(path: str) -> bool:
    value = PurePosixPath(path)
    name = value.name.lower()
    return name in DEPENDENCY_NAMES or name.startswith("requirements") and name.endswith(".txt") or "requirements" in value.parts and name.endswith(".txt") or "systemd" in path.lower() or path.startswith("scripts/bootstrap/") or path.startswith("scripts/install/")


def is_protected_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(part in PROTECTED_PARTS for part in parts) or path.endswith((".min.js", ".generated.py"))


def detect_migration(request: str, paths: tuple[str, ...] = ()) -> tuple[str, ...]:
    text = " ".join((request, *paths)).lower()
    reasons = [f"Migration signal: {word}" for word in sorted(MIGRATION_WORDS) if word in text]
    if re.search(r"(^|/)(migrations?|alembic)/", text):
        reasons.append("Migration directory is in scope.")
    return tuple(dict.fromkeys(reasons))


def detect_security(request: str, paths: tuple[str, ...] = ()) -> tuple[str, ...]:
    text = " ".join((request, *paths)).lower()
    return tuple(f"Security-sensitive signal: {word}" for word in sorted(SECURITY_WORDS) if word in text)


class ScopeAnalyzer:
    def __init__(self, repository: Path, symbols: SymbolIndex, legacy_retrieve=None) -> None:
        self.repository = repository.resolve()
        self.symbols = symbols
        self.legacy_retrieve = legacy_retrieve
        try:
            relative = self.repository.relative_to(symbols.repository).as_posix()
            self.index_prefix = "" if relative == "." else relative + "/"
        except ValueError:
            self.index_prefix = ""

    def analyze(self, request: str) -> tuple[ScopeCandidate, ...]:
        candidates: dict[tuple[str, str | None, str], ScopeCandidate] = {}
        identifiers = dict.fromkeys(re.findall(r"\b[A-Za-z_]\w*\b", request))
        direct_symbols: list[SymbolRecord] = []
        for name in identifiers:
            exact = [item for item in self.symbols.find_exact(name) if self._in_repository(item)]
            direct_symbols.extend(exact)
            for symbol in exact:
                self._add(candidates, symbol, "Identifier appears exactly in request.", "exact_symbol", 1.0, 0.98, ScopeRole.DIRECT)
        for name in (item for item in identifiers if len(item) >= 3):
            for symbol in self.symbols.search_name(name, 20):
                if not self._in_repository(symbol):
                    continue
                self._add(candidates, symbol, "Symbol name matches a request term.", "name_match", None, 0.8, ScopeRole.DIRECT)
        normalized_request = request.lower()
        for indexed_path in self.symbols.repository_map():
            if self.index_prefix and not indexed_path.startswith(self.index_prefix):
                continue
            relative = self._relative_path(indexed_path)
            if relative.lower() in normalized_request or PurePosixPath(relative).name.lower() in normalized_request:
                self._add_path(candidates, indexed_path, "Repository map path is explicitly named in the request.", "repository_map", 0.92, ScopeRole.DIRECT)
        for result in self.symbols.hybrid_search(request, 8):
            if not self._in_repository(result["symbol"]):
                continue
            self._add(
                candidates,
                result["symbol"],
                "Local semantic and lexical retrieval selected this symbol via RRF.",
                "symbol_hybrid",
                result["hybrid_score"],
                0.65,
                ScopeRole.OPTIONAL,
                {
                    "semantic_rank": result["semantic_rank"],
                    "lexical_rank": result["lexical_rank"],
                    "retrieval_method": "symbol_hybrid_rrf",
                },
            )
        for symbol in direct_symbols:
            for edge, relationship in (
                (self.symbols.callers(symbol.identifier), "caller"),
                (self.symbols.callees(symbol.identifier), "callee"),
            ):
                for call in edge:
                    related_id = call.caller if relationship == "caller" else call.callee
                    related = self._symbol(related_id)
                    if related:
                        self._add(candidates, related, f"Static {relationship} of {symbol.qualified_name}.", relationship, None, 0.72, ScopeRole.DEPENDENT)
            module = self.symbols.containing_module(symbol.identifier)
            if module:
                module_name = module.qualified_name
                local_module_name = self._module_name(module.path)
                for importer in self.symbols.imported_by(local_module_name):
                    if self.index_prefix and not importer.startswith(self.index_prefix):
                        continue
                    self._add_path(candidates, importer, f"Imports affected module {local_module_name}.", "reverse_import", 0.68, ScopeRole.DEPENDENT)
                for imported in self.symbols.imports_of(module.path):
                    imported_module = next(
                        (
                            item
                            for item in self.symbols.symbols
                            if item.kind.value == "module"
                            and self._in_repository(item)
                            and self._module_name(item.path) == imported
                        ),
                        None,
                    )
                    if imported_module:
                        self._add(candidates, imported_module, f"Imported by affected module {module_name}.", "import", None, 0.6, ScopeRole.OPTIONAL)
        self._add_tests(candidates, direct_symbols)
        if not any(item.role is ScopeRole.DIRECT for item in candidates.values()) and self.legacy_retrieve:
            for result in self.legacy_retrieve(request):
                if result.get("retrieval_method") != "line_chunk_fallback":
                    continue
                source = result["source"]
                if self.index_prefix and not source.startswith(self.index_prefix):
                    continue
                candidate = ScopeCandidate(
                    self._relative_path(source),
                    None,
                    None,
                    "Legacy line-chunk fallback supplied context where no direct symbol matched.",
                    "legacy_line_chunk",
                    result.get("hybrid_score"),
                    {
                        "source": self._relative_path(source),
                        "line_start": result.get("line_start"),
                        "line_end": result.get("line_end"),
                        "symbol_identifier": None,
                        "retrieval_method": "line_chunk_fallback",
                    },
                    0.5,
                    ScopeRole.OPTIONAL,
                )
                candidates[(candidate.path, None, candidate.relationship)] = candidate
        return tuple(sorted(candidates.values(), key=lambda item: (list(ScopeRole).index(item.role), -item.confidence, item.path, item.qualified_name or "")))

    def _add_tests(self, candidates, direct_symbols):
        modules = {self.symbols.containing_module(item.identifier).qualified_name for item in direct_symbols if self.symbols.containing_module(item.identifier)}
        names = {item.name for item in direct_symbols}
        for path in self.repository.rglob("test*.py"):
            if not path.is_file():
                continue
            relative = path.relative_to(self.repository).as_posix()
            text = path.read_text(encoding="utf-8", errors="replace")
            matched = sorted(name for name in names | modules if name and name in text)
            if matched:
                self._add_path(candidates, relative, f"Test references affected code: {', '.join(matched)}.", "relevant_test", 0.84, ScopeRole.DEPENDENT)

    def _add(
        self,
        candidates,
        symbol,
        reason,
        relationship,
        score,
        confidence,
        role,
        extra_provenance=None,
    ):
        path = self._relative_path(symbol.path)
        provenance = {
            "source": path,
            "line_start": symbol.start_line,
            "line_end": symbol.end_line,
            "symbol_identifier": symbol.identifier,
        }
        provenance.update(extra_provenance or {})
        candidate = ScopeCandidate(path, symbol.identifier, symbol.qualified_name, reason, relationship, score, provenance, confidence, role)
        candidates[(candidate.path, candidate.symbol_id, relationship)] = candidate

    def _add_path(self, candidates, path, reason, relationship, confidence, role):
        path = self._relative_path(path)
        candidate = ScopeCandidate(path, None, None, reason, relationship, None, {"source": path, "line_start": 1, "line_end": 1, "symbol_identifier": None}, confidence, role)
        candidates[(path, None, relationship)] = candidate

    def _symbol(self, identifier):
        return next((item for item in self.symbols.symbols if identifier and item.identifier == identifier and self._in_repository(item)), None)

    def _in_repository(self, symbol: SymbolRecord) -> bool:
        return not self.index_prefix or symbol.path.startswith(self.index_prefix)

    def _relative_path(self, path: str) -> str:
        return path[len(self.index_prefix):] if self.index_prefix and path.startswith(self.index_prefix) else path

    def _module_name(self, path: str) -> str:
        from local_ai_assistant.code_index.python_parser import PythonSymbolExtractor

        return PythonSymbolExtractor.module_name(self._relative_path(path))


def assess_confidence(classification: TaskClassification, candidates: tuple[ScopeCandidate, ...], warning_count: int = 0, unresolved_questions: int = 0) -> ConfidenceAssessment:
    exact = sum(item.relationship == "exact_symbol" for item in candidates)
    graph = sum(item.relationship in {"caller", "callee", "import", "reverse_import"} for item in candidates)
    tests = sum(item.relationship == "relevant_test" for item in candidates)
    factors = {
        "classification": classification.confidence,
        "exact_symbol_coverage": min(1.0, exact / 2),
        "graph_support": min(1.0, graph / 3),
        "test_support": min(1.0, tests / 2),
        "ambiguity_penalty": min(1.0, (warning_count + unresolved_questions) / 5),
    }
    score = 0.3 * factors["classification"] + 0.35 * factors["exact_symbol_coverage"] + 0.15 * factors["graph_support"] + 0.1 * factors["test_support"] + 0.1 * (1 - factors["ambiguity_penalty"])
    return ConfidenceAssessment(round(max(0.0, min(1.0, score)), 3), factors, ("Heuristic planning confidence; not a probability.",))


def assess_risk(request: str, classification: TaskClassification, paths: tuple[str, ...], dependency_changes: tuple[str, ...] = ()) -> RiskAssessment:
    security = detect_security(request, paths)
    migration = detect_migration(request, paths)
    dependency = bool(dependency_changes or any(is_dependency_file(path) for path in paths))
    text = " ".join((request, *paths)).lower()
    critical = [word for word in CRITICAL_WORDS if word in text]
    elevated = [word for word in HIGH_RISK_WORDS if word in text]
    reasons: list[str] = []
    if critical:
        level = RiskLevel.CRITICAL
        reasons.append("Critical irreversible/value/credential signal: " + ", ".join(sorted(critical)))
    elif security or migration or dependency or elevated or classification.category in {
        TaskCategory.AUTHENTICATION_AUTHORIZATION, TaskCategory.SECURITY_SENSITIVE,
        TaskCategory.DATABASE_MIGRATION, TaskCategory.DEPLOYMENT_OPERATIONS,
        TaskCategory.DEPENDENCY_CHANGE,
    }:
        level = RiskLevel.HIGH
        reasons.extend((*security, *migration))
        if elevated:
            reasons.append("High-risk API/concurrency signal: " + ", ".join(sorted(elevated)))
        if dependency:
            reasons.append("Dependency or deployment manifest is in scope.")
    elif paths and all(path.lower().startswith(("docs/", "tests/")) or PurePosixPath(path).name.lower() in {"readme.md"} for path in paths):
        level = RiskLevel.LOW
        reasons.append("Scope is limited to documentation/tests.")
    else:
        level = RiskLevel.MEDIUM
        reasons.append("Ordinary application or internal API scope.")
    return RiskAssessment(level, tuple(dict.fromkeys(reasons)) or ("No elevated deterministic risk signal.",), bool(security), dependency, bool(migration))


def decide_approval(risk: RiskAssessment, confidence: ConfidenceAssessment, issues: tuple[ValidationIssue, ...], scope_size: int, unresolved_questions: int) -> ApprovalDecision:
    if any(issue.severity.value == "error" for issue in issues):
        return ApprovalDecision(ApprovalStatus.REJECTED, ("Plan validation contains errors.",))
    if risk.level is RiskLevel.CRITICAL:
        return ApprovalDecision(ApprovalStatus.BLOCKED, ("Critical-risk work requires explicit approval.",))
    if risk.level is RiskLevel.HIGH:
        return ApprovalDecision(ApprovalStatus.REVIEW, ("High-risk work requires human review before patch generation.",))
    if confidence.score < 0.45 or unresolved_questions or scope_size > 12:
        return ApprovalDecision(ApprovalStatus.REVIEW, ("Low confidence, ambiguity, or broad scope requires review.",))
    return ApprovalDecision(ApprovalStatus.AUTOMATIC, ("Validated low/medium-risk scope has sufficient deterministic support.",))


def scope_guard_from_plan(plan: ImplementationPlan) -> ScopeGuardPolicy:
    files = tuple(dict.fromkeys((*plan.files_to_modify, *plan.files_to_inspect)))
    protected = tuple(path for path in files if is_protected_path(path))
    return ScopeGuardPolicy(files, tuple(dict.fromkeys(plan.symbols_to_modify)), tuple(dict.fromkeys(plan.files_to_create)), tuple(dict.fromkeys(plan.files_to_delete_or_rename)), max(1, len(set((*files, *plan.files_to_create, *plan.files_to_delete_or_rename)))), max(1, len(set(plan.symbols_to_modify))), protected, "approval_required" if plan.dependency_changes else "deny_unplanned", "deny", "approval_required")


def compare_scope(policy: ScopeGuardPolicy, changed_files: tuple[str, ...], changed_symbols: tuple[str, ...] = ()) -> tuple[str, ...]:
    issues = []
    allowed = set((*policy.allowed_files, *policy.allowed_new_files, *policy.allowed_deletes_or_renames))
    unexpected = set(changed_files) - allowed
    if unexpected:
        issues.append("Unplanned files: " + ", ".join(sorted(unexpected)))
    if len(set(changed_files)) > policy.max_file_count:
        issues.append("Patch exceeds planned file count.")
    unexpected_symbols = set(changed_symbols) - set(policy.allowed_symbols)
    if unexpected_symbols:
        issues.append("Unplanned symbols: " + ", ".join(sorted(unexpected_symbols)))
    if len(set(changed_symbols)) > policy.max_symbol_count:
        issues.append("Patch exceeds planned symbol count.")
    return tuple(issues)
