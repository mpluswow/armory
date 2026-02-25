# Dokumentacja API backendu

Backend to aplikacja FastAPI nasłuchująca na `http://127.0.0.1:8000`. Wszystkie endpointy są tylko do odczytu (`GET`) i mają prefiks `/api`.

Serwer deweloperski Vite przekazuje wszystkie żądania `/api/*` do `:8000` transparentnie, więc frontend wywołuje ścieżki jak `/api/character` bez podawania hosta.

---

## `GET /api/characters`

Lista wszystkich postaci w bazie danych, posortowana malejąco według poziomu, następnie rosnąco według nazwy.

### Parametry zapytania

| Parametr | Typ | Domyślny | Ograniczenia | Opis |
|----------|-----|----------|-------------|------|
| `limit` | liczba całkowita | `100` | 1–500 | Maksymalna liczba zwracanych postaci |

### Odpowiedź `200 OK`

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
    }
  ]
}
```

### Logika frakcji

| ID Ras | Frakcja |
|--------|---------|
| 1, 3, 4, 7, 11 | Alliance (Przymierze) |
| 2, 5, 6, 8, 10 | Horde (Horda) |

---

## `GET /api/character`

Szczegółowe dane postaci wraz z wszystkimi wyposażonymi przedmiotami i statystykami.

### Parametry zapytania

| Parametr | Typ | Wymagany | Opis |
|----------|-----|----------|------|
| `name` | string | tak | Nazwa postaci (uwzględnia wielkość liter, minimum 1 znak) |

### Odpowiedź `200 OK`

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
      "name": "Hełm Zaginionego Zdobywcy",
      "quality": 4,
      "itemLevel": 213,
      "requiredLevel": 80,
      "itemType": "Head",
      "stats": [
        "+1208 Pancerza",
        "+89 Wytrzymałości",
        "+67 Intelektu",
        "+45 Oceny trafień krytycznych",
        "+50 Oceny pośpiechu"
      ],
      "description": "",
      "icon": "40186"
    }
  ]
}
```

### Pola postaci

| Pole | Typ | Opis |
|------|-----|------|
| `guid` | liczba całkowita | Unikalny ID postaci |
| `name` | string | Nazwa postaci |
| `race` | liczba całkowita | ID rasy (1–11) |
| `class` | liczba całkowita | ID klasy (1–11) |
| `gender` | liczba całkowita | 0 = Mężczyzna, 1 = Kobieta |
| `level` | liczba całkowita | Poziom postaci (1–80) |
| `skin` | liczba całkowita | Indeks wariacji koloru skóry |
| `face` | liczba całkowita | Indeks stylu twarzy |
| `hairStyle` | liczba całkowita | Indeks stylu włosów |
| `hairColor` | liczba całkowita | Indeks koloru włosów |
| `facialStyle` | liczba całkowita | Indeks zarostu/cech twarzy |

### Pola przedmiotów wyposażenia

| Pole | Typ | Opis |
|------|-----|------|
| `slot` | liczba całkowita | Slot wyposażenia 0–18 |
| `entry` | liczba całkowita | ID szablonu przedmiotu |
| `displayId` | liczba całkowita | ID wyświetlania (wizualny) |
| `name` | string | Nazwa przedmiotu |
| `quality` | liczba całkowita | 0=Lichej jakości … 7=Heirloom |
| `itemLevel` | liczba całkowita\|null | Poziom przedmiotu |
| `requiredLevel` | liczba całkowita\|null | Wymagany poziom postaci |
| `itemType` | string | Nazwa slotu |
| `stats` | string[] | Sformatowane statystyki |
| `description` | string | Tekst fabularny |
| `icon` | string | ID entry do pobrania ikony |

### Numery slotów wyposażenia

| Slot | Nazwa | Slot | Nazwa |
|------|-------|------|-------|
| 0 | Głowa | 10 | Palec 1 |
| 1 | Szyja | 11 | Palec 2 |
| 2 | Naramienniki | 12 | Talizman 1 |
| 3 | Koszula | 13 | Talizman 2 |
| 4 | Tors | 14 | Plecy |
| 5 | Pas | 15 | Prawa ręka |
| 6 | Nogi | 16 | Lewa ręka |
| 7 | Buty | 17 | Dystansowa |
| 8 | Nadgarstek | 18 | Tabard |
| 9 | Rękawice | | |

### ID Ras

