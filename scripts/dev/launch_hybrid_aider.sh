#!/bin/bash
set -e

# Load environment variables from .env if it exists
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
fi

# Ensure keys are set
if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "Error: DEEPSEEK_API_KEY is not set."
    echo "Please set it in your .env file or environment."
    exit 1
fi

if [ -z "$MINIMAX_API_KEY" ]; then
    echo "Error: MINIMAX_API_KEY is not set."
    echo "Please set it in your .env file or environment."
    exit 1
fi

# 1. Set DeepSeek Key for the Architect (R1)
# Already exported from .env, but ensuring it's available
export DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY

# 2. Set MiniMax Key for the Editor (M2.5)
# We map this to OPENAI_API_KEY to trick Aider into using the MiniMax API via the OpenAI client
export OPENAI_API_KEY=$MINIMAX_API_KEY
export OPENAI_API_BASE=https://api.minimax.chat/v1

echo "Launching Aider with DeepSeek R1 (Architect) + MiniMax 2.5 (Editor)..."

# 3. Launch Aider
aider \
  --architect deepseek/deepseek-reasoner \
  --model openai/MiniMax-M2.5 \
  --editor-model openai/MiniMax-M2.5 \
  --yes-always  # Optional: Approves read-only suggestions automatically
