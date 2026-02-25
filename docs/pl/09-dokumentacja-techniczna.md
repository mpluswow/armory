# Dokumentacja techniczna

Ten dokument opisuje wewnętrzne formaty danych, układy współrzędnych i algorytmy używane przez pipeline ekstrakcji i backend.

---

## Format modeli WoW M2

M2 (zwany też MD20) to własnościowy binarny format modeli Blizzarda używany dla postaci, stworów i przedmiotów w WotLK 3.3.5a.

### Identyfikacja pliku

Pierwsze 4 bajty: `4D 44 32 30` = ASCII "MD20"

### Kluczowe offsety nagłówka

Wszystkie offsety od początku pliku:

| Offset | Rozmiar | Pole | Opis |
|--------|---------|------|------|
| 0x00 | 4 | magic | "MD20" |
| 0x04 | 4 | version | Wersja pliku (264 dla WotLK) |
| 0x14 | 4 | nVertices | Liczba wierzchołków |
| 0x18 | 4 | ofsVertices | Offset tablicy wierzchołków |
| 0x1C | 4 | ofsSequences | **M2Array** sekwencji animacji |
| 0x2C | 4 | ofsBones | **M2Array** definicji kości |
| 0x30 | 4 | nBones | Liczba kości |
| 0x48 | 4 | nTextures | Liczba tekstur |
| 0x4C | 4 | ofsTextures | Offset definicji tekstur |
| 0x88 | 4 | nTextureCombos | Liczba kombinacji tekstur |
| 0x8C | 4 | ofsTextureCombos | Offset kombinacji tekstur |
| 0xF0 | 4 | nAttachments | Liczba punktów przyczepu |
| 0xF4 | 4 | ofsAttachments | Offset danych przyczepu |

> **Ważne:** Dane kości są pod offsetem **0x2C**, nie 0x6C jak podaje część starszej dokumentacji.

### Struktura M2Array

Wiele pól nagłówka M2 używa struktury M2Array:
```
Offset +0: uint32  count
Offset +4: uint32  offset (offset bajtowy od początku pliku)
```

### Struktura wierzchołka (48 bajtów)

```
+0  float[3]  position        Przestrzeń współrzędnych WoW
+12 uint8[4]  bone_weights    Wagi skinowania, suma = 255
+16 uint8[4]  bone_indices    Indeksy do tablicy kości
+20 float[3]  normal
+32 float[2]  uv_coord_1
+40 float[2]  uv_coord_2
```

### Struktura kości (88 bajtów)

```
+0  int32     boneId          DBC ID kości (-1 jeśli brak)
+4  uint32    flags
+8  int16     parent          Indeks kości rodzica (-1 dla korzenia)
+10 uint16    submeshId
+12 uint32    unknown[2]
+16 M2Track   translation     Ścieżka animacji (vec3)
+32 M2Track   rotation        Ścieżka animacji (kwaternion) (M2CompQuat!)
+48 M2Track   scale           Ścieżka animacji (vec3)
+76 float[3]  pivot           Absolutny punkt obrotu w przestrzeni modelu
```

> **Krytyczne:** Punkty obrotu kości są w **absolutnej przestrzeni modelu**, nie względem kości rodzica.

### Struktura M2Track

```
+0  uint16    interpolation_type
+2  int16     global_sequence  (-1 = brak globalnej sekwencji)
+4  M2Array   timestamps       (uint32 na klatkę)
+12 M2Array   values           (zależy od typu)
```

### Sekwencje animacji

Tablica sekwencji jest pod offsetem z M2Array w nagłówku `0x1C`. Każdy wpis ma 64 bajty:

```
+0  uint16    animId       ID animacji (0 = Stand)
+2  uint16    subAnimId
+4  uint32    length       Czas trwania w milisekundach
...
```

Wyszukiwanie animacji Stand:
```python
def _find_stand_anim_index(m2_data):
    # Odczyt M2Array z 0x1C
    n_seqs, ofs_seqs = struct.unpack_from('<II', m2_data, 0x1C)
    for i in range(n_seqs):
        anim_id = struct.unpack_from('<H', m2_data, ofs_seqs + i * 64)[0]
        if anim_id == 0:  # Stand
            return i
    return 0  # fallback
```

---

## M2CompQuat (Skompresowany kwaternion)

Ścieżki rotacji kości przechowują kwaterniony jako `M2CompQuat` — cztery 16-bitowe liczby całkowite ze znakiem.

### Formuła dekompresji

```python
def decompress_quat(v: int) -> float:
    if v < 0:          # ujemna int16
        return (v + 32768) / 32767.0 - 1.0
    else:
        return (v - 32767) / 32767.0
```

Zakres wyniku: [-1.0, 1.0]. Zastosować do każdego z czterech składowych (x, y, z, w).