| ID | Rasa | Frakcja |
|----|------|---------|
| 1 | Człowiek | Przymierze |
| 2 | Ork | Horda |
| 3 | Krasnolud | Przymierze |
| 4 | Nocny Elf | Przymierze |
| 5 | Nieumarły | Horda |
| 6 | Tauren | Horda |
| 7 | Gnom | Przymierze |
| 8 | Troll | Horda |
| 10 | Elfi Krwi | Horda |
| 11 | Draenei | Przymierze |

### ID Klas

| ID | Klasa | Kolor |
|----|-------|-------|
| 1 | Wojownik | `#C79C6E` |
| 2 | Paladyn | `#F58CBA` |
| 3 | Łowca | `#ABD473` |
| 4 | Łotrzyk | `#FFF569` |
| 5 | Kapłan | `#FFFFFF` |
| 6 | Rycerz Śmierci | `#C41F3B` |
| 7 | Szaman | `#0070DE` |
| 8 | Mag | `#69CCF0` |
| 9 | Czarnoksiężnik | `#9482C9` |
| 11 | Druid | `#FF7D0A` |

### Odpowiedzi błędów

```json
// 404 — postać nie znaleziona
{ "detail": "Character \"Nieznana\" not found" }

// 422 — brak wymaganego parametru
{ "detail": [{ "loc": ["query", "name"], "msg": "field required" }] }
```

### Cache

Wyniki cachowane są w `TTLCache` (max 256 wpisów, TTL 30 sekund) z kluczem: nazwa postaci pisana małymi literami.

---

## `GET /api/model-texture/{name}`

Generuje i zwraca złożoną teksturę skóry postaci PNG. Łączy:
- Bazowy kolor skóry
- Tekstury twarzy (dolna + górna)
- Tekstury zarostu/cech twarzy
- Nakładkę skóry głowy i koloru włosów
- Elementy zbroi per slot (koszula, tors, nogi, buty, rękawice, tabard)

**Odpowiedź `200 OK`:** `Content-Type: image/png` — obraz RGBA 512×512.

**Cache:** Klucz MD5 oparty na rasie, płci, skórze, twarzy, stylu włosów, kolorze włosów, stylu zarostu i posortowanych ID wyświetlania.

---

## `GET /api/model-hair-texture/{name}`

Zwraca teksturę **meshu** włosów dla wybranego stylu i koloru włosów postaci. Stosowana do submeshy `geoset_*_hair` w modelu 3D — inna niż nakładka skóry głowy wbudowana w atlas skóry.

**Odpowiedź `200 OK`:** `Content-Type: image/png`

---

## `GET /api/model-extra-skin-texture/{name}`

Zwraca teksturę dodatkowej skóry specyficznej dla rasy stosowaną do submeshy `geoset_*_skin_extra`. Używana dla:
- Tauren: detal futra
- Nieumarli: nakładka kości
- Inne cechy specyficzne dla rasy

Zwraca `404` dla ras bez dodatkowej tekstury skóry.

---

## `GET /api/model-cape-texture/{name}`

