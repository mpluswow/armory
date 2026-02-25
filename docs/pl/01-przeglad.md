# Przegląd

## Czym jest AzerothCore Armory?

AzerothCore Armory to pełnostackowa aplikacja webowa odwzorowująca doświadczenie oficjalnego Armory World of Warcraft dla prywatnych serwerów opartych na [AzerothCore](https://www.azerothcore.org/) (patch WotLK 3.3.5a). Odczytuje dane postaci bezpośrednio z bazy danych MySQL AzerothCore i renderuje interaktywną przeglądarkę 3D z pełnym wyposażeniem, dynamicznymi teksturami skóry, widocznością geosetek i punktami przyczepu przedmiotów — wszystko z lokalnie wyekstrahowanych zasobów gry, bez korzystania z zewnętrznych CDN ani serwerów Blizzarda.

---

## Funkcjonalności

| Funkcja | Opis |
|---------|------|
| Dane postaci na żywo | Odczyt bezpośrednio z baz `acore_characters` i `acore_world` |
| Renderowanie 3D postaci | Modele GLB specyficzne dla rasy i płci, wyekstrahowane z plików M2 |
| Złożona tekstura skóry | Bazowa skóra + twarz + zarost + skóra głowy + zbroja baked w jednym atlasie PNG |
| Osobne sloty tekstur | Włosy, dodatkowa skóra (futro taurena), płaszcz jako niezależne tekstury |
| Modele 3D przedmiotów | Broń, tarcze, naramienniki, hełmy wyodrębniane na żądanie z MPQ |
| Widoczność geosetek | Wyposażenie kontroluje widoczność submeshy (włosy ukryte pod hełmem itp.) |
| Interfejs "paper doll" | Układ w stylu Blizzarda z ikonkami przedmiotów, kolorami jakości i tooltipami ze statystykami |
| Samodzielny startup | `./start.sh` instaluje wszystkie zależności, buduje StormLib jeśli potrzeba, uruchamia oba serwery |

---

## Stos technologiczny

### Backend
| Komponent | Technologia |
|-----------|-------------|
| Język | Python 3.8+ |
| Framework webowy | [FastAPI](https://fastapi.tiangolo.com/) |
| Serwer ASGI | [Uvicorn](https://www.uvicorn.org/) |
| Sterownik bazy danych | [aiomysql](https://aiomysql.readthedocs.io/) (async) |
| Konfiguracja | [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| Cache w pamięci | [cachetools](https://cachetools.readthedocs.io/) (TTLCache) |

### Frontend
| Komponent | Technologia |
|-----------|-------------|
| Język | TypeScript |
| Framework UI | [React 19](https://react.dev/) |
| Narzędzie build | [Vite 7](https://vitejs.dev/) |
| Silnik 3D | [Three.js 0.182](https://threejs.org/) przez [React Three Fiber 9](https://r3f.docs.pmnd.rs/) |
| Helpery 3D | [@react-three/drei](https://github.com/pmndrs/drei) |

### Narzędzia ekstrakcji
| Komponent | Technologia |
|-----------|-------------|
| Język | Python 3.8+ |
| Odczyt MPQ | [StormLib](https://github.com/ladislav-zezula/StormLib) przez ctypes |
| Przetwarzanie obrazów | [Pillow](https://python-pillow.org/) |
| Tablice numeryczne | [NumPy](https://numpy.org/) |
| Zapis GLB | [pygltflib](https://github.com/dodgyville/pygltflib) |

---

## Architektura

```
Przeglądarka (http://localhost:5173)
  │
  │  React + Vite dev server
  │  Proxy /api/* → localhost:8000
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FRONTEND  (port 5173)                         │
│                                                                 │
│  CharacterSearch ─── CharacterList                             │
│        │                                                        │
│  PaperDoll                                                      │
│    ├── ItemSlot ×19  (ikony, tooltipy, ramki jakości)          │
│    ├── ModelViewer   (Three.js / React Three Fiber)            │
│    │     ├── CharacterModel  (GLB + tekstury + przyczepia)     │
│    │     └── OrbitControls                                      │
│    └── StatsPanel   (rasa, klasa, frakcja, śr. poziom przedm.) │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP  /api/*
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BACKEND  (port 8000)                          │
│                                                                 │
│  FastAPI + Uvicorn                                              │
│                                                                 │
│  routes/characters.py                                           │
│    GET /api/character        ← dane postaci + wyposażenie       │
│    GET /api/characters       ← lista postaci na serwerze        │
│                                                                 │
│  routes/models.py                                               │
│    GET /api/model-texture/{name}           ← skóra PNG          │
│    GET /api/model-hair-texture/{name}      ← włosy PNG          │
│    GET /api/model-extra-skin-texture/{name}← futro/kości PNG    │
│    GET /api/model-cape-texture/{name}      ← płaszcz PNG        │
│    GET /api/model-geosets/{name}           ← ID geosetek        │
│    GET /api/character-attachments/{name}   ← pozycje przedmiotów│
│    GET /api/item-model/{displayId}         ← GLB przedmiotu     │
│                                                                 │
│  Lazy-loaded cache DBC:                                         │
│    ItemDisplayInfo, CharHairGeosets, CharFacialHairStyles,      │
│    HelmetGeosetVisData, CharSections                            │
│                                                                 │
│  Trwała pula MPQ (unika ponownego otwierania dużych archiwów)   │
└──────────┬───────────────────────────────────────┬──────────────┘
           │ aiomysql (async)                       │ system plików
           ▼                                        ▼
┌──────────────────────┐           ┌────────────────────────────┐
│   MySQL / MariaDB    │           │  frontend/public/models/   │
│                      │           │                            │
│   acore_characters   │           │  characters/  *.glb        │
│     characters       │           │  attachments.json          │
│     character_inv.   │           │  manifest.json             │
│     item_instance    │           │  cache/  PNG + GLB         │
│                      │           └──────────────┬─────────────┘
│   acore_world        │                          │ wyekstrahowane przez
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
                                   │  Data/  (pliki MPQ WoW)  │
                                   │  patch.MPQ               │
                                   │  patch-2.MPQ             │
                                   │  locale-enUS.MPQ  itd.   │
                                   └──────────────────────────┘
```

---

## Przepływ żądania: Wczytywanie postaci

1. Użytkownik wpisuje nazwę postaci i klika Szukaj.
2. Frontend React wywołuje `GET /api/character?name=<name>`.
3. FastAPI sprawdza TTLCache; jeśli brak — odpytuje `acore_characters` + `acore_world`.
4. Odpowiedź JSON zawiera wszystkie pola postaci i sformatowaną tablicę `equipment`.
5. Frontend renderuje układ paper-doll i jednocześnie wczytuje zasoby 3D:
   - `GET /api/model-texture/{name}` → złożony atlas skóry PNG
   - `GET /api/model-hair-texture/{name}` → tekstura meshu włosów
   - `GET /api/model-extra-skin-texture/{name}` → dodatkowa warstwa skóry
   - `GET /api/model-cape-texture/{name}` → tekstura płaszcza
   - `GET /api/model-geosets/{name}` → lista widocznych ID geosetek
   - `GET /api/character-attachments/{name}` → pozycje punktów przyczepu + ID wyświetlania przedmiotów
6. Dla każdego przypiętego przedmiotu (broń, naramienniki, hełm) frontend wywołuje `GET /api/item-model/{displayId}`, aby pobrać modele GLB na żądanie.
7. Wszystkie tekstury są nakładane na odpowiednie typy meshy; geosetki przełączają widoczność; modele GLB przedmiotów są podpinane pod węzły pivot punktów przyczepu.

---

## Struktura projektu

```
armory/
├── .env                          # Dane bazy danych (niezatwierdzane do repo)
├── .env.example                  # Szablon dla .env
├── .gitignore
├── start.sh                      # Launcher + instalator pierwszego uruchomienia
├── about.md                      # Intro projektu i indeks dokumentacji
├── DOCUMENTATION.md              # Rozszerzone wiki dla deweloperów
│
├── backend/                      # Serwer FastAPI
│   ├── main.py                   # Fabryka aplikacji, lifespan, CORS
│   ├── config.py                 # Ustawienia Pydantic (czyta .env)
│   ├── database.py               # Pula połączeń aiomysql
│   ├── requirements.txt
│   ├── routes/
│   │   ├── characters.py         # /api/character, /api/characters
│   │   └── models.py             # Wszystkie /api/model-* i /api/item-model/*
│   └── services/
│       └── character.py          # Zapytania SQL, formatowanie statystyk
│
├── frontend/                     # Aplikacja React + Vite
│   ├── package.json
│   ├── vite.config.ts            # Proxy /api → :8000
│   └── src/
│       ├── App.tsx
│       ├── api/character.ts      # Wywołania HTTP
│       ├── hooks/
│       │   ├── useCharacter.ts
│       │   └── useItemIcon.ts
│       ├── utils/
│       │   ├── constants.ts      # Nazwy ras/klas, układ slotów
│       │   └── quality.ts        # Kolory jakości
│       ├── types/character.ts    # Interfejsy TypeScript
│       └── components/
│           ├── PaperDoll.tsx     # Główny układ
│           ├── ModelViewer.tsx   # Przeglądarka 3D Three.js
│           ├── ItemSlot.tsx
│           ├── ItemTooltip.tsx
│           ├── StatsPanel.tsx
│           ├── CharacterSearch.tsx
│           └── CharacterList.tsx
│   └── public/
│       └── models/               # Generowane przez pipeline ekstrakcji
│           ├── characters/       # *.glb (rasa_płeć.glb)
│           ├── attachments.json
│           ├── manifest.json
│           └── cache/            # Cache PNG + GLB generowany w czasie rzeczywistym
│
├── tools/                        # Pipeline ekstrakcji
│   ├── extract_models.py         # Konwerter M2 → GLB
│   ├── gear_compositor.py        # Compositor tekstur BLP + logika geosetek
│   ├── libstorm.so               # StormLib (dołączony, Linux x86_64)
│   └── requirements.txt          # Pillow, numpy, pygltflib
│
├── Data/                         # Archiwa MPQ WoW (NIEZATWIERDZANE — duże pliki)
│   └── *.MPQ
│
├── docs/
│   ├── en/                       # Dokumentacja angielska
│   └── pl/                       # Dokumentacja polska
│
└── logs/
    ├── backend.log
    └── frontend.log
```
