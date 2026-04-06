#!/bin/bash

echo "Starting Schism..."

# Start backend
cd "$(dirname "$0")/../api"
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# Start frontend
cd ../../frontend
npm run dev &
FRONTEND_PID=$!

echo "Backend running at http://localhost:8000"
echo "Frontend running at http://localhost:3000"
echo "Press Ctrl+C to stop both"

# Kill both on Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Schism stopped.'" EXIT

# Wait for both processes
wait
