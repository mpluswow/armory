# AzerothCore Armory - Developer Documentation

> A fully self-hosted WoW 3.3.5a (WotLK) character armory with interactive 3D model rendering, equipment display, and gear texture compositing. Built with FastAPI, React, Three.js, and extracted WotLK game data.

---

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env        # Edit with your AzerothCore DB credentials

# 2. Extract models (one-time, requires WoW 3.3.5a Data/ directory)
cd tools
python3 -m venv venv && source venv/bin/activate
pip install numpy Pillow pygltflib
# Build StormLib (https://github.com/ladislav-zezula/StormLib) and place libstorm.so here
python extract_models.py --data-dir ../Data --output-dir ../frontend/public/models
deactivate && cd ..

# 3. Run everything
./start.sh
# Frontend: http://localhost:5173
# Backend:  http://127.0.0.1:8000
# Ctrl+C to stop both
```

### Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.10+ | Backend API, extraction tools |
| Node.js | 18+ | Frontend build & dev server |
| MySQL | 5.7+ / 8.0 | AzerothCore character & world databases |
| WoW Client | 3.3.5a (12340) | MPQ archives in `Data/` directory |
| StormLib | any | `libstorm.so` for reading MPQ files |

### Environment Variables (`.env`)

```ini
DB_HOST=localhost
DB_USER=acore
DB_PASS=your_password
DB_NAME=acore_characters
WORLD_DB_NAME=acore_world
CORS_ORIGINS=http://localhost:5173,http://localhost:5000
```

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Project Structure](#2-project-structure)
3. [Backend (FastAPI)](#3-backend-fastapi)
4. [Frontend (React + Three.js)](#4-frontend-react--threejs)
5. [WoW Data Formats](#5-wow-data-formats)
6. [Model Extraction Pipeline](#6-model-extraction-pipeline)
7. [Texture Compositing System](#7-texture-compositing-system)
8. [Geoset Visibility System](#8-geoset-visibility-system)
9. [3D Rendering Pipeline](#9-3d-rendering-pipeline)
10. [DBC File Reference](#10-dbc-file-reference)
11. [API Reference](#11-api-reference)
12. [Data Flow](#12-data-flow)
13. [Coordinate Systems](#13-coordinate-systems)
14. [Performance & Caching](#14-performance--caching)
15. [Deployment](#15-deployment)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. Architecture Overview

The armory is a full-stack application that reads character data from an AzerothCore MySQL database and renders fully textured 3D character models in the browser using self-hosted assets extracted from the WoW 3.3.5a game client.

```
                                    +-----------------------+
                                    |   WoW 3.3.5 Client    |
                                    |   (MPQ Archives)      |
                                    +-----------+-----------+
                                                |
                                    +-----------v-----------+
                                    |  Extraction Pipeline   |
                                    |  extract_models.py     |
                                    |  (M2 -> GLB, BLP->PNG) |
                                    +-----------+-----------+
                                                |
                                    +-----------v-----------+
                                    |   Static GLB Models    |
                                    |   (20 race/gender)     |
                                    +-----------+-----------+
                                                |
+---------------+    +----------+    +----------v----------+
|  AzerothCore  |    |  FastAPI  |    |    React Frontend   |
|    MySQL DB   +--->+  Backend  +--->+    (Three.js)       |
|               |    |  :8000   |    |    :5173            |
+---------------+    +-----+----+    +---------------------+
                           |
                    +------v-------+
                    | gear_compositor|
                    | (DBC + MPQ    |
                    |  texture gen) |
                    +--------------+
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend | FastAPI + Uvicorn | Async REST API |
| Database | aiomysql | Async MySQL connection pool |
| Config | Pydantic Settings | Environment-based configuration |
| Texture Engine | Pillow (PIL) | Image compositing, BLP decoding |
| MPQ Reading | StormLib (ctypes) | Reading Blizzard MPQ archives |
| Frontend | React + TypeScript | UI components |
| 3D Rendering | Three.js + R3F | WebGL character model rendering |
| Build Tool | Vite | Frontend bundling, dev server |
| Model Format | glTF 2.0 (GLB) | Browser-compatible 3D models |

---

## 2. Project Structure

```
armory/
├── .env                          # Database credentials (gitignored)
├── .env.example                  # Template for .env
├── Data/                         # WoW 3.3.5 MPQ archives
│   ├── common.MPQ
│   ├── common-2.MPQ
│   ├── expansion.MPQ
│   ├── lichking.MPQ
│   ├── patch.MPQ
│   ├── patch-2.MPQ
│   └── patch-3.MPQ
│
├── backend/                      # FastAPI Python API
│   ├── main.py                   # App entry, CORS, lifespan
│   ├── config.py                 # Pydantic settings (.env loader)
│   ├── database.py               # Async MySQL connection pool
│   ├── requirements.txt          # Python dependencies
│   ├── venv/                     # Backend virtual environment
│   ├── routes/
│   │   ├── characters.py         # /api/character, /api/characters
│   │   └── models.py             # /api/model-texture, geosets, hair, etc.
│   └── services/
│       └── character.py          # DB queries, stat formatting
│
├── frontend/                     # React + Vite + TypeScript
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts            # Vite config with API proxy
│   ├── public/
│   │   └── models/
│   │       ├── characters/       # Extracted GLB models (20 files)
│   │       │   ├── human_male.glb
│   │       │   ├── human_female.glb
│   │       │   └── ...
│   │       ├── cache/            # Generated texture PNGs (auto)
│   │       └── manifest.json     # Model key -> file path mapping
│   └── src/
│       ├── App.tsx               # Root component
│       ├── main.tsx              # React entry point
│       ├── types/
│       │   └── character.ts      # TypeScript interfaces
│       ├── api/
│       │   └── character.ts      # Fetch wrappers
│       ├── components/
│       │   ├── CharacterSearch.tsx
│       │   ├── CharacterList.tsx
│       │   ├── PaperDoll.tsx     # 3-column equipment layout
│       │   ├── ItemSlot.tsx      # Single equipment slot
│       │   ├── ItemTooltip.tsx   # Hover tooltip with stats
│       │   ├── ModelViewer.tsx   # Three.js 3D renderer
│       │   └── StatsPanel.tsx    # Character stats
│       ├── hooks/
│       │   ├── useCharacter.ts
│       │   └── useItemIcon.ts
│       ├── utils/
│       │   ├── constants.ts      # Races, classes, colors, slot configs
│       │   └── quality.ts        # Item quality colors
│       └── styles/
│           ├── global.css
│           ├── paperdoll.css
│           └── tooltip.css
│
└── tools/                        # Extraction & compositing scripts
    ├── extract_models.py         # M2 -> GLB conversion pipeline
    ├── gear_compositor.py        # DBC parsing + texture compositing
    ├── libstorm.so               # StormLib shared library
    └── venv/                     # Tools virtual environment
```

---

## 3. Backend (FastAPI)

### 3.1 Configuration (`config.py`)

Uses Pydantic Settings to load configuration from `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | MySQL server host |
| `DB_USER` | `acore` | MySQL username |
| `DB_PASS` | _(empty)_ | MySQL password |
| `DB_NAME` | `acore_characters` | Character database |
| `WORLD_DB_NAME` | `acore_world` | World database (item templates) |
| `CORS_ORIGINS` | `http://localhost:5000` | Comma-separated allowed origins |