Zwraca teksturę płaszcza/peleryny dla wyposażonego przedmiotu na plecy (slot 14). Ładowana z `Item\ObjectComponents\Cape\` wewnątrz MPQ.

Zwraca `404` jeśli postać nie ma wyposażonego płaszcza.

---

## `GET /api/model-geosets/{name}`

Zwraca listę ID geosetek które powinny być **widoczne** dla tej postaci na podstawie wyposażenia i wyglądu. Frontend używa tego do przełączania widoczności węzłów submeshy w GLB.

### Odpowiedź `200 OK`

```json
{
  "geosets": [0, 100, 200, 300, 401, 501, 806, 1011, 1101, 1500, 1800, 2600, 2700]
}
```

Każda liczba całkowita odpowiada węzłowi `geoset_{id}_*` w pliku GLB postaci. Węzły których ID **nie ma** na liście powinny być ukryte.

---

## `GET /api/item-model/{displayId}`

Wyodrębnia i zwraca model 3D przedmiotu jako plik GLB. Obsługuje broń, tarcze, naramienniki i hełmy. Model wyodrębniany jest z MPQ przy pierwszym żądaniu i cachowany na dysku.

### Parametry ścieżki

| Parametr | Typ | Opis |
|----------|-----|------|
| `displayId` | liczba całkowita | ID wyświetlania przedmiotu z `item_template.displayid` |

### Parametry zapytania

| Parametr | Typ | Domyślny | Opis |
|----------|-----|----------|------|
| `side` | string | `"left"` | Model z `ItemDisplayInfo.dbc`: `"left"` lub `"right"` |
| `race` | liczba całkowita | `0` | ID rasy — wymagane dla hełmów (wariant specyficzny dla rasy) |
| `gender` | liczba całkowita | `0` | Płeć (0=mężczyzna, 1=kobieta) — używane z `race` dla hełmów |

### Sufiksy modeli hełmów (tylko hełmy)

| ID Rasy | Sufiks (M/K) |
|---------|-------------|
| 1 (Człowiek) | `_HuM` / `_HuF` |
| 2 (Ork) | `_OrM` / `_OrF` |
| 3 (Krasnolud) | `_DwM` / `_DwF` |
| 4 (Nocny Elf) | `_NiM` / `_NiF` |
| 5 (Nieumarły) | `_ScM` / `_ScF` |
| 6 (Tauren) | `_TaM` / `_TaF` |
| 7 (Gnom) | `_GoM` / `_GoF` |
| 8 (Troll) | `_TrM` / `_TrF` |
| 10 (Elf Krwi) | `_BeM` / `_BeF` |
| 11 (Draenei) | `_DrM` / `_DrF` |

**Odpowiedź `200 OK`:** `Content-Type: model/gltf-binary`

---

## `GET /api/character-attachments/{name}`

Zwraca pozycje punktów przyczepu i wyposażone przedmioty które powinny być renderowane w każdym punkcie. Używane przez frontend do pozycjonowania modeli 3D na postaci.

### Odpowiedź `200 OK`

```json
{
  "attachments": {
    "0":  { "position": [-0.074, 1.036, -0.575], "rotation": [0,0,0,1] },
    "1":  { "position": [ 0.016, 0.827,  0.059], "rotation": [0,0,0,1] },
    "2":  { "position": [-0.016, 0.827,  0.059], "rotation": [0,0,0,1] },
    "5":  { "position": [ 0.170, 1.370, -0.053], "rotation": [0,0,0,1] },
    "6":  { "position": [-0.170, 1.370, -0.053], "rotation": [0,0,0,1] },
    "11": { "position": [ 0.000, 1.860,  0.010], "rotation": [0,0,0,1] }
  },
  "items": {
    "mainHand":     { "displayId": 40343, "attachPoint": "1",  "hasModel": true },
    "offHand":      { "displayId": 40267, "attachPoint": "0",  "hasModel": true },
    "shoulderRight":{ "displayId": 45834, "attachPoint": "5",  "side": "right", "hasModel": true },
    "shoulderLeft": { "displayId": 45834, "attachPoint": "6",  "side": "left",  "hasModel": true },
    "helm":         { "displayId": 41628, "attachPoint": "11", "hasModel": true }
  },
  "race": 1,
  "gender": 0
}
```

### Mapowanie punktów przyczepu na sloty wyposażenia

| ID Przyczepu | Slot | Przedmiot |
|-------------|------|-----------|
| 0 | 16 (lewa ręka) | Uchwyt tarczy / trzymany przedmiot |
| 1 | 15 (prawa ręka) | Broń w prawej ręce |
| 2 | 16 (lewa ręka) | Broń w lewej ręce (dual wield) |
| 5 | 2 (naramienniki) | Prawy naramiennik |
| 6 | 2 (naramienniki) | Lewy naramiennik |
| 11 | 0 (głowa) | Hełm |

### Logika routingu lewej ręki

Przedmiot w lewej ręce (slot 16) trafia do różnych punktów przyczepu zależnie od tego czy jest bronią czy nie:

```
Typ komponentu == "Weapon" → attachPoint = "2"  (uchwyt lewej ręki)
Typ komponentu != "Weapon" → attachPoint = "0"  (uchwyt tarczy)
```

Typ komponentu jest określany przez sprawdzenie który podfolder `Item\ObjectComponents\` zawiera model.

---

## Wewnętrzne cache backendu

| Cache | Typ | Zasięg | Wygasanie |
|-------|-----|--------|-----------|
| Dane postaci | TTLCache (256 wpisów, 30s) | Per-proces | Czas |
| Bazy DBC | Globalny słownik modułu | Per-proces | Nigdy |
| Typ komponentu (displayId → typ) | Słownik modułu | Per-proces | Nigdy |
| Plik JSON punktów przyczepu | Globalny modułu | Per-proces | Nigdy |
| Tekstury PNG | System plików (`cache/*.png`) | Trwały | Ręcznie |
| Modele GLB przedmiotów | System plików (`cache/*.glb`) | Trwały | Ręcznie |
| Pula MPQ | Słownik otwartych uchwytów | Per-proces | Nigdy |
