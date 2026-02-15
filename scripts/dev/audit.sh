#!/bin/bash
set -e

echo "Running security audit with bandit..."
bandit -r src/backend/app --exclude src/frontend,src/tauri

echo "Running type check with mypy..."
mypy src/backend/app --exclude src/frontend --exclude src/tauri

echo "Audit complete."