### 3.2 Database (`database.py`)

Async MySQL connection pool using aiomysql:

- **Pool size**: min=2, max=10
- **Cursor type**: `DictCursor` (rows returned as dicts)
- **Charset**: `utf8mb4`
- **Autocommit**: True (read-only queries)
- **Lifecycle**: Created on app startup, closed on shutdown

```python
async with get_conn() as conn:
    async with conn.cursor() as cur:
        await cur.execute("SELECT * FROM characters WHERE name=%s", (name,))
        row = await cur.fetchone()
```

### 3.3 Character Service (`services/character.py`)

#### SQL Queries

**Character query** - fetches base character data:
```sql
SELECT guid, name, race, class, gender, level,
       skin, face, hairStyle, hairColor, facialStyle
FROM characters WHERE name = %s
```

**Equipment query** - joins 3 tables across 2 databases:
```
character_inventory (ci)
  └─ item_instance (ii) ON ci.item = ii.guid
      └─ acore_world.item_template (it) ON ii.itemEntry = it.entry

WHERE ci.guid = %s AND ci.bag = 0 AND ci.slot BETWEEN 0 AND 18
```

Returns 50+ fields per item: entry, displayId, name, quality, itemLevel, all 10 stat pairs, armor, resistances, damage ranges, speed.

#### Stat Formatting

The service converts raw stat type IDs to readable strings:

| Stat Type | Name | Stat Type | Name |
|-----------|------|-----------|------|
| 0 | Mana | 32 | Critical Strike Rating |
| 1 | Health | 35 | Resilience Rating |
| 3 | Agility | 36 | Haste Rating |
| 4 | Strength | 37 | Expertise Rating |
| 5 | Intellect | 38 | Attack Power |
| 6 | Spirit | 43 | MP5 |
| 7 | Stamina | 45 | Spell Power |
| 12 | Defense Rating | 47 | Spell Penetration |
| 13 | Dodge Rating | 48 | Block Value |
| 31 | Hit Rating | | |

Equipment formatting pipeline:
1. Armor value -> `"+{armor} Armor"`
2. Stats (stat_type1..10 / stat_value1..10) -> `"+{value} {StatName}"`
3. Resistances (holy/fire/nature/frost/shadow/arcane) -> `"+{value} {Type} Resistance"`
4. Damage -> `"{min}-{max} {DmgType} Damage"`, `"Speed {delay/1000:.2f}"`

### 3.4 Application Entry (`main.py`)

```python
app = FastAPI(title="AzerothCore Armory", lifespan=lifespan)

# CORS middleware - allows frontend access
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"])

# Router registration
app.include_router(characters_router)  # /api/character, /api/characters
app.include_router(models_router)      # /api/model-texture, geosets, etc.
```

---

## 4. Frontend (React + Three.js)

### 4.1 Type Definitions (`types/character.ts`)

```typescript
interface Character {
  guid: number;
  name: string;
  race: number;        // 1-11 (see RACES)
  class: number;       // 1-11 (see CLASSES)
  gender: number;      // 0=male, 1=female
  level: number;
  skin: number;        // Skin color index
  face: number;        // Face variation
  hairStyle: number;
  hairColor: number;
  facialStyle: number; // Beard/markings
  equipment: EquipmentItem[];
}

interface EquipmentItem {
  slot: number;          // 0-18 inventory slot
  entry: number;         // item_template.entry
  displayId: number;     // ItemDisplayInfo ID
  name: string;
  quality: number;       // 0=Poor..5=Legendary
  itemLevel: number;
  requiredLevel: number;
  itemType: string;      // "Head", "Two-Hand", etc.
  stats: string[];       // ["+50 Stamina", "+30 Spell Power", ...]
  description: string;   // Flavor text
  icon: string;          // Item entry for icon lookup
}
```

### 4.2 Constants (`utils/constants.ts`)

**Race IDs**: 1=Human, 2=Orc, 3=Dwarf, 4=Night Elf, 5=Undead, 6=Tauren, 7=Gnome, 8=Troll, 10=Blood Elf, 11=Draenei

**Class Colors** (WoW standard):
| Class | Color | Hex |
|-------|-------|-----|
| Warrior | Tan | `#C79C6E` |
| Paladin | Pink | `#F58CBA` |
| Hunter | Green | `#ABD473` |
| Rogue | Yellow | `#FFF569` |
| Priest | White | `#FFFFFF` |
| Death Knight | Red | `#C41F3B` |
| Shaman | Blue | `#0070DE` |
| Mage | Cyan | `#69CCF0` |
| Warlock | Purple | `#9482C9` |
| Druid | Orange | `#FF7D0A` |

**Item Quality Colors**: 0=Poor(gray), 1=Common(white), 2=Uncommon(green), 3=Rare(blue), 4=Epic(purple), 5=Legendary(orange)

**Equipment Slot Layout**:
```
Left Column:        Center:          Right Column:
  Head (0)           3D Model          Hands (9)
  Neck (1)           StatsPanel        Waist (5)
  Shoulders (2)                        Legs (6)
  Back (14)                            Feet (7)
  Chest (4)                            Finger 1 (10)
  Tabard (18)                          Finger 2 (11)
  Wrist (8)                            Trinket 1 (12)
                                       Trinket 2 (13)
             Weapons Row:
         Main Hand (15) | Off Hand (16) | Ranged (17)
```

### 4.3 Component Architecture

```
App.tsx
  ├── CharacterSearch.tsx   (search input)
  ├── CharacterList.tsx     (browse all characters)
  └── PaperDoll.tsx         (main character display)
        ├── ItemSlot.tsx     (x19, each equipment slot)
        ├── ModelViewer.tsx  (3D model)
        │     └── CharacterModel (Three.js scene)
        ├── StatsPanel.tsx   (race, class, ilvl)
        └── ItemTooltip.tsx  (hover tooltip)
```

### 4.4 API Client (`api/character.ts`)

```typescript
// Fetches use Vite proxy in dev (/api/* -> localhost:8000)
const API_BASE = import.meta.env.VITE_API_URL || "";

fetchCharacter(name: string): Promise<Character>
  // GET /api/character?name={name}

fetchCharacters(): Promise<CharacterListResponse>
  // GET /api/characters
```

---

## 5. WoW Data Formats

### 5.1 MPQ Archives (MoPaQ)

Blizzard's archive format containing all game data. The WotLK client uses a patch-based load order where later archives override files from earlier ones.

**Load order** (highest priority last):
```
common.MPQ          # Base game assets
common-2.MPQ        # Additional base assets
expansion.MPQ       # TBC expansion data
lichking.MPQ        # WotLK expansion data
patch.MPQ           # First patch
patch-2.MPQ         # Second patch
patch-3.MPQ         # Latest patch (highest priority)
```

When searching for a file, archives are checked in **reverse** order (patches first) so the newest version of a file is always found first.

**StormLib** (C library) is used to read MPQ files via ctypes bindings. The library is compiled as `libstorm.so` and placed in `tools/`.

### 5.2 M2 Model Format (WotLK Version 264)

M2 is Blizzard's 3D model format. Character models contain the base mesh for all body part variations (geosets), UV mappings, and texture references.

