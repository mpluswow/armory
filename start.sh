#!/usr/bin/env bash
# AzerothCore Armory — launcher + first-run setup
# Designed for Debian/Ubuntu. Installs ALL dependencies automatically.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
TOOLS_DIR="$ROOT/tools"
BACKEND_VENV="$BACKEND_DIR/venv"
TOOLS_VENV="$TOOLS_DIR/venv"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
LOG_DIR="$ROOT/logs"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

mkdir -p "$LOG_DIR"

# ── Helpers ───────────────────────────────────────────────────────────────────
_log()  { echo -e "${CYAN}  [•] $*${NC}"; }
_ok()   { echo -e "${GREEN}  [✓] $*${NC}"; }
_warn() { echo -e "${YELLOW}  [!] $*${NC}"; }
_err()  { echo -e "\n${RED}  [✗] $*${NC}\n" >&2; exit 1; }

cleanup() {
    echo ""
    _warn "Shutting down..."
    [[ -n "${BACKEND_PID:-}"  ]] && kill "$BACKEND_PID"  2>/dev/null && _log "Backend stopped"
    [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null && _log "Frontend stopped"
    wait 2>/dev/null
    _ok "Done."
    exit 0
}
trap cleanup SIGINT SIGTERM

# ── Sudo helper ───────────────────────────────────────────────────────────────
# Called once before any apt/sudo work to make sure credentials are cached.
_SUDO_READY=false
_ensure_sudo() {
    $_SUDO_READY && return 0
    if ! command -v sudo &>/dev/null; then
        _err "sudo not found. Please run as root or install sudo."
    fi
    if ! sudo -n true 2>/dev/null; then
        echo -e "${YELLOW}  Sudo password needed to install system packages:${NC}"
        sudo true || _err "Could not get sudo access."
    fi
    _SUDO_READY=true
}

# ── apt install — only for Debian/Ubuntu ─────────────────────────────────────
_APT_UPDATED=false
_apt() {
    command -v apt-get &>/dev/null || {
        _warn "Not a Debian/Ubuntu system — skipping apt install of: $*"
        return 0
    }
    _ensure_sudo
    if ! $_APT_UPDATED; then
        _log "Updating apt package lists..."
        sudo apt-get update -qq
        _APT_UPDATED=true
    fi
    sudo apt-get install -y -qq "$@" || _err "apt-get install failed for: $*"
}

# ─────────────────────────────────────────────────────────────────────────────
echo -e "${CYAN}====================================${NC}"
echo -e "${CYAN}  AzerothCore Armory Launcher       ${NC}"
echo -e "${CYAN}====================================${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Python
# ─────────────────────────────────────────────────────────────────────────────
echo -e "${CYAN}── [1/5] Python ────────────────────${NC}"

if ! command -v python3 &>/dev/null; then
    _log "Installing python3..."
    _apt python3
fi

if ! python3 -m venv --help &>/dev/null 2>&1; then
    _log "Installing python3-venv..."
    _apt python3-venv
fi

# python3-dev provides headers needed if any package must be compiled from source
if ! dpkg -l python3-dev 2>/dev/null | grep -q "^ii"; then
    _log "Installing python3-dev (C extension headers)..."
    _apt python3-dev
fi

_ok "Python $(python3 --version | cut -d' ' -f2) ready"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Build tools (needed for StormLib and any native pip packages)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}── [2/5] Build tools ───────────────${NC}"

_NEED_BUILD=false
command -v gcc   &>/dev/null || _NEED_BUILD=true
command -v cmake &>/dev/null || _NEED_BUILD=true
command -v git   &>/dev/null || _NEED_BUILD=true
command -v curl  &>/dev/null || _NEED_BUILD=true
command -v lsof  &>/dev/null || _NEED_BUILD=true

if $_NEED_BUILD; then
    _log "Installing build tools..."
    _PKGS=()
    command -v gcc   &>/dev/null || _PKGS+=(build-essential)
    command -v cmake &>/dev/null || _PKGS+=(cmake)
    command -v git   &>/dev/null || _PKGS+=(git)
    command -v curl  &>/dev/null || _PKGS+=(curl)
    command -v lsof  &>/dev/null || _PKGS+=(lsof)
    _apt "${_PKGS[@]}"
fi

