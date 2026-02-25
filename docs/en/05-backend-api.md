# Backend API Reference

The backend is a FastAPI application listening on `http://127.0.0.1:8000`. All endpoints are read-only (`GET`) and prefixed with `/api`.

The Vite dev server proxies all `/api/*` requests to `:8000` transparently, so the frontend calls paths like `/api/character` without specifying the host.

---

## `GET /api/characters`

List all characters in the database, sorted by level descending then name ascending.

### Query Parameters

| Parameter | Type | Default | Constraints | Description |
|-----------|------|---------|-------------|-------------|
| `limit` | integer | `100` | 1–500 | Maximum number of characters to return |

### Response `200 OK`

```json
{
  "count": 3,
  "characters": [
    {
      "name": "Thrall",
      "race": 2,
      "class": 7,
      "level": 80,
      "faction": "Horde"
    },
    {
      "name": "Arthas",
      "race": 1,
      "class": 6,
      "level": 80,
      "faction": "Alliance"
    }
  ]
}
```

### Faction Logic

| Race IDs | Faction |
|----------|---------|
| 1, 3, 4, 7, 11 | Alliance |
| 2, 5, 6, 8, 10 | Horde |

### Caching

No in-memory cache on this endpoint. Results reflect the current database state on every call.

---

## `GET /api/character`

Detailed character data including all equipped items with stats.

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Character name (case-sensitive, minimum 1 character) |

### Response `200 OK`

```json
{
  "guid": 1,
  "name": "Arthas",
  "race": 1,
  "class": 6,
  "gender": 0,
  "level": 80,
  "skin": 0,
  "face": 0,
  "hairStyle": 3,
  "hairColor": 2,
  "facialStyle": 1,
  "equipment": [
    {
      "slot": 0,
      "entry": 40186,
      "displayId": 41628,
      "name": "Helm of the Lost Conqueror",
      "quality": 4,
      "itemLevel": 213,
      "requiredLevel": 80,
      "itemType": "Head",
      "stats": [
        "+1208 Armor",
        "+89 Stamina",
        "+67 Intellect",
        "+45 Critical Strike Rating",
        "+50 Haste Rating"
      ],
      "description": "",
      "icon": "40186"
    }
  ]
}
```

### Character Fields

| Field | Type | Description |
|-------|------|-------------|
| `guid` | integer | Unique character ID |
| `name` | string | Character name |
| `race` | integer | Race ID (1–11, see table below) |
| `class` | integer | Class ID (1–11, see table below) |
| `gender` | integer | 0 = Male, 1 = Female |
| `level` | integer | Character level (1–80) |
| `skin` | integer | Skin colour variation index |
| `face` | integer | Face style index |
| `hairStyle` | integer | Hair style index |
| `hairColor` | integer | Hair colour index |
| `facialStyle` | integer | Facial hair / feature index |

### Equipment Item Fields

| Field | Type | Description |
|-------|------|-------------|
| `slot` | integer | Equipment slot 0–18 |
| `entry` | integer | Item template ID (`item_template.entry`) |
| `displayId` | integer | Visual display ID (`item_template.displayid`) |
| `name` | string | Item name |
| `quality` | integer | 0=Poor, 1=Common, 2=Uncommon, 3=Rare, 4=Epic, 5=Legendary, 6=Artifact, 7=Heirloom |
| `itemLevel` | integer\|null | Item level |
| `requiredLevel` | integer\|null | Required character level |
| `itemType` | string | Slot name ("Head", "Chest", "Main Hand", etc.) |
| `stats` | string[] | Human-readable stat strings |
| `description` | string | Item flavour text |
| `icon` | string | Item entry ID string (used by frontend to fetch icon) |

### Equipment Slot Numbers

| Slot | Name | Slot | Name |
|------|------|------|------|
| 0 | Head | 10 | Finger 1 |
| 1 | Neck | 11 | Finger 2 |
| 2 | Shoulders | 12 | Trinket 1 |
| 3 | Shirt | 13 | Trinket 2 |
| 4 | Chest | 14 | Back |
| 5 | Waist | 15 | Main Hand |
| 6 | Legs | 16 | Off Hand |
| 7 | Feet | 17 | Ranged |
| 8 | Wrist | 18 | Tabard |
| 9 | Hands | | |

### Race IDs

| ID | Race | Faction |
|----|------|---------|
| 1 | Human | Alliance |
| 2 | Orc | Horde |
| 3 | Dwarf | Alliance |
| 4 | Night Elf | Alliance |
| 5 | Undead | Horde |
| 6 | Tauren | Horde |
| 7 | Gnome | Alliance |
| 8 | Troll | Horde |
| 10 | Blood Elf | Horde |
| 11 | Draenei | Alliance |

