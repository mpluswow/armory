# Technical Reference

This document covers the internal data formats, coordinate systems, and algorithms used by the extraction pipeline and backend.

---

## WoW M2 Model Format

M2 (also called MD20) is Blizzard's binary model format used for characters, creatures, and items in WotLK 3.3.5a.

### File Identification

First 4 bytes: `4D 44 32 30` = ASCII "MD20"

### Header Key Offsets

All offsets from the start of the file:

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0x00 | 4 | magic | "MD20" |
| 0x04 | 4 | version | File version (must be 264 for WotLK) |
| 0x14 | 4 | nVertices | Number of vertices |
| 0x18 | 4 | ofsVertices | Byte offset to vertex array |
| 0x1C | 4 | ofsSequences | **M2Array** for animation sequences |
| 0x2C | 4 | ofsBones | **M2Array** for bone definitions |
| 0x30 | 4 | nBones | Bone count |
| 0x48 | 4 | nTextures | Number of textures |
| 0x4C | 4 | ofsTextures | Byte offset to texture definitions |
| 0x88 | 4 | nTextureCombos | Texture combo count |
| 0x8C | 4 | ofsTextureCombos | Byte offset to texture combos |
| 0xF0 | 4 | nAttachments | Attachment point count |
| 0xF4 | 4 | ofsAttachments | Byte offset to attachment definitions |

> **Important:** Bone data is at `0x2C`, not `0x6C` as some older documentation states.

### M2Array Structure

Many fields in the M2 header use the M2Array structure:
```
Offset +0: uint32  count
Offset +4: uint32  offset (byte offset from file start)
```

### Vertex Structure (48 bytes)

```
+0  float[3]  position        WoW coordinate space
+12 uint8[4]  bone_weights    Skinning weights, sum = 255
+16 uint8[4]  bone_indices    Indices into bone array
+20 float[3]  normal
+32 float[2]  uv_coord_1
+40 float[2]  uv_coord_2
```

### Bone Structure (88 bytes)

```
+0  int32     boneId          DBC bone ID (-1 if none)
+4  uint32    flags
+8  int16     parent          Parent bone index (-1 for root)
+10 uint16    submeshId
+12 uint32    unknown[2]
+16 M2Track   translation     Animation track (vec3)  [offset 0x10]
+32 M2Track   rotation        Animation track (quat)  [offset 0x20] (M2CompQuat!)
+48 M2Track   scale           Animation track (vec3)  [offset 0x30]
+76 float[3]  pivot           Absolute world-space pivot point
```

> **Critical:** Bone pivot points are in **absolute model space**, not relative to the parent bone.

### M2Track Structure

```
+0  uint16    interpolation_type
+2  int16     global_sequence  (-1 = no global sequence)
+4  M2Array   timestamps       (uint32 per frame)
+12 M2Array   values           (varies by type)
```

### Animation Sequences

The sequence array is at the offset stored in the M2Array at header `0x1C`. Each sequence entry is 64 bytes:

```
+0  uint16    animId       Animation ID (0 = Stand)
+2  uint16    subAnimId
+4  uint32    length       Duration in milliseconds
...
```

To find the Stand animation frame:
```python
def _find_stand_anim_index(m2_data):
    # Read M2Array at 0x1C
    n_seqs, ofs_seqs = struct.unpack_from('<II', m2_data, 0x1C)
    for i in range(n_seqs):
        anim_id = struct.unpack_from('<H', m2_data, ofs_seqs + i * 64)[0]
        if anim_id == 0:  # Stand
            return i
    return 0  # fallback
```

---

## M2CompQuat (Compressed Quaternion)

Bone rotation tracks store quaternions as `M2CompQuat` — four signed 16-bit integers.

### Decompression Formula

```python
def decompress_quat(v: int) -> float:
    if v < 0:          # negative int16
        return (v + 32768) / 32767.0 - 1.0
    else:
        return (v - 32767) / 32767.0
```

Result range: [-1.0, 1.0]. Apply to each of the four components (x, y, z, w).

> This decompression formula was the subject of a long debugging session. The M2CompQuat stores values differently for negative vs positive ranges.

