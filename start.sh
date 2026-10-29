#!/bin/bash
# ==============================================================================
# SevaFund India — Full Stack Launcher (Backend + Angular Frontend)
# ==============================================================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/.local/node/bin:$PATH"

echo "=========================================================="
echo "🇮🇳  Starting SevaFund India (Backend + Angular Frontend)"
echo "=========================================================="

# Trap to kill both background processes on Ctrl+C
cleanup() {
    echo ""
    echo "🛑 Shutting down SevaFund India services..."
    kill $(jobs -p) 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 1. Start FastAPI Backend
echo "🚀 [1/2] Starting FastAPI Backend on http://localhost:8000..."
cd "$PROJECT_ROOT"
"$PROJECT_ROOT/.venv/bin/python" run.py &
BACKEND_PID=$!

# Wait briefly for backend to initialize
sleep 2

# 2. Start Angular Frontend
echo "✨ [2/2] Starting Angular Frontend on http://localhost:4200..."
cd "$PROJECT_ROOT/frontend"
npm start &
FRONTEND_PID=$!

echo ""
echo "=========================================================="
echo "✅ SevaFund India is up and running!"
echo "   🌐 Frontend: http://localhost:4200"
echo "   📖 API Docs: http://localhost:8000/docs"
echo "Press Ctrl+C to stop both servers."
echo "=========================================================="

wait
