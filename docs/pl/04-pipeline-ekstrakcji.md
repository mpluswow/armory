# Pipeline ekstrakcji

Pipeline ekstrakcji to zestaw narzędzi Python odczytujących surowe zasoby gry z archiwów MPQ WoW i konwertujących je do formatów używanych przez aplikację webową. Jest to **jednorazowy krok konfiguracyjny** — po pierwszym uruchomieniu wystarczy powtórzyć go tylko przy chęci regeneracji modeli.

---

## Przegląd

```
Data/*.MPQ  (archiwa WoW 3.3.5a)
     │
     │  StormLib (libstorm.so przez ctypes)
     ▼
extract_models.py
     │
     ├── Odczytuje modele postaci M2
     ├── Odczytuje pliki skin (.skin)
     ├── Dekoduje tekstury BLP
     ├── Konwertuje współrzędne WoW → glTF
     ├── Buduje pliki GLB (per rasa/płeć)
     └── Wyodrębnia pozycje punktów przyczepu
     │
     └── Wynik: frontend/public/models/
                   characters/*.glb   (20 modeli)
                   manifest.json
                   attachments.json

gear_compositor.py  (wywoływany przez backend w czasie działania, nie bezpośrednio)
     │
     ├── Odczytuje pliki DBC (CharSections, ItemDisplayInfo, itp.)
     ├── Dekoduje tekstury BLP skóry/zbroi
     ├── Komponuje warstwy na atlasie 512×512
     └── Oblicza widoczność geosetek na podstawie wyposażenia
```

---

## Uruchamianie ekstrakcji

```bash
tools/venv/bin/python tools/extract_models.py \
  --data-dir ./Data \
  --output-dir ./frontend/public/models
```

Oczekiwany wynik (ok. 1–5 minut, zależy od sprzętu):
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

### Czym jest

