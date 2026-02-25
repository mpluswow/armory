# Database

The application connects to the standard AzerothCore MySQL/MariaDB databases. It is **read-only** — it never writes to the database.

---

## Databases Used

| Database | Default name | Purpose |
|----------|-------------|---------|
| Characters | `acore_characters` | Character data, inventory |
| World | `acore_world` | Item template definitions |

---

## Tables

### `acore_characters.characters`

Core character information.

| Column | Type | Description |
|--------|------|-------------|
| `guid` | INT UNSIGNED | Primary key, unique character ID |
| `name` | VARCHAR(12) | Character name |
| `race` | TINYINT UNSIGNED | Race ID (1–11) |
| `class` | TINYINT UNSIGNED | Class ID (1–11) |
| `gender` | TINYINT UNSIGNED | 0 = Male, 1 = Female |
| `level` | TINYINT UNSIGNED | Level 1–80 |
| `skin` | TINYINT UNSIGNED | Skin colour variation |
| `face` | TINYINT UNSIGNED | Face style |
| `hairStyle` | TINYINT UNSIGNED | Hair style |
| `hairColor` | TINYINT UNSIGNED | Hair colour |
| `facialStyle` | TINYINT UNSIGNED | Facial hair / feature |

### `acore_characters.character_inventory`

Links items to characters.

| Column | Type | Description |
|--------|------|-------------|
| `guid` | INT UNSIGNED | Character GUID (FK → characters.guid) |
| `bag` | TINYINT UNSIGNED | 0 = equipped on character |
| `slot` | TINYINT UNSIGNED | Equipment slot (0–18 for equipped) |
| `item` | INT UNSIGNED | Item instance GUID (FK → item_instance.guid) |

Only rows with `bag = 0` and `slot < 19` are used by this application.

### `acore_characters.item_instance`

One row per item instance in the world.

| Column | Type | Description |
|--------|------|-------------|
| `guid` | INT UNSIGNED | Item instance GUID |
| `itemEntry` | MEDIUMINT UNSIGNED | Item template ID (FK → item_template.entry) |

### `acore_world.item_template`

The complete item database — one row per unique item definition.

**Columns used by this application:**

| Column | Type | Description |
|--------|------|-------------|
| `entry` | MEDIUMINT UNSIGNED | Item ID (same as itemEntry above) |
| `name` | VARCHAR(255) | Item name |
| `displayid` | MEDIUMINT UNSIGNED | Visual display ID (used to load 3D model + textures) |
| `Quality` | TINYINT UNSIGNED | 0=Poor, 1=Common, 2=Uncommon, 3=Rare, 4=Epic, 5=Legendary, 6=Artifact, 7=Heirloom |
| `ItemLevel` | SMALLINT UNSIGNED | Item level |
| `RequiredLevel` | TINYINT UNSIGNED | Required character level |
| `InventoryType` | TINYINT UNSIGNED | Inventory slot type (used to determine "Head", "Chest", etc.) |
| `bonding` | TINYINT UNSIGNED | Binding type (0=none, 1=BoP, 2=BoE, 3=BoU, 4=Quest) |
| `armor` | MEDIUMINT UNSIGNED | Armour value |
| `holy_res` | SMALLINT | Holy resistance |
| `fire_res` | SMALLINT | Fire resistance |
| `nature_res` | SMALLINT | Nature resistance |
| `frost_res` | SMALLINT | Frost resistance |
| `shadow_res` | SMALLINT | Shadow resistance |
| `arcane_res` | SMALLINT | Arcane resistance |
| `dmg_min1` | FLOAT | Minimum weapon damage |
| `dmg_max1` | FLOAT | Maximum weapon damage |
| `dmg_type1` | TINYINT UNSIGNED | Damage school (0=Physical, 1=Holy, 2=Fire, etc.) |
| `delay` | SMALLINT UNSIGNED | Weapon speed in milliseconds |
| `stat_type1`–`stat_type10` | TINYINT UNSIGNED | Stat type IDs |
| `stat_value1`–`stat_value10` | INT | Stat values |
| `description` | VARCHAR(255) | Flavour text |

---

## SQL Queries

### Character Lookup