> Format M2CompQuat przechowuje wartości inaczej dla zakresów ujemnych i dodatnich — to ważna różnica względem prostego skalowania int16.

---

## Punkty przyczepu

Każdy wpis przyczepu w M2 ma 40 bajtów:

```
+0  uint32    id          ID slotu przyczepu
+4  uint16    bone        Indeks kości rodzica
+6  uint16    unknown
+8  float[3]  position    W przestrzeni modelu WoW (absolutna)
+20 M2Track   visibility  Nieużywane przez tę aplikację
```

### Mapowanie ID przyczepu

| ID | Przeznaczenie |
|----|---------------|
| 0 | Uchwyt tarczy (lewa ręka, nie-broniowy) |
| 1 | Prawa ręka (uchwyt broni głównej) |
| 2 | Lewa ręka (uchwyt broni / dual wield) |
| 5 | Prawy naramiennik |
| 6 | Lewy naramiennik |
| 11 | Hełm |
| 26 | Plecy (schowana broń) |
| 27 | Prawe biodro (schowana broń) |
| 28 | Lewe biodro (schowana broń) |

---

## Konwersja układu współrzędnych

WoW i glTF (konwencja OpenGL) używają różnych prawostronnych układów współrzędnych.

### Przestrzeń M2 WoW
- X = w prawo
- Y = do przodu (w głąb ekranu)
- Z = w górę

### Przestrzeń glTF / Three.js
- X = w prawo
- Y = w górę
- Z = w stronę widza (z ekranu)

### Konwersja

Stosowana do każdej pozycji wierzchołka, normali i pozycji punktu przyczepu:

```python
gltf_x = wow_x
gltf_y = wow_z      # Z WoW staje się Y glTF (góra)
gltf_z = -wow_y     # Y WoW staje się -Z glTF (odwrócony kierunek)
```

Dla kwaternionów (rotacji):
```python
gltf_qx = wow_qx
gltf_qy = wow_qz
gltf_qz = -wow_qy
gltf_qw = wow_qw    # część skalarna bez zmian
```

### Obrót modelu postaci

Po konwersji układu współrzędnych modele postaci są zwrócone tyłem do widza. Komponent `ModelViewer` kompensuje to dodatkowym obrotem o 180° wokół osi Y.

---

## Transformacja pivot-sandwich

Lokalne transformacje kości używają wzorca "pivot sandwich":

```
Local = T(pivot + translation) * R(rotation) * S(scale) * T(-pivot)
World = parent.World * Local
```

Gdzie:
- `T(v)` = macierz translacji
- `R(q)` = macierz rotacji z kwaternionu
- `S(v)` = macierz skali
- `pivot` = absolutny punkt obrotu kości w przestrzeni modelu

Ponieważ punkty obrotu są w przestrzeni **absolutnej**, człon `-pivot` na końcu anuluje przesunięcie obrotu, następnie stosowana jest transformacja i pivot jest ponownie dodawany — co zapewnia poprawne pozycje kości potomnych względem początku modelu.

---

## Format tekstur BLP

BLP to własnościowy format tekstur Blizzarda. WotLK używa BLP2 (nagłówek: `BLP2`).

### Nagłówek

```
+0   char[4]     magic         "BLP2"
+4   uint32      type          0=JPEG, 1=Direct
+8   uint8       encoding      1=nieskompresowana, 2=DXT, 3=surowe BGRA
+9   uint8       alphaDepth    0, 1, 4 lub 8
+10  uint8       alphaEncoding 0=DXT1, 1=DXT3, 7=DXT5
+11  uint8       hasMips
+12  uint32      width
+16  uint32      height
+20  uint32[16]  mipOffsets
+84  uint32[16]  mipSizes
+148 uint32[256] palette       (tylko dla encoding=1)
```

### Dekodowanie według typu kodowania

| Kodowanie | Głębokość alpha | Kompresja |
|-----------|-----------------|-----------|
| 1 | 0 | Paleta, bez alpha |
| 1 | 1 | Paleta, 1-bitowa alpha |
| 1 | 8 | Paleta, 8-bitowa alpha |
| 2 | dowolna | DXT1/DXT3/DXT5 (wg alphaEncoding) |
| 3 | dowolna | Nieskompresowane BGRA |

DXT1: 4 bpp, 1-bitowa alpha
DXT3: 8 bpp, jawna 4-bitowa alpha
DXT5: 8 bpp, interpolowana alpha (najwyższa jakość)

Wszystkie zdekodowane obrazy zwracane są jako obiekty RGBA `PIL.Image`.

---

## Format pliku DBC

DBC (DataBase Client) przechowuje statyczne dane gry (statystyki przedmiotów, informacje o rasach, sekwencje animacji itd.). Pliki te znajdują się w archiwach MPQ lokalizacyjnych.

