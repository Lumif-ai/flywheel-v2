#!/bin/bash
# Start all services needed for Flywheel dev + public sharing
# Usage: ./start-dev.sh

set -e

echo "Starting Flywheel dev stack..."

# 1. Backend
echo "[1/3] Starting backend (port 8000)..."
cd /Users/sharan/Projects/flywheel-v2/backend
uv run uvicorn flywheel.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/flywheel-backend.log 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# 2. Frontend
echo "[2/3] Starting frontend (port 5173)..."
cd /Users/sharan/Projects/flywheel-v2/frontend
npm exec vite -- --host 0.0.0.0 > /tmp/flywheel-frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

# 3. ngrok tunnel
echo "[3/3] Starting ngrok tunnel..."
ngrok http 5173 --url=methodical-jessenia-unannotated.ngrok-free.dev > /tmp/flywheel-ngrok.log 2>&1 &
NGROK_PID=$!
echo "  ngrok PID: $NGROK_PID"

sleep 3

echo ""
echo "================================================"
echo "  Flywheel dev stack running!"
echo "================================================"
echo "  Local:  http://localhost:5173"
echo "  Public: https://methodical-jessenia-unannotated.ngrok-free.dev"
echo ""
echo "  Logs:"
echo "    Backend:  tail -f /tmp/flywheel-backend.log"
echo "    Frontend: tail -f /tmp/flywheel-frontend.log"
echo "    ngrok:    tail -f /tmp/flywheel-ngrok.log"
echo ""
echo "  Stop all: kill $BACKEND_PID $FRONTEND_PID $NGROK_PID"
echo "================================================"

# Save PIDs for stop script
echo "$BACKEND_PID $FRONTEND_PID $NGROK_PID" > /tmp/flywheel-pids

# Wait for any to exit
wait