**Header layout** (key fields):
```
Offset  Size  Field
0x00    4     Magic ("MD20")
0x04    4     Version (264 for WotLK)
0x3C    8     nVertices, ofsVertices
0x44    8     nViews, ofsViews (skin profiles)
0x50    8     nTextures, ofsTextures
0x6C    8     nBones, ofsBones
0x80    8     nTextureCombos, ofsTextureCombos
0xA8    24    Bounding box (min xyz, max xyz)
```

**Vertex format** (48 bytes per vertex):
```
Offset  Size  Field
0       12    Position (3x float32)
12      4     Bone weights (4x uint8)
16      4     Bone indices (4x uint8)
20      12    Normal (3x float32)
32      8     UV coordinates (2x float32)
40      8     UV coordinates 2 (2x float32)
```

**Texture entry** (16 bytes each):
```
Offset  Size  Field
0       4     Type (see Texture Types below)
4       4     Flags
8       4     Filename length
12      4     Filename offset
```

#### M2 Texture Types

| Type | Name | Description | Texture Source |
|------|------|-------------|----------------|
| 0 | HARDCODED | Filename embedded in M2 | M2 file itself |
| 1 | BODY/SKIN | Character skin atlas | Composited at runtime |
| 2 | OBJECT_SKIN | Cape/clothing texture | ItemDisplayInfo.dbc |
| 6 | HAIR | Character hair model | CharSections.dbc (section 3, tex1) |
| 8 | SKIN_EXTRA | Additional skin detail | CharSections.dbc (section 0, tex2) |
| 11 | CREATURE_SKIN_1 | Creature/NPC skins | Creature model data |

### 5.3 Skin Files (.skin)

Companion files to M2 models defining mesh subdivision. Named `{ModelName}00.skin` (first LOD level).

**Header**:
```
Offset  Size  Field
0       4     Magic ("SKIN", optional)
+0      8     nIndices, ofsIndices (vertex lookup table)
+8      8     nTriangles, ofsTriangles
+16     8     nBones, ofsBones
+24     8     nSubmeshes, ofsSubmeshes
+32     8     nBatches, ofsBatches
```

**Submesh entry** (48 bytes):
```
Field 0: geosetId (uint16)    - Identifies which body part group
Field 1: level (uint16)       - LOD level
Field 2: startVertex (uint16)
Field 3: nVertices (uint16)
Field 4: startTriangle (uint16)
Field 5: nTriangles (uint16)
... (additional fields)
```

**Batch entry** (24 bytes):
```
Offset  Size  Field
0       1     flags
1       1     priority
2       2     shader_id
4       2     skinSectionIndex (-> submesh)
6       2     geosetIndex
8       2     colorIndex
10      2     materialIndex
12      2     materialLayer
14      2     textureCount
16      2     textureComboIndex (-> texture lookup chain)
... (additional fields)
```

**Texture type resolution chain**:
```
Batch.textureComboIndex
  -> M2.textureCombos[textureComboIndex]    (uint16 -> texture index)
      -> M2.textures[textureIndex].type     (uint32 -> texture type 0/1/2/6/8)
```

This chain maps each submesh to its texture type, determining which texture should be applied to that piece of geometry.

### 5.4 BLP Texture Format (BLP2)

Blizzard's texture format supporting multiple compression modes.

**Header** (148+ bytes):
```
Offset  Size  Field
0       4     Magic ("BLP2")
4       4     Type
8       1     Encoding (1=palettized, 2=DXT, 3=raw BGRA)
9       1     Alpha depth (0, 1, 4, or 8 bits)
10      1     Alpha encoding (0=DXT1, 1=DXT3, 7=DXT5)
11      1     Has mipmaps
12      8     Width, height (uint32 each)
20      64    Mipmap offsets (16x uint32)
84      64    Mipmap sizes (16x uint32)
148+    1024  Color palette (256 BGRA entries, palettized only)
```

#### Encoding Types

**Palettized (encoding=1)**:
- 256-color palette stored at offset 148 (1024 bytes, BGRA format)
- Pixel data = color indices (1 byte/pixel) followed by alpha data
- Alpha stored SEPARATELY after color indices:
  - `alpha_depth=8`: 1 byte per pixel
  - `alpha_depth=4`: 4 bits per pixel (nibble)
  - `alpha_depth=1`: 1 bit per pixel (bitmask)

```
Pixel data layout:
[color_index_0, color_index_1, ..., color_index_N,    <- N bytes
 alpha_0, alpha_1, ..., alpha_N]                       <- varies by depth
```

> **Critical**: The alpha data is in a separate block AFTER all color indices, NOT interleaved. Many decoders get this wrong, resulting in lost transparency (scalp textures need alpha to mask hair vs face areas).

**DXT Compressed (encoding=2)**:
- **DXT1** (alpha_encoding=0): 8 bytes per 4x4 block, 1-bit alpha
- **DXT3** (alpha_encoding=1): 16 bytes per block, 4-bit explicit alpha
- **DXT5** (alpha_encoding=7): 16 bytes per block, 8-bit interpolated alpha

**Raw BGRA (encoding=3)**: Uncompressed 4 bytes per pixel.

### 5.5 DBC Files (Database Client)

Binary lookup tables used by the WoW client. All DBCs share a common header:

```
Offset  Size  Field
0       4     Magic ("WDBC")
4       4     Record count
8       4     Field count
12      4     Record size (bytes)
16      4     String block size

20+     ...   Record data (record_count * record_size bytes)
...     ...   String block (null-terminated strings, referenced by offset)
```

**String fields**: Stored as uint32 offsets into the string block. Offset 0 = empty string.

**DBC location in MPQ**: `DBFilesClient\{name}.dbc` (some in locale MPQs like `enUS\patch-enUS-*.MPQ`)

---

## 6. Model Extraction Pipeline

The extraction pipeline (`tools/extract_models.py`) converts WoW M2 character models to browser-compatible glTF/GLB format.

### 6.1 Process Overview

```
For each of 20 race/gender combinations:

1. Search MPQ archives (patches first) for:
   ├── {Race}{Gender}.m2    (model geometry)
   └── {Race}{Gender}00.skin (submesh definitions)

2. Parse M2 header -> vertex count, texture info, bounding box

3. Read vertices (48 bytes each) -> positions, normals, UVs
   └── Coordinate conversion: WoW(x,y,z) -> glTF(x,z,-y)

4. Parse skin file:
   ├── Read submeshes (geosetId, triangle ranges)
   └── Resolve triangle indices through lookup table

5. Map submesh -> texture type:
   └── Batch -> textureCombos -> textures -> type (1/6/8/etc.)

6. Find default skin texture (type 1):
   └── Convention path: {Race}{Gender}Skin00_00.blp

7. Build GLB:
   ├── Shared vertex buffer (positions + normals + UVs)
   ├── Per-submesh index buffers
   ├── Embedded skin texture (PNG)
   ├── 2 materials (skin=textured, non-skin=gray placeholder)
   └── Named nodes: geoset_{id}_{textype}

8. Save: characters/{race}_{gender}.glb
```

### 6.2 Character Model Paths in MPQ

