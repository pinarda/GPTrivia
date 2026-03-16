#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "${SCRIPT_DIR}"
git config core.hooksPath .githooks

chmod +x .githooks/post-merge update_server.sh

echo "Repo hooks installed."
echo "Git will now use ${SCRIPT_DIR}/.githooks"
echo "For push-to-deploy instead, run ${SCRIPT_DIR}/install_post_receive_deploy.sh on the server."
