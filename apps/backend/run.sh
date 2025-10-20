#!/bin/bash

# SynthAI Backend Startup Script
# Handles conda/venv activation automatically

echo "Starting SynthAI Backend..."

# Check if we're in conda and deactivate it
if [[ ! -z "$CONDA_DEFAULT_ENV" ]]; then
    echo "Conda environment detected, deactivating..."
    conda deactivate 2>/dev/null || true
fi

# Activate venv
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Check if dependencies are installed
if ! python -c "import anthropic" 2>/dev/null && ! python -c "import openai" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Start uvicorn
echo " Starting FastAPI server on http://localhost:8000"
uvicorn synthai_backend.main:app --reload --port 8000