| Model Key | MPQ Path |
|-----------|----------|
| `human_male` | `Character\Human\Male\HumanMale.m2` |
| `human_female` | `Character\Human\Female\HumanFemale.m2` |
| `orc_male` | `Character\Orc\Male\OrcMale.m2` |
| `undead_male` | `Character\Scourge\Male\ScourgeMale.m2` |
| `nightelf_male` | `Character\NightElf\Male\NightElfMale.m2` |
| ... | _(20 total: 10 races x 2 genders)_ |

Skin files use the same path with `00.skin` suffix: `HumanMale00.skin`

### 6.3 GLB Output Format

Each GLB file contains:

**Buffer layout** (single binary buffer):
```
[Positions (float32x3)]  [padding]
[Normals (float32x3)]    [padding]
[UVs (float32x2)]        [padding]
[Submesh 0 indices (uint32)]  [padding]
[Submesh 1 indices (uint32)]  [padding]
...
[Texture PNG bytes]       [padding]
```

All sections are 4-byte aligned.

**Materials**:
- **Material 0 (skin)**: Has embedded skin texture. Used by type-1 (body) submeshes.
- **Material 1 (non-skin)**: Neutral gray placeholder. Used by hair, cape, env, skin_extra submeshes. Texture loaded at runtime from API.

**Node naming convention**: `geoset_{geosetId}_{textureType}`

Examples:
```
geoset_0_skin          # Body mesh, skin type
geoset_101_hair        # Hair variant, hair type
geoset_1501_cape       # Cloak mesh, cape type
geoset_1703_env        # Eye glow, environment type
geoset_0_skin_extra    # Tauren fur detail, extra skin type
```

The naming encodes both the geoset ID (for visibility control) and the texture type (for correct texture assignment).

### 6.4 Running the Extraction

```bash
cd armory
tools/venv/bin/python tools/extract_models.py \
    --data-dir ./Data \
    --output-dir ./frontend/public/models
```

**Requirements**:
- `libstorm.so` in `tools/` directory (build from StormLib source)
- Python packages: `numpy`, `Pillow`, `pygltflib`
- WoW 3.3.5a Data directory with MPQ files

**Output**: 20 GLB files in `frontend/public/models/characters/` + `manifest.json`

---

## 7. Texture Compositing System

The WoW character rendering system works by layering multiple textures onto a single 512x512 skin atlas. The `gear_compositor.py` module replicates this process.

### 7.1 Skin Atlas Layout (512x512)

The character skin texture is divided into body regions:

```
     0        256       512
  0  +--------+--------+
     |  Arm   | Torso  |
     | Upper  | Upper  |
 128 +--------+--------+
     |  Arm   | Torso  |
     | Lower  | Lower  |
 192 +--------+--------+
     |        | Leg    |
     |  Hand  | Upper  |
 256 +--------+        |
     |        |        |
 320 + Face   +--------+
     | Upper  | Leg    |
 384 +--------+ Lower  |
     |  Face  |        |
     | Lower  |        |
 448 +--------+--------+
     |        | Foot   |
 512 +--------+--------+
```

**Exact region coordinates** (x, y, width, height):

| Region | Position | Size |
|--------|----------|------|
| ArmUpperTexture | (0, 0) | 256x128 |
| ArmLowerTexture | (0, 128) | 256x128 |
| HandTexture | (0, 256) | 256x64 |
| FaceUpperTexture | (0, 320) | 256x64 |
| FaceLowerTexture | (0, 384) | 256x128 |
| TorsoUpperTexture | (256, 0) | 256x128 |
| TorsoLowerTexture | (256, 128) | 256x64 |
| LegUpperTexture | (256, 192) | 256x128 |
| LegLowerTexture | (256, 320) | 256x128 |
| FootTexture | (256, 448) | 256x64 |

These coordinates come from WoW Model Viewer source code (`texture.h`, `REGION_FAC=2`).

### 7.2 Compositing Layer Order

Textures are composited using **Porter-Duff SourceOver** blending (`Image.alpha_composite()`). Each layer's transparent pixels preserve the layer below.

```
Layer 0:  Base skin texture
          Source: CharSections.dbc, section=0 (Skin)
          Covers: Entire 512x512 atlas

Layer 1:  Face textures
          Source: CharSections.dbc, section=1 (Face)
          FaceLower -> FaceLowerTexture region (0, 384, 256, 128)
          FaceUpper -> FaceUpperTexture region (0, 320, 256, 64)

Layer 2:  Facial hair (beard, sideburns, markings)
          Source: CharSections.dbc, section=2 (FacialHair)
          FacialLower -> FaceLowerTexture region
          FacialUpper -> FaceUpperTexture region

Layer 3:  Scalp/hair color overlay
          Source: CharSections.dbc, section=3 (Hair)
          ScalpLower (tex2) -> FaceLowerTexture region
          ScalpUpper (tex3) -> FaceUpperTexture region
          NOTE: tex1 is HairModelTexture (for 3D hair mesh, NOT composited)

Layer 10+: Equipment textures (sorted by slot)
           Source: ItemDisplayInfo.dbc -> MPQ textures
           Order: Shirt -> Legs -> Boots -> Chest -> Wrist -> Belt -> Gloves -> Tabard
           Each piece maps to specific body regions
```

> **Critical**: Use `Image.alpha_composite()` (Porter-Duff SourceOver), NOT `Image.paste()`. Paste ignores source alpha and overwrites destination completely. Alpha composite respects transparency, which is essential for scalp textures (alpha marks hair vs face areas) and equipment textures (alpha preserves skin around armor edges).

### 7.3 Equipment Texture Lookup

For each equipped item:

```
1. Get displayId from equipment slot

2. Look up in ItemDisplayInfo.dbc:
   ├── Fields 15-22: Texture region base names
   │   (ArmUpper, ArmLower, Hand, TorsoUpper, TorsoLower, LegUpper, LegLower, Foot)
   └── Fields 7-9: Geoset groups (for mesh visibility)

3. For each non-empty region texture name:
   ├── Try: ITEM\TEXTURECOMPONENTS\{RegionFolder}\{TexName}_M.blp (male)
   ├── Try: ITEM\TEXTURECOMPONENTS\{RegionFolder}\{TexName}_F.blp (female)
   └── Try: ITEM\TEXTURECOMPONENTS\{RegionFolder}\{TexName}_U.blp (unisex)

4. Alpha-composite found texture onto the matching atlas region
```

### 7.4 Non-Atlas Textures (Runtime Loaded)

Some mesh types use textures that are NOT part of the 512x512 skin atlas. These are loaded separately at runtime:

| Texture Type | Source | API Endpoint |
|-------------|--------|--------------|
| Hair (type 6) | CharSections.dbc section=3, tex1 (HairModelTexture) | `/api/model-hair-texture/{name}` |
| Extra Skin (type 8) | CharSections.dbc section=0, tex2 (ExtraSkinTexture) | `/api/model-extra-skin-texture/{name}` |
| Cape (type 2) | ItemDisplayInfo.dbc (cape texture) | _(not yet implemented)_ |
| Environment (type 0) | Hardcoded filename in M2 | Embedded in GLB at extraction |

**Hair texture**: Applied to 3D hair geometry meshes. Different from scalp overlay (which goes on the skin atlas). Varies by hair style and color.

