# Installation

## System Requirements

The application runs on **Linux** (Debian/Ubuntu recommended). Windows and macOS are not tested.

### Minimum System Software

| Dependency | Minimum version | Notes |
|------------|----------------|-------|
| Python | 3.8 | Must include `venv` module (`python3-venv`) |
| Node.js | 18 | Vite 7 requires Node ≥ 18. Ubuntu's default apt package is often too old — `start.sh` handles this automatically via NodeSource |
| npm | 8 | Comes with Node.js |
| gcc / g++ | any | Required to build StormLib (`build-essential`) |
| cmake | 3.x | Required to build StormLib |
| git | any | Required to clone StormLib if building from source |
| MySQL / MariaDB | 5.7 / 10.3 | An existing, running AzerothCore database |

> `start.sh` checks for all of the above and installs any that are missing automatically on Debian/Ubuntu systems using `apt-get`. You only need `sudo` access.

---

## Quick Start

This is the complete workflow for a first-time setup.

### Step 1 — Clone the repository

```bash
git clone <repo-url> armory
cd armory
```

### Step 2 — Set up the database configuration

```bash
cp .env.example .env
nano .env   # or any editor
```

Fill in your AzerothCore database credentials:

```env
DB_HOST=localhost
DB_USER=acore
DB_PASS=your_password
DB_NAME=acore_characters
WORLD_DB_NAME=acore_world
CORS_ORIGINS=http://localhost:5173
```

See [Configuration](03-configuration.md) for all available settings.

### Step 3 — Extract character models (one-time, requires MPQ files)

Your WoW 3.3.5a `Data/` folder (the one containing `.MPQ` files) must be present at `armory/Data/`.

```bash
# start.sh will create this venv for you, but for manual extraction:
python3 -m venv tools/venv
tools/venv/bin/pip install -r tools/requirements.txt

tools/venv/bin/python tools/extract_models.py \
  --data-dir ./Data \
  --output-dir ./frontend/public/models
```

This produces:
- `frontend/public/models/characters/*.glb` — 20 character models (10 races × 2 genders)
- `frontend/public/models/manifest.json` — model index
- `frontend/public/models/attachments.json` — attachment point positions

This is a one-time step. Re-run it only if you want to regenerate models.

### Step 4 — Launch

```bash
chmod +x start.sh
./start.sh
```

Open **http://localhost:5173** in your browser.

---

## What `start.sh` Does Automatically

On first run `start.sh` performs a complete setup before starting the servers. On subsequent runs it detects what is already installed and skips those steps.

### Step 1 — Python
- Checks for `python3` → installs if missing
- Checks for `python3-venv` → installs if missing
- Checks for `python3-dev` (C extension headers) → installs if missing

### Step 2 — Build tools
- Checks for `gcc` (build-essential) → installs if missing
- Checks for `cmake` → installs if missing
- Checks for `git` → installs if missing
- Checks for `curl` and `lsof` → installs if missing
- Only runs `apt-get update` once, only if something is missing

### Step 3 — Node.js
- Reads the installed Node.js version
- If < 18 or missing: adds the NodeSource repository and installs **Node.js 20 LTS**
- This handles the common situation where Ubuntu's built-in `nodejs` package is Node 12 or 14

### Step 4 — StormLib (`libstorm.so`)
- Tests whether `tools/libstorm.so` exists and loads correctly via ctypes
- If it does not load (missing, or wrong CPU architecture): **clones StormLib from GitHub, runs cmake + make, copies the result** — fully automated, no user interaction required
- Installs `zlib1g-dev` and `libbz2-dev` as build dependencies before compiling

### Step 5 — Python virtual environments
- Creates `tools/venv` if missing → installs `Pillow`, `numpy`, `pygltflib`
- Creates `backend/venv` if missing → installs `fastapi`, `uvicorn[standard]`, `aiomysql`, `pydantic-settings`, `python-dotenv`, `cachetools`
- Installs `libjpeg-dev`, `libpng-dev`, `zlib1g-dev` before Pillow in case wheels are unavailable

### Step 6 — Frontend
- Runs `npm install` in `frontend/` if `node_modules/` is absent

### Pre-flight checks
- Verifies `.env` exists — exits with instructions if not
- Warns (but does not abort) if `manifest.json` is missing (no extracted models)
- Kills any process already listening on ports 8000 or 5173

### Server startup
- Starts uvicorn backend in background, waits up to 10 seconds for it to accept connections
- Starts Vite frontend in background
- Prints URLs and waits (Ctrl+C to stop both)

---

## Manual Setup (without `start.sh`)

If you prefer to set up manually or are on a non-Debian/Ubuntu system:

### 1. Install system dependencies

**Debian/Ubuntu:**
```bash
sudo apt-get update
sudo apt-get install -y \
  python3 python3-venv python3-dev \
  build-essential cmake git \
  curl lsof \
  libjpeg-dev libpng-dev zlib1g-dev libbz2-dev
```

**Node.js 20 LTS (via NodeSource):**
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 2. Build StormLib (if `libstorm.so` doesn't load)

```bash
git clone --depth=1 https://github.com/ladislav-zezula/StormLib.git /tmp/StormLib
cmake -S /tmp/StormLib -B /tmp/StormLib/build \
  -DBUILD_SHARED_LIBS=ON \
  -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/StormLib/build --parallel $(nproc)
cp /tmp/StormLib/build/libstorm.so tools/libstorm.so
```

### 3. Tools venv

```bash
python3 -m venv tools/venv
tools/venv/bin/pip install -r tools/requirements.txt
```

### 4. Backend venv

```bash
python3 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt
```

### 5. Frontend

```bash
cd frontend && npm install && cd ..
```

### 6. Copy and edit `.env`

```bash
cp .env.example .env
# Edit .env with your database credentials
```

### 7. Extract models

```bash
tools/venv/bin/python tools/extract_models.py \
  --data-dir ./Data \
  --output-dir ./frontend/public/models
```

### 8. Start servers

Terminal 1 (backend):
```bash
cd backend
../venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

Terminal 2 (frontend):
```bash
cd frontend
npx vite --host 0.0.0.0 --port 5173
```

---

## Port Overrides

```bash
BACKEND_PORT=8080 FRONTEND_PORT=3000 ./start.sh
```

---

## Verifying the Installation

After `./start.sh` successfully starts, confirm each layer works:

```bash
# Backend is alive
curl http://127.0.0.1:8000/api/characters

# Character data endpoint
curl "http://127.0.0.1:8000/api/character?name=YourCharName"
```

Then open **http://localhost:5173** and search for a character name from your server.

---

## Log Files

Both servers write to `logs/`:

| File | Contents |
|------|----------|
| `logs/backend.log` | Uvicorn access log + Python exceptions |
| `logs/frontend.log` | Vite build output + HMR messages |

```bash
tail -f logs/backend.log    # watch backend live
tail -f logs/frontend.log   # watch frontend live
```
