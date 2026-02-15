#!/bin/bash
set -e

# Set PYTHONPATH to include the backend directory
export PYTHONPATH="./backend"

echo "Running tests with pytest..."
pytest backend/tests -v

if [ $? -eq 0 ]; then
    echo "Tests passed!"
    exit 0
else
    echo "Tests failed!"
    exit 1
fi
