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

# Handle cleanup arguments
CLEANUP_MODE=""
for arg in "$@"; do
    case $arg in
        --forget)
            CLEANUP_MODE="forget"
            shift
            ;;
        --clean)
            CLEANUP_MODE="clean"
            shift
            ;;
        *)
            # Unknown option
            echo "❌ Unknown option: $arg"
            echo "Usage: ./start_server.sh [--forget] [--clean]"
            echo "  --forget: Delete all memory and logs before starting"
            echo "  --clean:  Remove session concepts before starting"
            exit 1
            ;;
    esac
done

# Run cleanup if specified
if [[ -n "$CLEANUP_MODE" ]]; then
    echo "🧹 Running cleanup operation: $CLEANUP_MODE"
    python cleanup.py --$CLEANUP_MODE
    if [[ $? -ne 0 ]]; then
        echo "❌ Cleanup failed, aborting server start"
        exit 1
    fi
    echo ""
fi

echo "⚡ Starting Ray cluster..."
ray start --head --port=6379 --dashboard-port=8265

echo "🌐 Starting uvicorn server..."
uvicorn app:app --host 127.0.0.1 --port 8000 --reload

echo "🛑 Server stopped. Shutting down Ray cluster..."
ray stop

echo "✅ Shutdown complete!" 