#!/usr/bin/env python3
"""
WoW Gear Texture Compositor
Composites equipped armor textures onto character skin to create a dressed model texture.

The WoW character rendering system works by overlaying armor region textures
on top of the base skin texture. Each armor piece provides textures for
specific body regions (upper arm, lower arm, chest, legs, etc.).

Usage:
    python gear_compositor.py --data-dir ../Data --output-dir ../frontend/public/models
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extract_models import MPQArchive, MPQ_LOAD_ORDER, decode_blp
from PIL import Image

# ── DBC Parser ──────────────────────────────────────────────────────────

class ItemDisplayInfoDB:
    """Parse ItemDisplayInfo.dbc to map displayId -> texture region names + geoset groups."""

    # Geoset group field indices (control which mesh variants to show)
    FIELD_GEOSET_GROUP1 = 7
    FIELD_GEOSET_GROUP2 = 8
    FIELD_GEOSET_GROUP3 = 9

    # Texture region field indices in the DBC record
    FIELD_UPPER_ARM = 15
    FIELD_LOWER_ARM = 16
    FIELD_HANDS = 17
    FIELD_UPPER_CHEST = 18
    FIELD_LOWER_CHEST = 19
    FIELD_UPPER_LEG = 20
    FIELD_LOWER_LEG = 21
    FIELD_FOOT = 22

    REGION_FIELDS = {
        "ArmUpperTexture": FIELD_UPPER_ARM,
        "ArmLowerTexture": FIELD_LOWER_ARM,
        "HandTexture": FIELD_HANDS,
        "TorsoUpperTexture": FIELD_UPPER_CHEST,
        "TorsoLowerTexture": FIELD_LOWER_CHEST,
        "LegUpperTexture": FIELD_UPPER_LEG,
        "LegLowerTexture": FIELD_LOWER_LEG,
        "FootTexture": FIELD_FOOT,
    }

    def __init__(self, dbc_data: bytes):
        magic = dbc_data[0:4]
        if magic != b"WDBC":
            raise ValueError(f"Invalid DBC magic: {magic}")

        self.record_count, self.field_count, self.record_size, self.string_block_size = (
            struct.unpack_from("<4I", dbc_data, 4)
        )
        self.header_size = 20
        self.string_block_offset = self.header_size + self.record_count * self.record_size
        self.data = dbc_data
        self._index: dict[int, int] = {}  # displayId -> record offset

        # Build index
        for i in range(self.record_count):
            offset = self.header_size + i * self.record_size
            display_id = struct.unpack_from("<I", dbc_data, offset)[0]
            self._index[display_id] = offset

    def _get_string(self, str_offset: int) -> str:
        if str_offset == 0:
            return ""
        start = self.string_block_offset + str_offset
        end = self.data.index(b"\x00", start)
        return self.data[start:end].decode("utf-8", errors="replace")

    def get_textures(self, display_id: int) -> dict[str, str]:
        """Get texture region names for a display ID.
        Returns dict mapping region folder name -> texture base name.
        """
        offset = self._index.get(display_id)
        if offset is None:
            return {}

        fields = struct.unpack_from("<" + "I" * self.field_count, self.data, offset)
        result = {}
        for region_folder, field_idx in self.REGION_FIELDS.items():
            if field_idx < self.field_count:
                name = self._get_string(fields[field_idx])
                if name:
                    result[region_folder] = name
        return result

    def get_geoset_groups(self, display_id: int) -> tuple[int, int, int]:
        """Get geosetGroup1/2/3 values for a display ID.
        These control which mesh geoset variants are visible when the item is equipped.
        """
        offset = self._index.get(display_id)
        if offset is None:
            return (0, 0, 0)
        fields = struct.unpack_from("<" + "I" * self.field_count, self.data, offset)
        g1 = fields[self.FIELD_GEOSET_GROUP1] if self.FIELD_GEOSET_GROUP1 < self.field_count else 0
        g2 = fields[self.FIELD_GEOSET_GROUP2] if self.FIELD_GEOSET_GROUP2 < self.field_count else 0
        g3 = fields[self.FIELD_GEOSET_GROUP3] if self.FIELD_GEOSET_GROUP3 < self.field_count else 0
        return (g1, g2, g3)

    def get_model_name(self, display_id: int) -> tuple[str, str]:
        """Get model name and texture name for attachment models (shoulders, helmets, weapons)."""
        offset = self._index.get(display_id)
        if offset is None:
            return ("", "")
        fields = struct.unpack_from("<" + "I" * self.field_count, self.data, offset)
        return (self._get_string(fields[1]), self._get_string(fields[3]))


# ── DBC lookup helpers for hair/facial hair geosets ─────────────────────

class CharHairGeosetsDB:
    """Parse CharHairGeosets.dbc: maps (race, sex, hairStyle) -> geosetId."""

    def __init__(self, dbc_data: bytes):
        magic = dbc_data[0:4]
        if magic != b"WDBC":
            raise ValueError("Invalid DBC")
        rec_count, field_count, rec_size, _ = struct.unpack_from("<4I", dbc_data, 4)
        self._lookup: dict[tuple[int, int, int], int] = {}
        for i in range(rec_count):
            offset = 20 + i * rec_size
            fields = struct.unpack_from("<" + "I" * field_count, dbc_data, offset)
            # fields: [ID, RaceID, SexID, VariationID, GeosetID, ShowBald]
            race_id, sex_id, variation, geoset_id = fields[1], fields[2], fields[3], fields[4]
            self._lookup[(race_id, sex_id, variation)] = geoset_id

    def get_geoset(self, race: int, sex: int, hair_style: int) -> int:
        return self._lookup.get((race, sex, hair_style), 0)


class CharFacialHairDB:
    """Parse CharacterFacialHairStyles.dbc: maps (race, sex, beardStyle) -> geoset offsets."""

    def __init__(self, dbc_data: bytes):
        magic = dbc_data[0:4]
        if magic != b"WDBC":
            raise ValueError("Invalid DBC")
        rec_count, field_count, rec_size, _ = struct.unpack_from("<4I", dbc_data, 4)
        self._lookup: dict[tuple[int, int, int], tuple[int, int, int, int, int]] = {}
        for i in range(rec_count):
            offset = 20 + i * rec_size
            fields = struct.unpack_from("<" + "I" * field_count, dbc_data, offset)
            # fields: [RaceID, SexID, VariationID, Geoset1, Geoset2, Geoset3, Geoset4, Geoset5]
            key = (fields[0], fields[1], fields[2])
            self._lookup[key] = (fields[3], fields[4], fields[5], fields[6], fields[7])

    def get_geosets(self, race: int, sex: int, beard_style: int) -> tuple[int, int, int, int, int]:
        """Returns (geoset1, geoset2, geoset3, geoset4, geoset5) offsets."""
        return self._lookup.get((race, sex, beard_style), (0, 0, 0, 0, 0))


class CharSectionsDB:
    """Parse CharSections.dbc: maps (race, sex, section, variation, color) -> texture names.

    BaseSection types: 0=Skin, 1=Face, 2=FacialHair, 3=Hair, 4=Underwear
    For Face (section=1): texture1=FaceLower, texture2=FaceUpper
    For Skin (section=0): texture1=SkinTexture
    """

    SECTION_SKIN = 0
    SECTION_FACE = 1
    SECTION_FACIAL_HAIR = 2
    SECTION_HAIR = 3
    SECTION_UNDERWEAR = 4

    def __init__(self, dbc_data: bytes):
        magic = dbc_data[0:4]
        if magic != b"WDBC":
            raise ValueError("Invalid DBC")
        rec_count, field_count, rec_size, string_block_size = struct.unpack_from("<4I", dbc_data, 4)
        self.data = dbc_data
        self.string_block_offset = 20 + rec_count * rec_size

        # Build lookup: (race, sex, section, variation, color) -> (tex1, tex2, tex3)
        self._lookup: dict[tuple[int, int, int, int, int], tuple[str, str, str]] = {}
        for i in range(rec_count):
            offset = 20 + i * rec_size
            fields = struct.unpack_from("<" + "I" * field_count, dbc_data, offset)
            # fields: [ID, RaceID, SexID, BaseSection, Tex1(str), Tex2(str), Tex3(str), Flags, VariationIndex, ColorIndex]
            race_id = fields[1]
            sex_id = fields[2]
            section = fields[3]
            tex1 = self._get_string(fields[4])
            tex2 = self._get_string(fields[5])
            tex3 = self._get_string(fields[6])
            variation = fields[8]
            color = fields[9]
            self._lookup[(race_id, sex_id, section, variation, color)] = (tex1, tex2, tex3)

    def _get_string(self, str_offset: int) -> str:
        if str_offset == 0:
            return ""
        start = self.string_block_offset + str_offset
        end = self.data.index(b"\x00", start)
        return self.data[start:end].decode("utf-8", errors="replace")

    def get_face_textures(self, race: int, sex: int, face: int, skin_color: int) -> tuple[str, str]:
        """Get (face_lower, face_upper) texture paths for a character.
        Returns empty strings if not found.
        """
        result = self._lookup.get((race, sex, self.SECTION_FACE, face, skin_color))
        if result:
            return (result[0], result[1])  # tex1=FaceLower, tex2=FaceUpper
        # Try with color=0 as fallback
        result = self._lookup.get((race, sex, self.SECTION_FACE, face, 0))
        if result:
            return (result[0], result[1])
        return ("", "")

    def get_underwear_textures(self, race: int, sex: int) -> tuple[str, str]:
        """Get (underwear_upper, underwear_lower) texture paths.
        Returns empty strings if not found.
        """
        result = self._lookup.get((race, sex, self.SECTION_UNDERWEAR, 0, 0))
        if result:
            return (result[0], result[1])
        return ("", "")

    def get_scalp_textures(self, race: int, sex: int, hair_style: int, hair_color: int) -> tuple[str, str]:
        """Get (scalp_lower, scalp_upper) texture paths for hair compositing.
        For Hair section (3): tex1=HairModelTexture (3D model, NOT for compositing),
        tex2=ScalpLowerTexture -> FACE_LOWER, tex3=ScalpUpperTexture -> FACE_UPPER.
        Returns empty strings if not found.
        """
        result = self._lookup.get((race, sex, self.SECTION_HAIR, hair_style, hair_color))
        if result:
            return (result[1], result[2])  # tex2=ScalpLower, tex3=ScalpUpper (skip tex1=HairModel)
        return ("", "")

    def get_hair_model_texture(self, race: int, sex: int, hair_style: int, hair_color: int) -> str:
        """Get the 3D hair model texture path (for hair mesh, type 6).
        For Hair section (3): tex1=HairModelTexture is the texture applied to 3D hair geometry.
        """
        result = self._lookup.get((race, sex, self.SECTION_HAIR, hair_style, hair_color))
        if result and result[0]:
            return result[0]
        return ""

    def get_extra_skin_texture(self, race: int, sex: int, skin_color: int) -> str:
        """Get extra skin texture path (for type 8 meshes - tauren fur, undead bones, etc.).
        From Skin section (0): tex2=ExtraSkinTexture.
        """
        result = self._lookup.get((race, sex, self.SECTION_SKIN, 0, skin_color))
        if result and result[1]:
            return result[1]
        return ""

    def get_facial_hair_textures(self, race: int, sex: int, facial_style: int, hair_color: int) -> tuple[str, str]:
        """Get (facial_lower, facial_upper) texture paths for facial hair.
        tex1 -> FaceLower region, tex2 -> FaceUpper region.
        Returns empty strings if not found.
        """
        result = self._lookup.get((race, sex, self.SECTION_FACIAL_HAIR, facial_style, hair_color))
        if result:
            return (result[0], result[1])
        # Try with color=0 as fallback
        result = self._lookup.get((race, sex, self.SECTION_FACIAL_HAIR, facial_style, 0))
        if result:
            return (result[0], result[1])
        return ("", "")


# ── Texture region layout on character skin texture ─────────────────────
# WoW character skin textures are 512x512 atlases with specific body part regions.
# Layout from WoW Model Viewer source (texture.h) with REGION_FAC=2:
#
# Left half (x=0..255):                Right half (x=256..511):
#   ArmUpper   (0,  0,  256, 128)        TorsoUpper (256, 0,   256, 128)
#   ArmLower   (0,  128, 256, 128)       TorsoLower (256, 128, 256, 64)
#   Hand       (0,  256, 256, 64)        LegUpper   (256, 192, 256, 128)
#   FaceUpper  (0,  320, 256, 64)        LegLower   (256, 320, 256, 128)
#   FaceLower  (0,  384, 256, 128)       Foot       (256, 448, 256, 64)

# Region: (x, y, width, height) on the 512x512 skin atlas
TEXTURE_REGIONS_512 = {
    "ArmUpperTexture":   (0,   0,   256, 128),
    "ArmLowerTexture":   (0,   128, 256, 128),
    "HandTexture":       (0,   256, 256, 64),
    "TorsoUpperTexture": (256, 0,   256, 128),
    "TorsoLowerTexture": (256, 128, 256, 64),
    "LegUpperTexture":   (256, 192, 256, 128),
    "LegLowerTexture":   (256, 320, 256, 128),
    "FootTexture":       (256, 448, 256, 64),
}

# Face regions (not from ItemDisplayInfo, but from CharSections.dbc face textures)
FACE_REGIONS_512 = {
    "FaceUpperTexture":  (0,   320, 256, 64),
    "FaceLowerTexture":  (0,   384, 256, 128),
}


def load_dbc_from_mpq(data_dir: str, dbc_name: str) -> bytes | None:
    """Load a DBC file from the MPQ archives."""
    # DBC files are in locale MPQs
    locale_mpqs = [
        os.path.join(data_dir, "enUS", "patch-enUS-3.MPQ"),
        os.path.join(data_dir, "enUS", "patch-enUS-2.MPQ"),
        os.path.join(data_dir, "enUS", "patch-enUS.MPQ"),
        os.path.join(data_dir, "enUS", "locale-enUS.MPQ"),
    ]

    for mpq_path in locale_mpqs:
        if not os.path.exists(mpq_path):
            continue
        try:
            with MPQArchive(mpq_path) as mpq:
                data = mpq.read_file(f"DBFilesClient\\{dbc_name}")
                if data:
                    return data
        except OSError:
            continue
    return None


# ── Persistent MPQ archive pool (avoids reopening archives per texture) ───
_mpq_pool: dict[str, MPQArchive] = {}


def _get_mpq(mpq_path: str) -> MPQArchive | None:
    """Get or open an MPQ archive from the pool."""
    if mpq_path not in _mpq_pool:
        try:
            mpq = MPQArchive(mpq_path)
            mpq.__enter__()  # Open the archive
            _mpq_pool[mpq_path] = mpq
        except OSError:
            return None
    return _mpq_pool[mpq_path]


def _read_from_mpqs(mpq_archives: list[str], file_path: str) -> bytes | None:
    """Read a file from the first MPQ archive that contains it."""
    for mpq_path in mpq_archives:
        mpq = _get_mpq(mpq_path)
        if mpq is None:
            continue
        try:
            data = mpq.read_file(file_path)
            if data:
                return data
        except OSError:
            continue
    return None


def find_texture_in_mpq(mpq_archives: list[str], region_folder: str, tex_name: str, gender: int) -> Image.Image | None:
    """Find and decode an armor texture from MPQ archives.

    Tries gender-specific suffix first, then unisex:
      {tex_name}_M.blp (male) or {tex_name}_F.blp (female)
      {tex_name}_U.blp (unisex)
    """
    gender_suffix = "_M" if gender == 0 else "_F"
    suffixes = [gender_suffix, "_U"]

    for suffix in suffixes:
        filename = f"{tex_name}{suffix}.blp"
        path = f"ITEM\\TEXTURECOMPONENTS\\{region_folder}\\{filename}"
        data = _read_from_mpqs(mpq_archives, path)
        if data:
            img = decode_blp(data)
            if img:
                return img

    return None


def load_blp_from_mpq(mpq_archives: list[str], blp_path: str) -> Image.Image | None:
    """Load and decode a BLP texture by its full MPQ path."""
    data = _read_from_mpqs(mpq_archives, blp_path)
    if data:
        img = decode_blp(data)
        if img:
            return img
    return None


def _paste_region(result: Image.Image, tex: Image.Image, region: tuple[int, int, int, int]) -> None:
    """Alpha-composite a texture into a region on the atlas (Porter-Duff SourceOver).
    Respects source alpha - transparent pixels won't overwrite the destination.
    """
    rx, ry, rw, rh = region
    skin_w, skin_h = result.size
    sx = rx * skin_w // 512
    sy = ry * skin_h // 512
    sw = rw * skin_w // 512
    sh = rh * skin_h // 512

    resized = tex.convert("RGBA").resize((sw, sh), Image.LANCZOS)
    result.alpha_composite(resized, dest=(sx, sy))


def composite_gear_texture(
    base_skin: Image.Image,
    equipment: list[dict],
    display_info_db: ItemDisplayInfoDB,
    mpq_archives: list[str],
    gender: int,
    face_lower: Image.Image | None = None,
    face_upper: Image.Image | None = None,
    facial_lower: Image.Image | None = None,
    facial_upper: Image.Image | None = None,
    scalp_lower: Image.Image | None = None,
    scalp_upper: Image.Image | None = None,
) -> Image.Image:
    """Composite character textures in WoW layer order onto the base skin.

    Compositing order (from WoW Model Viewer character.cpp):
      Layer 0: Base skin (already provided)
      Layer 1: Face textures (face lower + face upper)
      Layer 2: Facial hair textures (beard, sideburns etc)
      Layer 3: Scalp/hair textures (hair color on head)
      Layer 10+: Equipment textures (shirt, legs, boots, chest, gloves, tabard)

    Args:
        base_skin: The base character skin texture (512x512)
        equipment: List of equipment dicts with 'displayId' and 'slot' fields
        display_info_db: Parsed ItemDisplayInfo.dbc
        mpq_archives: List of MPQ file paths (newest first)
        gender: 0=male, 1=female
        face_lower: Face lower texture
        face_upper: Face upper texture
        facial_lower: Facial hair lower texture (beard)
        facial_upper: Facial hair upper texture
        scalp_lower: Scalp/hair lower texture (hair color on back of head)
        scalp_upper: Scalp/hair upper texture (hair color on top of head)

    Returns:
        New image with all textures composited
    """
    result = base_skin.copy().convert("RGBA")

    # Layer 1: Face textures
    if face_lower:
        _paste_region(result, face_lower, FACE_REGIONS_512["FaceLowerTexture"])
    if face_upper:
        _paste_region(result, face_upper, FACE_REGIONS_512["FaceUpperTexture"])

    # Layer 2: Facial hair textures (tex1 -> FaceLower, tex2 -> FaceUpper)
    if facial_lower:
        _paste_region(result, facial_lower, FACE_REGIONS_512["FaceLowerTexture"])
    if facial_upper:
        _paste_region(result, facial_upper, FACE_REGIONS_512["FaceUpperTexture"])

    # Layer 3: Scalp/hair textures (tex1 -> FaceLower, tex2 -> FaceUpper)
    if scalp_lower:
        _paste_region(result, scalp_lower, FACE_REGIONS_512["FaceLowerTexture"])
    if scalp_upper:
        _paste_region(result, scalp_upper, FACE_REGIONS_512["FaceUpperTexture"])

    # Layers 10-25: Equipment textures (sorted by slot for correct layering)
    # Layer order: shirt(10) -> legs(13) -> boots(15) -> chest(17) -> gloves(20) -> tabard(25)
    SLOT_LAYER_ORDER = {3: 10, 6: 13, 7: 15, 4: 17, 8: 18, 5: 19, 9: 20, 18: 25}

    # Sort equipment by render layer
    sorted_equipment = sorted(
        equipment,
        key=lambda item: SLOT_LAYER_ORDER.get(item.get("slot", -1), 50)
    )

    for item in sorted_equipment:
        display_id = item.get("displayId", 0)
        if not display_id:
            continue

        textures = display_info_db.get_textures(display_id)
        if not textures:
            continue

        for region_folder, tex_name in textures.items():
            region = TEXTURE_REGIONS_512.get(region_folder)
            if not region:
                continue

            armor_tex = find_texture_in_mpq(mpq_archives, region_folder, tex_name, gender)
            if armor_tex:
                _paste_region(result, armor_tex, region)

    return result


def build_mpq_list(data_dir: str) -> list[str]:
    """Build ordered list of MPQ archives, newest patches first."""
    mpq_files = []
    for mpq_name in reversed(MPQ_LOAD_ORDER):
        path = os.path.join(data_dir, mpq_name)
        if os.path.exists(path):
            mpq_files.append(path)
    return mpq_files


# ── Geoset visibility computation ────────────────────────────────────────
# WoW character models contain many submeshes (geosets) for body part variants.
# Equipment items control which variants are visible via geosetGroup fields
# in ItemDisplayInfo.dbc.
#
# Each geoset group has a base ID (e.g. boots=501, gloves=401).
# Default = "nothing equipped" variant. Equipment shifts to armored variants.
# WoW inventory slots:
#   0=Head, 2=Shoulder, 3=Shirt, 4=Chest, 5=Belt, 6=Legs,
#   7=Feet, 8=Wrist, 9=Gloves, 14=Back(Cape), 18=Tabard

def compute_active_geosets(
    equipment: list[dict],
    display_info_db: ItemDisplayInfoDB,
    race: int = 1,
    gender: int = 0,
    hair_style: int = 0,
    facial_style: int = 0,
    hair_geosets_db: CharHairGeosetsDB | None = None,
    facial_hair_db: CharFacialHairDB | None = None,
) -> list[int]:
    """Compute which geoset IDs should be visible based on equipped items.

    Returns a list of active geoset IDs. Only submeshes matching these
    IDs should be rendered.
    """
    # Resolve hair geoset from DBC
    hair_geoset = 0
    if hair_geosets_db:
        hair_geoset = hair_geosets_db.get_geoset(race, gender, hair_style)

    # Resolve facial hair geosets from DBC
    facial1_offset = 0
    facial2_offset = 0
    facial3_offset = 0
    nose_offset = 0
    eyeglow_offset = 0
    if facial_hair_db:
        g1, g2, g3, g4, g5 = facial_hair_db.get_geosets(race, gender, facial_style)
        facial1_offset = g1
        # Note: reference code swaps geoset2 and geoset3
        facial2_offset = g3
        facial3_offset = g2
        nose_offset = g4
        eyeglow_offset = g5

    # Defaults (no equipment = bare body)
    # Groups with xx01 = visible bare body part (hands, feet, etc.)
    # Groups with xx00 = nothing visible (cloak, tabard, helm, shoulders, belt)
    geosets = {
        "skin": 0,
        "hair": hair_geoset,
        "facial1": 100 + facial1_offset,
        "facial2": 200 + facial2_offset,
        "facial3": 300 + facial3_offset,
        "glove": 401,           # bare hands
        "boots": 501,           # bare feet
        "tail": 600,
        "ears": 702,
        "sleeves": 801,         # no sleeves
        "legcuffs": 901,        # no leg cuffs
        "chest": 1001,          # bare chest
        "pants": 1101,          # underwear/bare
        "tabard": 1200,         # no tabard (xx00 = hidden)
        "trousers": 1301,       # no trousers
        "femaleLoincloth": 1400,
        "cloak": 1500,          # no cloak (xx00 = hidden)
        "noseEarrings": 1600 + nose_offset,
        "eyeglows": 1700 + eyeglow_offset,
        "belt": 1800,           # no belt (xx00 = hidden)
        "bone": 1900,
        "feet": 2001,
        "head": 2101,
        "torso": 2201,
        "handsAttach": 2300,    # no hand attachments (xx00 = hidden)
        "headAttach": 2400,
        "blindfolds": 2500,
        "shoulders": 2600,      # no shoulders (xx00 = hidden)
        "helm": 2700,           # no helm (xx00 = hidden)
        "unk28": 2801,
    }

    # Map equipment by slot for easier lookup
    slot_items: dict[int, int] = {}
    for item in equipment:
        did = item.get("displayId", 0)
        slot = item.get("slot", -1)
        if did and slot >= 0:
            slot_items[slot] = did

    # Helm (slot 0)
    if 0 in slot_items:
        g1, g2, g3 = display_info_db.get_geoset_groups(slot_items[0])
        geosets["helm"] = 2702 + g1

    # Shoulder (slot 2)
    if 2 in slot_items:
        g1, g2, g3 = display_info_db.get_geoset_groups(slot_items[2])
        geosets["shoulders"] = 2601 + g1

    # Shirt (slot 3) - affects sleeves and chest
    if 3 in slot_items:
        g1, g2, g3 = display_info_db.get_geoset_groups(slot_items[3])
        geosets["sleeves"] = 801 + g1
        geosets["chest"] = 1001 + g2

    # Chest/Cuirass (slot 4) - overrides shirt for sleeves and chest
    if 4 in slot_items:
        g1, g2, g3 = display_info_db.get_geoset_groups(slot_items[4])
        geosets["sleeves"] = 801 + g1
        geosets["chest"] = 1001 + g2

    # Belt (slot 5)
    if 5 in slot_items:
        g1, g2, g3 = display_info_db.get_geoset_groups(slot_items[5])
        geosets["belt"] = 1801 + g1

    # Legs (slot 6)
    if 6 in slot_items:
        g1, g2, g3 = display_info_db.get_geoset_groups(slot_items[6])
        geosets["pants"] = 1101 + g1
        geosets["legcuffs"] = 901 + g2
        geosets["trousers"] = 1301 + g3

    # Feet/Boots (slot 7)
    if 7 in slot_items:
        g1, g2, g3 = display_info_db.get_geoset_groups(slot_items[7])
        geosets["boots"] = 501 + g1
        geosets["feet"] = 2002 + g2

    # Wrist (slot 8) - no geoset changes typically

    # Gloves (slot 9)
    if 9 in slot_items:
        g1, g2, g3 = display_info_db.get_geoset_groups(slot_items[9])
        geosets["glove"] = 401 + g1
        geosets["handsAttach"] = 2301 + g2

    # Back/Cape (slot 14)
    if 14 in slot_items:
        g1, g2, g3 = display_info_db.get_geoset_groups(slot_items[14])
        geosets["cloak"] = 1501 + g1

    # Tabard (slot 18)
    if 18 in slot_items:
        g1, g2, g3 = display_info_db.get_geoset_groups(slot_items[18])
        geosets["tabard"] = 1201 + g1

    # Chest overrides trousers if equipped
    if 4 in slot_items:
        g1, g2, g3 = display_info_db.get_geoset_groups(slot_items[4])
        geosets["trousers"] = 1301 + g3

    return list(geosets.values())


# Race key -> (MPQ dir name, numeric race ID)
RACE_INFO = {
    "human": ("Human", 1), "orc": ("Orc", 2), "dwarf": ("Dwarf", 3),
    "nightelf": ("NightElf", 4), "undead": ("Scourge", 5), "tauren": ("Tauren", 6),
    "gnome": ("Gnome", 7), "troll": ("Troll", 8), "bloodelf": ("BloodElf", 10),
    "draenei": ("Draenei", 11),
}

# Lazy-loaded CharSections DB
_char_sections_db = None


def _get_char_sections_db(data_dir: str) -> CharSectionsDB | None:
    global _char_sections_db
    if _char_sections_db is None:
        dbc_data = load_dbc_from_mpq(data_dir, "CharSections.dbc")
        if dbc_data:
            _char_sections_db = CharSectionsDB(dbc_data)
    return _char_sections_db


# Public API for the backend to call
def generate_character_texture(
    data_dir: str,
    race_key: str,
    gender: int,
    skin_color: int,
    equipment: list[dict],
    face: int = 0,
    hair_style: int = 0,
    hair_color: int = 0,
    facial_style: int = 0,
) -> Image.Image | None:
    """Generate a composited character texture with gear.

    Args:
        data_dir: Path to WoW Data directory
        race_key: e.g. "human", "orc" (lowercase)
        gender: 0=male, 1=female
        skin_color: Character skin color index
        equipment: List of {displayId, slot} dicts
        face: Character face variation index
        hair_style: Character hair style index
        hair_color: Character hair color index
        facial_style: Character facial hair/markings style index

    Returns:
        PIL Image with composited texture, or None on failure
    """
    # Load DBC
    dbc_data = load_dbc_from_mpq(data_dir, "ItemDisplayInfo.dbc")
    if not dbc_data:
        print("ERROR: Could not find ItemDisplayInfo.dbc")
        return None

    display_info_db = ItemDisplayInfoDB(dbc_data)

    race_dir, race_id = RACE_INFO.get(race_key, ("Human", 1))
    mpq_archives = build_mpq_list(data_dir)

    # Use CharSections.dbc for all character textures (skin, face, hair, facial hair)
    char_sections = _get_char_sections_db(data_dir)

    # Load skin texture from CharSections.dbc (section=0)
    skin_img = None
    if char_sections:
        skin_entry = char_sections._lookup.get((race_id, gender, CharSectionsDB.SECTION_SKIN, 0, skin_color))
        if skin_entry and skin_entry[0]:
            skin_img = load_blp_from_mpq(mpq_archives, skin_entry[0])

    if not skin_img:
        # Fallback: try hardcoded path pattern
        gender_dir = "Male" if gender == 0 else "Female"
        skin_path = f"Character\\{race_dir}\\{gender_dir}\\{race_dir}{gender_dir}Skin00_{skin_color:02d}.blp"
        skin_img = load_blp_from_mpq(mpq_archives, skin_path)

    if not skin_img:
        print(f"WARNING: Could not find skin texture for {race_key} gender={gender} skin={skin_color}")
        return None

    # Load face textures from CharSections.dbc (section=1)
    # tex1 -> FaceLower, tex2 -> FaceUpper
    face_lower = None
    face_upper = None
    if char_sections:
        face_lower_path, face_upper_path = char_sections.get_face_textures(
            race_id, gender, face, skin_color
        )
        if face_lower_path:
            face_lower = load_blp_from_mpq(mpq_archives, face_lower_path)
        if face_upper_path:
            face_upper = load_blp_from_mpq(mpq_archives, face_upper_path)

    # Load facial hair textures from CharSections.dbc (section=2)
    # tex1 -> FaceLower, tex2 -> FaceUpper
    facial_lower = None
    facial_upper = None
    if char_sections and facial_style > 0:
        facial_lower_path, facial_upper_path = char_sections.get_facial_hair_textures(
            race_id, gender, facial_style, hair_color
        )
        if facial_lower_path:
            facial_lower = load_blp_from_mpq(mpq_archives, facial_lower_path)
        if facial_upper_path:
            facial_upper = load_blp_from_mpq(mpq_archives, facial_upper_path)

    # Load scalp/hair textures from CharSections.dbc (section=3)
    # tex1 -> FaceLower, tex2 -> FaceUpper
    scalp_lower = None
    scalp_upper = None
    if char_sections:
        scalp_lower_path, scalp_upper_path = char_sections.get_scalp_textures(
            race_id, gender, hair_style, hair_color
        )
        if scalp_lower_path:
            scalp_lower = load_blp_from_mpq(mpq_archives, scalp_lower_path)
        if scalp_upper_path:
            scalp_upper = load_blp_from_mpq(mpq_archives, scalp_upper_path)

    # Composite: skin -> face -> facial hair -> scalp/hair -> gear
    result = composite_gear_texture(
        skin_img, equipment, display_info_db, mpq_archives, gender,
        face_lower=face_lower, face_upper=face_upper,
        facial_lower=facial_lower, facial_upper=facial_upper,
        scalp_lower=scalp_lower, scalp_upper=scalp_upper,
    )
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test gear texture compositing")
    parser.add_argument("--data-dir", default="../Data")
    parser.add_argument("--race", default="human")
    parser.add_argument("--gender", type=int, default=0)
    parser.add_argument("--skin", type=int, default=0)
    parser.add_argument("--display-ids", nargs="+", type=int, default=[])
    parser.add_argument("--output", default="/tmp/test_gear.png")
    args = parser.parse_args()

    equipment = [{"displayId": did, "slot": i} for i, did in enumerate(args.display_ids)]
    img = generate_character_texture(
        os.path.abspath(args.data_dir), args.race, args.gender, args.skin, equipment
    )
    if img:
        img.save(args.output)
        print(f"Saved: {args.output}")
    else:
        print("Failed to generate texture")
