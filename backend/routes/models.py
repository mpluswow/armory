import hashlib
import json
import os
import sys

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, JSONResponse

from config import settings
from services.character import get_character

# Project root is 3 levels up from routes/models.py: routes/ -> backend/ -> armory/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add tools dir to path for gear compositor
TOOLS_DIR = os.path.join(PROJECT_ROOT, "tools")
sys.path.insert(0, TOOLS_DIR)

router = APIRouter(prefix="/api")

DATA_DIR = os.path.join(PROJECT_ROOT, "Data")
MODELS_DIR = os.path.join(PROJECT_ROOT, "frontend", "public", "models")
CACHE_DIR = os.path.join(MODELS_DIR, "cache")

RACE_MODEL_NAMES = {
    1: "human", 2: "orc", 3: "dwarf", 4: "nightelf", 5: "undead",
    6: "tauren", 7: "gnome", 8: "troll", 10: "bloodelf", 11: "draenei",
}

# Lazy-loaded DBC databases (shared across requests)
_display_info_db = None
_hair_geosets_db = None
_facial_hair_db = None
_helmet_geoset_vis_db = None


def _get_display_info_db():
    global _display_info_db
    if _display_info_db is None:
        from gear_compositor import load_dbc_from_mpq, ItemDisplayInfoDB
        dbc_data = load_dbc_from_mpq(DATA_DIR, "ItemDisplayInfo.dbc")
        if dbc_data:
            _display_info_db = ItemDisplayInfoDB(dbc_data)
    return _display_info_db


def _get_hair_dbs():
    global _hair_geosets_db, _facial_hair_db
    if _hair_geosets_db is None:
        from gear_compositor import load_dbc_from_mpq, CharHairGeosetsDB, CharFacialHairDB
        data = load_dbc_from_mpq(DATA_DIR, "CharHairGeosets.dbc")
        if data:
            _hair_geosets_db = CharHairGeosetsDB(data)
        data = load_dbc_from_mpq(DATA_DIR, "CharacterFacialHairStyles.dbc")
        if data:
            _facial_hair_db = CharFacialHairDB(data)
    return _hair_geosets_db, _facial_hair_db


def _get_helmet_geoset_vis_db():
    global _helmet_geoset_vis_db
    if _helmet_geoset_vis_db is None:
        from gear_compositor import load_dbc_from_mpq, HelmetGeosetVisDataDB
        data = load_dbc_from_mpq(DATA_DIR, "HelmetGeosetVisData.dbc")
        if data:
            _helmet_geoset_vis_db = HelmetGeosetVisDataDB(data)
    return _helmet_geoset_vis_db


_component_type_cache: dict[int, str | None] = {}


def _get_item_component_type(display_id: int) -> str | None:
    """Check which MPQ component folder contains this item's model.
    Returns 'Weapon', 'Shield', 'Shoulder', 'Head', or None.
    Uses persistent MPQ pool for fast lookups."""
    if display_id in _component_type_cache:
        return _component_type_cache[display_id]
    db = _get_display_info_db()
    if not db:
        return None
    info = db.get_item_model_info(display_id)
    model_name = info.get("leftModel", "") or info.get("rightModel", "")
    if not model_name:
        return None
    base = model_name
    for ext in [".m2", ".M2", ".mdx", ".MDX"]:
        base = base.replace(ext, "")
    from extract_models import _read_from_mpqs, MPQ_LOAD_ORDER
    mpq_list = [os.path.join(DATA_DIR, n) for n in MPQ_LOAD_ORDER
                if os.path.exists(os.path.join(DATA_DIR, n))]
    for comp in ["Shield", "Weapon", "Shoulder", "Head"]:
        m2_path = f"Item\\ObjectComponents\\{comp}\\{base}.m2"
        if _read_from_mpqs(mpq_list, m2_path):
            _component_type_cache[display_id] = comp
            return comp
    _component_type_cache[display_id] = None
    return None


