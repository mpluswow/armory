# Extraction Pipeline

The extraction pipeline is a set of Python tools that read raw game assets from WoW MPQ archives and convert them into formats the web application can use. It is a **one-time setup step**; after running it once you only need to re-run if you want to regenerate models.

---

## Overview

```
Data/*.MPQ  (WoW 3.3.5a archives)
     │
     │  StormLib (libstorm.so via ctypes)
     ▼
extract_models.py
     │
     ├── Reads M2 character models
     ├── Reads skin files (.skin)
     ├── Decodes BLP textures
     ├── Converts WoW coordinates → glTF coordinates
     ├── Builds GLB files (per race/gender)
     └── Extracts attachment point positions
     │
     └── Output: frontend/public/models/
                   characters/*.glb   (20 models)
                   manifest.json
                   attachments.json

gear_compositor.py  (called at runtime by the backend, not directly)
     │
     ├── Reads DBC files (CharSections, ItemDisplayInfo, etc.)
     ├── Decodes BLP skin/armor textures
     ├── Composites layers onto 512×512 skin atlas
     └── Computes geoset visibility from equipped items
```

---

## Running the Extraction

```bash
tools/venv/bin/python tools/extract_models.py \
  --data-dir ./Data \
  --output-dir ./frontend/public/models
```

Expected output (about 1–5 minutes depending on hardware):
```
Extracting nightelf_male...   OK  (models/characters/nightelf_male.glb)
Extracting nightelf_female... OK  (models/characters/nightelf_female.glb)
...
Writing manifest.json
Extracting attachments...     OK  (models/attachments.json)
Done. 20 models extracted.
```

---

## StormLib (`libstorm.so`)

### What it is

