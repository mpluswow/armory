#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
BACKEND_VENV="$BACKEND_DIR/venv"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
LOG_DIR="$ROOT/logs"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

mkdir -p "$LOG_DIR"

cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null && echo -e "  Backend (PID $BACKEND_PID) stopped"
    [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null && echo -e "  Frontend (PID $FRONTEND_PID) stopped"
    wait 2>/dev/null
    echo -e "${GREEN}Done.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# ── Preflight checks ─────────────────────────────────────────────────

echo -e "${CYAN}==============================${NC}"
echo -e "${CYAN}  AzerothCore Armory Launcher${NC}"
echo -e "${CYAN}==============================${NC}"
echo ""

# System dependencies
MISSING_DEPS=()

if ! command -v python3 &>/dev/null; then
    MISSING_DEPS+=("python3  (sudo apt install python3)")
fi

if command -v python3 &>/dev/null && ! python3 -m venv --help &>/dev/null; then
    MISSING_DEPS+=("python3-venv  (sudo apt install python3-venv)")
fi

if ! command -v node &>/dev/null; then
    MISSING_DEPS+=("node  (https://nodejs.org or: sudo apt install nodejs)")
fi

if ! command -v npm &>/dev/null; then
    MISSING_DEPS+=("npm  (sudo apt install npm)")
fi

if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
    echo -e "${RED}ERROR: Missing system dependencies:${NC}"
    for dep in "${MISSING_DEPS[@]}"; do
        echo -e "  - $dep"
    done
    exit 1
fi

# .env
if [[ ! -f "$ROOT/.env" ]]; then
    echo -e "${RED}ERROR: .env not found. Copy .env.example and fill in your DB credentials:${NC}"
    echo "  cp $ROOT/.env.example $ROOT/.env"
    exit 1
fi

# Backend venv
if [[ ! -d "$BACKEND_VENV" ]]; then
    echo -e "${YELLOW}Creating backend venv...${NC}"
    python3 -m venv "$BACKEND_VENV"
    "$BACKEND_VENV/bin/pip" install --quiet -r "$BACKEND_DIR/requirements.txt"
    echo -e "${GREEN}Backend dependencies installed.${NC}"
elif ! "$BACKEND_VENV/bin/python" -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}Installing backend dependencies...${NC}"
    "$BACKEND_VENV/bin/pip" install --quiet -r "$BACKEND_DIR/requirements.txt"
fi

# Frontend node_modules
if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    (cd "$FRONTEND_DIR" && npm install --silent)
    echo -e "${GREEN}Frontend dependencies installed.${NC}"
fi

# GLB models
if [[ ! -f "$FRONTEND_DIR/public/models/manifest.json" ]]; then
    echo -e "${YELLOW}WARNING: No extracted models found.${NC}"
    echo "  Run the extraction pipeline first:"
    echo "    python3 -m venv $ROOT/tools/venv"
    echo "    $ROOT/tools/venv/bin/pip install -r $ROOT/tools/requirements.txt"
    echo "    $ROOT/tools/venv/bin/python $ROOT/tools/extract_models.py --data-dir $ROOT/Data --output-dir $ROOT/frontend/public/models"
    echo ""
fi

# Kill anything already on our ports
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    pid=$(lsof -ti :"$port" 2>/dev/null || true)
    if [[ -n "$pid" ]]; then
        echo -e "${YELLOW}Killing existing process on port $port (PID $pid)${NC}"
        kill "$pid" 2>/dev/null || true
        sleep 1
    fi
done

# ── Start backend ────────────────────────────────────────────────────

echo -e "${CYAN}Starting backend on :${BACKEND_PORT}...${NC}"
(
    cd "$BACKEND_DIR"
    "$BACKEND_VENV/bin/uvicorn" main:app \
        --host 127.0.0.1 \
        --port "$BACKEND_PORT" \
        2>&1 | tee "$LOG_DIR/backend.log"
) &
BACKEND_PID=$!

# Wait for backend to be ready
for i in $(seq 1 20); do
    if curl -s -o /dev/null "http://127.0.0.1:$BACKEND_PORT/api/characters" 2>/dev/null; then
        echo -e "${GREEN}  Backend ready.${NC}"
        break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo -e "${RED}  Backend failed to start. Check logs/backend.log${NC}"
        exit 1
    fi
    sleep 0.5
done

# ── Start frontend ───────────────────────────────────────────────────

echo -e "${CYAN}Starting frontend on :${FRONTEND_PORT}...${NC}"
(
    cd "$FRONTEND_DIR"
    npx vite --host 0.0.0.0 --port "$FRONTEND_PORT" \
        2>&1 | tee "$LOG_DIR/frontend.log"
) &
FRONTEND_PID=$!
sleep 2

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Armory is running!${NC}"
echo -e "${GREEN}  Frontend:  http://localhost:${FRONTEND_PORT}${NC}"
echo -e "${GREEN}  Backend:   http://127.0.0.1:${BACKEND_PORT}${NC}"
echo -e "${GREEN}  Logs:      ${LOG_DIR}/${NC}"
echo -e "${GREEN}============================================${NC}"
echo -e "${YELLOW}  Press Ctrl+C to stop both servers${NC}"
echo ""

wait
