#!/bin/zsh
set -e

cd "$(dirname "$0")"

echo "Starting Bookbinder 4..."
echo

python3 -m pip install -r requirements.txt

cd frontend
npm install
cd ..

open "http://127.0.0.1:5173" >/dev/null 2>&1 || true

python3 scripts/dev.py