### Class IDs

| ID | Class | Colour |
|----|-------|--------|
| 1 | Warrior | `#C79C6E` |
| 2 | Paladin | `#F58CBA` |
| 3 | Hunter | `#ABD473` |
| 4 | Rogue | `#FFF569` |
| 5 | Priest | `#FFFFFF` |
| 6 | Death Knight | `#C41F3B` |
| 7 | Shaman | `#0070DE` |
| 8 | Mage | `#69CCF0` |
| 9 | Warlock | `#9482C9` |
| 11 | Druid | `#FF7D0A` |

### Error Responses

```json
// 404 — character not found
{ "detail": "Character \"Unknownchar\" not found" }

// 422 — missing required parameter
{ "detail": [{ "loc": ["query", "name"], "msg": "field required" }] }
```

### Caching

Results are cached in a `TTLCache` (max 256 entries, 30-second TTL) keyed by lowercased character name.

---

## `GET /api/model-texture/{name}`

Generate and return a composited character skin texture PNG. This bakes together:
- Base skin colour
- Face textures (lower + upper)
- Facial hair / feature textures
- Scalp and hair-colour overlay
- Equipped body armour pieces (shirt, chest, legs, feet, hands, tabard)

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string | Character name (case-sensitive) |

### Response `200 OK`

`Content-Type: image/png` — a 512×512 RGBA PNG texture.

### Caching

The cache key is an MD5 hash of:
```
{race}_{gender}_{skin}_{face}_{hairStyle}_{hairColor}_{facialStyle}_{sorted display IDs}
```

The PNG is written to `frontend/public/models/cache/{hash}.png` and served directly on subsequent requests.

### Error Responses

```json
{ "error": "Character not found" }      // 404
{ "error": "Could not generate texture" } // 500
```

---

## `GET /api/model-hair-texture/{name}`

Return the hair **mesh** texture for the character's selected hair style and colour. This texture is applied to the `geoset_*_hair` submeshes in the 3D model — it is distinct from the scalp overlay which is baked into the skin atlas.

### Response `200 OK`

`Content-Type: image/png`

### Error Responses

```json
{ "error": "Hair texture not found" }   // 404 — valid for race/style combos that have none
{ "error": "DBC not available" }        // 500 — locale DBC missing
```

---

## `GET /api/model-extra-skin-texture/{name}`

Return a race-specific extra-skin texture applied to `geoset_*_skin_extra` meshes. Used for:
- Tauren: fur detail
- Undead: bone overlay
- Some other race-specific skin features

Returns `404` for races that have no extra skin texture.

### Response `200 OK`

`Content-Type: image/png`

---

## `GET /api/model-cape-texture/{name}`

Return the cape/cloak texture for the character's equipped back item (slot 14). Loaded from `Item\ObjectComponents\Cape\` inside the MPQ.

Returns `404` if no cape is equipped or if the texture cannot be located.

### Response `200 OK`

`Content-Type: image/png`

---

## `GET /api/model-geosets/{name}`

Return the list of geoset IDs that should be **visible** for this character based on their equipment and appearance. The frontend uses this to toggle visibility of submesh nodes in the GLB.

### Response `200 OK`

```json
{
  "geosets": [0, 100, 200, 300, 401, 501, 806, 1011, 1101, 1500, 1800, 2600, 2700]
}
```

Each integer corresponds to a `geoset_{id}_*` node in the character GLB. Any node whose ID is **not** in this list should be hidden.

### Error Responses

```json
{ "error": "DBC data not available" }  // 500 — ItemDisplayInfo.dbc missing
```

---

## `GET /api/item-model/{displayId}`

Extract and return a 3D item model as a GLB file. Supports weapons, shields, shoulders, and helms. The model is extracted from MPQ on first request and cached to disk.

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `displayId` | integer | Item display ID from `item_template.displayid` |

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `side` | string | `"left"` | Which model to use from `ItemDisplayInfo.dbc`: `"left"` or `"right"` |
| `race` | integer | `0` | Race ID — required for helmets to select race-specific model variant |
| `gender` | integer | `0` | Gender (0=male, 1=female) — used with `race` for helms |

### Race Model Suffixes (helms only)

