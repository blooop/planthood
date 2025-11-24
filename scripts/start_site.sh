#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SITE_DIR="${PROJECT_ROOT}/site"

PORT_VALUE="${PORT:-4000}"
OUTPUT_DIR="${SITE_DIR}/out"

if [[ ! -d "${OUTPUT_DIR}" ]]; then
  echo "Static export not found at ${OUTPUT_DIR}."
  echo "Run 'pixi run build-site' to generate the site before starting the server."
  exit 1
fi

echo "Serving static export from ${OUTPUT_DIR} on port ${PORT_VALUE}"
cd "${SITE_DIR}"
npx serve -s -l "${PORT_VALUE}" "${OUTPUT_DIR}"