@router.get("/model-texture/{name}")
async def get_model_texture(name: str):
    """Generate a composited character texture with equipped gear baked in.
    Returns a PNG image that the frontend can use as a texture override.
    """
    char = await get_character(name)
    if not char:
        return JSONResponse({"error": "Character not found"}, status_code=404)

    race_key = RACE_MODEL_NAMES.get(char["race"], "human")
    gender = char["gender"]
    skin = char["skin"]
    face = char.get("face", 0)
    hair_style = char.get("hairStyle", 0)
    hair_color = char.get("hairColor", 0)
    facial_style = char.get("facialStyle", 0)
    equipment = char["equipment"]

    # Build a cache key from character appearance + equipped display IDs
    display_ids = sorted(str(e["displayId"]) for e in equipment if e.get("displayId"))
    cache_key_str = f"{race_key}_{gender}_{skin}_{face}_{hair_style}_{hair_color}_{facial_style}_{'_'.join(display_ids)}"
    cache_hash = hashlib.md5(cache_key_str.encode()).hexdigest()[:12]
    cache_path = os.path.join(CACHE_DIR, f"{cache_hash}.png")

    if os.path.exists(cache_path):
        return FileResponse(cache_path, media_type="image/png")

    # Generate composited texture
    try:
        from gear_compositor import generate_character_texture

        img = generate_character_texture(
            DATA_DIR, race_key, gender, skin, equipment,
            face=face, hair_style=hair_style, hair_color=hair_color,
            facial_style=facial_style,
        )
        if img is None:
            return JSONResponse({"error": "Could not generate texture"}, status_code=500)

        os.makedirs(CACHE_DIR, exist_ok=True)
        img.save(cache_path, "PNG")
        return FileResponse(cache_path, media_type="image/png")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/model-hair-texture/{name}")
async def get_model_hair_texture(name: str):
    """Serve the hair model texture for a character's 3D hair mesh (type 6).
    This is the texture applied to hair geometry, NOT the scalp overlay on the skin atlas.
    """
    char = await get_character(name)
    if not char:
        return JSONResponse({"error": "Character not found"}, status_code=404)

    race_key = RACE_MODEL_NAMES.get(char["race"], "human")
    gender = char["gender"]
    hair_style = char.get("hairStyle", 0)
    hair_color = char.get("hairColor", 0)

    cache_key_str = f"hair_{race_key}_{gender}_{hair_style}_{hair_color}"
    cache_hash = hashlib.md5(cache_key_str.encode()).hexdigest()[:12]
    cache_path = os.path.join(CACHE_DIR, f"{cache_hash}.png")

    if os.path.exists(cache_path):
        return FileResponse(cache_path, media_type="image/png")

    try:
        from gear_compositor import (
            _get_char_sections_db, RACE_INFO, build_mpq_list, load_blp_from_mpq,
        )

        char_sections = _get_char_sections_db(DATA_DIR)
        if not char_sections:
            return JSONResponse({"error": "DBC not available"}, status_code=500)

        _, race_id = RACE_INFO.get(race_key, ("Human", 1))
        hair_tex_path = char_sections.get_hair_model_texture(race_id, gender, hair_style, hair_color)
        if not hair_tex_path:
            return JSONResponse({"error": "Hair texture not found"}, status_code=404)

        mpq_archives = build_mpq_list(DATA_DIR)
        img = load_blp_from_mpq(mpq_archives, hair_tex_path)
        if img is None:
            return JSONResponse({"error": "Could not decode hair texture"}, status_code=500)

        os.makedirs(CACHE_DIR, exist_ok=True)
        img.save(cache_path, "PNG")
        return FileResponse(cache_path, media_type="image/png")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/model-extra-skin-texture/{name}")
async def get_model_extra_skin_texture(name: str):
    """Serve the extra skin texture (type 8) for races that have it (tauren fur, etc.)."""
    char = await get_character(name)
    if not char:
        return JSONResponse({"error": "Character not found"}, status_code=404)

    race_key = RACE_MODEL_NAMES.get(char["race"], "human")
    gender = char["gender"]
    skin = char["skin"]

    cache_key_str = f"extraskin_{race_key}_{gender}_{skin}"
    cache_hash = hashlib.md5(cache_key_str.encode()).hexdigest()[:12]
    cache_path = os.path.join(CACHE_DIR, f"{cache_hash}.png")

    if os.path.exists(cache_path):
        return FileResponse(cache_path, media_type="image/png")

    try:
        from gear_compositor import (
            _get_char_sections_db, RACE_INFO, build_mpq_list, load_blp_from_mpq,
        )

        char_sections = _get_char_sections_db(DATA_DIR)
        if not char_sections:
            return JSONResponse({"error": "DBC not available"}, status_code=500)

        _, race_id = RACE_INFO.get(race_key, ("Human", 1))
        extra_path = char_sections.get_extra_skin_texture(race_id, gender, skin)
        if not extra_path:
            return JSONResponse({"error": "Extra skin texture not found"}, status_code=404)

        mpq_archives = build_mpq_list(DATA_DIR)
        img = load_blp_from_mpq(mpq_archives, extra_path)
        if img is None:
            return JSONResponse({"error": "Could not decode extra skin texture"}, status_code=500)

        os.makedirs(CACHE_DIR, exist_ok=True)
        img.save(cache_path, "PNG")
        return FileResponse(cache_path, media_type="image/png")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/model-cape-texture/{name}")
