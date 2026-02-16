import aiomysql

from config import settings
from database import get_conn

STAT_TYPES = {
    0: "Mana", 1: "Health", 3: "Agility", 4: "Strength", 5: "Intellect",
    6: "Spirit", 7: "Stamina", 12: "Defense Rating", 13: "Dodge Rating",
    14: "Parry Rating", 15: "Block Rating", 16: "Hit Melee Rating",
    17: "Hit Ranged Rating", 18: "Hit Spell Rating", 19: "Crit Melee Rating",
    20: "Crit Ranged Rating", 21: "Crit Spell Rating", 22: "Hit Taken Melee Rating",
    23: "Hit Taken Ranged Rating", 24: "Hit Taken Spell Rating",
    25: "Crit Taken Melee Rating", 26: "Crit Taken Ranged Rating",
    27: "Crit Taken Spell Rating", 28: "Haste Melee Rating",
    29: "Haste Ranged Rating", 30: "Haste Spell Rating", 31: "Hit Rating",
    32: "Crit Rating", 33: "Hit Taken Rating", 34: "Crit Taken Rating",
    35: "Resilience Rating", 36: "Haste Rating", 37: "Expertise Rating",
    38: "Attack Power", 39: "Ranged Attack Power", 40: "Versatility",
    41: "Spell Healing Done", 42: "Spell Damage Done", 43: "Mana Regeneration",
    44: "Armor Penetration Rating", 45: "Spell Power", 46: "Health Regen",
    47: "Spell Penetration", 48: "Block Value",
}

INV_TYPES = {
    0: "Non-equippable", 1: "Head", 2: "Neck", 3: "Shoulder", 4: "Shirt",
    5: "Chest", 6: "Waist", 7: "Legs", 8: "Feet", 9: "Wrist", 10: "Hands",
    11: "Finger", 12: "Trinket", 13: "One-Hand", 14: "Shield", 15: "Ranged",
    16: "Back", 17: "Two-Hand", 18: "Bag", 19: "Tabard", 20: "Chest",
    21: "Main Hand", 22: "Off Hand", 23: "Holdable", 24: "Ammo",
    25: "Thrown", 26: "Ranged", 28: "Relic",
}

DMG_TYPES = {0: "Physical", 1: "Holy", 2: "Fire", 3: "Nature", 4: "Frost", 5: "Shadow", 6: "Arcane"}

WORLD_DB = settings.WORLD_DB_NAME

CHARACTER_SQL = """
    SELECT guid, name, race, class, gender, level, skin, face,
           hairStyle, hairColor, facialStyle
    FROM characters WHERE name = %s LIMIT 1
"""

EQUIPMENT_SQL = f"""
    SELECT
        ci.slot,
        ii.itemEntry as entry,
        it.displayid,
        it.name,
        it.Quality as quality,
        it.ItemLevel,
        it.InventoryType,
        it.RequiredLevel,
        it.stat_type1, it.stat_value1,
        it.stat_type2, it.stat_value2,
        it.stat_type3, it.stat_value3,
        it.stat_type4, it.stat_value4,
        it.stat_type5, it.stat_value5,
        it.stat_type6, it.stat_value6,
        it.stat_type7, it.stat_value7,
        it.stat_type8, it.stat_value8,
        it.stat_type9, it.stat_value9,
        it.stat_type10, it.stat_value10,
        it.armor,
        it.block,
        it.holy_res,
        it.fire_res,
        it.nature_res,
        it.frost_res,
        it.shadow_res,
        it.arcane_res,
        it.delay,
        it.dmg_min1, it.dmg_max1, it.dmg_type1,
        it.dmg_min2, it.dmg_max2, it.dmg_type2,
        it.bonding,
        it.description
    FROM character_inventory ci
    INNER JOIN item_instance ii ON ci.item = ii.guid
    INNER JOIN {WORLD_DB}.item_template it ON ii.itemEntry = it.entry
    WHERE ci.guid = %s AND ci.bag = 0 AND ci.slot < 19
    ORDER BY ci.slot
"""

LIST_SQL = """
    SELECT name, race, class, level,
    CASE WHEN race IN (1,3,4,7,11) THEN 'Alliance' ELSE 'Horde' END as faction
    FROM characters ORDER BY level DESC, name LIMIT %s
"""


def _format_equipment(items: list[dict]) -> list[dict]:
    result = []
    for item in items:
        stats = []

        if item.get("armor", 0) > 0:
            stats.append(f"+{item['armor']} Armor")

        for i in range(1, 11):
            st = item.get(f"stat_type{i}")
            sv = item.get(f"stat_value{i}")
            if st and sv:
                stats.append(f"+{sv} {STAT_TYPES.get(st, f'Stat {st}')}")

        for res_key, res_name in [
            ("holy_res", "Holy"), ("fire_res", "Fire"), ("nature_res", "Nature"),
            ("frost_res", "Frost"), ("shadow_res", "Shadow"), ("arcane_res", "Arcane"),
        ]:
            if item.get(res_key, 0) > 0:
                stats.append(f"+{item[res_key]} {res_name} Resistance")

        if item.get("dmg_min1") and item.get("dmg_max1"):
            dmg_type = DMG_TYPES.get(item.get("dmg_type1", 0), "Physical")
            stats.append(f"{item['dmg_min1']}-{item['dmg_max1']} {dmg_type} Damage")
            if item.get("delay"):
                stats.append(f"Speed {item['delay'] / 1000.0:.2f}")

        result.append({
            "slot": int(item["slot"]),
            "entry": int(item["entry"]),
            "displayId": int(item["displayid"]),
            "name": item["name"],
            "quality": int(item["quality"]),
            "itemLevel": int(item["ItemLevel"]) if item.get("ItemLevel") else None,
            "requiredLevel": int(item["RequiredLevel"]) if item.get("RequiredLevel") else None,
            "itemType": INV_TYPES.get(item.get("InventoryType", 0), "Item"),
            "stats": stats,
            "description": item.get("description", ""),
            "icon": str(item["entry"]),
        })
    return result


async def get_character(name: str) -> dict | None:
    async with get_conn() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(CHARACTER_SQL, (name,))
            char = await cur.fetchone()
            if not char:
                return None

            await cur.execute(EQUIPMENT_SQL, (char["guid"],))
            equipment = await cur.fetchall()

            return {
                "guid": char["guid"],
                "name": char["name"],
                "race": int(char["race"]),
                "class": int(char["class"]),
                "gender": int(char["gender"]),
                "level": int(char["level"]),
                "skin": int(char["skin"]),
                "face": int(char["face"]),
                "hairStyle": int(char["hairStyle"]),
                "hairColor": int(char["hairColor"]),
                "facialStyle": int(char["facialStyle"]),
                "equipment": _format_equipment(equipment),
            }


async def list_characters(limit: int = 100) -> dict:
    async with get_conn() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(LIST_SQL, (limit,))
            rows = await cur.fetchall()
            return {"count": len(rows), "characters": rows}