| Race ID | Suffix | Example |
|---------|--------|---------|
| 1 (Human) | `_HuM` / `_HuF` | `Helm_T10_01_HuM` |
| 2 (Orc) | `_OrM` / `_OrF` | |
| 3 (Dwarf) | `_DwM` / `_DwF` | |
| 4 (Night Elf) | `_NiM` / `_NiF` | |
| 5 (Undead) | `_ScM` / `_ScF` | |
| 6 (Tauren) | `_TaM` / `_TaF` | |
| 7 (Gnome) | `_GoM` / `_GoF` | |
| 8 (Troll) | `_TrM` / `_TrF` | |
| 10 (Blood Elf) | `_BeM` / `_BeF` | |
| 11 (Draenei) | `_DrM` / `_DrF` | |

### Response `200 OK`

`Content-Type: model/gltf-binary` — a GLB file.

### Cache Key

```
item_{displayId}_{side}[_{RaceGender}]
```

Cached as `frontend/public/models/cache/{key}.glb`.

### Error Responses

```json
{ "error": "DBC data not available" }         // 500
{ "error": "Display ID not found" }           // 404
{ "error": "No model name for this display ID" } // 404
{ "error": "Failed to extract item model" }   // 500
```

---

## `GET /api/character-attachments/{name}`

Return attachment point positions and the equipped items that should be rendered at each point. Used by the frontend to position 3D item models on the character.

### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string | Character name (case-sensitive) |

### Response `200 OK`

```json
{
  "attachments": {
    "0":  { "position": [-0.074, 1.036, -0.575], "rotation": [0.0, 0.0, 0.0, 1.0] },
    "1":  { "position": [ 0.016, 0.827,  0.059], "rotation": [0.0, 0.0, 0.0, 1.0] },
    "2":  { "position": [-0.016, 0.827,  0.059], "rotation": [0.0, 0.0, 0.0, 1.0] },
    "5":  { "position": [ 0.170, 1.370, -0.053], "rotation": [0.0, 0.0, 0.0, 1.0] },
    "6":  { "position": [-0.170, 1.370, -0.053], "rotation": [0.0, 0.0, 0.0, 1.0] },
    "11": { "position": [ 0.000, 1.860,  0.010], "rotation": [0.0, 0.0, 0.0, 1.0] }
  },
  "items": {
    "mainHand": {
      "displayId": 40343,
      "attachPoint": "1",
      "hasModel": true
    },
    "offHand": {
      "displayId": 40267,
      "attachPoint": "0",
      "hasModel": true
    },
    "shoulderRight": {
      "displayId": 45834,
      "attachPoint": "5",
      "side": "right",
      "hasModel": true
    },
    "shoulderLeft": {
      "displayId": 45834,
      "attachPoint": "6",
      "side": "left",
      "hasModel": true
    },
    "helm": {
      "displayId": 41628,
      "attachPoint": "11",
      "hasModel": true
    }
  },
  "race": 1,
  "gender": 0
}
```

### Attachment Point to Equipment Slot Mapping

| Attachment ID | Slot | Item |
|---------------|------|------|
| 0 | 16 (off-hand) | Shield mount / held item |
| 1 | 15 (main hand) | Right-hand weapon |
| 2 | 16 (off-hand) | Left-hand weapon (dual wield) |
| 5 | 2 (shoulders) | Right shoulder |
| 6 | 2 (shoulders) | Left shoulder |
| 11 | 0 (head) | Helm |

### Off-Hand Routing Logic

The off-hand item (slot 16) is routed to different attachment points depending on whether it is a weapon or a non-weapon:

```
Off-hand component type == "Weapon" → attachPoint = "2"  (left-hand grip)
Off-hand component type != "Weapon" → attachPoint = "0"  (shield mount)
```

Component type is determined by checking which `Item\ObjectComponents\` subfolder contains the model (`Weapon`, `Shield`, `Shoulder`, `Head`).

### Attachment Point Positions

All positions are in **glTF coordinate space**, pre-converted from WoW M2 space during extraction. Rotations are identity quaternions `[0,0,0,1]` for all models (see [Technical Reference](09-technical-reference.md) for details).

### Error Responses

```json
{ "error": "Character not found" }  // 404
```

---

## Backend Internal Caches

| Cache | Type | Scope | Eviction |
|-------|------|-------|----------|
| Character data | TTLCache (256 entries, 30s) | Per-process | Time |
| DBC databases | Global module dict | Per-process | Never (restart to reload) |
| Component type (displayId → type) | Module dict | Per-process | Never |
| Attachments JSON | Module global | Per-process | Never |
| PNG textures | Filesystem (`cache/*.png`) | Persistent | Manual deletion |
| Item GLBs | Filesystem (`cache/*.glb`) | Persistent | Manual deletion |
| MPQ pool | Module dict of open handles | Per-process | Never |
