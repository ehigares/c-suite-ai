#!/bin/bash

# LLM Council - Start script
# Works on macOS, Linux, and Git Bash on Windows

echo "Starting LLM Council..."
echo ""

# Start backend
echo "Starting backend on http://localhost:8001..."
uv run python -m backend.main &
BACKEND_PID=$!

# Poll /api/health until the backend is ready (max 30 seconds)
echo "Waiting for backend to be ready..."
TIMEOUT=30
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    # Use curl if available, fall back to python
    if command -v curl >/dev/null 2>&1; then
        if curl -s -o /dev/null -w "" http://localhost:8001/api/health 2>/dev/null; then
            break
        fi
    else
        if python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/api/health')" 2>/dev/null; then
            break
        fi
    fi
    sleep 0.5
    ELAPSED=$((ELAPSED + 1))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo ""
    echo "ERROR: Backend did not start within ${TIMEOUT} seconds."
    echo "Check the output above for errors."
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo "Backend is ready."

# Start frontend
echo "Starting frontend on http://localhost:5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "LLM Council is running!"
echo "  Backend:  http://localhost:8001"
echo "  Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