_ok "gcc $(gcc --version | head -1 | grep -oP '\d+\.\d+\.\d+' | head -1), cmake $(cmake --version | head -1 | grep -oP '\d+\.\d+\.\d+'), git $(git --version | grep -oP '\d+\.\d+\.\d+')"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Node.js (v18+ required by Vite)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}── [3/5] Node.js ───────────────────${NC}"

NODE_MIN=18
_node_ver=0
if command -v node &>/dev/null; then
    _node_ver=$(node --version 2>/dev/null | sed 's/v//' | cut -d. -f1 || echo 0)
fi

if [[ "${_node_ver}" -lt "$NODE_MIN" ]] 2>/dev/null; then
    if [[ "${_node_ver}" -gt 0 ]]; then
        _warn "Node.js $(node --version) is too old (need v${NODE_MIN}+). Installing v20 LTS via NodeSource..."
    else
        _log "Node.js not found. Installing v20 LTS via NodeSource..."
    fi

    if command -v apt-get &>/dev/null; then
        _ensure_sudo
        # NodeSource script adds the repo and runs apt-get update internally
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - > /dev/null 2>&1 \
            || _err "Failed to add NodeSource repo. Check internet and try again, or install Node.js v${NODE_MIN}+ manually: https://nodejs.org"
        sudo apt-get install -y -qq nodejs \
            || _err "Failed to install nodejs from NodeSource."
    else
        _err "Node.js v${NODE_MIN}+ is required. Install from https://nodejs.org then re-run this script."
    fi
fi

_ok "Node.js $(node --version) / npm $(npm --version)"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — libstorm.so  (StormLib — reads WoW MPQ archives)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}── [4/5] StormLib ──────────────────${NC}"

_storm_lib="$TOOLS_DIR/libstorm.so"

_build_libstorm() {
    _log "Building StormLib from source (~1–2 min)..."

    # Install StormLib's link-time dependencies
    _log "Installing StormLib build deps (zlib, bzip2)..."
    _apt zlib1g-dev libbz2-dev

    local tmp
    tmp="$(mktemp -d)"
    # shellcheck disable=SC2064
    trap "rm -rf '$tmp'" RETURN

    _log "Cloning StormLib repository..."
    git clone --depth=1 -q https://github.com/ladislav-zezula/StormLib.git "$tmp/src" \
        || _err "Failed to clone StormLib. Check your internet connection."

    _log "Configuring (cmake)..."
    cmake -S "$tmp/src" -B "$tmp/build" \
        -DBUILD_SHARED_LIBS=ON \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
        > "$tmp/cmake.log" 2>&1 \
        || { echo ""; cat "$tmp/cmake.log"; _err "StormLib cmake configure failed (see output above)."; }

    _log "Compiling (this may take a minute)..."
    cmake --build "$tmp/build" --parallel "$(nproc 2>/dev/null || echo 2)" \
        > "$tmp/build.log" 2>&1 \
        || { echo ""; cat "$tmp/build.log"; _err "StormLib compilation failed (see output above)."; }

    local so
    so=$(find "$tmp/build" -name "libstorm*.so*" ! -type l | head -1)
    [[ -z "$so" ]] && _err "StormLib compiled but no .so file was produced. Check $tmp/build."

    cp "$so" "$_storm_lib"
    _ok "libstorm.so built and installed"
}

if [[ ! -f "$_storm_lib" ]]; then
    _warn "libstorm.so not found — building from source..."
    _build_libstorm
elif ! python3 -c "import ctypes; ctypes.CDLL('$_storm_lib')" 2>/dev/null; then
    _warn "libstorm.so cannot be loaded (wrong arch or missing deps) — rebuilding..."
    _build_libstorm
else
    _ok "libstorm.so OK  ($(file "$_storm_lib" | grep -oP 'ELF \S+ \S+' || echo 'native'))"
fi

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Python venvs + npm
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}── [5/5] Application dependencies ─${NC}"

# ── Tools venv ────────────────────────────────────────────────────────────────
if [[ ! -d "$TOOLS_VENV" ]]; then
    _log "Creating tools/venv..."
    python3 -m venv "$TOOLS_VENV" || _err "Failed to create tools venv."
fi