---

## Attachment Points

M2 attachment entries are 40 bytes each:

```
+0  uint32    id          Attachment slot ID
+4  uint16    bone        Index of the parent bone
+6  uint16    unknown
+8  float[3]  position    In WoW model space (absolute)
+20 M2Track   visibility  Not used by this application
```

### Attachment ID Mapping

| ID | Purpose |
|----|---------|
| 0 | Shield mount (left hand, non-weapon off-hand) |
| 1 | Right hand (main-hand weapon grip) |
| 2 | Left hand (off-hand weapon grip / dual-wield) |
| 5 | Right shoulder pauldron |
| 6 | Left shoulder pauldron |
| 11 | Head attachment (helm) |
| 26 | Back (sheathed weapon) |
| 27 | Right hip (sheathed weapon) |
| 28 | Left hip (sheathed weapon) |

---

## Coordinate System Conversion

WoW and glTF (OpenGL convention) use different right-handed coordinate systems.

### WoW M2 Space
- X = right
- Y = forward (into screen)
- Z = up

### glTF / Three.js Space
- X = right
- Y = up
- Z = towards viewer (out of screen)

### Conversion

Applied to every vertex position, vertex normal, and attachment point position:

```python
gltf_x = wow_x
gltf_y = wow_z      # WoW Z becomes glTF Y (up)
gltf_z = -wow_y     # WoW Y becomes -glTF Z (forward inverted)
```

For quaternions (rotations), the conversion is:
```python
gltf_qx = wow_qx
gltf_qy = wow_qz
gltf_qz = -wow_qy
gltf_qw = wow_qw    # scalar unchanged
```

### Character Model Rotation

After coordinate conversion, character models face away from the viewer (they face +Z in WoW, which becomes -Z in glTF). The `ModelViewer` component compensates with an additional 180° rotation around the Y axis.

---

## Pivot-Sandwich Transform

Local bone transforms use the "pivot sandwich" pattern:

```
Local = T(pivot + translation) * R(rotation) * S(scale) * T(-pivot)
World = parent.World * Local
```

Where:
- `T(v)` = translation matrix
- `R(q)` = rotation matrix from quaternion
- `S(v)` = scale matrix
- `pivot` = bone's absolute model-space pivot point

Since pivots are in **absolute** model space, the `-pivot` term at the end un-does the pivot offset, the transform is applied, then the pivot is re-added — keeping child bone positions correct relative to the model origin.

---

## BLP Texture Format

BLP is Blizzard's proprietary texture format. WotLK uses BLP2 (header magic: `BLP2`).

### Header

```
+0  char[4]   magic         "BLP2"
+4  uint32    type          0=JPEG, 1=Direct
+8  uint8     encoding      1=uncompressed, 2=DXT, 3=raw BGRA
+9  uint8     alphaDepth    0, 1, 4, or 8
+10 uint8     alphaEncoding 0=DXT1, 1=DXT3, 7=DXT5
+11 uint8     hasMips
+12 uint32    width
+16 uint32    height
+20 uint32[16] mipOffsets
+84 uint32[16] mipSizes
+148 uint32[256] palette   (only for encoding=1)
```

### Decoding by Encoding Type

| Encoding | Alpha Depth | Compression |
|----------|-------------|-------------|
| 1 | 0 | Palettized, no alpha |
| 1 | 1 | Palettized, 1-bit alpha |
| 1 | 8 | Palettized, 8-bit alpha |
| 2 | any | DXT1/DXT3/DXT5 (from alphaEncoding) |
| 3 | any | Uncompressed BGRA |

DXT1: 4 bpp, 1-bit alpha
DXT3: 8 bpp, explicit 4-bit alpha
DXT5: 8 bpp, interpolated alpha (best quality)

All decoded images are returned as RGBA PIL Images.

---

## DBC File Format

DBC (DataBase Client) files store static game data (item stats, race info, animation sequences, etc.). They are in the locale MPQ archives.

### Header

