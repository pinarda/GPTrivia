#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${SCRIPT_DIR}"
CONDA_SH="${HOME}/miniconda3/etc/profile.d/conda.sh"
ENV_NAME="GPTrivia"
SKIP_GIT_PULL="${SKIP_GIT_PULL:-0}"
DAPHNE_INSTANCE_PORTS="${DAPHNE_INSTANCE_PORTS:-8000 8001}"

if [[ ! -f "${REPO_DIR}/manage.py" ]]; then
  REPO_DIR="${HOME}/git/GPTrivia"
fi

if [[ ! -d "${REPO_DIR}" ]]; then
  echo "Repo directory not found: ${REPO_DIR}" >&2
  exit 1
fi

STATIC_RELEASES_DIR="${REPO_DIR}/.static-releases"
STATIC_RELEASE_ID="release-$(date -u +%Y%m%d%H%M%S)-$$"
STATIC_RELEASE_DIR="${STATIC_RELEASES_DIR}/${STATIC_RELEASE_ID}"
STATIC_LINK="${REPO_DIR}/static"

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

if [[ "${SKIP_GIT_PULL}" != "1" ]]; then
  GPTRIVIA_SKIP_POST_MERGE_DEPLOY=1 git pull --ff-only
fi

python manage.py migrate

mkdir -p "${STATIC_RELEASE_DIR}"

cleanup_failed_static_release() {
  if [[ ! -L "${STATIC_LINK}" ]] || [[ "$(readlink "${STATIC_LINK}")" != "${STATIC_RELEASE_DIR}" ]]; then
    rm -rf "${STATIC_RELEASE_DIR}"
  fi
}
trap cleanup_failed_static_release EXIT

# Keep the two previous React entry bundles available for tabs that loaded before
# deployment. The HTML shell is not cached, but an already-open page can still
# request its original hashed bundle while the static release changes.
mapfile -t previous_static_releases < <(
  find "${STATIC_RELEASES_DIR}" -mindepth 1 -maxdepth 1 -type d -name 'release-*' \
    ! -path "${STATIC_RELEASE_DIR}" -print | sort -r | head -n 2
)
for previous_release in "${previous_static_releases[@]}"; do
  previous_bundle_dir="${previous_release}/scoresheet/build/static/js"
  previous_asset_manifest="${previous_release}/scoresheet/build/asset-manifest.json"
  if [[ ! -d "${previous_bundle_dir}" ]] || [[ ! -f "${previous_asset_manifest}" ]]; then
    continue
  fi

  previous_bundle_name="$(python - "${previous_asset_manifest}" <<'PY'
import json
import os
import sys

with open(sys.argv[1], encoding="utf-8") as manifest_file:
    manifest = json.load(manifest_file)
print(os.path.basename(manifest["files"]["main.js"]))
PY
)"
  mkdir -p "${STATIC_RELEASE_DIR}/scoresheet/build/static/js"
  for bundle_suffix in '' '.LICENSE.txt' '.map'; do
    previous_bundle="${previous_bundle_dir}/${previous_bundle_name}${bundle_suffix}"
    if [[ -f "${previous_bundle}" ]]; then
      cp -p "${previous_bundle}" "${STATIC_RELEASE_DIR}/scoresheet/build/static/js/"
    fi
  done
done

GPTRIVIA_STATIC_ROOT="${STATIC_RELEASE_DIR}" python manage.py collectstatic --noinput

if [[ -e "${STATIC_LINK}" && ! -L "${STATIC_LINK}" ]]; then
  mv "${STATIC_LINK}" "${STATIC_RELEASES_DIR}/legacy-${STATIC_RELEASE_ID}"
fi
ln -sfn "${STATIC_RELEASE_DIR}" "${STATIC_LINK}"

# Keep the active release and two quick rollback candidates.
mapfile -t static_releases < <(
  find "${STATIC_RELEASES_DIR}" -mindepth 1 -maxdepth 1 -type d -name 'release-*' -print | sort -r
)
for ((index = 3; index < ${#static_releases[@]}; index++)); do
  rm -rf "${static_releases[$index]}"
done

trap - EXIT

restart_daphne_services() {
  local ports=()
  local services=()
  local port

  read -r -a ports <<< "${DAPHNE_INSTANCE_PORTS}"

  if systemctl list-unit-files 'daphne@*.service' --no-legend 2>/dev/null | grep -q '^daphne@'; then
    for port in "${ports[@]}"; do
      services+=("daphne@${port}")
    done
    echo "Restarting Daphne instances: ${services[*]}"
    sudo systemctl restart "${services[@]}"
    return
  fi

  echo "Restarting legacy daphne.service"
  sudo systemctl restart daphne
}

restart_daphne_services

echo "Server update complete."
