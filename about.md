# AzerothCore Armory

A web-based character inspection tool for [AzerothCore](https://www.azerothcore.org/) WotLK private servers. Displays characters with their equipped gear in a 3D paper-doll layout, pulling live data from the AzerothCore MySQL database and rendering locally extracted game assets — no Wowhead viewer or external CDN required for the 3D model.

---

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Requirements](#requirements)
4. [Quick Start](#quick-start)
5. [Extraction Pipeline](#extraction-pipeline)
6. [Configuration](#configuration)
7. [Backend API](#backend-api)
8. [Project Structure](#project-structure)
9. [Troubleshooting](#troubleshooting)

---

## Features

- **Live character data** — reads directly from AzerothCore MySQL (`acore_characters` + `acore_world`)
- **3D character models** — race/gender GLB files extracted from your local MPQ archives
- **Composited skin textures** — base skin, face, facial hair, scalp, and equipped gear baked into one PNG per character
- **Per-mesh textures** — hair, extra-skin (tauren fur etc.), and cape served as separate API endpoints
- **3D item attachments** — weapons, shields, shoulders, and helms extracted on demand and placed at correct attachment points
- **Geoset visibility** — equipment controls which submeshes show or hide (hair hidden under helm, etc.)
- **Paper-doll UI** — item slots with icons, quality-color borders, stat tooltips, and character stats panel
- **Self-contained** — `./start.sh` auto-creates the Python venv and installs npm deps on first run

---

## Architecture

```
Browser
  │
  │  http://localhost:5173  (React + Vite dev server)
  │
  ▼
┌────────────────────────────────┐
│  Frontend  (React + Three.js)  │
│  frontend/                     │
│  port 5173                     │
│  /api/* → proxy → :8000        │
└───────────────┬────────────────┘
                │  HTTP (proxied /api/*)
                ▼
┌────────────────────────────────┐
│  Backend  (FastAPI + uvicorn)  │
│  backend/                      │
│  port 8000                     │
└──────┬─────────────────┬───────┘
       │ aiomysql        │ filesystem
       ▼                 ▼
┌─────────────┐   ┌─────────────────────────┐
│  AzerothCore│   │  frontend/public/models/ │
│  MySQL DB   │   │  ├── characters/*.glb    │
│             │   │  ├── attachments.json    │
│  acore_chars│   │  ├── manifest.json       │
│  acore_world│   │  └── cache/  (PNG + GLB) │
└─────────────┘   └─────────────────────────┘
                          ▲
                          │ extract once
                  ┌───────┴────────┐
                  │  tools/        │
                  │  extract_models│
                  │  gear_compositor│
                  │  (needs Data/) │
                  └────────────────┘
```

---

## Requirements

### System (must be installed manually)

| Dependency | Install |
|------------|---------|
| Python 3.8+ | `sudo apt install python3 python3-venv` |
| Node.js 18+ | `sudo apt install nodejs npm` or [nodejs.org](https://nodejs.org) |
| MySQL / MariaDB | Running AzerothCore database |

### Python — backend (`backend/requirements.txt`)

```
fastapi
uvicorn[standard]
aiomysql
pydantic-settings
python-dotenv
cachetools
```

### Python — tools (`tools/requirements.txt`)

```
Pillow
numpy
pygltflib
```

### Node.js — frontend (`frontend/package.json`)

Key packages: `react`, `three`, `@react-three/fiber`, `@react-three/drei`, `vite`

---

## Quick Start

### 1. Copy and fill in `.env`

```bash
cp .env.example .env
# Edit .env with your AzerothCore database credentials
```

### 2. Run the extraction pipeline (once, needs your MPQ files in `Data/`)

```bash
python3 -m venv tools/venv
tools/venv/bin/pip install -r tools/requirements.txt
tools/venv/bin/python tools/extract_models.py \
    --data-dir ./Data \
    --output-dir ./frontend/public/models
```

This produces `frontend/public/models/characters/*.glb`, `manifest.json`, and `attachments.json`.

### 3. Start the app

```bash
./start.sh
```

On the first run `start.sh` automatically:
- Creates `backend/venv` and installs Python deps
- Runs `npm install` for the frontend

Then open **http://localhost:5173** in your browser.

Press **Ctrl+C** to stop both servers.

---

## Extraction Pipeline

The `tools/` directory contains two Python scripts that read directly from your WoW MPQ archives using `libstorm.so` (bundled StormLib):

### `extract_models.py`

Converts M2 character models to GLB format and writes `manifest.json` + `attachments.json`.

```bash
tools/venv/bin/python tools/extract_models.py \
    --data-dir ./Data \
    --output-dir ./frontend/public/models
```

**Output:**
- `frontend/public/models/characters/{race}_{gender}.glb` — 20 models (10 races × 2 genders)
- `frontend/public/models/attachments.json` — attachment point positions per model
- `frontend/public/models/manifest.json` — list of extracted models

### `gear_compositor.py`

Generates composited skin textures at runtime (called by the backend, not run directly).
Reads `CharSections.dbc`, `CharHairGeosets.dbc`, `CharacterFacialHairStyles.dbc`, `HelmetGeosetVisData.dbc`, and `ItemDisplayInfo.dbc` from MPQ to build the final skin atlas.

### `libstorm.so`

Bundled precompiled StormLib (Linux x86_64) used via `ctypes` to open and read MPQ archives. No separate StormLib installation is required.

---

## Configuration

All settings are read from `.env` in the project root. Copy `.env.example` to get started:

```env
# AzerothCore database
DB_HOST=localhost
DB_USER=acore
DB_PASS=changeme
DB_NAME=acore_characters
WORLD_DB_NAME=acore_world

# CORS allowed origins (comma-separated)
CORS_ORIGINS=http://localhost:5173
```

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | MySQL host |
| `DB_USER` | `acore` | MySQL username |
| `DB_PASS` | _(empty)_ | MySQL password |
| `DB_NAME` | `acore_characters` | Characters database name |
| `WORLD_DB_NAME` | `acore_world` | World database name |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed frontend origin(s) |

Port overrides via environment variables before running `start.sh`:

```bash
BACKEND_PORT=8080 FRONTEND_PORT=3000 ./start.sh
```

---

## Backend API

Base URL: `http://127.0.0.1:8000`
All endpoints are prefixed with `/api`.

---

### `GET /api/characters`

List all characters, sorted by level descending.

**Query params:**

| Param | Default | Description |
|-------|---------|-------------|
| `limit` | `100` | Max characters to return (1–500) |

**Response:**
```json
[
  { "name": "Arthas", "race": 1, "class": 2, "level": 80, "gender": 0, "faction": "Alliance" }
]
```

---

### `GET /api/character`

Detailed character data including all equipped items.

**Query params:**

| Param | Required | Description |
|-------|----------|-------------|
| `name` | yes | Character name (case-sensitive) |

**Response:**
```json
{
  "guid": 1,
  "name": "Arthas",
  "race": 1,
  "class": 2,
  "gender": 0,
  "level": 80,
  "skin": 0,
  "face": 0,
  "hairStyle": 0,
  "hairColor": 0,
  "facialStyle": 0,
  "equipment": [
    {
      "slot": 0,
      "entry": 40186,
      "displayId": 41628,
      "name": "Helm of the Lost Conqueror",
      "quality": 4,
      "itemLevel": 213,
      "requiredLevel": 80,
      "inventoryType": 1,
      "stats": ["+89 Stamina", "+67 Intellect"],
      "armor": 1234,
      "description": ""
    }
  ]
}
```

---

### `GET /api/model-texture/{name}`

Composited character skin texture (PNG). Bakes base skin + face + facial hair + scalp + equipped body armor into one atlas.

Cached to `frontend/public/models/cache/{hash}.png`.

---

### `GET /api/model-hair-texture/{name}`

Hair mesh texture (PNG) for the character's selected hair style and color.
Applied to hair geometry submeshes (geoset type 6) in the 3D model.

---

### `GET /api/model-extra-skin-texture/{name}`

Extra skin texture (PNG) for races that have one (e.g. tauren fur detail layer).
Returns 404 if the race has no extra skin texture.

---

### `GET /api/model-cape-texture/{name}`

Cape/cloak texture (PNG) from `Item\ObjectComponents\Cape\` for the character's equipped back item (slot 14).

Returns 404 if no cape is equipped.

---

### `GET /api/model-geosets/{name}`

Active geoset IDs for the character based on their equipment and appearance settings.

The frontend uses this list to show/hide submesh nodes named `geoset_{id}_{textype}` in the GLB.

**Response:**
```json
{ "geosets": [1, 101, 301, 401, 702, 801] }
```

---

### `GET /api/item-model/{displayId}`

3D item model as GLB. Extracts M2 from MPQ on first request; cached to `frontend/public/models/cache/`.

**Query params:**

| Param | Default | Description |
|-------|---------|-------------|
| `side` | `left` | `left` or `right` model from `ItemDisplayInfo` |
| `race` | `0` | Race ID (required for helmets — selects race-specific model suffix like `_NiM`, `_HuF`) |
| `gender` | `0` | Gender ID (0=male, 1=female, used with `race` for helms) |

Supports: weapons, shields, shoulders, helms.

---

### `GET /api/character-attachments/{name}`

Attachment point world positions and the equipped items that should be rendered at each point.

**Response:**
```json
{
  "attachments": {
    "0": { "position": [x, y, z], "rotation": [qx, qy, qz, qw] },
    "1": { "position": [x, y, z], "rotation": [qx, qy, qz, qw] }
  },
  "items": {
    "mainHand":    { "displayId": 40343, "attachPoint": "1",  "hasModel": true },
    "offHand":     { "displayId": 40267, "attachPoint": "0",  "hasModel": true },
    "shoulderRight":{ "displayId": 45834, "attachPoint": "5", "side": "right", "hasModel": true },
    "shoulderLeft": { "displayId": 45834, "attachPoint": "6", "side": "left",  "hasModel": true },
    "helm":        { "displayId": 41628, "attachPoint": "11", "hasModel": true }
  },
  "race": 1,
  "gender": 0
}
```

**Attachment point mapping:**

| Point | Slot |
|-------|------|
| 0 | Shield mount (off-hand shields / held items) |
| 1 | Right hand (main-hand weapon) |
| 2 | Left hand (off-hand weapon / dual-wield) |
| 5 | Right shoulder |
| 6 | Left shoulder |
| 11 | Head (helm) |

---

## Project Structure

```
armory/
├── .env                        # DB credentials (not committed)
├── .env.example                # Template
├── start.sh                    # One-command launcher
│
├── backend/
│   ├── main.py                 # FastAPI app + lifespan (DB pool + MPQ warmup)
│   ├── config.py               # Pydantic settings (reads .env)
│   ├── database.py             # aiomysql connection pool
│   ├── requirements.txt
│   ├── routes/
│   │   ├── characters.py       # /api/character, /api/characters
│   │   └── models.py           # /api/model-*, /api/item-model/*, /api/character-attachments/*
│   └── services/
│       └── character.py        # DB queries
│
├── frontend/
│   ├── package.json
│   ├── vite.config.*           # Proxies /api → localhost:8000
│   └── src/
│       └── ...                 # React components
│   └── public/
│       └── models/
│           ├── manifest.json           # Generated by extract_models.py
│           ├── attachments.json        # Generated by extract_models.py
│           ├── characters/             # *.glb — extracted character models
│           └── cache/                  # Runtime texture/item cache (auto-generated)
│
├── tools/
│   ├── extract_models.py       # M2 → GLB extractor (character models + items)
│   ├── gear_compositor.py      # BLP texture compositor (skin atlas, hair, cape)
│   ├── libstorm.so             # Bundled StormLib (Linux x86_64, reads MPQ)
│   └── requirements.txt        # Pillow, numpy, pygltflib
│
└── Data/                       # Your WoW MPQ archives (not committed, large files)
    ├── patch.MPQ
    ├── patch-2.MPQ
    └── ...
```

---

## Troubleshooting

### `python3 -m venv` fails

Install the venv module:
```bash
sudo apt install python3-venv
```

### Backend fails to start — "Database connection error"

Check your `.env` credentials and that MySQL is running:
```bash
mysql -u acore -p -h localhost acore_characters -e "SELECT COUNT(*) FROM characters;"
```

### Models not showing — "No extracted models found"

Run the extraction pipeline (see [Extraction Pipeline](#extraction-pipeline)). You need the WoW MPQ archives in `Data/`.

### Textures are grey / blank

The backend composites textures on demand from MPQ. Check `logs/backend.log` for errors. Ensure the MPQ files are present and `tools/venv` is installed (the backend imports `gear_compositor` at runtime without needing the tools venv activated — it adds `tools/` to `sys.path` directly).

### Item models not appearing (weapons, shoulders, helms)

These are extracted on first request from MPQ. The first load will be slow. Check `logs/backend.log` if the `/api/item-model/{id}` call returns an error.

### Wrong CORS errors in the browser

Make sure `CORS_ORIGINS` in `.env` includes the frontend origin, e.g.:
```env
CORS_ORIGINS=http://localhost:5173
```

---

## Credits

- [AzerothCore](https://www.azerothcore.org/) — WoW 3.3.5 server emulator
- [StormLib](https://github.com/ladislav-zezula/StormLib) — MPQ archive reading (`libstorm.so`)
- [pygltflib](https://github.com/dodgyville/pygltflib) — GLB/glTF writing
- [React Three Fiber](https://github.com/pmndrs/react-three-fiber) — 3D rendering in React
- Blizzard Entertainment — World of Warcraft game assets (used for private/educational purposes only)
