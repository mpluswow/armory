# Frontend

The frontend is a React 19 + TypeScript application built with Vite 7. It renders the paper-doll character viewer and handles all 3D model loading via Three.js through React Three Fiber.

---

## Component Tree

```
App.tsx
├── CharacterSearch.tsx      — search input + character list toggle
├── CharacterList.tsx        — scrollable modal with all server characters
└── PaperDoll.tsx            — main layout (only shown when a character is loaded)
    ├── ItemSlot.tsx ×7      — left column slots (Head → Wrist)
    ├── ModelViewer.tsx      — central 3D viewer
    │   ├── CharacterModel   — loads GLB, applies textures, attaches items
    │   └── OrbitControls    — mouse/touch camera orbit
    ├── StatsPanel.tsx       — race/class/faction/avg ilvl below model
    ├── ItemSlot.tsx ×8      — right column slots (Hands → Trinket 2)
    ├── ItemSlot.tsx ×3      — weapon row (Main Hand, Off Hand, Ranged)
    └── ItemTooltip.tsx      — floating tooltip (portal, positioned by hover)
```

---

## Data Flow

```
User types name → CharacterSearch.search(name)
  ↓
useCharacter hook → api/character.ts → GET /api/character?name=…
  ↓
App.tsx state update: character = { guid, name, race, …, equipment: [] }
  ↓
PaperDoll receives character prop
  ├── ItemSlot: renders icon + tooltip for each equipped slot
  ├── StatsPanel: shows race/class/faction/avg ilvl
  └── ModelViewer: receives character prop, begins 3D loading
       ├── Load GLB:  /models/characters/{race}_{gender}.glb
       ├── GET /api/model-geosets/{name}        → show/hide submeshes
       ├── GET /api/model-texture/{name}         → skin atlas PNG
       ├── GET /api/model-hair-texture/{name}    → hair mesh PNG
       ├── GET /api/model-extra-skin-texture     → extra-skin PNG
       ├── GET /api/model-cape-texture/{name}    → cape PNG
       └── GET /api/character-attachments/{name}
            └── For each item:
                 GET /api/item-model/{displayId}?side=…&race=…&gender=…
                 → position GLB at attachment point
```

---

## TypeScript Interfaces

### `EquipmentItem`
```typescript
interface EquipmentItem {
  slot: number;
  entry: number;
  displayId: number;
  name: string;
  quality: number;       // 0=Poor … 7=Heirloom
  itemLevel: number | null;
  requiredLevel: number | null;
  itemType: string;
  stats: string[];       // formatted strings e.g. "+50 Intellect"
  description: string;
  icon: string;          // entry ID used to fetch icon URL
}
```

### `Character`
```typescript
interface Character {
  guid: number;
  name: string;
  race: number;
  class: number;
  gender: number;        // 0=male, 1=female
  level: number;
  skin: number;
  face: number;
  hairStyle: number;
  hairColor: number;
  facialStyle: number;
  equipment: EquipmentItem[];
}
```

### `CharacterListItem`
```typescript
interface CharacterListItem {
  name: string;
  race: number;
  class: number;
  level: number;
  faction: "Alliance" | "Horde";
}
```

---

## Hooks

### `useCharacter()`
```typescript
const { character, loading, error, search } = useCharacter()
```

| Member | Type | Description |
|--------|------|-------------|
| `character` | `Character \| null` | Currently loaded character |
| `loading` | `boolean` | True while API call is in flight |
| `error` | `string \| null` | Error message from last failed call |
| `search(name)` | `(string) => void` | Triggers a new character load |

### `useItemIcon(entry)`
```typescript
const iconUrl = useItemIcon(entry)
```

Fetches the icon URL for an item entry. Lookup order:
1. `localStorage` — key `icon_{entry}`
2. WowHead tooltip API: `https://nether.wowhead.com/tooltip/item/{entry}?dataEnv=1&locale=0`
3. MurlocVillage fallback: `https://wotlk.murlocvillage.com/items/icon_image.php?item={entry}`
4. Default: `https://wow.zamimg.com/images/wow/icons/large/inv_misc_questionmark.jpg`