[StormLib](https://github.com/ladislav-zezula/StormLib) is a C++ library for reading Blizzard's MPQ archive format. The tools use a compiled shared library (`libstorm.so`) loaded at runtime via Python's `ctypes`.

A precompiled x86_64 Linux binary is bundled in `tools/libstorm.so`. `start.sh` tests whether it loads correctly and rebuilds it from source if not.

### ctypes bindings

`extract_models.py` binds the following StormLib functions:

| Function | Purpose |
|----------|---------|
| `SFileOpenArchive` | Open an MPQ archive |
| `SFileCloseArchive` | Close an archive |
| `SFileOpenFileEx` | Open a file inside an archive |
| `SFileGetFileSize` | Get size of an open file |
| `SFileReadFile` | Read bytes from an open file |
| `SFileCloseFile` | Close an open file handle |
| `SFileFindFirstFile` | Begin iterating files in an archive |
| `SFileFindNextFile` | Continue iterating |
| `SFileFindClose` | End iteration |

### Persistent MPQ Pool

WoW MPQ archives can be 2–10 GB each. Opening and closing them for every request is prohibitively slow. The tools maintain a global pool:

```python
_mpq_pool: dict[str, MPQArchive] = {}

def _get_mpq(mpq_path: str) -> MPQArchive | None:
    if mpq_path not in _mpq_pool:
        _mpq_pool[mpq_path] = MPQArchive(mpq_path)
    return _mpq_pool[mpq_path]
```

The backend calls `_warmup_mpq_pool()` at startup to pre-open all archives so the first texture request is fast.

---

## M2 File Format

M2 is Blizzard's proprietary binary model format. The extraction pipeline reads the parts needed for GLB conversion.

### Header Layout (relevant fields)

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0x00 | Magic | char[4] | "MD20" |
| 0x04 | Version | uint32 | File version |
| 0x14 | nVertices | uint32 | Vertex count |
| 0x18 | ofsVertices | uint32 | Vertex data offset |
| 0x1C | ofsSequences | uint32 | Animation sequence array (M2Array) |
| 0x2C | ofsBones | uint32 | **Bone data array** |
| 0x48 | nTextures | uint32 | Texture count |
| 0x4C | ofsTextures | uint32 | Texture definition offset |
| 0xF0 | nAttachments | uint32 | Attachment point count |
| 0xF4 | ofsAttachments | uint32 | Attachment data offset |

> Note: Bone data is at offset **0x2C**, not 0x6C — this was a critical bug discovered during development.

### Vertex Layout (48 bytes each)

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 0 | position | float[3] | XYZ in WoW coordinate space |
| 12 | bone_weights | uint8[4] | Skinning weights (sum = 255) |
| 16 | bone_indices | uint8[4] | Bone indices |
| 20 | normal | float[3] | Vertex normal |
| 32 | tex_coords | float[2] | Primary UV |
| 40 | tex_coords2 | float[2] | Secondary UV |

### Bone Layout (88 bytes each)

| Offset | Field | Type | Description |
|--------|-------|------|-------------|
| 8 | parent | int16 | Parent bone index (-1 = root) |
| 0x10 | translation | M2Track | Position animation track |
| 0x24 | rotation | M2Track | Quaternion animation track |
| 0x38 | scale | M2Track | Scale animation track |
| 0x4C (76) | pivot | float[3] | Pivot point in **absolute** model space |

### Coordinate System Conversion

WoW and glTF use different coordinate systems:

| Axis | WoW | glTF |
|------|-----|------|
| X | Right | Right |
| Y | Forward | Up |
| Z | Up | Towards viewer (forward) |

Conversion applied to every vertex position, normal, and attachment position:
```python
gltf_x = wow_x
gltf_y = wow_z
gltf_z = -wow_y
```

---

## Skin Files

A `.skin` file accompanies each M2 and defines how vertices are grouped into submeshes (geosets). Each geoset maps to a different body region or equipment layer.

### Skin Batch to Texture Type Mapping

Each skin batch entry is mapped to a texture type that determines which material applies at runtime:

| Type ID | Name | Applied texture |
|---------|------|-----------------|
| 0 | hardcoded | fixed / skin |
| 1 | skin | character skin atlas (`/api/model-texture/`) |
| 2 | cape | cape texture (`/api/model-cape-texture/`) |
| 6 | hair | hair mesh texture (`/api/model-hair-texture/`) |
| 8 | skin_extra | extra skin layer (`/api/model-extra-skin-texture/`) |

### Geoset Node Naming

Each submesh node in the output GLB is named:
```
geoset_{id}_{textype}
```

Examples:
- `geoset_1_skin` — base body skin mesh
- `geoset_101_hair` — hair geometry
- `geoset_401_skin` — glove geometry (skin-type texture)
- `geoset_1501_cape` — cloak geometry

The frontend reads these names to determine which texture to apply and whether to show or hide the node based on equipped items.

---

## BLP Texture Decoding

BLP is Blizzard's proprietary texture format. The pipeline includes a pure-Python BLP decoder that supports all variants used in WotLK.

### Supported Encodings

| Encoding | Description | Compression |
|----------|-------------|-------------|
| 1 | Palettized | Uncompressed palette + alpha |
| 2 (type 1) | DXT1 | 4 bpp block compression, 1-bit alpha |
| 2 (type 2) | DXT3 | 8 bpp, explicit 4-bit alpha |
| 2 (type 3) | DXT5 | 8 bpp, interpolated alpha |
| 3 | Raw | Uncompressed BGRA |

Alpha depths supported: 0-bit, 1-bit, 4-bit, 8-bit.

All decoded images are returned as RGBA `PIL.Image` objects.

---

## GLB Output Format

Each character model is written as a single self-contained GLB (binary glTF) file.

### Buffer Layout

One binary buffer holds all data in this order:
1. Shared vertex attributes (positions, normals, UVs) — interleaved
2. Per-submesh index buffers

An optional embedded PNG texture is included for item models that have a baked texture. Character models use dynamic runtime textures from the API.

### Materials

Two materials are defined per GLB:
- **Material 0** — "skin" material with embedded texture
- **Material 1** — "dynamic" material, no embedded texture; overridden at runtime

### Node Hierarchy

```
root (unnamed scene root)
└── geoset_0_skin
└── geoset_1_skin
└── geoset_101_hair
└── geoset_201_skin_extra
...
```

---

## gear_compositor.py

This module is imported by the backend at runtime; you do not run it directly. It handles:
- DBC file parsing
- Character skin atlas compositing
- Geoset visibility computation

### DBC Files Used

| DBC File | Purpose |
|----------|---------|
| `ItemDisplayInfo.dbc` | Maps display IDs to model names, texture names, geoset groups |
| `CharSections.dbc` | Maps race/gender/style/color → skin, face, hair, facial hair texture paths |
| `CharHairGeosets.dbc` | Maps (race, sex, hairStyle) → geoset ID |
| `CharacterFacialHairStyles.dbc` | Maps (race, sex, facialStyle) → geoset IDs (up to 5) |
| `HelmetGeosetVisData.dbc` | Maps helmet visibility data → which geosets to hide |

DBC files are stored in the locale MPQs (e.g., `enUS/locale-enUS.MPQ`). The module searches for them in patch priority order.

### Skin Atlas Layout (512×512)

Character skin textures are assembled onto a fixed 512×512 atlas:

```
┌──────────────────┬──────────────────┐
│  Upper Arm       │  Upper Chest     │
│  (0,0) 256×128   │  (256,0) 256×128 │
├──────────────────┤──────────────────┤
│  Lower Arm       │  Lower Chest     │
│  (0,128) 256×128 │  (256,128) 256×64│
├──────────────────┼──────────────────┤
│  Hands           │  Upper Leg       │
│  (0,256) 256×64  │  (256,192) 256×128│
├──────────────────┼──────────────────┤
│  Face Upper      │  Lower Leg       │
│  (0,320) 256×64  │  (256,320) 256×128│
├──────────────────┼──────────────────┤
│  Face Lower      │  Foot            │
│  (0,384) 256×128 │  (256,448) 256×64│
└──────────────────┴──────────────────┘
```

### Compositing Order

Layers are blended using Porter-Duff SourceOver alpha compositing:

1. Base skin texture (CharSections section=0, skin colour variation)
2. Face lower + face upper (section=1, face variation)
3. Facial hair lower + upper (section=2, if facialStyle > 0)
4. Scalp/hair textures (section=3, hair style + colour on head region)
5. Equipped body armor per slot, in layer order:
   - Shirt (slot 3)
   - Wrist (slot 8)
   - Legs (slot 6)
   - Feet (slot 7)
   - Chest (slot 4)
   - Hands (slot 9)
   - Tabard (slot 18)

### Geoset Visibility Logic

Equipment controls which submeshes are shown or hidden via geoset IDs. The mapping from equipment slot to geoset group is:

| Slot | Body region | Geoset base | Notes |
|------|-------------|-------------|-------|
| 0 | Head | 2700 | Helm; also triggers HelmetGeosetVisData |
| 2 | Shoulders | 2600 | |
| 3 | Shirt | 800, 1000 | Sleeves, chest |
| 4 | Chest | 800, 1000, 1300 | Sleeves, chest, trousers |
| 5 | Belt | 1800 | |
| 6 | Legs | 1100, 900, 1300 | Pants, leg cuffs, trousers |
| 7 | Feet | 500, 2000 | Boots, feet |
| 9 | Hands/Gloves | 400, 2300 | Gloves, hands attachment |
| 14 | Back/Cape | 1500 | Cloak |
| 18 | Tabard | 1200 | |

Default geosets (nothing equipped):
```
gloves: 401       (bare hands)
boots: 501        (bare feet)
sleeves: 801      (no sleeves — bare arms)
chest: 1001       (bare torso)
pants: 1101       (underwear)
tabard: 1200      (no tabard)
cloak: 1501       (no cloak, back panel visible)
belt: 1800        (no belt)
shoulders: 2600   (no shoulders)
helm: 2700        (no helm — hair visible)
```

The actual geoset ID = base + group value from ItemDisplayInfo.dbc for the equipped item.

---

## Output Files

| File | Description |
|------|-------------|
| `frontend/public/models/characters/{race}_{gender}.glb` | 20 character GLBs |
| `frontend/public/models/manifest.json` | Maps `"{race}_{gender}"` → `"characters/{race}_{gender}.glb"` |
| `frontend/public/models/attachments.json` | Per-model attachment point positions and identity rotations |

### `attachments.json` Structure

```json
{
  "human_male": {
    "0":  { "position": [-0.074, 1.036, -0.575], "rotation": [0,0,0,1] },
    "1":  { "position": [ 0.016, 0.827,  0.059], "rotation": [0,0,0,1] },
    "2":  { "position": [-0.016, 0.827,  0.059], "rotation": [0,0,0,1] },
    "5":  { "position": [ 0.170, 1.370, -0.053], "rotation": [0,0,0,1] },
    "6":  { "position": [-0.170, 1.370, -0.053], "rotation": [0,0,0,1] },
    "11": { "position": [ 0.000, 1.860,  0.010], "rotation": [0,0,0,1] }
  },
  "human_female": { ... },
  ...
}
```

> Rotations are identity `[0,0,0,1]` for all models. Bone rotation extraction from the Stand animation was researched but reverted due to issues with the decompression formula and parent-chain accumulation. Item orientation is therefore a known limitation.

### `manifest.json` Structure

```json
{
  "human_male":       "characters/human_male.glb",
  "human_female":     "characters/human_female.glb",
  "orc_male":         "characters/orc_male.glb",
  "orc_female":       "characters/orc_female.glb",
  "dwarf_male":       "characters/dwarf_male.glb",
  "dwarf_female":     "characters/dwarf_female.glb",
  "nightelf_male":    "characters/nightelf_male.glb",
  "nightelf_female":  "characters/nightelf_female.glb",
  "undead_male":      "characters/undead_male.glb",
  "undead_female":    "characters/undead_female.glb",
  "tauren_male":      "characters/tauren_male.glb",
  "tauren_female":    "characters/tauren_female.glb",
  "gnome_male":       "characters/gnome_male.glb",
  "gnome_female":     "characters/gnome_female.glb",
  "troll_male":       "characters/troll_male.glb",
  "troll_female":     "characters/troll_female.glb",
  "bloodelf_male":    "characters/bloodelf_male.glb",
  "bloodelf_female":  "characters/bloodelf_female.glb",
  "draenei_male":     "characters/draenei_male.glb",
  "draenei_female":   "characters/draenei_female.glb"
}
```
