#!/bin/bash

# Nexus AI - Frontend/Backend One-Click Launcher (Mac/Linux) - Enhanced Version

echo ""
echo "========================================================"
echo "    Nexus AI - Frontend/Backend One-Click Launcher (Enhanced)"
echo "========================================================"
echo ""
echo "  Startup Mode:"
echo "    [1] Development Mode   - Hot reload for both (for debugging)"
echo "    [2] Stable Mode        - No hot reload for backend (for eval/training)"
echo "    [3] Backend Only       - Start backend service only"
echo "    [4] Frontend Only      - Start frontend service only"
echo ""
read -p "Select startup mode [1/2/3/4] (default=2): " MODE
MODE=${MODE:-2}

# Get script directory
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo ""
echo "Project directory: $PROJECT_DIR"
echo ""

# Check if backend directory exists
if [ ! -d "$PROJECT_DIR/backend" ]; then
    echo "[Error] Cannot find backend directory!"
    echo "Please ensure the script is in the project root directory"
    exit 1
fi

# ========== Backend Preparation ==========
start_backend() {
    echo "[Backend] Preparing..."
    cd "$PROJECT_DIR/backend"

    if [ ! -d "node_modules" ]; then
        echo "[Backend] Installing dependencies (first run may take a while)..."
        npm install
        if [ $? -ne 0 ]; then
            echo "[Error] Backend dependency installation failed!"
            exit 1
        fi
        echo "[Backend] Dependencies installed"
    fi

    if [ ! -d "node_modules/.prisma" ]; then
        echo "[Backend] Generating Prisma Client..."
        npx prisma generate
    fi

    if [ ! -f "prisma/dev.db" ]; then
        echo "[Backend] Initializing database..."
        npx prisma db push
        echo "[Backend] Inserting seed data..."
        npx tsx src/db/seed.ts
    fi

    # Start backend
    if [ "$MODE" == "2" ]; then
        echo "[Backend] Using stable mode (no hot reload, suitable for long tasks)"
        START_CMD="npm run stable"
    else
        echo "[Backend] Using development mode (hot reload)"
        START_CMD="npm run dev"
    fi

    if [[ "$OSTYPE" == "darwin"* ]]; then
        osascript -e "tell app \"Terminal\" to do script \"cd '$PROJECT_DIR/backend' && echo 'Backend service starting...' && $START_CMD\""
    else
        if command -v gnome-terminal &> /dev/null; then
            gnome-terminal -- bash -c "cd '$PROJECT_DIR/backend' && echo 'Backend service starting...' && $START_CMD; exec bash"
        elif command -v xterm &> /dev/null; then
            xterm -e "cd '$PROJECT_DIR/backend' && echo 'Backend service starting...' && $START_CMD; exec bash" &
        else
            nohup $START_CMD > backend.log 2>&1 &
            echo "[Backend] Started in background mode, logs output to backend.log"
        fi
    fi

    # Wait for backend to start
    echo "[Backend] Waiting for service to start..."
    sleep 3

    # Check if backend started successfully
    if command -v curl &> /dev/null; then
        if ! curl -s http://localhost:3001/health > /dev/null 2>&1; then
            echo "[Backend] Service still starting, please wait..."
            sleep 5
        fi
    fi
}

# ========== Frontend Preparation ==========
start_frontend() {
    echo "[Frontend] Preparing..."
    cd "$PROJECT_DIR"

    if [ ! -d "node_modules" ]; then
        echo "[Frontend] Installing dependencies (first run may take a while)..."
        npm install
        if [ $? -ne 0 ]; then
            echo "[Error] Frontend dependency installation failed!"
            exit 1
        fi
        echo "[Frontend] Dependencies installed"
    fi

    echo "[Frontend] Starting development server..."

    if [[ "$OSTYPE" == "darwin"* ]]; then
        osascript -e "tell app \"Terminal\" to do script \"cd '$PROJECT_DIR' && npm run dev -- --open\""
    else
        if command -v gnome-terminal &> /dev/null; then
            gnome-terminal -- bash -c "cd '$PROJECT_DIR' && npm run dev -- --open; exec bash"
        elif command -v xterm &> /dev/null; then
            xterm -e "cd '$PROJECT_DIR' && npm run dev -- --open; exec bash" &
        else
            npm run dev -- --open &
        fi
    fi
}

# ========== Start based on mode ==========
case $MODE in
    1|2)
        start_backend
        start_frontend
        ;;
    3)
        start_backend
        ;;
    4)
        start_frontend
        ;;
    *)
        echo "[Error] Invalid mode selection"
        exit 1
        ;;
esac

echo ""
echo "========================================================"
echo "  Startup Complete!"
echo "========================================================"
echo ""
if [ "$MODE" != "4" ]; then
    echo "  Backend API:     http://localhost:3001"
    echo "  Swagger Docs:    http://localhost:3001/docs"
    echo "  Health Check:    http://localhost:3001/health"
fi
if [ "$MODE" != "3" ]; then
    echo "  Frontend:        Will open automatically in browser"
fi
echo ""
if [ "$MODE" == "2" ]; then
    echo "  [Stable Mode] Backend will not restart on file changes"
    echo "  Suitable for long-running evaluation or training tasks"
fi
echo ""
echo "  Run ./stop.sh to stop all services"
echo ""