async def get_model_cape_texture(name: str):
    """Serve the cape/cloak texture for a character's equipped back item (slot 14, type 2 meshes)."""
    char = await get_character(name)
    if not char:
        return JSONResponse({"error": "Character not found"}, status_code=404)

    # Find slot 14 (back/cape) equipment
    cape_item = None
    for item in char["equipment"]:
        if item.get("slot") == 14 and item.get("displayId"):
            cape_item = item
            break

    if not cape_item:
        return JSONResponse({"error": "No cape equipped"}, status_code=404)

    display_id = cape_item["displayId"]

    cache_key_str = f"cape_{display_id}"
    cache_hash = hashlib.md5(cache_key_str.encode()).hexdigest()[:12]
    cache_path = os.path.join(CACHE_DIR, f"{cache_hash}.png")

    if os.path.exists(cache_path):
        return FileResponse(cache_path, media_type="image/png")

    try:
        from gear_compositor import build_mpq_list, load_blp_from_mpq

        db = _get_display_info_db()
        if db is None:
            return JSONResponse({"error": "DBC data not available"}, status_code=500)

        tex_name = db.get_cape_texture(display_id)
        if not tex_name:
            return JSONResponse({"error": "Cape texture not found in DBC"}, status_code=404)

        mpq_archives = build_mpq_list(DATA_DIR)

        # Cape textures live in Item\ObjectComponents\Cape\
        img = load_blp_from_mpq(mpq_archives, f"Item\\ObjectComponents\\Cape\\{tex_name}.blp")
        if img is None:
            return JSONResponse({"error": "Could not decode cape texture"}, status_code=500)

        os.makedirs(CACHE_DIR, exist_ok=True)
        img.save(cache_path, "PNG")
        return FileResponse(cache_path, media_type="image/png")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/model-geosets/{name}")
async def get_model_geosets(name: str):
    """Return the list of active geoset IDs for a character based on equipment.

    The frontend uses this to show/hide submeshes in the 3D model.
    Each geoset ID corresponds to a mesh node named 'geoset_{id}_{textype}' in the GLB.
    """
    char = await get_character(name)
    if not char:
        return JSONResponse({"error": "Character not found"}, status_code=404)

    equipment = char["equipment"]

    try:
        from gear_compositor import compute_active_geosets

        db = _get_display_info_db()
        if db is None:
            return JSONResponse({"error": "DBC data not available"}, status_code=500)

        hair_db, facial_db = _get_hair_dbs()
        hgv_db = _get_helmet_geoset_vis_db()

        active = compute_active_geosets(
            equipment, db,
            race=char["race"],
            gender=char["gender"],
            hair_style=char.get("hairStyle", 0),
            facial_style=char.get("facialStyle", 0),
            hair_geosets_db=hair_db,
            facial_hair_db=facial_db,
            helmet_geoset_vis_db=hgv_db,
        )
        return JSONResponse({"geosets": active})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# Lazy-loaded attachments data
_attachments_data = None


def _get_attachments_data():
    global _attachments_data
    if _attachments_data is None:
        attachments_path = os.path.join(MODELS_DIR, "attachments.json")
        if os.path.exists(attachments_path):
            with open(attachments_path) as f:
                _attachments_data = json.load(f)
    return _attachments_data


# WoW 2-letter race abbreviations for race-specific models (helms)
_RACE_ABBREV = {
    1: "Hu", 2: "Or", 3: "Dw", 4: "Ni", 5: "Sc",
    6: "Ta", 7: "Go", 8: "Tr", 10: "Be", 11: "Dr",
}


