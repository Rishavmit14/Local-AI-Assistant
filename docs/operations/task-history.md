# Task history operations

The default database is ignored runtime state at `var/history/tasks.sqlite3`. Override it with
`LOCAL_AI_TASK_HISTORY_DB`. Keep the database local and writable by the Friday service account;
the database, WAL files, exports, and archives are runtime artifacts and must not be committed.

```bash
local-ai-history migrate
local-ai-history status
local-ai-history create /path/to/configured/repository "Explain parser invalidation"
local-ai-history import var/code-index/plans/demo/task.json
local-ai-history list --status succeeded --risk medium
local-ai-history search "parser" --language rust
local-ai-history show TASK_ID
local-ai-history timeline TASK_ID
local-ai-history metrics
local-ai-history export TASK_ID /tmp/task.md --format markdown
local-ai-history archive TASK_ID /tmp/task.zip
local-ai-history storage
local-ai-history orphans
local-ai-history prune-orphans --confirm
local-ai-history vacuum
```

Import never changes or deletes source artifacts. Duplicate content hashes are ignored. Corrupt, unsupported, cross-repository, and identity-conflicting artifacts fail explicitly.

Before migration or maintenance, stop active writers and copy the database plus its `-wal` and `-shm` companions, or use SQLite's online backup API. Migrations are transactional; downgrade is not supported. `vacuum` is explicit and never deletes tasks. Automatic retention is intentionally absent. Orphaned temporary JSON files may be inspected manually, but Stage 7 does not delete them.

The synthetic benchmark is:

```bash
PYTHONPATH=src python scripts/benchmark/task-history.py --tasks 3000
```

It measures local SQLite mechanics, not model quality or production multi-user load.