**Extra skin texture**: Used by Tauren (fur pattern), Undead (bone/rot details). Filename pattern: `{Race}{Gender}Skin00_{color}_Extra.blp`

### 7.5 Compositing Function Call Chain

```
generate_character_texture(data_dir, race_key, gender, skin_color, equipment,
                           face, hair_style, hair_color, facial_style)
  │
  ├── Load ItemDisplayInfo.dbc
  ├── Load CharSections.dbc
  ├── Build MPQ archive list
  │
  ├── Load base skin:  CharSections(race, gender, SKIN, 0, skin_color).tex1
  ├── Load face:       CharSections(race, gender, FACE, face, skin_color).tex1/tex2
  ├── Load facial:     CharSections(race, gender, FACIAL_HAIR, facial_style, hair_color).tex1/tex2
  ├── Load scalp:      CharSections(race, gender, HAIR, hair_style, hair_color).tex2/tex3
  │
  └── composite_gear_texture(base_skin, equipment, display_info_db, mpq_archives, gender,
                              face_lower, face_upper, facial_lower, facial_upper,
                              scalp_lower, scalp_upper)
        │
        ├── Copy base skin as RGBA
        ├── Layer 1: alpha_composite face textures onto face regions
        ├── Layer 2: alpha_composite facial hair onto face regions
        ├── Layer 3: alpha_composite scalp/hair onto face regions
        └── Layers 10+: For each equipment piece:
              ├── Look up textures in ItemDisplayInfo.dbc
              ├── Find BLP in MPQ (gender-specific or unisex)
              └── alpha_composite onto matching body region
```

---

## 8. Geoset Visibility System

### 8.1 What Are Geosets?

Each WoW character model contains dozens of submeshes called **geosets**. These represent different body part variants: bare hands vs gloved hands, short pants vs long pants, different hair styles, etc.

Only certain geosets should be visible at any time, determined by equipped items and character customization.

### 8.2 Geoset ID System

Geoset IDs follow a grouping convention:

| ID Range | Group | Description |
|----------|-------|-------------|
| 0 | Skin | Base body mesh (always visible) |
| 1xx | Facial features | Face/beard variants |
| 2xx | Facial features | Additional facial geosets |
| 3xx | Facial features | Ears, piercings |
| 4xx | Gloves | Bare hands (401) to heavy gloves (404) |
| 5xx | Boots | Bare feet (501) to plate boots (504) |
| 6xx | Reserved | |
| 7xx | Ears | Ear visibility (701=show, 702=hidden by helm) |
| 8xx | Sleeves | Bare arms (801) to full sleeves (803) |
| 9xx | Legs/kneepads | Leg detail variants |
| 10xx | Chest | Bare chest (1001) to full breastplate |
| 11xx | Pants | Underwear (1101) to full leg armor |
| 12xx | Tabard | None (1200) to tabard shown (1201) |
| 13xx | Trousers | Leg covering variants |
| 14xx | Reserved | |
| 15xx | Cloak | None (1500) to long cloak (1504) |
| 16xx | Feet detail | |
| 17xx | Eyeglow | Death knight, etc. (1702+) |
| 18xx | Belt | None (1800) to belt (1801) |
| 19xx | Bone/tail | Race-specific (Undead bones, Draenei tail) |
| 20xx | Reserved | |
| 21xx | Reserved | |
| 22xx | Feet buttons | Boot detail |
| 23xx | Hands attach | Gauntlet additions |
| 24xx-25xx | Reserved | |
| 26xx | Shoulders | None (2600) to shoulder armor |
| 27xx | Helm | None (2700) to helm shown (2702+) |
| 28xx | Helm detail | Helm variant meshes |

### 8.3 Geoset Computation

The function `compute_active_geosets()` determines which geosets to show:

**Default state** (nothing equipped):
```python
defaults = {
    "glove": 401,      # Bare hands
    "boots": 501,      # Bare feet
    "chest": 1001,     # Bare chest (body mesh)
    "pants": 1101,     # Underwear
    "tabard": 1200,    # No tabard (hidden)
    "cloak": 1500,     # No cloak (hidden)
    "belt": 1800,      # No belt (hidden)
    "helm": 2700,      # No helm (hidden)
    "shoulders": 2600, # No shoulders (hidden)
}
```

**Equipment override rules** (slot -> geoset effect):

| Slot | Item Type | Geoset Changes |
|------|-----------|----------------|
| 0 | Head | `helm = 2702 + geosetGroup1` |
| 2 | Shoulders | `shoulders = 2601 + geosetGroup1` |
| 3 | Shirt | Affects sleeves (801 + g1), chest |
| 4 | Chest | Overrides shirt. Sets sleeves, chest, trousers |
| 5 | Belt | `belt = 1801 + geosetGroup1` |
| 6 | Legs | Sets pants (1101 + g1), kneepads, trousers |
| 7 | Feet | Sets boots (501 + g1), feet detail |
| 9 | Gloves | Sets glove (401 + g1), handsAttach |
| 14 | Back/Cloak | `cloak = 1501 + geosetGroup1` |
| 18 | Tabard | `tabard = 1201 + geosetGroup1` |

Where `g1`, `g2`, `g3` come from `ItemDisplayInfo.dbc` fields `geosetGroup1/2/3`.

**Hair and facial hair geosets** come from DBC lookups:
- Hair: `CharHairGeosets.dbc` maps (race, sex, hairStyle) -> geoset ID
- Facial: `CharacterFacialHairStyles.dbc` maps (race, sex, facialStyle) -> 5 geoset offsets

### 8.4 Frontend Geoset Application

```typescript
// Fetch active geosets
const response = await fetch(`/api/model-geosets/${characterName}`);
const { geosets } = await response.json(); // [0, 101, 401, 501, ...]
const activeSet = new Set(geosets);

// Show/hide mesh nodes
clone.traverse((child) => {
  const parsed = parseGeosetNode(child.name);
  // child.name = "geoset_401_skin" -> parsed = {id: 401, texType: "skin"}
  if (parsed) {
    child.visible = activeSet.has(parsed.id);
  }
});
```

---

## 9. 3D Rendering Pipeline

### 9.1 Overview

The frontend renders character models using Three.js via React Three Fiber. The rendering pipeline has 4 async stages that happen after the GLB model loads:

```
1. Load GLB model (useGLTF hook)
2. Clone scene, scale/center model
3. Fetch geoset visibility + apply
4. Fetch textures + apply per mesh type:
   ├── Skin texture  -> _skin meshes
   ├── Hair texture  -> _hair meshes
   └── Extra skin    -> _skin_extra meshes
```

### 9.2 Model Loading & Setup

```typescript
// Build model path from race + gender
const path = `/models/characters/${raceName}_${genderStr}.glb`;
const { scene } = useGLTF(path);

// Deep clone (preserves original for reuse across components)
const clone = scene.clone(true);

// Clone materials for per-instance modification
clone.traverse((child) => {
  if (child.isMesh) {
    const newMat = srcMat.clone();
    if (srcMat.map) newMat.map = srcMat.map.clone();
    mesh.material = newMat;
  }
});

// Scale to fit viewport (2.0 units total height)
const box = new THREE.Box3().setFromObject(clone);
const maxDim = Math.max(size.x, size.y, size.z);
clone.scale.setScalar(2.0 / maxDim);

// Center and position
clone.position.sub(center);
clone.position.y += height / 2;
clone.rotation.y = Math.PI; // Face camera
```

