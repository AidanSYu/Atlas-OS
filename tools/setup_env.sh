#!/bin/bash
set -e

# Create Python venv if it doesn't exist
if [ ! -d "backend/venv" ]; then
    echo "Creating virtual environment in backend/venv..."
    python -m venv backend/venv
fi

# Activate venv
source backend/venv/Scripts/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Configure pip to use Aliyun mirror
echo "Configuring pip to use Aliyun mirror..."
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# Install requirements
if [ -f "backend/requirements-dev.txt" ]; then
    echo "Installing development requirements..."
    pip install -r backend/requirements-dev.txt
fi

if [ -f "backend/requirements.txt" ]; then
    echo "Installing production requirements..."
    pip install -r backend/requirements.txt
fi

echo "Environment setup complete."
