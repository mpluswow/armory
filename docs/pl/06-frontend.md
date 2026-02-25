# Frontend

Frontend to aplikacja React 19 + TypeScript zbudowana przy użyciu Vite 7. Renderuje przeglądarkę postaci w stylu paper-doll i obsługuje ładowanie modeli 3D przez Three.js za pośrednictwem React Three Fiber.

---

## Drzewo komponentów

```
App.tsx
├── CharacterSearch.tsx      — pole wyszukiwania + przełącznik listy postaci
├── CharacterList.tsx        — modalne okno z listą wszystkich postaci
└── PaperDoll.tsx            — główny układ (widoczny gdy postać jest załadowana)
    ├── ItemSlot.tsx ×7      — lewa kolumna (Głowa → Nadgarstek)
    ├── ModelViewer.tsx      — centralny widok 3D
    │   ├── CharacterModel   — ładuje GLB, stosuje tekstury, przyczepy przedmiotów
    │   └── OrbitControls    — kamera myszka/dotyk
    ├── StatsPanel.tsx       — rasa/klasa/frakcja/śr. poziom przedmiotów
    ├── ItemSlot.tsx ×8      — prawa kolumna (Rękawice → Talizman 2)
    ├── ItemSlot.tsx ×3      — rząd broni (Prawa ręka, Lewa ręka, Dystansowa)
    └── ItemTooltip.tsx      — pływający tooltip (portal, pozycjonowany przez hover)
```

---

## Przepływ danych

```
Użytkownik wpisuje nazwę → CharacterSearch.search(name)
  ↓
Hook useCharacter → api/character.ts → GET /api/character?name=…
  ↓
Aktualizacja stanu App.tsx: character = { guid, name, race, …, equipment: [] }
  ↓
PaperDoll otrzymuje prop character
  ├── ItemSlot: renderuje ikonę + tooltip dla każdego wyposażonego slotu
  ├── StatsPanel: wyświetla rasę/klasę/frakcję/śr. poziom
  └── ModelViewer: otrzymuje prop character, rozpoczyna ładowanie 3D
       ├── Załaduj GLB:  /models/characters/{rasa}_{płeć}.glb
       ├── GET /api/model-geosets/{name}         → pokaż/ukryj submeshy
       ├── GET /api/model-texture/{name}          → atlas skóry PNG
       ├── GET /api/model-hair-texture/{name}     → PNG włosów
       ├── GET /api/model-extra-skin-texture      → PNG dodatkowej skóry
       ├── GET /api/model-cape-texture/{name}     → PNG płaszcza
       └── GET /api/character-attachments/{name}
            └── Dla każdego przedmiotu:
                 GET /api/item-model/{displayId}?side=…&race=…&gender=…
                 → pozycjonuj GLB w punkcie przyczepu
```

---

## Interfejsy TypeScript

### `EquipmentItem`
```typescript
interface EquipmentItem {
  slot: number;
  entry: number;
  displayId: number;
  name: string;
  quality: number;        // 0=Lichej jakości … 7=Heirloom
  itemLevel: number | null;
  requiredLevel: number | null;
  itemType: string;
  stats: string[];        // np. "+50 Intelektu"
  description: string;
  icon: string;
}
```

### `Character`
```typescript
interface Character {
  guid: number;
  name: string;
  race: number;
  class: number;
  gender: number;         // 0=mężczyzna, 1=kobieta
  level: number;
  skin: number;
  face: number;
  hairStyle: number;
  hairColor: number;
  facialStyle: number;
  equipment: EquipmentItem[];
}
```

---

## Hooki

### `useCharacter()`
```typescript
const { character, loading, error, search } = useCharacter()
```

| Składowa | Typ | Opis |
|----------|-----|------|
| `character` | `Character \| null` | Aktualnie załadowana postać |
| `loading` | `boolean` | True podczas wywołania API |
| `error` | `string \| null` | Komunikat błędu ostatniego nieudanego wywołania |
| `search(name)` | `(string) => void` | Wywołuje nowe ładowanie postaci |

### `useItemIcon(entry)`
```typescript
const iconUrl = useItemIcon(entry)
```

Pobiera URL ikony dla ID przedmiotu. Kolejność wyszukiwania:
1. `localStorage` — klucz `icon_{entry}`
2. API tooltipów WowHead: `https://nether.wowhead.com/tooltip/item/{entry}?dataEnv=1&locale=0`
3. Fallback MurlocVillage: `https://wotlk.murlocvillage.com/items/icon_image.php?item={entry}`
4. Domyślna: `https://wow.zamimg.com/images/wow/icons/large/inv_misc_questionmark.jpg`

---

## Stałe (`utils/constants.ts`)

### Nazwy ras
```typescript
const RACE_NAMES: Record<number, string> = {
  1: "Human", 2: "Orc", 3: "Dwarf", 4: "Night Elf",
  5: "Undead", 6: "Tauren", 7: "Gnome", 8: "Troll",
  10: "Blood Elf", 11: "Draenei"
}
```

