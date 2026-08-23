#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python_command="${PYTHON:-python3}"

"${python_command}" -m venv "${repository_dir}/.venv"
"${repository_dir}/.venv/bin/python" -m pip install --upgrade pip
"${repository_dir}/.venv/bin/python" -m pip install -e "${repository_dir}[rag,ui,coding-agent,dev]"
mkdir -p "${repository_dir}/var/documents" "${repository_dir}/var/rag" \
  "${repository_dir}/var/repos" "${repository_dir}/var/code-index" \
  "${repository_dir}/var/patches"

printf 'Bootstrap complete. Copy .env.example to .env and adjust machine-local paths.\n'
