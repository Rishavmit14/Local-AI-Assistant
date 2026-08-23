#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  printf 'Usage: %s USER REPOSITORY_DIR LLAMA_CPP_DIR MODEL_PATH\n' "$0" >&2
  exit 2
fi

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
local_ai_user="$1"
repository_dir="$2"
llama_cpp_dir="$3"
model_path="$4"
output_dir="${source_dir}/var/systemd"

mkdir -p "${output_dir}"

sed \
  -e "s|LOCAL_AI_USER|${local_ai_user}|g" \
  -e "s|REPOSITORY_DIR|${repository_dir}|g" \
  "${source_dir}/config/services/local-ai-ui.service.example" \
  > "${output_dir}/local-ai-ui.service"

sed \
  -e "s|LOCAL_AI_USER|${local_ai_user}|g" \
  -e "s|LLAMA_CPP_DIR|${llama_cpp_dir}|g" \
  -e "s|MODEL_PATH|${model_path}|g" \
  "${source_dir}/config/services/llama-qwen.service.example" \
  > "${output_dir}/llama-qwen.service"

printf 'Rendered units in %s\n' "${output_dir}"
printf 'Review them before installing into /etc/systemd/system.\n'
