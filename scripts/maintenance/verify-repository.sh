#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python_command="${PYTHON:-python3}"
cd "${repository_dir}"

"${python_command}" -m compileall -q src ui tests examples/demo-app/app
"${python_command}" -m pytest

if git ls-files | grep -E '(^|/)(\.venv|venv|__pycache__|rag_data|index|documents|logs?)(/|$)|\.gguf$|\.faiss$|\.db$|\.pyc$'; then
  printf 'Forbidden generated/private artifact is tracked.\n' >&2
  exit 1
fi

printf 'Repository verification passed.\n'