[StormLib](https://github.com/ladislav-zezula/StormLib) to biblioteka C++ do odczytu archiwów MPQ Blizzarda. Narzędzia używają skompilowanej biblioteki współdzielonej (`libstorm.so`) ładowanej w czasie działania przez `ctypes` Pythona.

Skompilowany binarny plik x86_64 dla Linuksa jest dołączony w `tools/libstorm.so`. `start.sh` testuje czy ładuje się poprawnie i przebudowuje go ze źródeł jeśli nie.

### Powiązania ctypes

`extract_models.py` wiąże następujące funkcje StormLib:

| Funkcja | Przeznaczenie |
|---------|---------------|
| `SFileOpenArchive` | Otwiera archiwum MPQ |
| `SFileCloseArchive` | Zamyka archiwum |
| `SFileOpenFileEx` | Otwiera plik wewnątrz archiwum |
| `SFileGetFileSize` | Pobiera rozmiar otwartego pliku |
| `SFileReadFile` | Odczytuje bajty z otwartego pliku |
| `SFileCloseFile` | Zamyka uchwyt pliku |
| `SFileFindFirstFile` | Rozpoczyna iterację plików w archiwum |
| `SFileFindNextFile` | Kontynuuje iterację |
| `SFileFindClose` | Kończy iterację |

### Trwała pula MPQ

Archiwa MPQ mogą mieć 2–10 GB każde. Otwieranie i zamykanie ich przy każdym żądaniu jest bardzo wolne. Narzędzia utrzymują globalną pulę:

```python
_mpq_pool: dict[str, MPQArchive] = {}

def _get_mpq(mpq_path: str) -> MPQArchive | None:
    if mpq_path not in _mpq_pool:
        _mpq_pool[mpq_path] = MPQArchive(mpq_path)
    return _mpq_pool[mpq_path]
```

Backend wywołuje `_warmup_mpq_pool()` przy starcie, aby wstępnie otworzyć wszystkie archiwa — pierwsze żądanie tekstury jest dzięki temu szybkie.

---

## Format pliku M2

M2 (zwany też MD20) to własnościowy binarny format modeli Blizzarda używany dla postaci, stworów i przedmiotów w WotLK 3.3.5a.

### Kluczowe offsety nagłówka

| Offset | Pole | Typ | Opis |
|--------|------|-----|------|
| 0x00 | magic | char[4] | "MD20" |
| 0x04 | version | uint32 | Wersja pliku |
| 0x14 | nVertices | uint32 | Liczba wierzchołków |
| 0x18 | ofsVertices | uint32 | Offset tablicy wierzchołków |
| 0x1C | ofsSequences | uint32 | M2Array sekwencji animacji |
| 0x2C | ofsBones | uint32 | **M2Array definicji kości** |
| 0xF0 | nAttachments | uint32 | Liczba punktów przyczepu |
| 0xF4 | ofsAttachments | uint32 | Offset danych przyczepu |

> **Ważne:** Dane kości są pod offsetem **0x2C**, nie 0x6C jak podaje część starszej dokumentacji.

### Układ wierzchołka (48 bajtów)

```
+0  float[3]  position        Przestrzeń współrzędnych WoW
+12 uint8[4]  bone_weights    Wagi skinowania, suma = 255
+16 uint8[4]  bone_indices    Indeksy do tablicy kości
+20 float[3]  normal
+32 float[2]  uv_coord_1
+40 float[2]  uv_coord_2
```

### Konwersja układu współrzędnych

WoW i glTF używają różnych układów współrzędnych:

| Oś | WoW | glTF |
|----|-----|------|
| X | w prawo | w prawo |
| Y | do przodu | w górę |
| Z | w górę | w stronę widza |

Konwersja stosowana do każdej pozycji wierzchołka, normali i pozycji punktu przyczepu:
```python
gltf_x = wow_x
gltf_y = wow_z      # Z WoW staje się Y glTF (góra)
gltf_z = -wow_y     # Y WoW staje się -Z glTF
```

---

## Pliki skin

Plik `.skin` towarzyszy każdemu M2 i definiuje jak wierzchołki są grupowane w submeshy (geosetki). Każda geosetka odpowiada innemu regionowi ciała lub warstwie wyposażenia.

### Mapowanie batchy skin na typy tekstur

| ID Typu | Nazwa | Tekstura stosowana |
|---------|-------|-------------------|
| 0 | hardcoded | stała / skóra |
| 1 | skin | atlas skóry postaci (`/api/model-texture/`) |
| 2 | cape | tekstura płaszcza (`/api/model-cape-texture/`) |
| 6 | hair | tekstura meshu włosów (`/api/model-hair-texture/`) |
| 8 | skin_extra | dodatkowa warstwa skóry (`/api/model-extra-skin-texture/`) |

### Nazewnictwo węzłów geosetek

Każdy węzeł submeshu w wynikowym GLB jest nazwany:
```
geoset_{id}_{textype}
```

Przykłady:
- `geoset_1_skin` — bazowy mesh ciała, tekstura skóry
- `geoset_101_hair` — geometria włosów, tekstura włosów
- `geoset_401_skin` — geometria rękawic
- `geoset_1501_cape` — geometria płaszcza

---

## Dekodowanie tekstur BLP

BLP to własnościowy format tekstur Blizzarda. Pipeline zawiera dekoder BLP napisany w czystym Pythonie obsługujący wszystkie warianty używane w WotLK.

### Obsługiwane kodowania

| Kodowanie | Opis | Kompresja |
|-----------|------|-----------|
| 1 | Paleta kolorów | Nieskompresowana paleta + alpha |
| 2 (typ 1) | DXT1 | 4 bpp kompresja blokowa, 1-bit alpha |
| 2 (typ 2) | DXT3 | 8 bpp, jawna 4-bitowa alpha |
| 2 (typ 3) | DXT5 | 8 bpp, interpolowana alpha (najwyższa jakość) |
| 3 | Surowe | Nieskompresowane BGRA |

Głębokości alpha: 0-bit, 1-bit, 4-bit, 8-bit. Wszystkie zdekodowane obrazy zwracane są jako obiekty RGBA `PIL.Image`.

---

## Format wyjściowy GLB

Każdy model postaci zapisywany jest jako jeden samodzielny plik GLB (binarny glTF).

### Układ bufora

Jeden bufor binarny przechowuje wszystkie dane w tej kolejności:
1. Wspólne atrybuty wierzchołków (pozycje, normalne, UV) — przeplatane
2. Bufory indeksów per-submesh

### Hierarchia węzłów

```
root (nienazwany korzeń sceny)
└── geoset_0_skin
└── geoset_1_skin
└── geoset_101_hair
└── geoset_201_skin_extra
...
```

---

## gear_compositor.py

Ten moduł jest importowany przez backend w czasie działania; nie uruchamiasz go bezpośrednio. Obsługuje:
- Parsowanie plików DBC
- Komponowanie atlasów skóry postaci
- Obliczanie widoczności geosetek

### Używane pliki DBC

| Plik DBC | Przeznaczenie |
|----------|---------------|
| `ItemDisplayInfo.dbc` | Mapuje ID wyświetlania → nazwy modeli, tekstury, grupy geosetek |
| `CharSections.dbc` | Mapuje rasa/płeć/styl/kolor → ścieżki tekstur skóry, twarzy, włosów |
| `CharHairGeosets.dbc` | Mapuje (rasa, płeć, styl włosów) → ID geosetki |
| `CharacterFacialHairStyles.dbc` | Mapuje (rasa, płeć, styl zarostu) → ID geosetek |
| `HelmetGeosetVisData.dbc` | Mapuje dane widoczności hełmu → które geosetki ukryć |

### Układ atlasu skóry 512×512

Tekstury skóry postaci są składane na stałym atlasie 512×512:

```
┌──────────────────┬──────────────────┐
│  Górne ramię     │  Górny tors      │
│  (0,0) 256×128   │  (256,0) 256×128 │
├──────────────────┤──────────────────┤
│  Dolne ramię     │  Dolny tors      │
│  (0,128) 256×128 │  (256,128) 256×64│
├──────────────────┼──────────────────┤
│  Dłonie          │  Górna noga      │
│  (0,256) 256×64  │  (256,192) 256×128│
├──────────────────┼──────────────────┤
│  Górna twarz     │  Dolna noga      │
│  (0,320) 256×64  │  (256,320) 256×128│
├──────────────────┼──────────────────┤
│  Dolna twarz     │  Stopa           │
│  (0,384) 256×128 │  (256,448) 256×64│
└──────────────────┴──────────────────┘
```

### Kolejność kompozytowania

Warstwy łączone są przy użyciu kompozytowania alpha Porter-Duff SourceOver:

1. Bazowa tekstura skóry (CharSections sekcja=0, wariacja koloru skóry)
2. Dolna + górna tekstura twarzy (sekcja=1, wariacja twarzy)
3. Dolna + górna tekstura zarostu (sekcja=2, jeśli facialStyle > 0)
4. Tekstury skóry głowy/włosów (sekcja=3, styl + kolor włosów)
5. Zbroja ciała per slot w kolejności warstw:
   - Koszula (slot 3)
   - Nadgarstek (slot 8)
   - Nogi (slot 6)
   - Buty (slot 7)
   - Tors (slot 4)
   - Rękawice (slot 9)
   - Tabard (slot 18)

### Logika widoczności geosetek

Wyposażenie kontroluje które submeshy są widoczne lub ukryte poprzez ID geosetek. Mapowanie slotu wyposażenia na grupę geosetek:

| Slot | Region ciała | Baza geosetki | Uwagi |
|------|-------------|---------------|-------|
| 0 | Głowa | 2700 | Hełm; wyzwala też HelmetGeosetVisData |
| 2 | Naramienniki | 2600 | |
| 3 | Koszula | 800, 1000 | Rękawy, tors |
| 4 | Tors | 800, 1000, 1300 | Rękawy, tors, spodnie |
| 5 | Pas | 1800 | |
| 6 | Nogi | 1100, 900, 1300 | Spodnie, mankiety, nogawki |
| 7 | Buty | 500, 2000 | Obuwie, stopy |
| 9 | Rękawice | 400, 2300 | Rękawice, przyczepa dłoni |
| 14 | Plecy/płaszcz | 1500 | Peleryna |
| 18 | Tabard | 1200 | |

Domyślne geosetki (bez wyposażenia):
```
rękawice: 401      (gołe dłonie)
buty: 501          (gołe stopy)
rękawy: 801        (bez rękawów)
tors: 1001         (goły tors)
spodnie: 1101      (bielizna)
tabard: 1200       (brak tabarda)
płaszcz: 1501      (brak płaszcza, widoczny panel pleców)
pas: 1800          (brak pasa)
naramienniki: 2600 (brak naramienników)
hełm: 2700         (brak hełmu — włosy widoczne)
```

---

## Pliki wyjściowe

| Plik | Opis |
|------|------|
| `frontend/public/models/characters/{rasa}_{płeć}.glb` | 20 plików GLB postaci |
| `frontend/public/models/manifest.json` | Mapuje `"{rasa}_{płeć}"` → `"characters/{rasa}_{płeć}.glb"` |
| `frontend/public/models/attachments.json` | Pozycje punktów przyczepu i kwaterniiony rotacji per model |

### Struktura `attachments.json`

```json
{
  "human_male": {
    "0":  { "position": [-0.074, 1.036, -0.575], "rotation": [0,0,0,1] },
    "1":  { "position": [ 0.016, 0.827,  0.059], "rotation": [0,0,0,1] },
    "2":  { "position": [-0.016, 0.827,  0.059], "rotation": [0,0,0,1] },
    "5":  { "position": [ 0.170, 1.370, -0.053], "rotation": [0,0,0,1] },
    "6":  { "position": [-0.170, 1.370, -0.053], "rotation": [0,0,0,1] },
    "11": { "position": [ 0.000, 1.860,  0.010], "rotation": [0,0,0,1] }
  }
}
```

> Rotacje są identycznościami `[0,0,0,1]` dla wszystkich modeli. Ekstrakcja rotacji kości ze Stand animacji była badana, ale wycofana z powodu problemów z formułą dekompresji i akumulacją łańcucha rodzic-dziecko. Orientacja przedmiotów jest zatem znane ograniczenie.