### 9.3 Texture Application by Type

The system uses a helper to parse node names and apply textures:

```typescript
// Parse "geoset_{id}_{textype}" -> { id, texType }
const parseGeosetNode = (name: string) => {
  const match = name.match(/^geoset_(\d+)_(\w+)$/);
  if (match) return { id: parseInt(match[1]), texType: match[2] };
  return null;
};

// Apply texture to matching mesh types
const applyTextureToType = (texture: THREE.Texture, ...texTypes: string[]) => {
  clone.traverse((child) => {
    if (child.isMesh) {
      const parsed = parseGeosetNode(child.name);
      if (parsed && texTypes.includes(parsed.texType)) {
        child.material.map = texture;
        child.material.needsUpdate = true;
      }
    }
  });
};
```

**Texture assignments**:

| API Endpoint | Applied To | Texture Type |
|-------------|-----------|--------------|
| `/api/model-texture/{name}` | `"skin"` meshes | Composited skin + face + gear atlas |
| `/api/model-hair-texture/{name}` | `"hair"` meshes | 3D hair model texture |
| `/api/model-extra-skin-texture/{name}` | `"skin_extra"` meshes | Tauren fur, undead bones |
| _(embedded in GLB)_ | `"env"` meshes | Eye glow, environment maps |
| _(not yet implemented)_ | `"cape"` meshes | Cloak/cape textures |

**Texture setup** (required for all loaded textures):
```typescript
texture.flipY = false;                     // GLB convention
texture.colorSpace = THREE.SRGBColorSpace; // Correct color rendering
texture.needsUpdate = true;                // Force GPU upload
```

### 9.4 Scene Configuration

```typescript
<Canvas camera={{ position: [0, 1, 3.5], fov: 40 }}>
  <ambientLight intensity={0.6} />
  <directionalLight position={[3, 4, 3]} intensity={1.2} />   // Main light
  <directionalLight position={[-2, 2, 1]} intensity={0.5} />  // Fill light
  <directionalLight position={[0, 2, -3]} intensity={0.3} />  // Back light

  <OrbitControls
    target={[0, 0.8, 0]}     // Orbit around chest height
    enablePan={false}
    minDistance={1.5}
    maxDistance={8}
    maxPolarAngle={Math.PI * 0.85}  // Prevent going under floor
  />
</Canvas>
```

### 9.5 Error Handling

```
ModelViewer
  └── ModelErrorBoundary (React error boundary)
        ├── Success: Renders Scene with CharacterModel
        └── Failure: Renders FallbackDisplay (2D class icon + info)
```

If the GLB file fails to load (missing model, network error), the error boundary catches it and shows a styled fallback with character name, level, race, and class.

---

## 10. DBC File Reference

### 10.1 ItemDisplayInfo.dbc

Maps item display IDs to visual properties (textures, mesh variants, models).

**Key fields**:

| Index | Field | Description |
|-------|-------|-------------|
| 0 | displayId | Primary key |
| 7 | geosetGroup1 | Primary mesh variant offset |
| 8 | geosetGroup2 | Secondary mesh variant offset |
| 9 | geosetGroup3 | Tertiary mesh variant offset |
| 15 | ArmUpperTexture | Texture name for upper arm region |
| 16 | ArmLowerTexture | Texture name for lower arm region |
| 17 | HandTexture | Texture name for hand region |
| 18 | TorsoUpperTexture | Texture name for upper chest region |
| 19 | TorsoLowerTexture | Texture name for lower chest region |
| 20 | LegUpperTexture | Texture name for upper leg region |
| 21 | LegLowerTexture | Texture name for lower leg region |
| 22 | FootTexture | Texture name for foot region |

Texture names are base names. Full path: `ITEM\TEXTURECOMPONENTS\{RegionFolder}\{BaseName}_{M|F|U}.blp`

### 10.2 CharSections.dbc

Maps character appearance parameters to texture file paths.

**Record fields**: `[ID, RaceID, SexID, BaseSection, Tex1, Tex2, Tex3, Flags, VariationIndex, ColorIndex]`

**Lookup key**: `(RaceID, SexID, BaseSection, VariationIndex, ColorIndex)`

**Sections and their textures**:

| Section | Name | Tex1 | Tex2 | Tex3 |
|---------|------|------|------|------|
| 0 | Skin | Base skin texture | Extra skin (fur/bones) | _(unused)_ |
| 1 | Face | Face lower | Face upper | _(unused)_ |
| 2 | Facial Hair | Facial lower | Facial upper | _(unused)_ |
| 3 | Hair | **HairModelTexture** (3D mesh) | Scalp lower (composited) | Scalp upper (composited) |
| 4 | Underwear | Upper body | Lower body | _(unused)_ |

> **Critical distinction for Section 3 (Hair)**:
> - **tex1** = HairModelTexture: The texture applied to the 3D hair **geometry** (geoset type 6). This is NOT composited onto the skin atlas.
> - **tex2** = ScalpLower: Composited onto the FaceLower region of the skin atlas (hair color on back of head).
> - **tex3** = ScalpUpper: Composited onto the FaceUpper region (hair color on top of head).
>
> Mixing these up causes the face to appear on hair meshes or hair color to be missing from the head.

### 10.3 CharHairGeosets.dbc

Maps character hair style to the corresponding geoset ID.

**Lookup**: `(RaceID, SexID, HairStyle)` -> `GeosetID`

The geoset ID determines which hair mesh variant is visible in the 3D model. Different hair styles correspond to different submeshes in the M2 model.

### 10.4 CharacterFacialHairStyles.dbc

Maps facial hair/marking style to geoset offsets.

**Lookup**: `(RaceID, SexID, FacialStyle)` -> `(geoset1, geoset2, geoset3, geoset4, geoset5)`

These offsets are added to base facial geoset IDs (100, 300, 200, 2400, 2500) to select the correct facial hair mesh variant.

> **Note**: In the DBC data, geoset2 and geoset3 are **swapped** compared to the logical order. The code accounts for this.

---

## 11. API Reference

### `GET /api/character?name={name}`
Returns full character data with formatted equipment.

**Parameters**: `name` (string, required, min length 1)

**Response** (200):
```json
{
  "guid": 1,
  "name": "CharName",
  "race": 1,
  "class": 8,
  "gender": 0,
  "level": 80,
  "skin": 4,
  "face": 2,
  "hairStyle": 5,
  "hairColor": 3,
  "facialStyle": 1,
  "equipment": [
    {
      "slot": 4,
      "entry": 51290,
      "displayId": 64145,
      "name": "Sanctified Bloodmage Robe",
      "quality": 4,
      "itemLevel": 264,
      "requiredLevel": 80,
      "itemType": "Chest",
      "stats": ["+100 Intellect", "+95 Stamina", "+72 Spell Power"],
      "description": "",
      "icon": "51290"
    }
  ]
}
```

**Errors**: 404 if character not found

**Caching**: 30-second TTL cache (in-memory, max 256 entries)

---

### `GET /api/characters?limit={limit}`
Returns a list of all characters.

**Parameters**: `limit` (integer, default=100, min=1, max=500)

