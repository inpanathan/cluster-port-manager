#!/bin/bash
# Start vLLM server for local GPU inference.
#
# Usage:
#   bash scripts/start_vllm.sh                           # default model
#   bash scripts/start_vllm.sh Qwen/Qwen2.5-7B-Instruct  # custom model
#   bash scripts/start_vllm.sh stop                       # stop running server
#
# Environment variables:
#   LLM__VLLM_MODEL          Model to serve (default: Qwen/Qwen2.5-14B-Instruct)
#   VLLM_PORT                Port to bind (default: 8001)
#   VLLM_GPU_MEMORY_UTIL     GPU memory utilization 0-1 (default: 0.90)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load .env if present
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
fi

MODEL="${1:-${LLM__VLLM_MODEL:-Qwen/Qwen2.5-14B-Instruct}}"
PORT="${VLLM_PORT:-8001}"
GPU_MEM="${VLLM_GPU_MEMORY_UTIL:-0.90}"

# Handle stop command
if [ "$MODEL" = "stop" ]; then
    echo "Stopping vLLM server on port $PORT..."
    PIDS=$(lsof -ti:"$PORT" 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo "$PIDS" | xargs kill 2>/dev/null || true
        echo "Stopped processes on port $PORT"
    else
        echo "No process found on port $PORT"
    fi
    exit 0
fi

# Kill existing processes on port (REQ-RUN-009)
EXISTING_PIDS=$(lsof -ti:"$PORT" 2>/dev/null || true)
if [ -n "$EXISTING_PIDS" ]; then
    echo "Killing existing processes on port $PORT..."
    echo "$EXISTING_PIDS" | xargs kill 2>/dev/null || true
    sleep 2
fi

echo "Starting vLLM server..."
echo "  Model: $MODEL"
echo "  Port:  $PORT"
echo "  GPU memory utilization: $GPU_MEM"
echo ""

exec uv run python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --port "$PORT" \
    --gpu-memory-utilization "$GPU_MEM" \
    --trust-remote-code
