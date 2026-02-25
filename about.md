# AzerothCore Armory

A web-based character inspection tool for [AzerothCore](https://www.azerothcore.org/) WotLK 3.3.5a private servers. Displays characters with their equipped gear in a 3D paper-doll layout, pulling live data from the AzerothCore MySQL database and rendering locally extracted game assets — no external CDN or Wowhead viewer required for the 3D model.

---

## Quick Start

```bash
cp .env.example .env      # fill in your DB credentials
./start.sh                # installs everything, starts both servers
```

Open **http://localhost:5173** in your browser. Press **Ctrl+C** to stop.

> `start.sh` automatically installs all Python venvs, compiles StormLib if needed, and runs `npm install` on first run.

---

## What It Does

- Live character data from `acore_characters` + `acore_world` MySQL databases
- 20 race/gender 3D character GLB models extracted from your local MPQ archives
- Composited skin textures — base skin, face, facial hair, scalp, and body armor baked into one PNG per character per outfit
- Separate hair, extra-skin (Tauren fur, Undead bones), and cape textures
- 3D item models (weapons, shields, shoulders, helms) extracted on demand from MPQ
- Geoset visibility — equipment controls which submeshes show or hide (hair hidden under helm, etc.)
- Paper-doll UI with item icons, quality-color borders, stat tooltips, and stats panel

---

## Architecture

```
Browser (http://localhost:5173)
  │
  ▼
Frontend — React 19 + TypeScript + Vite 7
  frontend/   port 5173
  /api/* → proxy →
  │
  ▼
Backend — Python FastAPI + Uvicorn
  backend/    port 8000
  │                   │
  ▼                   ▼
AzerothCore       frontend/public/models/
MySQL DB            characters/*.glb   (extracted once)
acore_characters    attachments.json
acore_world         manifest.json
                    cache/             (PNG + GLB, runtime)
                         ▲
                         │ extract once
                    tools/
                    extract_models.py
                    gear_compositor.py
                    libstorm.so
                    (needs Data/*.MPQ)
```

---

## Documentation

Full developer documentation is in the `docs/` folder in two languages.

### English — `docs/en/`

| # | Document | Topic |
|---|----------|-------|
| 01 | [Overview](docs/en/01-overview.md) | Features, architecture, project structure |
| 02 | [Installation](docs/en/02-installation.md) | Requirements, quick start, what `start.sh` does |
| 03 | [Configuration](docs/en/03-configuration.md) | `.env` variables, ports, CORS, MPQ load order |
| 04 | [Extraction Pipeline](docs/en/04-extraction-pipeline.md) | M2→GLB conversion, StormLib, BLP decoding, skin atlas |
| 05 | [Backend API](docs/en/05-backend-api.md) | All endpoints with request/response examples |
| 06 | [Frontend](docs/en/06-frontend.md) | Component tree, data flow, hooks, ModelViewer sequence |
| 07 | [Database](docs/en/07-database.md) | Tables, SQL queries, connection pool, stat IDs |
| 08 | [Troubleshooting](docs/en/08-troubleshooting.md) | Common errors, diagnostics, reset commands |
| 09 | [Technical Reference](docs/en/09-technical-reference.md) | M2/BLP/DBC formats, coordinate systems, geoset IDs |

### Polski — `docs/pl/`

| # | Dokument | Temat |
|---|----------|-------|
| 01 | [Przegląd](docs/pl/01-przeglad.md) | Funkcje, architektura, struktura projektu |
| 02 | [Instalacja](docs/pl/02-instalacja.md) | Wymagania, szybki start, co robi `start.sh` |
| 03 | [Konfiguracja](docs/pl/03-konfiguracja.md) | Zmienne `.env`, porty, CORS, kolejność MPQ |
| 04 | [Pipeline ekstrakcji](docs/pl/04-pipeline-ekstrakcji.md) | Konwersja M2→GLB, StormLib, dekodowanie BLP, atlas skóry |
| 05 | [API backendu](docs/pl/05-api-backendu.md) | Wszystkie endpointy z przykładami zapytań i odpowiedzi |
| 06 | [Frontend](docs/pl/06-frontend.md) | Drzewo komponentów, przepływ danych, hooki, sekwencja ModelViewer |
| 07 | [Baza danych](docs/pl/07-baza-danych.md) | Tabele, zapytania SQL, pula połączeń, ID statystyk |
| 08 | [Rozwiązywanie problemów](docs/pl/08-rozwiazywanie-problemow.md) | Typowe błędy, diagnostyka, polecenia resetowania |
| 09 | [Dokumentacja techniczna](docs/pl/09-dokumentacja-techniczna.md) | Formaty M2/BLP/DBC, układy współrzędnych, ID geosetek |

---

## Project Structure

```
armory/
├── .env                        # DB credentials (not committed)
├── .env.example
├── start.sh                    # Complete installer + launcher
├── about.md                    # This file
│
├── backend/
│   ├── main.py                 # FastAPI app + lifespan
│   ├── config.py               # Settings (Pydantic, reads .env)
│   ├── database.py             # aiomysql connection pool
│   ├── requirements.txt
│   ├── routes/
│   │   ├── characters.py       # /api/character, /api/characters
│   │   └── models.py           # /api/model-*, /api/item-model/*, /api/character-attachments/*
│   └── services/
│       └── character.py        # DB query logic
│
├── frontend/
│   ├── package.json
│   ├── vite.config.*           # Proxies /api → :8000
│   └── src/
│       └── ...                 # React + TypeScript source
│   └── public/
│       └── models/
│           ├── manifest.json           # Generated by extract_models.py
│           ├── attachments.json        # Generated by extract_models.py
│           ├── characters/             # *.glb — extracted character models
│           └── cache/                  # Runtime texture/item cache (auto-generated)
│
├── tools/
│   ├── extract_models.py       # M2 → GLB (character models, attachment points)
│   ├── gear_compositor.py      # BLP compositor (skin atlas, hair, cape textures)
│   ├── libstorm.so             # Bundled StormLib x86_64 (MPQ reader via ctypes)
│   └── requirements.txt        # Pillow, numpy, pygltflib
│
├── Data/                       # WoW 3.3.5a MPQ archives (not committed — large files)
│   ├── patch.MPQ
│   ├── patch-2.MPQ
│   └── ...
│
└── docs/
    ├── en/                     # English documentation (9 files)
    └── pl/                     # Polish documentation (9 files)
```

---

## Credits

- [AzerothCore](https://www.azerothcore.org/) — WoW 3.3.5a open-source server emulator
- [StormLib](https://github.com/ladislav-zezula/StormLib) — MPQ archive reading
- [pygltflib](https://github.com/dodgyville/pygltflib) — GLB/glTF file writing
- [React Three Fiber](https://github.com/pmndrs/react-three-fiber) — Three.js in React
- Blizzard Entertainment — World of Warcraft game assets (used for private/educational purposes only)