```
+0  char[4]  magic          "WDBC"
+4  uint32   recordCount
+8  uint32   fieldCount
+12 uint32   recordSize      (fieldCount × 4)
+16 uint32   stringBlockSize
```

### Layout

```
Header (20 bytes)
Records (recordCount × recordSize bytes)
String block (stringBlockSize bytes)
```

Strings are stored as offsets into the string block (a flat zero-terminated string pool). Integer field at byte offset `fieldIndex * 4` within a record.

### DBC Files Used

| DBC | MPQ Location | Fields Used |
|-----|-------------|-------------|
| `ItemDisplayInfo.dbc` | `patch.MPQ` | displayId → models, textures, geosets, helmet vis |
| `CharSections.dbc` | `locale-enUS.MPQ` | race/sex/section → skin, face, hair texture paths |
| `CharHairGeosets.dbc` | `locale-enUS.MPQ` | race/sex/hairStyle → geoset ID |
| `CharacterFacialHairStyles.dbc` | `locale-enUS.MPQ` | race/sex/facialStyle → geoset IDs |
| `HelmetGeosetVisData.dbc` | `locale-enUS.MPQ` | visId → which geosets to hide |

---

## MPQ Archive Load Order

Files in later patches override files in earlier archives. The pipeline searches in this order (earlier = higher priority):

```
Data/patch-3.MPQ
Data/patch-2.MPQ
Data/patch.MPQ
Data/Expansion.MPQ
Data/Lichking.MPQ
Data/common-2.MPQ
Data/common.MPQ
Data/enUS/patch-enUS-3.MPQ
Data/enUS/patch-enUS-2.MPQ
Data/enUS/patch-enUS.MPQ
Data/enUS/locale-enUS.MPQ
```

Not all of these need to exist. The pipeline reads whichever are present.

---

## Geoset ID System

Character models contain many overlapping submeshes. The M2 format uses "geosets" to group submeshes that represent the same body region at different detail levels or equipment states.

### Geoset ID Ranges

| Range | Body part |
|-------|-----------|
| 0 | Base character (always visible) |
| 100–199 | Hair |
| 200–299 | Extra-skin / face details |
| 300–399 | Face / facial hair |
| 400–499 | Gloves / hands |
| 500–599 | Boots / feet |
| 600–699 | Ears |
| 700–799 | Sleeves |
| 800–899 | Pants legs |
| 900–999 | Leg cuffs |
| 1000–1099 | Chest |
| 1100–1199 | Trousers |
| 1200–1299 | Tabard |
| 1300–1399 | Upper trousers |
| 1400–1499 | Unknown |
| 1500–1599 | Cloak / cape |
| 1600–1699 | Unknown |
| 1700–1799 | Unknown |
| 1800–1899 | Belt |
| 2000–2099 | Feet (bare vs shoe) |
| 2300–2399 | Hands attachment |
| 2600–2699 | Shoulders |
| 2700–2799 | Helm |

### Equipment → Active Geoset Calculation

For each equipped item:
1. Look up the item's `displayId` in `ItemDisplayInfo.dbc`
2. Get geoset groups `(g1, g2, g3)` from the DBC record
3. Add `base + g_n` to the active set for each triggered body region

For body regions with no equipment in that slot, the default geoset ID (base + 0 or base + 1) is used.

---

## Filesystem Cache Layout

All runtime-generated assets are cached in `frontend/public/models/cache/`. Filenames are deterministic based on the generation parameters.

### Texture Cache Keys

```
{12-char MD5 hash}.png
```

The MD5 is computed from:
```
{race}_{gender}_{skin}_{face}_{hairStyle}_{hairColor}_{facialStyle}_{sorted displayIds}
```

### Item Model Cache Keys

```
item_{displayId}_{side}[_{RaceGender}].glb
```

Examples:
- `item_40343_right.glb` — right-hand sword
- `item_41628_left_NiM.glb` — Night Elf Male helm

### Special Texture Keys

```
hair_{race}_{gender}_{hairStyle}_{hairColor}   → {hash}.png
extraskin_{race}_{gender}_{skin}               → {hash}.png
cape_{displayId}                               → {hash}.png
```
