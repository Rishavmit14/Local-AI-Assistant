"""Ordered SQLite migrations for the local task-history store."""

SCHEMA_VERSION = 2

MIGRATIONS: dict[int, tuple[str, ...]] = {
    1: (
        """CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY, original_request TEXT NOT NULL,
            repository TEXT NOT NULL, starting_commit TEXT NOT NULL, final_commit TEXT,
            branch TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            status TEXT NOT NULL, classification TEXT NOT NULL, risk TEXT NOT NULL,
            confidence REAL, approval_state TEXT NOT NULL, plan_hash TEXT,
            final_decision TEXT, outcome TEXT, failure_reason TEXT,
            human_review_state TEXT NOT NULL, duration_seconds REAL,
            summary TEXT NOT NULL, metadata_json TEXT NOT NULL
        )""",
        """CREATE TABLE task_status_events (
            event_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
            timestamp TEXT NOT NULL, subsystem TEXT NOT NULL, event_type TEXT NOT NULL,
            summary TEXT NOT NULL, artifact_id TEXT, artifact_path TEXT, status TEXT,
            risk_or_severity TEXT, metadata_json TEXT NOT NULL
        )""",
        """CREATE TABLE plans (
            artifact_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
            version INTEGER NOT NULL, artifact_path TEXT NOT NULL, artifact_hash TEXT NOT NULL,
            plan_hash TEXT, created_at TEXT NOT NULL, metadata_json TEXT NOT NULL,
            UNIQUE(task_id, artifact_hash)
        )""",
        """CREATE TABLE executions (
            artifact_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
            run_id TEXT NOT NULL, artifact_path TEXT NOT NULL, artifact_hash TEXT NOT NULL,
            status TEXT, duration_seconds REAL, repairs INTEGER NOT NULL DEFAULT 0,
            replans INTEGER NOT NULL DEFAULT 0, final_commit TEXT, metadata_json TEXT NOT NULL,
            UNIQUE(task_id, artifact_hash)
        )""",
        """CREATE TABLE tool_events (
            event_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
            run_id TEXT, timestamp TEXT NOT NULL, tool_name TEXT NOT NULL, success INTEGER NOT NULL,
            duration_seconds REAL, affected_files_json TEXT NOT NULL, summary TEXT NOT NULL,
            permission TEXT, metadata_json TEXT NOT NULL
        )""",
        """CREATE TABLE validations (
            artifact_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
            validation_id TEXT, artifact_path TEXT NOT NULL, artifact_hash TEXT NOT NULL,
            decision TEXT, duration_seconds REAL, required_passed INTEGER,
            failure_count INTEGER NOT NULL DEFAULT 0, tests_run INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT NOT NULL, UNIQUE(task_id, artifact_hash)
        )""",
        """CREATE TABLE reviews (
            artifact_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
            review_id TEXT, artifact_path TEXT NOT NULL, artifact_hash TEXT NOT NULL,
            blocking_findings INTEGER NOT NULL DEFAULT 0, security_findings INTEGER NOT NULL DEFAULT 0,
            model_assisted INTEGER NOT NULL DEFAULT 0, metadata_json TEXT NOT NULL,
            UNIQUE(task_id, artifact_hash)
        )""",
        """CREATE TABLE approvals (
            approval_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
            plan_hash TEXT NOT NULL, state TEXT NOT NULL, timestamp TEXT NOT NULL,
            actor TEXT NOT NULL, reason TEXT NOT NULL, metadata_json TEXT NOT NULL
        )""",
        """CREATE TABLE affected_files (
            task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
            path TEXT NOT NULL, role TEXT NOT NULL, language TEXT, change_type TEXT,
            PRIMARY KEY(task_id, path, role)
        )""",
        """CREATE TABLE affected_symbols (
            task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
            symbol_id TEXT NOT NULL, qualified_name TEXT, path TEXT, language TEXT, role TEXT NOT NULL,
            PRIMARY KEY(task_id, symbol_id, role)
        )""",
        """CREATE TABLE metrics_summary (
            task_id TEXT PRIMARY KEY REFERENCES tasks(task_id) ON DELETE CASCADE,
            planning_seconds REAL, validation_seconds REAL, repairs INTEGER NOT NULL DEFAULT 0,
            first_pass_success INTEGER, scope_violations INTEGER NOT NULL DEFAULT 0,
            reapprovals INTEGER NOT NULL DEFAULT 0, rollbacks INTEGER NOT NULL DEFAULT 0,
            validation_failures INTEGER NOT NULL DEFAULT 0,
            security_blocking_findings INTEGER NOT NULL DEFAULT 0,
            tests_run INTEGER NOT NULL DEFAULT 0, tool_calls INTEGER NOT NULL DEFAULT 0,
            model_calls INTEGER NOT NULL DEFAULT 0, input_tokens INTEGER, output_tokens INTEGER,
            index_refresh_seconds REAL, failure_category TEXT,
            plan_validation_success INTEGER, patch_preflight_success INTEGER,
            first_targeted_test_pass INTEGER, first_full_suite_pass INTEGER,
            repeated_failures INTEGER NOT NULL DEFAULT 0,
            review_blocking_findings INTEGER NOT NULL DEFAULT 0, commit_success INTEGER
        )""",
        """CREATE TABLE artifact_imports (
            artifact_hash TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
            artifact_type TEXT NOT NULL, artifact_path TEXT NOT NULL, imported_at TEXT NOT NULL,
            schema_version INTEGER NOT NULL
        )""",
        "CREATE INDEX idx_tasks_repository_status ON tasks(repository, status)",
        "CREATE INDEX idx_tasks_created ON tasks(created_at DESC)",
        "CREATE INDEX idx_tasks_risk_classification ON tasks(risk, classification)",
        "CREATE INDEX idx_events_task_time ON task_status_events(task_id, timestamp)",
        "CREATE INDEX idx_files_path ON affected_files(path)",
        "CREATE INDEX idx_symbols_name ON affected_symbols(qualified_name)",
    ),
    2: (
        "ALTER TABLE task_status_events ADD COLUMN sequence INTEGER",
        "UPDATE task_status_events SET sequence = rowid WHERE sequence IS NULL",
        "CREATE UNIQUE INDEX idx_events_task_sequence ON task_status_events(task_id, sequence)",
    ),
}
