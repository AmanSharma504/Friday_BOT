#!/usr/bin/env bash

# Friday Telegram Bot Runner Script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================="
echo "🤖 Starting Friday AI Telegram Bot..."
echo "=================================================="

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment .venv..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Check if required packages are installed
python -c "import telegram, dotenv, edge_tts" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing required dependencies from requirements.txt..."
    pip install -r requirements.txt
fi

# Run the bot
python bot.py
