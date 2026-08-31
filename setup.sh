#!/usr/bin/env bash
# Course environment setup. Run once. Takes 3-6 minutes.
#   bash setup.sh
set -euo pipefail

PY=${PYTHON:-python3}
echo "==> using $($PY --version)"

case "$($PY -c 'import sys; print(sys.version_info[:2] >= (3,11))')" in
  True) ;;
  *) echo "ERROR: need Python 3.11+. Install it, then re-run: PYTHON=python3.12 bash setup.sh"; exit 1;;
esac

$PY -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo
  echo "==> Created .env — open it and paste your keys before continuing."
fi

echo
echo "==> Done. Now run:"
echo "      source .venv/bin/activate"
echo "      python check_env.py"
