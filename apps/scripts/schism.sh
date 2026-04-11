#!/bin/bash

set -e

echo "Starting Schism..."

# Kill any existing processes on ports 8000 and 3000
echo "Checking for existing processes..."
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$SCRIPT_DIR/../api"
FRONTEND_DIR="$SCRIPT_DIR/../../frontend"

echo "API directory: $API_DIR"
echo "Frontend directory: $FRONTEND_DIR"

# Verify frontend directory exists
if [ ! -d "$FRONTEND_DIR" ]; then
    echo "ERROR: Frontend directory not found at $FRONTEND_DIR"
    exit 1
fi

# Verify npm is available
if ! command -v npm &> /dev/null; then
    echo "ERROR: npm not found. Please install Node.js"
    exit 1
fi

# Start backend
echo "Starting backend..."
cd "$API_DIR"
export SCHISM_API_PROXY_TARGET=http://localhost:8000
uvicorn app.main:app --reload --port 8000 > /tmp/schism-backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to start
sleep 3

# Check if backend started
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "ERROR: Backend failed to start. Check /tmp/schism-backend.log"
    cat /tmp/schism-backend.log
    exit 1
fi

echo "Backend started successfully on port 8000"

# Start frontend
echo "Starting frontend..."
cd "$FRONTEND_DIR"
export SCHISM_API_PROXY_TARGET=http://localhost:8000
npm run dev > /tmp/schism-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

# Wait for frontend to start
sleep 5

# Check if frontend started
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "ERROR: Frontend failed to start. Check /tmp/schism-frontend.log"
    cat /tmp/schism-frontend.log
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo "Frontend started successfully on port 3000"

echo ""
echo "========================================"
echo "  Backend running at http://localhost:8000"
echo "  Frontend running at http://localhost:3000"
echo "========================================"
echo ""
echo "  Access the app at: http://localhost:3000"
echo ""
echo "  Press Ctrl+C to stop both"
echo ""
echo "  Logs:"
echo "    Backend:  tail -f /tmp/schism-backend.log"
echo "    Frontend: tail -f /tmp/schism-frontend.log"
echo ""

# Kill both on exit
cleanup() {
    echo ""
    echo "Shutting down Schism..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
    lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
    echo "Schism stopped."
    exit 0
}
trap cleanup INT EXIT

# Show logs in real-time
tail -f /tmp/schism-backend.log /tmp/schism-frontend.log 2>/dev/null || wait