### Nagłówek

```
+0  char[4]  magic          "WDBC"
+4  uint32   recordCount
+8  uint32   fieldCount
+12 uint32   recordSize      (fieldCount × 4)
+16 uint32   stringBlockSize
```

### Układ

```
Nagłówek (20 bajtów)
Rekordy (recordCount × recordSize bajtów)
Blok tekstów (stringBlockSize bajtów)
```

Teksty przechowywane są jako offsety do bloku tekstów (płaska pula tekstów zakończonych zerem). Pole całkowite pod offsetem bajtowym `fieldIndex * 4` w rekordzie.

### Używane pliki DBC

| DBC | Lokalizacja w MPQ | Używane pola |
|-----|-------------------|--------------|
| `ItemDisplayInfo.dbc` | `patch.MPQ` | displayId → modele, tekstury, geosetki, dane hełmów |
| `CharSections.dbc` | `locale-enUS.MPQ` | rasa/płeć/sekcja → ścieżki tekstur skóry, twarzy, włosów |
| `CharHairGeosets.dbc` | `locale-enUS.MPQ` | rasa/płeć/styl włosów → ID geosetki |
| `CharacterFacialHairStyles.dbc` | `locale-enUS.MPQ` | rasa/płeć/styl zarostu → ID geosetek |
| `HelmetGeosetVisData.dbc` | `locale-enUS.MPQ` | visId → które geosetki ukryć |

---

## Kolejność ładowania archiwów MPQ

Pliki w późniejszych łatkach nadpisują pliki z wcześniejszych archiwów. Pipeline przeszukuje w tej kolejności (wcześniejsze = wyższy priorytet):

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

Nie wszystkie muszą istnieć. Pipeline odczytuje te, które są dostępne.

---

## System ID geosetek

Modele postaci zawierają wiele nakładających się submeshy. Format M2 używa "geosetek" do grupowania submeshy reprezentujących ten sam region ciała w różnych stanach wyposażenia.

### Zakresy ID geosetek

| Zakres | Część ciała |
|--------|-------------|
| 0 | Baza postaci (zawsze widoczna) |
| 100–199 | Włosy |
| 200–299 | Dodatkowa skóra / detale twarzy |
| 300–399 | Twarz / zarost |
| 400–499 | Rękawice / dłonie |
| 500–599 | Buty / stopy |
| 600–699 | Uszy |
| 700–799 | Rękawy |
| 800–899 | Nogawki spodni |
| 900–999 | Mankiety nogawek |
| 1000–1099 | Tors |
| 1100–1199 | Spodnie |
| 1200–1299 | Tabard |
| 1300–1399 | Górne spodnie |
| 1400–1499 | Nieznane |
| 1500–1599 | Peleryna / płaszcz |
| 1600–1699 | Nieznane |
| 1700–1799 | Nieznane |
| 1800–1899 | Pas |
| 2000–2099 | Stopy (gołe vs obuwie) |
| 2300–2399 | Przyczepa dłoni |
| 2600–2699 | Naramienniki |
| 2700–2799 | Hełm |

### Obliczanie aktywnych geosetek na podstawie wyposażenia

Dla każdego wyposażonego przedmiotu:
1. Wyszukaj `displayId` przedmiotu w `ItemDisplayInfo.dbc`
2. Pobierz grupy geosetek `(g1, g2, g3)` z rekordu DBC
3. Dodaj `baza + g_n` do aktywnego zestawu dla każdego regionu ciała

Dla regionów ciała bez wyposażenia w danym slocie używany jest domyślny ID geosetki (baza + 0 lub baza + 1).

---

## Układ cache systemu plików

Wszystkie wygenerowane w czasie działania zasoby są cachowane w `frontend/public/models/cache/`. Nazwy plików są deterministyczne i oparte na parametrach generowania.

### Klucze cache tekstur skóry

```
{12-znakowy hash MD5}.png
```

MD5 obliczany z:
```
{rasa}_{płeć}_{skóra}_{twarz}_{stylWłosów}_{kolorWłosów}_{stylZarostu}_{posortowane displayId}
```

### Klucze cache modeli przedmiotów

```
item_{displayId}_{side}[_{RasaPłeć}].glb
```

Przykłady:
- `item_40343_right.glb` — miecz w prawej ręce
- `item_41628_left_NiM.glb` — hełm Nocnego Elfa (Mężczyzna)

### Specjalne klucze tekstur

```
hair_{rasa}_{płeć}_{stylWłosów}_{kolorWłosów}   → {hash}.png
extraskin_{rasa}_{płeć}_{skóra}                  → {hash}.png
cape_{displayId}                                  → {hash}.png
```
