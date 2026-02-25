# Overview

## What is AzerothCore Armory?

AzerothCore Armory is a full-stack web application that replicates the official World of Warcraft Armory experience for [AzerothCore](https://www.azerothcore.org/) private servers running the WotLK 3.3.5a patch. It reads live character data directly from the AzerothCore MySQL database and renders an interactive 3D character viewer complete with equipped gear, dynamic skin textures, geoset visibility, and item attachments — all from locally extracted game assets with no reliance on external CDNs or Blizzard's servers for the 3D model.

---

## Features

| Feature | Description |
|---------|-------------|
| Live character data | Reads directly from AzerothCore `acore_characters` and `acore_world` databases |
| 3D character rendering | Race- and gender-specific GLB models from extracted M2 files |
| Composited skin textures | Base skin + face + facial hair + scalp + equipped armor baked into one PNG atlas per character |
| Per-mesh texture slots | Hair, extra-skin (tauren fur), cape each served as independent textures |
| 3D item models | Weapons, shields, shoulders, helms extracted on demand from MPQ and placed at correct attachment points |
| Geoset visibility | Equipment controls which model submeshes show or hide (hair hidden under helm, etc.) |
| Paper-doll UI | Blizzard-style layout with item icons, quality-colour borders, and hover tooltips showing all item stats |
| Self-contained startup | `./start.sh` installs all dependencies, builds StormLib if needed, and launches both servers |

---

## Technology Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Language | Python 3.8+ |
| Web framework | [FastAPI](https://fastapi.tiangolo.com/) |
| ASGI server | [Uvicorn](https://www.uvicorn.org/) |
| Database driver | [aiomysql](https://aiomysql.readthedocs.io/) (async) |
| Settings | [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| In-memory cache | [cachetools](https://cachetools.readthedocs.io/) (TTLCache) |

### Frontend
| Component | Technology |
|-----------|-----------|
| Language | TypeScript |
| UI framework | [React 19](https://react.dev/) |
| Build tool | [Vite 7](https://vitejs.dev/) |
| 3D engine | [Three.js 0.182](https://threejs.org/) via [React Three Fiber 9](https://r3f.docs.pmnd.rs/) |
| 3D helpers | [@react-three/drei](https://github.com/pmndrs/drei) |

### Extraction Tools
| Component | Technology |
|-----------|-----------|
| Language | Python 3.8+ |
| MPQ reading | [StormLib](https://github.com/ladislav-zezula/StormLib) via ctypes |
| Image processing | [Pillow](https://python-pillow.org/) |
| Numeric arrays | [NumPy](https://numpy.org/) |
| GLB writing | [pygltflib](https://github.com/dodgyville/pygltflib) |

---

## Architecture

```
Browser (http://localhost:5173)
  │
  │  React + Vite dev server
  │  Proxies /api/* → localhost:8000
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND  (port 5173)                        │
│                                                                 │
│  CharacterSearch ─── CharacterList                             │
│        │                                                        │
│  PaperDoll                                                      │
│    ├── ItemSlot ×19  (icons, tooltips, quality borders)        │
│    ├── ModelViewer   (Three.js / React Three Fiber)            │
│    │     ├── CharacterModel  (GLB + textures + attachments)    │
│    │     └── OrbitControls                                      │
│    └── StatsPanel   (race, class, faction, avg ilvl)           │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP  /api/*
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND  (port 8000)                         │
│                                                                 │
│  FastAPI + Uvicorn                                              │
│                                                                 │
│  routes/characters.py                                           │
│    GET /api/character         ← character data + equipment      │
│    GET /api/characters        ← server character list           │
│                                                                 │
│  routes/models.py                                               │
│    GET /api/model-texture/{name}           ← skin PNG           │
│    GET /api/model-hair-texture/{name}      ← hair PNG           │
│    GET /api/model-extra-skin-texture/{name}← fur/bone PNG       │
│    GET /api/model-cape-texture/{name}      ← cape PNG           │
│    GET /api/model-geosets/{name}           ← geoset IDs         │
│    GET /api/character-attachments/{name}   ← 3D item positions  │
│    GET /api/item-model/{displayId}         ← item GLB           │
│                                                                 │
│  Lazy-loaded DBC caches:                                        │
│    ItemDisplayInfo, CharHairGeosets, CharFacialHairStyles,      │
│    HelmetGeosetVisData, CharSections                            │
│                                                                 │
│  Persistent MPQ pool (avoids re-opening large archives)         │
└──────────┬───────────────────────────────────────┬──────────────┘
           │ aiomysql (async)                       │ filesystem
           ▼                                        ▼
┌──────────────────────┐           ┌────────────────────────────┐
│   MySQL / MariaDB    │           │  frontend/public/models/   │
│                      │           │                            │
│   acore_characters   │           │  characters/  *.glb        │
│     characters       │           │  attachments.json          │
│     character_inv.   │           │  manifest.json             │
│     item_instance    │           │  cache/  PNG + GLB         │
│                      │           └──────────────┬─────────────┘
│   acore_world        │                          │ extracted by
│     item_template    │           ┌──────────────┴─────────────┐
└──────────────────────┘           │  tools/                    │
                                   │                            │
                                   │  extract_models.py         │
                                   │  gear_compositor.py        │
                                   │  libstorm.so  (StormLib)   │
                                   └──────────────┬─────────────┘
                                                  │ ctypes / StormLib
                                                  ▼
                                   ┌──────────────────────────┐
                                   │  Data/  (WoW MPQ files)  │
                                   │  patch.MPQ               │
                                   │  patch-2.MPQ             │
                                   │  locale-enUS.MPQ  etc.   │
                                   └──────────────────────────┘
```

---

## Request Flow: Character Load

1. User types a character name and presses Search.
2. The React frontend calls `GET /api/character?name=<name>`.
3. FastAPI checks its TTLCache; on miss it queries `acore_characters` + `acore_world`.
4. The response JSON includes all character fields and a formatted `equipment` array.
5. The frontend renders the paper-doll layout and simultaneously begins loading 3D assets:
   - `GET /api/model-texture/{name}` → composited skin atlas PNG
   - `GET /api/model-hair-texture/{name}` → hair mesh texture
   - `GET /api/model-extra-skin-texture/{name}` → extra-skin layer (race-specific)
   - `GET /api/model-cape-texture/{name}` → cape/cloak texture
   - `GET /api/model-geosets/{name}` → list of visible geoset IDs
   - `GET /api/character-attachments/{name}` → attachment point positions + item display IDs
6. For each attached item (weapons, shoulders, helm), the frontend calls `GET /api/item-model/{displayId}` to fetch on-demand GLB models.
7. All textures are applied to their respective mesh types; geosets toggle visibility; item GLBs are parented to attachment pivot nodes.

---

## Project Structure

```
armory/
├── .env                          # DB credentials (not committed)
├── .env.example                  # Template for .env
├── .gitignore
├── start.sh                      # Complete launcher + first-run installer
├── about.md                      # Project intro and docs index
├── DOCUMENTATION.md              # Extended developer wiki
│
├── backend/                      # FastAPI server
│   ├── main.py                   # App factory, lifespan, CORS
│   ├── config.py                 # Pydantic settings (reads .env)
│   ├── database.py               # aiomysql connection pool
│   ├── requirements.txt
│   ├── routes/
│   │   ├── characters.py         # /api/character, /api/characters
│   │   └── models.py             # All /api/model-* and /api/item-model/*
│   └── services/
│       └── character.py          # SQL queries, stat formatting
│
├── frontend/                     # React + Vite application
│   ├── package.json
│   ├── vite.config.ts            # Proxy /api → :8000
│   └── src/
│       ├── App.tsx
│       ├── api/character.ts      # HTTP calls
│       ├── hooks/
│       │   ├── useCharacter.ts
│       │   └── useItemIcon.ts
│       ├── utils/
│       │   ├── constants.ts      # Race/class names, slot layout
│       │   └── quality.ts        # Quality colours
│       ├── types/character.ts    # TypeScript interfaces
│       └── components/
│           ├── PaperDoll.tsx     # Main layout
│           ├── ModelViewer.tsx   # Three.js 3D viewer
│           ├── ItemSlot.tsx
│           ├── ItemTooltip.tsx
│           ├── StatsPanel.tsx
│           ├── CharacterSearch.tsx
│           └── CharacterList.tsx
│   └── public/
│       └── models/               # Generated by extraction pipeline
│           ├── characters/       # *.glb (race_gender.glb)
│           ├── attachments.json
│           ├── manifest.json
│           └── cache/            # Runtime PNG + GLB cache
│
├── tools/                        # Extraction pipeline
│   ├── extract_models.py         # M2 → GLB converter
│   ├── gear_compositor.py        # BLP texture compositor + geoset logic
│   ├── libstorm.so               # StormLib (bundled, Linux x86_64)
│   └── requirements.txt          # Pillow, numpy, pygltflib
│
├── Data/                         # WoW MPQ archives (NOT committed)
│   └── *.MPQ
│
├── docs/
│   ├── en/                       # English documentation
│   └── pl/                       # Polish documentation (Polska dokumentacja)
│
└── logs/
    ├── backend.log
    └── frontend.log
```