**Response** (200):
```json
{
  "count": 42,
  "characters": [
    {
      "name": "CharName",
      "race": 1,
      "class": 8,
      "level": 80,
      "faction": "Alliance"
    }
  ]
}
```

---

### `GET /api/model-texture/{name}`
Returns a composited 512x512 PNG texture with the character's skin, face, hair color, facial hair, and all equipped gear baked in. This texture is applied to skin-type (type 1) submeshes in the 3D model.

**Response**: PNG image (binary)

**Cache key**: MD5 hash of `{race}_{gender}_{skin}_{face}_{hairStyle}_{hairColor}_{facialStyle}_{sortedDisplayIds}`

**Generation time**: ~10s cold (first request loads MPQ pool), ~0.1s warm (cached MPQ handles)

---

### `GET /api/model-hair-texture/{name}`
Returns the hair model texture for the character's current hair style and color. Applied to hair-type (type 6) submeshes.

**Response**: PNG image (binary), typically 64x128 or similar

**Cache key**: MD5 of `hair_{race}_{gender}_{hairStyle}_{hairColor}`

**Errors**: 404 if character or hair texture not found (e.g., bald characters)

---

### `GET /api/model-extra-skin-texture/{name}`
Returns the extra skin detail texture. Only applicable to certain races (Tauren fur, Undead bones).

**Response**: PNG image (binary), typically 128x128

**Cache key**: MD5 of `extraskin_{race}_{gender}_{skin}`

**Errors**: 404 if race doesn't have extra skin textures (most races)

---

### `GET /api/model-geosets/{name}`
Returns the list of active geoset IDs that should be visible for the character based on their equipped items and customization.

**Response** (200):
```json
{
  "geosets": [0, 2, 106, 202, 306, 401, 501, 702, 801, 1001, 1101, 1301, 1500, ...]
}
```

The frontend uses this list to show/hide submesh nodes in the 3D model. A submesh named `geoset_401_skin` is visible if `401` is in the active geosets list.

---

## 12. Data Flow

### 12.1 Full Request Lifecycle

```
User types character name and clicks Search
  │
  ▼
App.tsx: useCharacter hook calls fetchCharacter()
  │
  ▼
GET /api/character?name=Test
  │
  ▼
routes/characters.py: Check TTL cache -> Miss -> services/character.py
  │
  ▼
services/character.py:
  ├── Query 1: SELECT from characters WHERE name='Test'
  ├── Query 2: SELECT from character_inventory JOIN item_instance JOIN item_template
  └── Format equipment stats, return JSON
  │
  ▼
Frontend receives Character object
  │
  ├─► PaperDoll renders equipment slots (ItemSlot x19)
  │     └─► ItemTooltip shows on hover
  │
  ├─► StatsPanel shows race, class, avg ilvl
  │
  └─► ModelViewer renders 3D model:
        │
        ├── 1. useGLTF loads /models/characters/human_male.glb (static file)
        │      └── GLB contains mesh nodes: geoset_0_skin, geoset_101_hair, etc.
        │
        ├── 2. Clone scene, scale to fit, center, rotate to face camera
        │
        ├── 3. GET /api/model-geosets/Test -> [0, 401, 501, ...]
        │      └── Show/hide mesh nodes based on active geoset list
        │
        ├── 4. GET /api/model-texture/Test -> 512x512 PNG
        │      └── gear_compositor.py: skin + face + facial + scalp + equipment
        │      └── Apply to all meshes with texType="skin"
        │
        ├── 5. GET /api/model-hair-texture/Test -> hair PNG
        │      └── CharSections.dbc: section=3, tex1 (HairModelTexture)
        │      └── Apply to all meshes with texType="hair"
        │
        └── 6. GET /api/model-extra-skin-texture/Test -> extra skin PNG (or 404)
               └── CharSections.dbc: section=0, tex2 (ExtraSkinTexture)
               └── Apply to all meshes with texType="skin_extra"
```

### 12.2 Texture Generation Flow (Detail)

```
GET /api/model-texture/Test
  │
  ▼
routes/models.py:
  ├── Fetch character data (race, gender, skin, face, hair, equipment)
  ├── Build cache key: "human_0_4_2_5_3_1_64145_72830"
  ├── Hash: MD5[:12] -> "a7f2b9c1e3d4"
  ├── Check: cache/a7f2b9c1e3d4.png exists? -> Return cached
  │
  ▼ (Cache miss)
  │
  gear_compositor.py: generate_character_texture()
  │
  ├── 1. Load ItemDisplayInfo.dbc (lazy, cached globally)
  ├── 2. Load CharSections.dbc (lazy, cached globally)
  ├── 3. Open MPQ archives (persistent pool, never closed)
  │
  ├── 4. Find base skin: CharSections(1, 0, SKIN, 0, 4)
  │      -> "Character\Human\Male\HumanMaleSkin00_04.blp"
  │      -> Read from MPQ -> decode_blp() -> 512x512 RGBA
  │
  ├── 5. Find face: CharSections(1, 0, FACE, 2, 4)
  │      -> face_lower + face_upper BLP files
  │
  ├── 6. Find facial hair: CharSections(1, 0, FACIAL_HAIR, 1, 3)
  │      -> facial_lower + facial_upper BLP files
  │
  ├── 7. Find scalp: CharSections(1, 0, HAIR, 5, 3)
  │      -> scalp_lower (tex2) + scalp_upper (tex3)
  │      -> NOTE: tex1 is HairModelTexture, NOT used here
  │
  └── 8. composite_gear_texture():
         ├── result = base_skin.copy()
         ├── alpha_composite(face_lower, FaceLowerTexture region)
         ├── alpha_composite(face_upper, FaceUpperTexture region)
         ├── alpha_composite(facial_lower, FaceLowerTexture region)
         ├── alpha_composite(scalp_lower, FaceLowerTexture region)
         ├── alpha_composite(scalp_upper, FaceUpperTexture region)
         │
         ├── For each equipped item (sorted by slot):
         │   ├── displayId -> ItemDisplayInfo -> texture region names
         │   ├── Find: ITEM\TEXTURECOMPONENTS\ArmUpperTexture\{name}_M.blp
         │   └── alpha_composite onto ArmUpperTexture region (0, 0, 256, 128)
         │
         └── Save result as PNG, return FileResponse
```

---

## 13. Coordinate Systems

### WoW M2 Coordinate System
```
      Z (up)
      |
      |
      +---- X (right)
     /
    Y (forward, into screen)
```

### glTF Coordinate System
```
      Y (up)
      |
      |
      +---- X (right)
     /
    Z (forward, towards viewer)
```

### Conversion Formula

```
glTF.x =  WoW.x    (right axis unchanged)
glTF.y =  WoW.z    (up axis: WoW Z -> glTF Y)
glTF.z = -WoW.y    (forward axis: WoW Y -> glTF -Z)
```

Applied to both positions and normals during extraction.

---

## 14. Performance & Caching

### 14.1 Backend Caching

| Cache | Type | TTL | Size | Purpose |
|-------|------|-----|------|---------|
| Character data | In-memory (cachetools) | 30s | 256 entries | Avoid repeated DB queries |
| Texture PNGs | Filesystem | Infinite | Unlimited | Avoid re-compositing identical textures |
| DBC databases | Global Python objects | App lifetime | 3-4 objects | Avoid re-parsing DBC files |
| MPQ archive pool | Global dict | App lifetime | 7 handles | Avoid reopening MPQ archives |