Successful lookups are cached in `localStorage` to avoid redundant network calls.

---

## Constants (`utils/constants.ts`)

### Race Names
```typescript
const RACE_NAMES: Record<number, string> = {
  1: "Human", 2: "Orc", 3: "Dwarf", 4: "Night Elf",
  5: "Undead", 6: "Tauren", 7: "Gnome", 8: "Troll",
  10: "Blood Elf", 11: "Draenei"
}
```

### Class Names and Colours
```typescript
const CLASS_NAMES: Record<number, string> = {
  1: "Warrior", 2: "Paladin", 3: "Hunter", 4: "Rogue",
  5: "Priest", 6: "Death Knight", 7: "Shaman", 8: "Mage",
  9: "Warlock", 11: "Druid"
}

const CLASS_COLORS: Record<number, string> = {
  1: "#C79C6E", 2: "#F58CBA", 3: "#ABD473", 4: "#FFF569",
  5: "#FFFFFF", 6: "#C41F3B", 7: "#0070DE", 8: "#69CCF0",
  9: "#9482C9", 11: "#FF7D0A"
}
```

### Item Quality Colours (`utils/quality.ts`)
```typescript
const QUALITY_COLORS: Record<number, string> = {
  0: "#9d9d9d",  // Poor — grey
  1: "#ffffff",  // Common — white
  2: "#1eff00",  // Uncommon — green
  3: "#0070dd",  // Rare — blue
  4: "#a335ee",  // Epic — purple
  5: "#ff8000",  // Legendary — orange
  6: "#e6cc80",  // Artifact — light gold
  7: "#00ccff"   // Heirloom — light blue
}
```

### Equipment Slot Layout

The paper-doll uses three columns. Slot assignment:

**Left column:**
```
0  Head       1  Neck       2  Shoulders
14 Back       4  Chest      18 Tabard
8  Wrist
```

**Right column:**
```
9  Hands      5  Waist      6  Legs
7  Feet       10 Finger 1   11 Finger 2
12 Trinket 1  13 Trinket 2
```

**Weapon row (bottom):**
```
15 Main Hand  16 Off Hand   17 Ranged
```

---

## ModelViewer Component

The most complex component. It manages the entire 3D rendering lifecycle.

### Scene Setup

```
Canvas (React Three Fiber)
├── ambientLight        intensity=0.6
├── directionalLight    position=(3,4,3)   intensity=1.2
├── directionalLight    position=(-2,2,1)  intensity=0.5
├── directionalLight    position=(0,2,-3)  intensity=0.3
├── CharacterModel      (main character)
└── OrbitControls       target=(0,0.8,0)  minDist=1.5  maxDist=8  noPan=true
```

**Camera:** position `(0, 1, 3.5)`, looking at `(0, 0.8, 0)`.

### CharacterModel Loading Sequence

1. **Load GLB** — fetches `/models/characters/{race}_{gender}.glb` using `@react-three/drei`'s `useGLTF` hook.
2. **Clone scene** — the GLB scene is cloned so multiple instances don't share state.
3. **Collect mesh nodes** — traverses the clone, collects all mesh nodes by name.
4. **Scale and centre** — computes bounding box; scales so max dimension = 2 units; translates to align feet with y=0; rotates 180° around Y (models face away from viewer in GLB).
5. **Fetch geosets** — calls `/api/model-geosets/{name}`; sets `mesh.visible` for each node.
6. **Load skin texture** — calls `/api/model-texture/{name}`; applies to all nodes whose name contains `_skin` and not `_skin_extra`.
7. **Load hair texture** — calls `/api/model-hair-texture/{name}`; applies to `_hair` nodes.
8. **Load extra-skin texture** — calls `/api/model-extra-skin-texture/{name}`; applies to `_skin_extra` nodes.
9. **Load cape texture** — calls `/api/model-cape-texture/{name}`; applies to `_cape` nodes.
10. **Load attachment data** — calls `/api/character-attachments/{name}`; for each item:
    - Calls `/api/item-model/{displayId}?side=…&race=…&gender=…`
    - Creates a Three.js `Group` at the attachment position
    - Applies identity rotation (from attachments.json)
    - Loads item GLB, parents it to the group
    - Parents the group to the character root

