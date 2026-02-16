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

        active = compute_active_geosets(
            equipment, db,
            race=char["race"],
            gender=char["gender"],
            hair_style=char.get("hairStyle", 0),
            facial_style=char.get("facialStyle", 0),
            hair_geosets_db=hair_db,
            facial_hair_db=facial_db,
        )
        return JSONResponse({"geosets": active})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
