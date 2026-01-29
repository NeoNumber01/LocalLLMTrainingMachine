#!/bin/bash

# Nexus AI - Service Stopper (Mac/Linux)

echo ""
echo "========================================================"
echo "    Nexus AI - Service Stopper"
echo "========================================================"
echo ""

# Get script directory
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Stop backend processes
echo "[*] Stopping backend service..."
# Find and kill processes running on port 3001
if command -v lsof &> /dev/null; then
    BACKEND_PID=$(lsof -ti :3001)
    if [ -n "$BACKEND_PID" ]; then
        kill -9 $BACKEND_PID 2>/dev/null
        echo "    Backend service stopped (PID: $BACKEND_PID)"
    else
        echo "    No running backend service found"
    fi
else
    # Use fuser as fallback
    if command -v fuser &> /dev/null; then
        fuser -k 3001/tcp 2>/dev/null
        echo "    Backend service stopped"
    else
        echo "    Cannot detect backend service (requires lsof or fuser)"
    fi
fi

# Stop frontend processes
echo "[*] Stopping frontend service..."
# Check common frontend ports
for PORT in 3000 5173 5174 5175; do
    if command -v lsof &> /dev/null; then
        FRONTEND_PID=$(lsof -ti :$PORT)
        if [ -n "$FRONTEND_PID" ]; then
            kill -9 $FRONTEND_PID 2>/dev/null
            echo "    Frontend service stopped (Port: $PORT, PID: $FRONTEND_PID)"
        fi
    else
        if command -v fuser &> /dev/null; then
            fuser -k $PORT/tcp 2>/dev/null
        fi
    fi
done

# Stop possible Python training/evaluation processes
echo "[*] Checking training/evaluation processes..."
pkill -f "python.*train.py" 2>/dev/null && echo "    Training process stopped" || true
pkill -f "python.*eval.py" 2>/dev/null && echo "    Evaluation process stopped" || true

echo ""
echo "========================================================"
echo "  All services stopped"
echo "========================================================"
echo ""
