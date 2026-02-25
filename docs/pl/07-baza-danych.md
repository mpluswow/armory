# Baza danych

Aplikacja łączy się ze standardowymi bazami danych MySQL/MariaDB AzerothCore. Jest **tylko do odczytu** — nigdy nie zapisuje danych do bazy.

---

## Używane bazy danych

| Baza | Domyślna nazwa | Przeznaczenie |
|------|----------------|---------------|
| Postacie | `acore_characters` | Dane postaci, ekwipunek |
| Świat | `acore_world` | Definicje szablonów przedmiotów |

---

## Tabele

### `acore_characters.characters`

Podstawowe informacje o postaci.

| Kolumna | Typ | Opis |
|---------|-----|------|
| `guid` | INT UNSIGNED | Klucz główny, unikalny ID postaci |
| `name` | VARCHAR(12) | Nazwa postaci |
| `race` | TINYINT UNSIGNED | ID rasy (1–11) |
| `class` | TINYINT UNSIGNED | ID klasy (1–11) |
| `gender` | TINYINT UNSIGNED | 0 = Mężczyzna, 1 = Kobieta |
| `level` | TINYINT UNSIGNED | Poziom 1–80 |
| `skin` | TINYINT UNSIGNED | Wariacja koloru skóry |
| `face` | TINYINT UNSIGNED | Styl twarzy |
| `hairStyle` | TINYINT UNSIGNED | Styl włosów |
| `hairColor` | TINYINT UNSIGNED | Kolor włosów |
| `facialStyle` | TINYINT UNSIGNED | Zarost / cechy twarzy |

### `acore_characters.character_inventory`

Łączy przedmioty z postaciami.

| Kolumna | Typ | Opis |
|---------|-----|------|
| `guid` | INT UNSIGNED | GUID postaci (FK → characters.guid) |
| `bag` | TINYINT UNSIGNED | 0 = wyposażony na postaci |
| `slot` | TINYINT UNSIGNED | Slot wyposażenia (0–18 dla wyposażonych) |
| `item` | INT UNSIGNED | GUID instancji przedmiotu |

Używane są tylko wiersze z `bag = 0` i `slot < 19`.

### `acore_characters.item_instance`

Jeden wiersz na każdą instancję przedmiotu w świecie.

| Kolumna | Typ | Opis |
|---------|-----|------|
| `guid` | INT UNSIGNED | GUID instancji przedmiotu |
| `itemEntry` | MEDIUMINT UNSIGNED | ID szablonu przedmiotu |

### `acore_world.item_template`

Kompletna baza danych przedmiotów — jeden wiersz na unikalną definicję.

| Kolumna | Typ | Opis |
|---------|-----|------|
| `entry` | MEDIUMINT UNSIGNED | ID przedmiotu |
| `name` | VARCHAR(255) | Nazwa przedmiotu |
| `displayid` | MEDIUMINT UNSIGNED | ID wyświetlania (modele 3D i tekstury) |
| `Quality` | TINYINT UNSIGNED | 0=Lichej jakości … 7=Heirloom |
| `ItemLevel` | SMALLINT UNSIGNED | Poziom przedmiotu |
| `RequiredLevel` | TINYINT UNSIGNED | Wymagany poziom postaci |
| `InventoryType` | TINYINT UNSIGNED | Typ slotu (głowa, tors, itd.) |
| `armor` | MEDIUMINT UNSIGNED | Wartość pancerza |
| `holy_res` … `arcane_res` | SMALLINT | Odporności żywiołowe |
| `dmg_min1`, `dmg_max1` | FLOAT | Minimalne/maksymalne obrażenia broni |
| `dmg_type1` | TINYINT | Szkoła obrażeń (0=Fizyczne, 1=Święte, itd.) |
| `delay` | SMALLINT | Szybkość ataku w milisekundach |
| `stat_type1`–`stat_type10` | TINYINT UNSIGNED | ID typów statystyk |
| `stat_value1`–`stat_value10` | INT | Wartości statystyk |
| `description` | VARCHAR(255) | Tekst fabularny |

---

## Zapytania SQL

### Wyszukiwanie postaci

```sql
SELECT guid, name, race, class, gender, level,
       skin, face, hairStyle, hairColor, facialStyle
FROM   characters
WHERE  name = %s
LIMIT  1
```

### Wyszukiwanie wyposażenia

```sql
SELECT
    ci.slot,
    it.entry,
    it.displayid          AS displayId,
    it.name,
    it.Quality            AS quality,
    it.ItemLevel          AS itemLevel,
    it.RequiredLevel      AS requiredLevel,
    it.InventoryType      AS inventoryType,
    it.bonding,
    it.armor,
    it.holy_res, it.fire_res, it.nature_res,
    it.frost_res, it.shadow_res, it.arcane_res,
    it.dmg_min1, it.dmg_max1, it.dmg_type1, it.delay,
    it.stat_type1, it.stat_value1,
    -- ... stat_type2-10 i stat_value2-10 ...
    it.description
FROM   character_inventory ci
JOIN   item_instance        ii ON ci.item  = ii.guid
JOIN   acore_world.item_template it ON ii.itemEntry = it.entry
WHERE  ci.guid = %s
AND    ci.bag  = 0
AND    ci.slot < 19
ORDER  BY ci.slot
```

### Lista postaci

```sql
SELECT
    name, race, class, level,
    CASE
        WHEN race IN (1, 3, 4, 7, 11) THEN 'Alliance'
        ELSE 'Horde'
    END AS faction
FROM   characters
ORDER  BY level DESC, name ASC
LIMIT  %s
```

---

## ID Typów statystyk

| ID | Statystyka | ID | Statystyka |
|----|------------|----|----|
| 0 | Mana | 31 | Ocena trafień |
| 1 | Zdrowie | 32 | Ocena trafień krytycznych |
| 3 | Zręczność | 35 | Ocena odporności (PvP) |
| 4 | Siła | 36 | Ocena pośpiechu |
| 5 | Intelekt | 37 | Ocena Ekspertyzy |
| 6 | Duch | 38 | Moc ataku |
| 7 | Wytrzymałość | 39 | Dystansowa moc ataku |
| 12 | Ocena obrony | 45 | Moc zaklęć |
| 13 | Ocena uników | 49 | Penetracja pancerza |
| 14 | Ocena parowania | 50 | Regeneracja many co 5 sek |
| 15 | Ocena blokowania | 53 | Penetracja zaklęć |
| 16 | Ocena trafień walki | 54 | Wartość bloku |

---

## Weryfikacja połączenia z bazą

```bash
# Test połączenia
mysql -u acore -p -h localhost -e "USE acore_characters; SELECT COUNT(*) FROM characters;"

# Lista postaci (powinna zgadzać się z listą w Armory)
mysql -u acore -p -h localhost acore_characters \
  -e "SELECT name, race, class, level FROM characters ORDER BY level DESC LIMIT 10;"

# Weryfikacja dostępu do bazy świata
mysql -u acore -p -h localhost acore_world \
  -e "SELECT COUNT(*) FROM item_template;"
```

---

## Ustawienia puli połączeń

| Ustawienie | Wartość |
|------------|---------|
| Minimalna liczba połączeń | 2 |
| Maksymalna liczba połączeń | 10 |
| Zestaw znaków | utf8mb4 |
| Format wierszy | Słownik (nazwa kolumny → wartość) |
| Autocommit | True |

Pula tworzona jest przy starcie aplikacji w handlerze `lifespan` w `main.py`.
