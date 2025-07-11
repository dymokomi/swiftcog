#!/bin/bash

# SwiftCog Python Server Startup Script
# This script starts the Ray cluster and then runs the server with uvicorn

echo "🚀 Starting SwiftCog Python Server..."
echo "======================================"

# Check if OPENAI_API_KEY is set
if [[ -z "${OPENAI_API_KEY}" ]]; then
    echo "❌ Error: OPENAI_API_KEY environment variable not set"
    echo "Please set your OpenAI API key:"
    echo "export OPENAI_API_KEY='your-api-key-here'"
    exit 1
fi

# Navigate to server directory
cd "$(dirname "$0")"

echo "⚡ Starting Ray cluster..."
ray start --head --port=6379 --dashboard-port=8265

echo "🌐 Starting uvicorn server..."
uvicorn app:app --host 127.0.0.1 --port 8000 --reload

echo "🛑 Server stopped. Shutting down Ray cluster..."
ray stop

echo "✅ Shutdown complete!" 