### 14.2 MPQ Pool Performance Impact

| Approach | Texture Generation Time |
|----------|----------------------|
| Open/close MPQ per texture lookup | ~89 seconds |
| Persistent MPQ pool (current) | ~10s cold, ~0.1s warm |

The MPQ pool keeps archive handles open for the application lifetime. Without it, each `SFileOpenArchive`/`SFileCloseArchive` call adds significant overhead (file scanning, hash table building).

### 14.3 Texture Cache Keys

Cache keys are MD5 hashes (12 chars) of the input parameters, ensuring identical character appearances produce identical cache hits:

```
Skin texture:  MD5("human_0_4_2_5_3_1_64145_72830")[:12] -> "a7f2b9c1e3d4.png"
Hair texture:  MD5("hair_human_0_5_3")[:12] -> "b8d1e4f2a9c7.png"
Extra skin:    MD5("extraskin_tauren_0_2")[:12] -> "c9e2f5a3b8d1.png"
```

### 14.4 Frontend Caching

- **GLB models**: Cached by `useGLTF` (Three.js loader cache). Only re-fetched when race/gender changes.
- **Textures**: Loaded via `THREE.TextureLoader`, cached by URL in the browser HTTP cache.
- **Item icons**: Cached in `localStorage` via `useItemIcon` hook (avoids re-fetching Wowhead icons).

---

## 15. Deployment

### 15.1 Development Setup

**Backend**:
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env  # Edit with your DB credentials
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev  # Starts Vite dev server on :5173 with API proxy
```

**Tools** (one-time model extraction):
```bash
cd tools
python -m venv venv
source venv/bin/activate
pip install numpy Pillow pygltflib
# Build StormLib and place libstorm.so here
python extract_models.py --data-dir ../Data --output-dir ../frontend/public/models
```

### 15.2 Production Deployment

**Backend** (systemd service):
```ini
[Unit]
Description=AzerothCore Armory API
After=network.target mysql.service

[Service]
User=dr3am
WorkingDirectory=/home/dr3am/armory/backend
EnvironmentFile=/home/dr3am/armory/.env
ExecStart=/home/dr3am/armory/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**Frontend** (Nginx):
```nginx
server {
    listen 5000;
    root /home/dr3am/armory/frontend/dist;
    index index.html;

    # API proxy to backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
    }

    # Static models with long cache
    location /models/ {
        alias /home/dr3am/armory/frontend/dist/models/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Build frontend for production:
```bash
cd frontend && npm run build  # Output in dist/
```

---

## 16. Troubleshooting

### Common Issues

**Face appears on hair/cape/other meshes**
- Cause: All meshes share the skin atlas texture, but hair/cape meshes should use different textures.
- Fix: Ensure GLB nodes are named `geoset_{id}_{textype}` and the frontend only applies the composited skin atlas to `_skin` type meshes. Hair meshes should load their own texture from `/api/model-hair-texture/{name}`.

**Face is black/missing**
- Cause: Face textures not being composited, or wrong CharSections lookup.
- Fix: Check `CharSectionsDB.get_face_textures()` returns valid paths. Verify the face textures exist in MPQ archives.

**Face is wrong color (blue, brown, etc.)**
- Cause: Scalp/hair texture overwriting face region with opaque pixels.
- Fix: Verify `get_scalp_textures()` returns `(result[1], result[2])` NOT `(result[0], result[1])`. tex1 is HairModelTexture (fully opaque, NOT for compositing).

**Hair texture is fully opaque, covering face**
- Cause: BLP alpha channel not being read. Palettized BLP stores alpha separately.
- Fix: Ensure BLP decoder reads alpha from the separate block after color indices, based on `alpha_depth` (8/4/1 bit).

**Texture generation takes 89+ seconds**
- Cause: Opening and closing MPQ archives for every texture lookup.
- Fix: Use persistent `_mpq_pool` that keeps archive handles open.

**Cloak appears when not equipped**
- Cause: Default cloak geoset set to 1501 (short cloak) instead of 1500 (no cloak).
- Fix: Default geosets for "hidden" items should use the base ID (1500, 1200, 1800, 2700, 2600).

**Light brown/untextured models**
- Cause: Texture generation API timing out or erroring, frontend falls back to embedded GLB texture.
- Fix: Check uvicorn logs for errors. Verify MPQ files exist in Data directory.

**Models not centered or scaled correctly**
- Cause: Bounding box calculation includes hidden geoset meshes.
- Fix: Recalculate bounding box AFTER applying geoset visibility filters.

### Debug Commands

```bash
# Check if backend is running
curl -s http://127.0.0.1:8000/api/characters | python -m json.tool

# Test texture generation
curl -s -o /tmp/test_tex.png http://127.0.0.1:8000/api/model-texture/CharName
# View: open /tmp/test_tex.png

# Test hair texture
curl -s -o /tmp/test_hair.png http://127.0.0.1:8000/api/model-hair-texture/CharName

# Check geoset computation
curl -s http://127.0.0.1:8000/api/model-geosets/CharName | python -m json.tool

# Inspect GLB node names
python -c "
from pygltflib import GLTF2
g = GLTF2.load('frontend/public/models/characters/human_male.glb')
for n in g.nodes:
    print(n.name)
"

# Check backend logs
tail -f /tmp/uvicorn.log

# Clear texture cache
rm -rf frontend/public/models/cache/*.png
```

---

## Appendix: Race/Model Reference

| Race ID | Name | MPQ Dir | Model Key |
|---------|------|---------|-----------|
| 1 | Human | Human | human_male / human_female |
| 2 | Orc | Orc | orc_male / orc_female |
| 3 | Dwarf | Dwarf | dwarf_male / dwarf_female |
| 4 | Night Elf | NightElf | nightelf_male / nightelf_female |
| 5 | Undead | Scourge | undead_male / undead_female |
| 6 | Tauren | Tauren | tauren_male / tauren_female |
| 7 | Gnome | Gnome | gnome_male / gnome_female |
| 8 | Troll | Troll | troll_male / troll_female |
| 10 | Blood Elf | BloodElf | bloodelf_male / bloodelf_female |
| 11 | Draenei | Draenei | draenei_male / draenei_female |

> Note: Race ID 9 is unused in WotLK. Blood Elf starts at 10.

### Texture Type per Race

| Race | Skin | Hair | Env | Cape | Skin Extra |
|------|------|------|-----|------|------------|
| Human M | 38 | 17 | 1 | 5 | 0 |
| Human F | 35 | 24 | 1 | 5 | 0 |
| Night Elf M | 24 | 24 | 2 | 5 | 0 |
| Blood Elf F | 26 | 32 | 2 | 5 | 0 |
| Tauren M | 39 | 0 | 1 | 5 | **29** |
| Tauren F | 33 | 0 | 1 | 5 | **9** |
| Undead M | 32 | 14 | 2 | 5 | 0 |
| Draenei F | 32 | 18 | 1 | 5 | 0 |

Tauren models have no hair-type meshes (their "hair" is horn/mane variants in skin_extra). All races have exactly 5 cape-type meshes (cloak variants).