### Geoset Node Parsing

Node names follow the format `geoset_{id}_{textype}`. The component parses these to determine:
- Which geoset ID the node belongs to (for visibility)
- Which texture type to apply (`skin`, `hair`, `cape`, `skin_extra`)

```typescript
// Example node names:
"geoset_1_skin"        // base body, skin texture
"geoset_101_hair"      // hair mesh, hair texture
"geoset_401_skin"      // glove geometry
"geoset_1501_cape"     // cloak geometry
"geoset_201_skin_extra"// extra skin layer
```

### Texture Application

All textures use the same settings:
```typescript
texture.flipY = false          // GLB UVs are already correct
texture.colorSpace = SRGBColorSpace
material.map = texture
material.needsUpdate = true
```

### Resource Cleanup

On component unmount, all Three.js resources are disposed:
```typescript
useEffect(() => {
  return () => {
    scene.traverse((obj) => {
      if (obj instanceof Mesh) {
        obj.geometry.dispose()
        if (Array.isArray(obj.material)) {
          obj.material.forEach(m => { m.map?.dispose(); m.dispose() })
        } else {
          obj.material.map?.dispose()
          obj.material.dispose()
        }
      }
    })
  }
}, [scene])
```

### Error Boundary

`ModelViewer` is wrapped in a React error boundary. If the 3D scene fails to initialise, it renders a text fallback showing race, class, and level rather than crashing the whole page.

---

## ItemSlot Component

Renders a single equipment slot with:
- An icon fetched via `useItemIcon` hook (external URL)
- Quality-colour CSS border
- Empty state shown when no item is equipped
- Hover event that triggers the `ItemTooltip` via a callback

### Quality Border CSS Classes

```css
.q0 { border-color: #9d9d9d; }  /* Poor */
.q1 { border-color: #ffffff; }  /* Common */
.q2 { border-color: #1eff00; }  /* Uncommon */
.q3 { border-color: #0070dd; }  /* Rare */
.q4 { border-color: #a335ee; }  /* Epic */
.q5 { border-color: #ff8000; }  /* Legendary */
.q6 { border-color: #e6cc80; }  /* Artifact */
.q7 { border-color: #00ccff; }  /* Heirloom */
```

---

## ItemTooltip Component

Floating tooltip rendered at fixed position near the hovered slot. Contents:
- Item name coloured by quality
- Item Level line
- "Binds when equipped" line
- Item type (slot name)
- Stat strings (one per line)
- Required level (if > 1)
- Flavour text (if present)

---

## StatsPanel Component

Character info shown below the 3D model:

| Field | Source | Notes |
|-------|--------|-------|
| Race | `RACE_NAMES[character.race]` | |
| Class | `CLASS_NAMES[character.class]` | Coloured with `CLASS_COLORS` |
| Gender | `character.gender === 0 ? "Male" : "Female"` | |
| Faction | Derived from race | Alliance (blue) or Horde (red) |
| Avg Item Level | Mean of all `itemLevel` values in `equipment` | Ignores slots with `null` itemLevel |

---

## Vite Proxy Configuration

All `/api/*` requests from the frontend are automatically forwarded to the backend:

```typescript
// vite.config.ts
server: {
  port: 5173,
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
  },
},
```

This means the frontend code calls `/api/character` with no host, and Vite transparently forwards it to `http://127.0.0.1:8000/api/character`.

---

## Build for Production

```bash
cd frontend
npm run build
```

Output goes to `frontend/dist/`. Serve the `dist/` folder with any static file server. In production, configure a reverse proxy (nginx, Caddy) to:
- Serve `dist/` for all non-API routes
- Proxy `/api/*` to `http://127.0.0.1:8000`
- Serve `dist/models/` (or the `public/models/` folder) as static assets