@router.get("/item-model/{display_id}")
async def get_item_model(
    display_id: int, side: str = "left", race: int = 0, gender: int = 0,
):
    """Serve an item 3D model (weapon/shield/shoulder/helm) as GLB.

    Extracts from MPQ on first request, caches to filesystem.
    side: 'left' or 'right' (determines which model from ItemDisplayInfo).
    race/gender: needed for helms (race-specific models with suffix like _NiM, _HuF).
    """
    race_suffix = ""
    if race > 0:
        abbr = _RACE_ABBREV.get(race, "")
        gender_char = "M" if gender == 0 else "F"
        if abbr:
            race_suffix = f"_{abbr}{gender_char}"

    cache_key = f"item_{display_id}_{side}{race_suffix}"
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.glb")

    if os.path.exists(cache_path):
        return FileResponse(cache_path, media_type="model/gltf-binary")

    db = _get_display_info_db()
    if db is None:
        return JSONResponse({"error": "DBC data not available"}, status_code=500)

    model_info = db.get_item_model_info(display_id)
    if not model_info:
        return JSONResponse({"error": "Display ID not found"}, status_code=404)

    if side == "right":
        model_name = model_info.get("rightModel", "") or model_info.get("leftModel", "")
        tex_name = model_info.get("rightTexture", "") or model_info.get("leftTexture", "")
    else:
        model_name = model_info.get("leftModel", "") or model_info.get("rightModel", "")
        tex_name = model_info.get("leftTexture", "") or model_info.get("rightTexture", "")

    if not model_name:
        return JSONResponse({"error": "No model name for this display ID"}, status_code=404)

    # For helms, append race/gender suffix to the model name (e.g., Helm_X_01 → Helm_X_01_NiM)
    if race_suffix:
        for ext in [".m2", ".M2", ".mdx", ".MDX"]:
            if model_name.endswith(ext):
                model_name = model_name[:-len(ext)] + race_suffix + ext
                break
        else:
            model_name = model_name + race_suffix

    try:
        from extract_models import extract_item_model

        os.makedirs(CACHE_DIR, exist_ok=True)
        success = extract_item_model(DATA_DIR, model_name, tex_name, cache_path)
        if not success:
            return JSONResponse({"error": "Failed to extract item model"}, status_code=500)

        return FileResponse(cache_path, media_type="model/gltf-binary")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/character-attachments/{name}")
async def get_character_attachments(name: str):
    """Return attachment point positions and equipped attachment-item displayIds for a character.

    Returns positions in glTF coordinate space (matching the character GLB model).
    """
    char = await get_character(name)
    if not char:
        return JSONResponse({"error": "Character not found"}, status_code=404)

    race_key = RACE_MODEL_NAMES.get(char["race"], "human")
    gender_str = "male" if char["gender"] == 0 else "female"
    model_key = f"{race_key}_{gender_str}"

    attachments_data = _get_attachments_data()
    attachments = {}
    if attachments_data and model_key in attachments_data:
        attachments = attachments_data[model_key]

    db = _get_display_info_db()
    equipment = char["equipment"]
    slot_map = {item["slot"]: item for item in equipment}

    # Build items dict for attachment-rendered slots
    items = {}

    # Main hand (slot 15) → attachment point 1 (right hand)
    if 15 in slot_map and slot_map[15].get("displayId"):
        did = slot_map[15]["displayId"]
        model_info = db.get_item_model_info(did) if db else {}
        items["mainHand"] = {
            "displayId": did,
            "attachPoint": "1",
            "hasModel": bool(model_info.get("leftModel") or model_info.get("rightModel")),
        }

    # Off hand (slot 16) → attachment point depends on item type:
    #   Weapon → point 2 (left hand grip for dual-wield)
    #   Shield/held items (lanterns, books, orbs) → point 0 (shield mount)
    if 16 in slot_map and slot_map[16].get("displayId"):
        did = slot_map[16]["displayId"]
        model_info = db.get_item_model_info(did) if db else {}
        comp_type = _get_item_component_type(did)
        attach_point = "2" if comp_type == "Weapon" else "0"
        items["offHand"] = {
            "displayId": did,
            "attachPoint": attach_point,
            "hasModel": bool(model_info.get("leftModel") or model_info.get("rightModel")),
        }

    # Ranged (slot 17) → skip for now (shown sheathed on back in-game, not in hand)
    # Rendering ranged at attachment point 1 would overlap with mainHand

    # Shoulders (slot 2) → attachment points 5 (right) and 6 (left)
    if 2 in slot_map and slot_map[2].get("displayId"):
        did = slot_map[2]["displayId"]
        model_info = db.get_item_model_info(did) if db else {}
        items["shoulderRight"] = {
            "displayId": did,
            "attachPoint": "5",
            "side": "right",
            "hasModel": bool(model_info.get("rightModel") or model_info.get("leftModel")),
        }
        items["shoulderLeft"] = {
            "displayId": did,
            "attachPoint": "6",
            "side": "left",
            "hasModel": bool(model_info.get("leftModel") or model_info.get("rightModel")),
        }

    # Helm (slot 0) → attachment point 11
    if 0 in slot_map and slot_map[0].get("displayId"):
        did = slot_map[0]["displayId"]
        model_info = db.get_item_model_info(did) if db else {}
        items["helm"] = {
            "displayId": did,
            "attachPoint": "11",
            "hasModel": bool(model_info.get("leftModel") or model_info.get("rightModel")),
        }

    return JSONResponse({
        "attachments": attachments,
        "items": items,
        "race": char["race"],
        "gender": char["gender"],
    })