if ! "$TOOLS_VENV/bin/python" -c "import PIL, numpy, pygltflib" 2>/dev/null; then
    _log "Installing tools dependencies (Pillow, numpy, pygltflib)..."
    # Pillow may build from source on some setups — provide its native deps
    if command -v apt-get &>/dev/null; then
        _apt libjpeg-dev libpng-dev zlib1g-dev
    fi
    "$TOOLS_VENV/bin/pip" install --quiet -r "$TOOLS_DIR/requirements.txt" \
        || _err "Failed to install tools dependencies. See pip output above."
    _ok "Tools dependencies installed"
else
    _ok "Tools dependencies OK"
fi

# ── Backend venv ──────────────────────────────────────────────────────────────
if [[ ! -d "$BACKEND_VENV" ]]; then
    _log "Creating backend/venv..."
    python3 -m venv "$BACKEND_VENV" || _err "Failed to create backend venv."
fi

if ! "$BACKEND_VENV/bin/python" -c "import fastapi" 2>/dev/null; then
    _log "Installing backend dependencies (FastAPI, uvicorn, aiomysql...)..."
    "$BACKEND_VENV/bin/pip" install --quiet -r "$BACKEND_DIR/requirements.txt" \
        || _err "Failed to install backend dependencies. See pip output above."
    _ok "Backend dependencies installed"
else
    _ok "Backend dependencies OK"
fi

# ── Frontend (npm) ────────────────────────────────────────────────────────────
if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    _log "Installing frontend dependencies (npm install)..."
    (cd "$FRONTEND_DIR" && npm install --silent) \
        || _err "npm install failed. See output above."
    _ok "Frontend dependencies installed"
else
    _ok "Frontend node_modules OK"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Pre-flight checks
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}── Pre-flight ──────────────────────${NC}"

if [[ ! -f "$ROOT/.env" ]]; then
    _err ".env not found.\n  Copy the example and fill in your AzerothCore DB credentials:\n  cp $ROOT/.env.example $ROOT/.env"
fi
_ok ".env found"

if [[ ! -f "$FRONTEND_DIR/public/models/manifest.json" ]]; then
    echo ""
    _warn "No extracted character models found."
    echo -e "  The 3D viewer needs models extracted from your WoW MPQ files."
    echo -e "  Run this once (Data/ must contain your MPQ archives):"
    echo ""
    echo "    $TOOLS_VENV/bin/python $TOOLS_DIR/extract_models.py \\"
    echo "      --data-dir  $ROOT/Data \\"
    echo "      --output-dir $ROOT/frontend/public/models"
    echo ""
else
    _ok "Character models found"
fi

# Kill any leftover processes on our ports
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    pid=$(lsof -ti :"$port" 2>/dev/null || true)
    if [[ -n "$pid" ]]; then
        _warn "Port $port already in use (PID $pid) — killing"
        kill "$pid" 2>/dev/null || true
        sleep 1
    fi
done

# ─────────────────────────────────────────────────────────────────────────────
# Start servers
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}── Starting servers ────────────────${NC}"

_log "Backend  → http://127.0.0.1:${BACKEND_PORT}"
(
    cd "$BACKEND_DIR"
    "$BACKEND_VENV/bin/uvicorn" main:app \
        --host 127.0.0.1 \
        --port "$BACKEND_PORT" \
        2>&1 | tee "$LOG_DIR/backend.log"
) &
BACKEND_PID=$!

# Wait for backend to accept connections (up to 10 seconds)
for i in $(seq 1 20); do
    if curl -s -o /dev/null "http://127.0.0.1:$BACKEND_PORT/api/characters" 2>/dev/null; then
        _ok "Backend ready"
        break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        _err "Backend crashed on startup. Check logs/backend.log"
    fi
    sleep 0.5
done

_log "Frontend → http://localhost:${FRONTEND_PORT}"
(
    cd "$FRONTEND_DIR"
    npx vite --host 0.0.0.0 --port "$FRONTEND_PORT" \
        2>&1 | tee "$LOG_DIR/frontend.log"
) &
FRONTEND_PID=$!
sleep 2

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Armory is running!                        ${NC}"
echo -e "${GREEN}  Open:  http://localhost:${FRONTEND_PORT}               ${NC}"
echo -e "${GREEN}  API:   http://127.0.0.1:${BACKEND_PORT}                ${NC}"
echo -e "${GREEN}  Logs:  ${LOG_DIR}/                    ${NC}"
echo -e "${GREEN}============================================${NC}"
echo -e "${YELLOW}  Press Ctrl+C to stop                      ${NC}"
echo ""

wait
