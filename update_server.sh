#!/usr/bin/env bash

set -euo pipefail

REPO_DIR="${HOME}/git/GPTrivia"
CONDA_SH="${HOME}/miniconda3/etc/profile.d/conda.sh"
ENV_NAME="GPTrivia"

if [[ ! -d "${REPO_DIR}" ]]; then
  echo "Repo directory not found: ${REPO_DIR}" >&2
  exit 1
fi

if [[ -f "${CONDA_SH}" ]]; then
  # shellcheck disable=SC1090
  source "${CONDA_SH}"
elif command -v conda >/dev/null 2>&1; then
  eval "$(conda shell.bash hook)"
else
  echo "Conda not found. Expected ${CONDA_SH} or a working 'conda' command." >&2
  exit 1
fi

cd "${REPO_DIR}"
conda activate "${ENV_NAME}"

git pull --ff-only
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart daphne

echo "Server update complete."
