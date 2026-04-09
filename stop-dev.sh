#!/bin/bash
# Stop all Flywheel dev services
if [ -f /tmp/flywheel-pids ]; then
  read -r PIDS < /tmp/flywheel-pids
  echo "Stopping Flywheel dev stack (PIDs: $PIDS)..."
  kill $PIDS 2>/dev/null
  rm /tmp/flywheel-pids
  echo "Done."
else
  echo "No running stack found. Killing by name..."
  pkill -f "uvicorn flywheel" 2>/dev/null
  pkill -f "vite.*5173" 2>/dev/null
  pkill -f "ngrok http" 2>/dev/null
  echo "Done."
fi