### Kolory jakości (`utils/quality.ts`)
```typescript
const QUALITY_COLORS: Record<number, string> = {
  0: "#9d9d9d",  // Lichej jakości — szary
  1: "#ffffff",  // Zwykły — biały
  2: "#1eff00",  // Niezwykły — zielony
  3: "#0070dd",  // Rzadki — niebieski
  4: "#a335ee",  // Epicki — fioletowy
  5: "#ff8000",  // Legendarny — pomarańczowy
  6: "#e6cc80",  // Artefakt — jasne złoto
  7: "#00ccff"   // Heirloom — jasnoniebieski
}
```

---

## Komponent ModelViewer

Najbardziej złożony komponent. Zarządza całym cyklem życia renderowania 3D.

### Konfiguracja sceny

```
Canvas (React Three Fiber)
├── ambientLight        intensity=0.6
├── directionalLight    position=(3,4,3)   intensity=1.2
├── directionalLight    position=(-2,2,1)  intensity=0.5
├── directionalLight    position=(0,2,-3)  intensity=0.3
├── CharacterModel      (główna postać)
└── OrbitControls       target=(0,0.8,0)  minDist=1.5  maxDist=8  noPan=true
```

**Kamera:** pozycja `(0, 1, 3.5)`, patrzy w `(0, 0.8, 0)`.

### Sekwencja ładowania CharacterModel

1. **Ładowanie GLB** — pobiera `/models/characters/{rasa}_{płeć}.glb` hookiem `useGLTF`.
2. **Klonowanie sceny** — scena GLB jest klonowana by wiele instancji nie dzieliło stanu.
3. **Zbieranie węzłów mesh** — przechodzi po klonie, zbiera węzły mesh po nazwie.
4. **Skalowanie i centrowanie** — oblicza bounding box; skaluje by max wymiar = 2 jednostki; obraca 180° wokół Y.
5. **Pobranie geosetek** — wywołuje `/api/model-geosets/{name}`; ustawia `mesh.visible`.
6. **Ładowanie tekstury skóry** — wywołuje `/api/model-texture/{name}`; stosuje do węzłów `_skin`.
7. **Ładowanie tekstury włosów** — wywołuje `/api/model-hair-texture/{name}`; stosuje do węzłów `_hair`.
8. **Ładowanie dodatkowej skóry** — wywołuje `/api/model-extra-skin-texture/{name}`; stosuje do węzłów `_skin_extra`.
9. **Ładowanie płaszcza** — wywołuje `/api/model-cape-texture/{name}`; stosuje do węzłów `_cape`.
10. **Ładowanie punktów przyczepu** — wywołuje `/api/character-attachments/{name}`; dla każdego przedmiotu:
    - Wywołuje `/api/item-model/{displayId}?side=…`
    - Tworzy grupę Three.js w pozycji punktu przyczepu
    - Ładuje GLB przedmiotu, podpina pod grupę
    - Grupę podpina pod korzeń postaci

### Parsowanie nazw węzłów geosetek

Nazwy węzłów mają format `geoset_{id}_{textype}`. Komponent parsuje je, aby określić:
- Który ID geosetki przypisać węzłowi (dla widoczności)
- Który typ tekstury zastosować (`skin`, `hair`, `cape`, `skin_extra`)

### Stosowanie tekstur

Wszystkie tekstury używają tych samych ustawień:
```typescript
texture.flipY = false          // UV w GLB są już poprawne
texture.colorSpace = SRGBColorSpace
material.map = texture
material.needsUpdate = true
```

### Sprzątanie zasobów

Przy odmontowaniu komponentu wszystkie zasoby Three.js są zwalniane:
```typescript
useEffect(() => {
  return () => {
    scene.traverse((obj) => {
      if (obj instanceof Mesh) {
        obj.geometry.dispose()
        obj.material.map?.dispose()
        obj.material.dispose()
      }
    })
  }
}, [scene])
```

### Error Boundary

`ModelViewer` jest opakowany w React error boundary. Jeśli inicjalizacja sceny 3D się nie powiedzie, renderuje tekstowy fallback z rasą, klasą i poziomem.

---

## Komponent StatsPanel

Informacje o postaci wyświetlane pod modelem 3D:

| Pole | Źródło | Uwagi |
|------|--------|-------|
| Rasa | `RACE_NAMES[character.race]` | |
| Klasa | `CLASS_NAMES[character.class]` | Kolorowana przez `CLASS_COLORS` |
| Płeć | `character.gender === 0 ? "Male" : "Female"` | |
| Frakcja | Wyznaczana z rasy | Przymierze (niebieski) lub Horda (czerwony) |
| Śr. poz. przedm. | Średnia z wszystkich `itemLevel` w `equipment` | Pomija sloty z wartością `null` |

---

## Konfiguracja Proxy Vite

Wszystkie żądania `/api/*` z frontendu są automatycznie przekazywane do backendu:

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

---

## Build produkcyjny

```bash
cd frontend
npm run build
```

Wynik trafia do `frontend/dist/`. W produkcji skonfiguruj reverse proxy (nginx, Caddy) aby:
- Serwował `dist/` dla wszystkich tras nie-API
- Proxował `/api/*` do `http://127.0.0.1:8000`
- Serwował `dist/models/` jako pliki statyczne