```sql
SELECT guid, name, race, class, gender, level,
       skin, face, hairStyle, hairColor, facialStyle
FROM   characters
WHERE  name = %s
LIMIT  1
```

### Equipment Lookup

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
    it.stat_type1,  it.stat_value1,
    it.stat_type2,  it.stat_value2,
    it.stat_type3,  it.stat_value3,
    it.stat_type4,  it.stat_value4,
    it.stat_type5,  it.stat_value5,
    it.stat_type6,  it.stat_value6,
    it.stat_type7,  it.stat_value7,
    it.stat_type8,  it.stat_value8,
    it.stat_type9,  it.stat_value9,
    it.stat_type10, it.stat_value10,
    it.description
FROM   character_inventory ci
JOIN   item_instance        ii ON ci.item  = ii.guid
JOIN   acore_world.item_template it ON ii.itemEntry = it.entry
WHERE  ci.guid = %s
AND    ci.bag  = 0
AND    ci.slot < 19
ORDER  BY ci.slot
```

### Character List

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

## Stat Type IDs

The `stat_typeX` columns use integer IDs defined in the WoW DBC files. The service layer (`services/character.py`) maps these to readable names:

| ID | Stat |
|----|------|
| 0 | Mana |
| 1 | Health |
| 3 | Agility |
| 4 | Strength |
| 5 | Intellect |
| 6 | Spirit |
| 7 | Stamina |
| 12 | Defense Rating |
| 13 | Dodge Rating |
| 14 | Parry Rating |
| 15 | Block Rating |
| 16 | Melee Hit Rating |
| 17 | Ranged Hit Rating |
| 18 | Spell Hit Rating |
| 19 | Melee Crit Rating |
| 20 | Ranged Crit Rating |
| 21 | Spell Crit Rating |
| 28 | Melee Haste Rating |
| 29 | Ranged Haste Rating |
| 30 | Spell Haste Rating |
| 31 | Hit Rating |
| 32 | Critical Strike Rating |
| 35 | Resilience Rating |
| 36 | Haste Rating |
| 37 | Expertise Rating |
| 38 | Attack Power |
| 39 | Ranged Attack Power |
| 45 | Spell Power |
| 49 | Armor Penetration |
| 50 | Mana Regen per 5 sec |
| 53 | Spell Penetration |
| 54 | Block Value |

---

## Inventory Type IDs

| ID | Name | ID | Name |
|----|------|----|------|
| 1 | Head | 11 | Finger |
| 2 | Neck | 12 | Trinket |
| 3 | Shoulders | 13 | Weapon (1H) |
| 4 | Shirt | 14 | Shield |
| 5 | Chest | 15 | Ranged |
| 6 | Waist | 16 | Back |
| 7 | Legs | 17 | 2H Weapon |
| 8 | Feet | 20 | Chest (Robe) |
| 9 | Wrist | 21 | Main Hand |
| 10 | Hands | 22 | Off Hand |

---

## Connection Pool Settings

| Setting | Value |
|---------|-------|
| Minimum connections | 2 |
| Maximum connections | 10 |
| Character set | utf8mb4 |
| Row format | Dict (column name → value) |
| Autocommit | True |

The pool is created at application startup via the `lifespan` context manager in `main.py` and closed gracefully on shutdown.

---

## Recommended Indexes

AzerothCore already creates optimal indexes on its own tables. No changes are needed. For reference:

```sql
-- acore_characters.characters
-- PRIMARY KEY (guid), KEY idx_name (name) — already exists

-- acore_characters.character_inventory
-- PRIMARY KEY (guid, bag, slot) — already exists

-- acore_characters.item_instance
-- PRIMARY KEY (guid) — already exists

-- acore_world.item_template
-- PRIMARY KEY (entry) — already exists
```

---

## Verifying Your Database Connection

```bash
# Test connectivity
mysql -u acore -p -h localhost -e "USE acore_characters; SELECT COUNT(*) FROM characters;"

# List characters (should match armory's character list)
mysql -u acore -p -h localhost acore_characters \
  -e "SELECT name, race, class, level FROM characters ORDER BY level DESC LIMIT 10;"

# Verify world DB access
mysql -u acore -p -h localhost acore_world \
  -e "SELECT COUNT(*) FROM item_template;"
```
