#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python_command="${PYTHON:-}"

if [[ -z "${python_command}" ]]; then
  if [[ -x "${repository_dir}/.venv/bin/python" ]]; then
    python_command="${repository_dir}/.venv/bin/python"
  elif [[ -x "/AI/projects/local-ai/.venv/bin/python" ]]; then
    python_command="/AI/projects/local-ai/.venv/bin/python"
  else
    python_command="python3"
  fi
fi

cd "${repository_dir}"
export PYTHONPATH="${repository_dir}/src${PYTHONPATH:+:${PYTHONPATH}}"

"${python_command}" -m compileall -q \
  src tests examples/demo-app/app \
  local_llm.py rag.py code_rag.py code_agent.py
"${python_command}" -m pytest
"${python_command}" -m local_ai_assistant.agent.code_agent --help >/dev/null
"${python_command}" -m local_ai_assistant.code_index.repository --help >/dev/null
"${python_command}" -m local_ai_assistant.history.cli --help >/dev/null
"${python_command}" -m pip check

if git ls-files | grep -E '(^|/)(\.venv|venv|__pycache__|rag_data|index|documents|logs?)(/|$)|\.gguf$|\.faiss$|\.db$|\.pyc$'; then
  printf 'Forbidden generated/private artifact is tracked.\n' >&2
  exit 1
fi

printf 'Repository verification passed.\n'
