#!/usr/bin/env python3
"""
WotLK Model Extraction Pipeline
Extracts character M2 models from 3.3.5 MPQ archives and converts to glTF/GLB.

Usage:
    python extract_models.py --data-dir ../Data --output-dir ../frontend/public/models

Requirements:
    - StormLib (libstorm.so in same directory or system lib path)
    - Pillow, pygltflib, numpy
"""

import argparse
import ctypes
import ctypes.util
import json
import os
import struct
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from pygltflib import (
    GLTF2,
    Accessor,
    Asset,
    Buffer,
    BufferView,
    Image as GLTFImage,
    Material,
    Mesh,
    Node,
    Primitive,
    Sampler,
    Scene,
    Texture,
    TextureInfo,
)

# ── StormLib ctypes bindings ──────────────────────────────────────────────

STORMLIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libstorm.so")


def _load_stormlib():
    try:
        lib = ctypes.cdll.LoadLibrary(STORMLIB_PATH)
    except OSError:
        found = ctypes.util.find_library("storm")
        if found:
            lib = ctypes.cdll.LoadLibrary(found)
        else:
            print(f"ERROR: Cannot find libstorm.so at {STORMLIB_PATH}")
            print("Build StormLib and place libstorm.so in the tools/ directory.")
            sys.exit(1)

    # SFileOpenArchive
    lib.SFileOpenArchive.argtypes = [ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)]
    lib.SFileOpenArchive.restype = ctypes.c_bool

    # SFileCloseArchive
    lib.SFileCloseArchive.argtypes = [ctypes.c_void_p]
    lib.SFileCloseArchive.restype = ctypes.c_bool

    # SFileOpenFileEx
    lib.SFileOpenFileEx.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)]
    lib.SFileOpenFileEx.restype = ctypes.c_bool

    # SFileGetFileSize
    lib.SFileGetFileSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    lib.SFileGetFileSize.restype = ctypes.c_uint

    # SFileReadFile
    lib.SFileReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint), ctypes.c_void_p]
    lib.SFileReadFile.restype = ctypes.c_bool

    # SFileCloseFile
    lib.SFileCloseFile.argtypes = [ctypes.c_void_p]
    lib.SFileCloseFile.restype = ctypes.c_bool

    # SFileFindFirstFile
    lib.SFileFindFirstFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_char_p]
    lib.SFileFindFirstFile.restype = ctypes.c_void_p

    # SFileFindNextFile
    lib.SFileFindNextFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    lib.SFileFindNextFile.restype = ctypes.c_bool

    # SFileFindClose
    lib.SFileFindClose.argtypes = [ctypes.c_void_p]
    lib.SFileFindClose.restype = ctypes.c_bool

    return lib


# SFILE_FIND_DATA structure
class SFILE_FIND_DATA(ctypes.Structure):
    _fields_ = [
        ("cFileName", ctypes.c_char * 1024),
        ("szPlainName", ctypes.c_char_p),
        ("dwHashIndex", ctypes.c_uint),
        ("dwBlockIndex", ctypes.c_uint),
        ("dwFileSize", ctypes.c_uint),
        ("dwFileFlags", ctypes.c_uint),
        ("dwCompSize", ctypes.c_uint),
        ("dwFileTimeLo", ctypes.c_uint),
        ("dwFileTimeHi", ctypes.c_uint),
        ("lcLocale", ctypes.c_uint),
    ]


storm = _load_stormlib()


class MPQArchive:
    """Context manager for reading files from an MPQ archive."""

    def __init__(self, path: str):
        self.path = path
        self.handle = ctypes.c_void_p()

    def __enter__(self):
        ok = storm.SFileOpenArchive(
            self.path.encode(), 0, 0x100, ctypes.byref(self.handle)  # STREAM_FLAG_READ_ONLY
        )
        if not ok:
            raise OSError(f"Failed to open MPQ: {self.path}")
        return self

    def __exit__(self, *args):
        if self.handle:
            storm.SFileCloseArchive(self.handle)

    def read_file(self, internal_path: str) -> bytes | None:
        """Read a file from the MPQ archive. Returns None if not found."""
        fh = ctypes.c_void_p()
        ok = storm.SFileOpenFileEx(self.handle, internal_path.encode(), 0, ctypes.byref(fh))
        if not ok:
            return None

        try:
            high = ctypes.c_uint(0)
            size = storm.SFileGetFileSize(fh, ctypes.byref(high))
            if size == 0xFFFFFFFF or size == 0:
                return None

            buf = ctypes.create_string_buffer(size)
            read_bytes = ctypes.c_uint(0)
            ok = storm.SFileReadFile(fh, buf, size, ctypes.byref(read_bytes), None)
            if not ok:
                return None
            return buf.raw[:read_bytes.value]
        finally:
            storm.SFileCloseFile(fh)

    def find_files(self, pattern: str) -> list[str]:
        """List files matching a glob pattern."""
        results = []
        find_data = SFILE_FIND_DATA()
        handle = storm.SFileFindFirstFile(
            self.handle, pattern.encode(), ctypes.byref(find_data), None
        )
        if not handle or handle == ctypes.c_void_p(-1).value:
            return results

        results.append(find_data.cFileName.decode(errors="replace"))
        while storm.SFileFindNextFile(handle, ctypes.byref(find_data)):
            results.append(find_data.cFileName.decode(errors="replace"))

        storm.SFileFindClose(handle)
        return results


# ── M2 Parser (WotLK 3.3.5 format, version 264) ─────────────────────────

def _read_m2_header(data: bytes) -> dict:
    """Parse M2 header fields we need."""
    if len(data) < 324:
        return {}

    magic = data[0:4]
    if magic != b"MD20":
        return {}

    version = struct.unpack_from("<I", data, 4)[0]

    # Offsets/counts we care about
    nVertices, ofsVertices = struct.unpack_from("<II", data, 0x3C)
    nViews, ofsViews = struct.unpack_from("<II", data, 0x44)  # skin profiles
    nTextures, ofsTextures = struct.unpack_from("<II", data, 0x50)
    nBones, ofsBones = struct.unpack_from("<II", data, 0x6C)

    # Texture lookup/combo table (maps batch textureComboIndex -> texture index)
    nTextureCombos, ofsTextureCombos = struct.unpack_from("<II", data, 0x80)

    # Bounding box (for scaling)
    bb = struct.unpack_from("<6f", data, 0xA8)

    return {
        "version": version,
        "nVertices": nVertices, "ofsVertices": ofsVertices,
        "nViews": nViews, "ofsViews": ofsViews,
        "nTextures": nTextures, "ofsTextures": ofsTextures,
        "nBones": nBones, "ofsBones": ofsBones,
        "nTextureCombos": nTextureCombos, "ofsTextureCombos": ofsTextureCombos,
        "bboxMin": bb[0:3], "bboxMax": bb[3:6],
    }


def _read_m2_vertices(data: bytes, header: dict) -> np.ndarray:
    """Read M2 vertex data. Each vertex is 48 bytes in WotLK:
    position (3f), boneWeights (4B), boneIndices (4B), normal (3f), texCoords (2f), texCoords2 (2f)
    """
    n = header["nVertices"]
    ofs = header["ofsVertices"]
    vertex_size = 48

    if ofs + n * vertex_size > len(data):
        return np.empty((0, 48), dtype=np.uint8)

    raw = np.frombuffer(data, dtype=np.uint8, count=n * vertex_size, offset=ofs)
    return raw.reshape(n, vertex_size)


def _parse_vertices(raw: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract positions, normals, and UVs from raw vertex data.

    WoW M2 coordinate system: X=right, Y=forward, Z=up
    glTF coordinate system:   X=right, Y=up, Z=forward (towards viewer)

    Conversion: glTF(x, y, z) = WoW(x, z, -y)
    """
    n = raw.shape[0]
    if n == 0:
        return np.empty((0, 3), np.float32), np.empty((0, 3), np.float32), np.empty((0, 2), np.float32)

    flat = raw.tobytes()
    positions = np.zeros((n, 3), dtype=np.float32)
    normals = np.zeros((n, 3), dtype=np.float32)
    uvs = np.zeros((n, 2), dtype=np.float32)

    for i in range(n):
        base = i * 48
        wx, wy, wz = struct.unpack_from("<3f", flat, base)
        nx, ny, nz = struct.unpack_from("<3f", flat, base + 20)
        uvs[i] = struct.unpack_from("<2f", flat, base + 32)

        # WoW -> glTF coordinate conversion
        positions[i] = (wx, wz, -wy)
        normals[i] = (nx, nz, -ny)

    return positions, normals, uvs


def _read_skin_file(skin_data: bytes) -> list[dict] | None:
    """Parse an M2 .skin file to get submeshes with geoset IDs.

    Returns list of dicts: [{geosetId, startTriangle, nTriangles, indices(resolved)}]
    Each submesh maps to a geoset ID used for equipment visibility.
    """
    if len(skin_data) < 48:
        return None

    magic = skin_data[0:4]
    offset = 0
    if magic == b"SKIN":
        offset = 4

    nIndices, ofsIndices = struct.unpack_from("<II", skin_data, offset)
    nTriangles, ofsTriangles = struct.unpack_from("<II", skin_data, offset + 8)
    _nBones, _ofsBones = struct.unpack_from("<II", skin_data, offset + 16)
    nSubmeshes, ofsSubmeshes = struct.unpack_from("<II", skin_data, offset + 24)

    if ofsIndices + nIndices * 2 > len(skin_data):
        return None
    if ofsTriangles + nTriangles * 2 > len(skin_data):
        return None

    # Index lookup table
    indices_lut = np.frombuffer(skin_data, dtype=np.uint16, count=nIndices, offset=ofsIndices)
    # Triangle vertex references (into indices lookup table)
    triangles = np.frombuffer(skin_data, dtype=np.uint16, count=nTriangles, offset=ofsTriangles)

    if nSubmeshes == 0:
        # No submesh info - return single submesh with all triangles
        resolved = indices_lut[triangles].astype(np.uint32)
        return [{"geosetId": 0, "indices": resolved}]

    # Parse each submesh (48 bytes each in WotLK)
    submeshes = []
    for i in range(nSubmeshes):
        base = ofsSubmeshes + i * 48
        if base + 48 > len(skin_data):
            break

        fields = struct.unpack_from("<8H", skin_data, base)
        geoset_id = fields[0]
        _level = fields[1]
        _startVertex = fields[2]
        _nVertices = fields[3]
        startTri = fields[4]
        nTri = fields[5]

        # Resolve triangle indices for this submesh
        if startTri + nTri <= len(triangles):
            sub_tris = triangles[startTri:startTri + nTri]
            # Map through the index lookup table to get actual vertex indices
            valid_mask = sub_tris < len(indices_lut)
            if not np.all(valid_mask):
                sub_tris = sub_tris[valid_mask]
            resolved = indices_lut[sub_tris].astype(np.uint32)
            submeshes.append({"geosetId": geoset_id, "indices": resolved, "submeshIndex": i})

    return submeshes if submeshes else None


def _read_skin_batches(skin_data: bytes, m2_data: bytes, header: dict) -> dict[int, int]:
    """Read skin file batches to map submesh index -> texture type.

    Returns dict mapping submesh_index -> texture_type (1=skin, 6=hair, 0=hardcoded, etc.)
    """
    if len(skin_data) < 48:
        return {}

    offset = 4 if skin_data[0:4] == b"SKIN" else 0

    # Skin header: nIndices(4) ofsIndices(4) nTriangles(4) ofsTriangles(4)
    #              nBones(4) ofsBones(4) nSubmeshes(4) ofsSubmeshes(4)
    #              nBatches(4) ofsBatches(4)
    nBatches, ofsBatches = struct.unpack_from("<II", skin_data, offset + 32)

    # Read texture combo lookup table from M2
    nTexCombos = header.get("nTextureCombos", 0)
    ofsTexCombos = header.get("ofsTextureCombos", 0)
    tex_combos = []
    for i in range(nTexCombos):
        tc_ofs = ofsTexCombos + i * 2
        if tc_ofs + 2 <= len(m2_data):
            tex_combos.append(struct.unpack_from("<H", m2_data, tc_ofs)[0])

    # Read texture definitions from M2
    tex_info_list = []
    nTex = header.get("nTextures", 0)
    ofsTex = header.get("ofsTextures", 0)
    for i in range(nTex):
        base = ofsTex + i * 16
        if base + 16 <= len(m2_data):
            tex_type = struct.unpack_from("<I", m2_data, base)[0]
            tex_info_list.append(tex_type)

    # Parse batches (24 bytes each)
    submesh_tex_type: dict[int, int] = {}
    for i in range(nBatches):
        base = ofsBatches + i * 24
        if base + 24 > len(skin_data):
            break
        # Batch: flags(1) priority(1) shader_id(2) skinSectionIndex(2) geosetIndex(2)
        #        colorIndex(2) materialIndex(2) materialLayer(2) textureCount(2)
        #        textureComboIndex(2) ...
        skin_section_idx = struct.unpack_from("<H", skin_data, base + 4)[0]
        tex_combo_idx = struct.unpack_from("<H", skin_data, base + 16)[0]

        # Follow the lookup chain: batch -> textureCombos -> textures -> type
        tex_type = 0
        if tex_combo_idx < len(tex_combos):
            tex_idx = tex_combos[tex_combo_idx]
            if tex_idx < len(tex_info_list):
                tex_type = tex_info_list[tex_idx]

        submesh_tex_type[skin_section_idx] = tex_type

    return submesh_tex_type


def _read_texture_info(data: bytes, header: dict) -> list[dict]:
    """Read texture entries from M2. Each is 16 bytes: type(4), flags(4), nFilename(4), ofsFilename(4)."""
    n = header["nTextures"]
    ofs = header["ofsTextures"]
    textures = []
    for i in range(n):
        base = ofs + i * 16
        if base + 16 > len(data):
            break
        tex_type, flags, name_len, name_ofs = struct.unpack_from("<IIII", data, base)
        filename = ""
        if name_len > 0 and name_ofs + name_len <= len(data):
            filename = data[name_ofs:name_ofs + name_len].split(b"\x00")[0].decode(errors="replace")
        textures.append({"type": tex_type, "flags": flags, "filename": filename})
    return textures


# ── BLP texture decoding ────────────────────────────────────────────────

def decode_blp(data: bytes) -> Image.Image | None:
    """Decode a BLP2 texture to a Pillow Image."""
    if len(data) < 148:
        return None

    magic = data[0:4]
    if magic != b"BLP2":
        return None

    blp_type = struct.unpack_from("<I", data, 4)[0]
    encoding = struct.unpack_from("<B", data, 8)[0]
    alpha_depth = struct.unpack_from("<B", data, 9)[0]
    alpha_encoding = struct.unpack_from("<B", data, 10)[0]
    has_mips = struct.unpack_from("<B", data, 11)[0]
    width, height = struct.unpack_from("<II", data, 12)

    mip_offsets = struct.unpack_from("<16I", data, 20)
    mip_sizes = struct.unpack_from("<16I", data, 84)

    if encoding == 1:
        # Uncompressed, palettized
        palette = []
        for i in range(256):
            b, g, r, a = struct.unpack_from("<4B", data, 148 + i * 4)
            palette.append((r, g, b, a))

        mip_offset = mip_offsets[0]
        mip_size = mip_sizes[0]
        if mip_offset == 0 or mip_size == 0:
            return None

        pixel_data = data[mip_offset:mip_offset + mip_size]
        img = Image.new("RGBA", (width, height))
        pixels = img.load()

        num_pixels = width * height
        # Color indices come first, alpha data follows
        color_indices = pixel_data[:num_pixels]
        alpha_data = pixel_data[num_pixels:]

        idx = 0
        for y in range(height):
            for x in range(width):
                if idx < len(color_indices):
                    color_idx = color_indices[idx]
                    r, g, b, _ = palette[color_idx]
                    # Read alpha from separate block based on alpha_depth
                    if alpha_depth == 8 and idx < len(alpha_data):
                        a = alpha_data[idx]
                    elif alpha_depth == 4 and (idx // 2) < len(alpha_data):
                        byte = alpha_data[idx // 2]
                        a = ((byte >> 4) * 17) if (idx % 2) else ((byte & 0x0F) * 17)
                    elif alpha_depth == 1 and (idx // 8) < len(alpha_data):
                        byte = alpha_data[idx // 8]
                        a = 255 if (byte & (1 << (idx % 8))) else 0
                    else:
                        a = 255
                    pixels[x, y] = (r, g, b, a)
                    idx += 1
        return img

    elif encoding == 2:
        # DXT compressed
        mip_offset = mip_offsets[0]
        mip_size = mip_sizes[0]
        if mip_offset == 0 or mip_size == 0:
            return None

        compressed = data[mip_offset:mip_offset + mip_size]
        if alpha_encoding == 0:
            return _decode_dxt1(compressed, width, height)
        elif alpha_encoding == 1:
            return _decode_dxt3(compressed, width, height)
        elif alpha_encoding == 7:
            return _decode_dxt5(compressed, width, height)

    elif encoding == 3:
        # Raw BGRA
        mip_offset = mip_offsets[0]
        mip_size = mip_sizes[0]
        if mip_offset + mip_size > len(data):
            return None
        raw = data[mip_offset:mip_offset + mip_size]
        if len(raw) < width * height * 4:
            return None
        img = Image.frombytes("RGBA", (width, height), raw, "raw", "BGRA")
        return img

    return None


def _decode_color565(c: int) -> tuple[int, int, int]:
    r = ((c >> 11) & 0x1F) * 255 // 31
    g = ((c >> 5) & 0x3F) * 255 // 63
    b = (c & 0x1F) * 255 // 31
    return r, g, b


def _decode_dxt1(data: bytes, w: int, h: int) -> Image.Image:
    img = Image.new("RGBA", (w, h))
    pixels = img.load()
    blocks_x = max(1, (w + 3) // 4)
    blocks_y = max(1, (h + 3) // 4)
    offset = 0

    for by in range(blocks_y):
        for bx in range(blocks_x):
            if offset + 8 > len(data):
                return img
            c0, c1 = struct.unpack_from("<HH", data, offset)
            bits = struct.unpack_from("<I", data, offset + 4)[0]
            offset += 8

            r0, g0, b0 = _decode_color565(c0)
            r1, g1, b1 = _decode_color565(c1)

            colors = [(r0, g0, b0, 255), (r1, g1, b1, 255)]
            if c0 > c1:
                colors.append(((2*r0+r1)//3, (2*g0+g1)//3, (2*b0+b1)//3, 255))
                colors.append(((r0+2*r1)//3, (g0+2*g1)//3, (b0+2*b1)//3, 255))
            else:
                colors.append(((r0+r1)//2, (g0+g1)//2, (b0+b1)//2, 255))
                colors.append((0, 0, 0, 0))

            for py in range(4):
                for px in range(4):
                    x = bx * 4 + px
                    y = by * 4 + py
                    if x < w and y < h:
                        idx = (bits >> (2 * (4 * py + px))) & 3
                        pixels[x, y] = colors[idx]
    return img


def _decode_dxt3(data: bytes, w: int, h: int) -> Image.Image:
    img = Image.new("RGBA", (w, h))
    pixels = img.load()
    blocks_x = max(1, (w + 3) // 4)
    blocks_y = max(1, (h + 3) // 4)
    offset = 0

    for by in range(blocks_y):
        for bx in range(blocks_x):
            if offset + 16 > len(data):
                return img
            # 8 bytes alpha, then DXT1 color block
            alpha_data = struct.unpack_from("<8B", data, offset)
            c0, c1 = struct.unpack_from("<HH", data, offset + 8)
            bits = struct.unpack_from("<I", data, offset + 12)[0]
            offset += 16

            r0, g0, b0 = _decode_color565(c0)
            r1, g1, b1 = _decode_color565(c1)

            colors = [
                (r0, g0, b0), (r1, g1, b1),
                ((2*r0+r1)//3, (2*g0+g1)//3, (2*b0+b1)//3),
                ((r0+2*r1)//3, (g0+2*g1)//3, (b0+2*b1)//3),
            ]

            for py in range(4):
                for px in range(4):
                    x = bx * 4 + px
                    y = by * 4 + py
                    if x < w and y < h:
                        cidx = (bits >> (2 * (4 * py + px))) & 3
                        r, g, b = colors[cidx]
                        # Alpha is 4 bits per pixel
                        alpha_byte_idx = py * 2 + px // 2
                        if px % 2 == 0:
                            a = (alpha_data[alpha_byte_idx] & 0x0F) * 17
                        else:
                            a = ((alpha_data[alpha_byte_idx] >> 4) & 0x0F) * 17
                        pixels[x, y] = (r, g, b, a)
    return img


def _decode_dxt5(data: bytes, w: int, h: int) -> Image.Image:
    img = Image.new("RGBA", (w, h))
    pixels = img.load()
    blocks_x = max(1, (w + 3) // 4)
    blocks_y = max(1, (h + 3) // 4)
    offset = 0

    for by in range(blocks_y):
        for bx in range(blocks_x):
            if offset + 16 > len(data):
                return img

            a0, a1 = struct.unpack_from("<BB", data, offset)
            alpha_bits = int.from_bytes(data[offset+2:offset+8], "little")
            c0, c1 = struct.unpack_from("<HH", data, offset + 8)
            bits = struct.unpack_from("<I", data, offset + 12)[0]
            offset += 16

            # Build alpha table
            alphas = [a0, a1]
            if a0 > a1:
                for i in range(1, 7):
                    alphas.append(((7 - i) * a0 + i * a1) // 7)
            else:
                for i in range(1, 5):
                    alphas.append(((5 - i) * a0 + i * a1) // 5)
                alphas.extend([0, 255])

            r0, g0, b0 = _decode_color565(c0)
            r1, g1, b1 = _decode_color565(c1)
            colors = [
                (r0, g0, b0), (r1, g1, b1),
                ((2*r0+r1)//3, (2*g0+g1)//3, (2*b0+b1)//3),
                ((r0+2*r1)//3, (g0+2*g1)//3, (b0+2*b1)//3),
            ]

            for py in range(4):
                for px in range(4):
                    x = bx * 4 + px
                    y = by * 4 + py
                    if x < w and y < h:
                        cidx = (bits >> (2 * (4 * py + px))) & 3
                        r, g, b = colors[cidx]
                        pidx = py * 4 + px
                        aidx = (alpha_bits >> (3 * pidx)) & 7
                        a = alphas[aidx]
                        pixels[x, y] = (r, g, b, a)
    return img


# ── glTF generation ─────────────────────────────────────────────────────

def build_glb(
    positions: np.ndarray,
    normals: np.ndarray,
    uvs: np.ndarray,
    submeshes: list[dict],
    texture_img: Image.Image | None,
    output_path: str,
    submesh_tex_types: dict[int, int] | None = None,
):
    """Build a GLB file with separate mesh nodes per geoset submesh.

    Each submesh becomes a child node named 'geoset_{id}_{textype}' where textype
    is 'skin' (type 1) or 'hair' (type 6) so the frontend can apply different textures.
    """
    TEX_TYPE_NAMES = {0: "env", 1: "skin", 2: "cape", 6: "hair", 8: "skin_extra"}
    submesh_tex_types = submesh_tex_types or {}
    gltf = GLTF2()
    gltf.asset = Asset(generator="wotlk-extractor", version="2.0")
    gltf.scene = 0

    positions = positions.astype(np.float32)
    normals = normals.astype(np.float32)
    uvs = uvs.astype(np.float32)

    def pad4(b):
        pad = (4 - len(b) % 4) % 4
        return b + b"\x00" * pad

    # Shared vertex attribute data
    pos_bytes = positions.tobytes()
    norm_bytes = normals.tobytes()
    uv_bytes = uvs.tobytes()

    pos_bytes_p = pad4(pos_bytes)
    norm_bytes_p = pad4(norm_bytes)
    uv_bytes_p = pad4(uv_bytes)

    bin_data = pos_bytes_p + norm_bytes_p + uv_bytes_p

    # Build index buffers for each submesh
    submesh_idx_info = []
    for si, sm in enumerate(submeshes):
        idx = sm["indices"].astype(np.uint32)
        idx_raw = idx.tobytes()
        idx_padded = pad4(idx_raw)
        submesh_idx_info.append({
            "geosetId": sm["geosetId"],
            "submeshIndex": sm.get("submeshIndex", si),
            "offset": len(bin_data),
            "byteLength": len(idx_raw),
            "count": len(idx),
        })
        bin_data += idx_padded

    # Texture image
    tex_raw = None
    if texture_img is not None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            texture_img.save(f, "PNG")
            f.seek(0)
            tex_raw = Path(f.name).read_bytes()
            os.unlink(f.name)
        tex_offset = len(bin_data)
        bin_data += pad4(tex_raw)

    gltf.buffers = [Buffer(byteLength=len(bin_data))]

    # Shared buffer views for vertex attributes
    bv_offset = 0
    gltf.bufferViews = [
        BufferView(buffer=0, byteOffset=bv_offset, byteLength=len(pos_bytes), target=34962),
    ]
    bv_offset += len(pos_bytes_p)
    gltf.bufferViews.append(
        BufferView(buffer=0, byteOffset=bv_offset, byteLength=len(norm_bytes), target=34962)
    )
    bv_offset += len(norm_bytes_p)
    gltf.bufferViews.append(
        BufferView(buffer=0, byteOffset=bv_offset, byteLength=len(uv_bytes), target=34962)
    )
    # BV indices: 0=positions, 1=normals, 2=UVs

    # Index buffer views for each submesh (starting at BV index 3)
    idx_bv_start = 3
    for info in submesh_idx_info:
        gltf.bufferViews.append(
            BufferView(buffer=0, byteOffset=info["offset"], byteLength=info["byteLength"], target=34963)
        )

    # Shared vertex attribute accessors
    n_verts = positions.shape[0]
    pos_min = positions.min(axis=0).tolist()
    pos_max = positions.max(axis=0).tolist()

    gltf.accessors = [
        Accessor(bufferView=0, componentType=5126, count=n_verts, type="VEC3", max=pos_max, min=pos_min),
        Accessor(bufferView=1, componentType=5126, count=n_verts, type="VEC3"),
        Accessor(bufferView=2, componentType=5126, count=n_verts, type="VEC2"),
    ]
    # Accessor indices: 0=positions, 1=normals, 2=UVs

    # Index accessors for each submesh (starting at accessor index 3)
    idx_acc_start = 3
    for i, info in enumerate(submesh_idx_info):
        gltf.accessors.append(
            Accessor(bufferView=idx_bv_start + i, componentType=5125, count=info["count"], type="SCALAR")
        )

    # Materials: material 0 = skin (with texture), material 1 = non-skin (neutral, no texture)
    # Non-skin meshes (hair, cape, env, skin_extra) get their textures loaded at runtime
    SKIN_MAT = 0
    NONSKIN_MAT = 1
    if tex_raw is not None:
        tex_bv = len(gltf.bufferViews)
        gltf.bufferViews.append(
            BufferView(buffer=0, byteOffset=tex_offset, byteLength=len(tex_raw))
        )
        gltf.images = [GLTFImage(bufferView=tex_bv, mimeType="image/png")]
        gltf.samplers = [Sampler(magFilter=9729, minFilter=9729, wrapS=10497, wrapT=10497)]
        gltf.textures = [Texture(source=0, sampler=0)]
        gltf.materials = [
            Material(  # 0: skin - has embedded texture
                doubleSided=True,
                pbrMetallicRoughness={
                    "baseColorTexture": {"index": 0},
                    "metallicFactor": 0.0,
                    "roughnessFactor": 1.0,
                }
            ),
            Material(  # 1: non-skin - neutral placeholder, texture loaded at runtime
                doubleSided=True,
                pbrMetallicRoughness={
                    "baseColorFactor": [0.5, 0.5, 0.5, 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 1.0,
                }
            ),
        ]
    else:
        gltf.materials = [
            Material(
                doubleSided=True,
                pbrMetallicRoughness={
                    "baseColorFactor": [0.6, 0.6, 0.6, 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 1.0,
                }
            ),
            Material(
                doubleSided=True,
                pbrMetallicRoughness={
                    "baseColorFactor": [0.5, 0.5, 0.5, 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 1.0,
                }
            ),
        ]

    # One mesh + node per submesh, named geoset_{id}_{textype}
    gltf.meshes = []
    gltf.nodes = []
    child_indices = []

    for i, info in enumerate(submesh_idx_info):
        gid = info["geosetId"]
        sm_idx = info.get("submeshIndex", i)
        tex_type = submesh_tex_types.get(sm_idx, 1)  # default to skin
        tex_label = TEX_TYPE_NAMES.get(tex_type, "skin")
        node_name = f"geoset_{gid}_{tex_label}"

        # Skin meshes use material 0 (with embedded skin texture)
        # All other types use material 1 (neutral placeholder)
        mat_idx = SKIN_MAT if tex_type == 1 else NONSKIN_MAT

        mesh_idx = len(gltf.meshes)
        gltf.meshes.append(Mesh(
            name=node_name,
            primitives=[Primitive(
                attributes={"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
                indices=idx_acc_start + i,
                material=mat_idx,
            )]
        ))
        node_idx = len(gltf.nodes)
        gltf.nodes.append(Node(name=node_name, mesh=mesh_idx))
        child_indices.append(node_idx)

    # Root node that parents all submesh nodes
    root_idx = len(gltf.nodes)
    gltf.nodes.append(Node(name="root", children=child_indices))
    gltf.scenes = [Scene(nodes=[root_idx])]

    gltf.set_binary_blob(bin_data)
    gltf.save(output_path)
    print(f"  Saved: {output_path} ({os.path.getsize(output_path)} bytes, {len(submeshes)} geosets)")


# ── Main extraction logic ───────────────────────────────────────────────

# WotLK character model paths in MPQ
RACE_MODELS = {
    "human_male": "Character\\Human\\Male\\HumanMale.m2",
    "human_female": "Character\\Human\\Female\\HumanFemale.m2",
    "orc_male": "Character\\Orc\\Male\\OrcMale.m2",
    "orc_female": "Character\\Orc\\Female\\OrcFemale.m2",
    "dwarf_male": "Character\\Dwarf\\Male\\DwarfMale.m2",
    "dwarf_female": "Character\\Dwarf\\Female\\DwarfFemale.m2",
    "nightelf_male": "Character\\NightElf\\Male\\NightElfMale.m2",
    "nightelf_female": "Character\\NightElf\\Female\\NightElfFemale.m2",
    "undead_male": "Character\\Scourge\\Male\\ScourgeMale.m2",
    "undead_female": "Character\\Scourge\\Female\\ScourgeFemale.m2",
    "tauren_male": "Character\\Tauren\\Male\\TaurenMale.m2",
    "tauren_female": "Character\\Tauren\\Female\\TaurenFemale.m2",
    "gnome_male": "Character\\Gnome\\Male\\GnomeMale.m2",
    "gnome_female": "Character\\Gnome\\Female\\GnomeFemale.m2",
    "troll_male": "Character\\Troll\\Male\\TrollMale.m2",
    "troll_female": "Character\\Troll\\Female\\TrollFemale.m2",
    "bloodelf_male": "Character\\BloodElf\\Male\\BloodElfMale.m2",
    "bloodelf_female": "Character\\BloodElf\\Female\\BloodElfFemale.m2",
    "draenei_male": "Character\\Draenei\\Male\\DraeneiMale.m2",
    "draenei_female": "Character\\Draenei\\Female\\DraeneiFemale.m2",
}

# MPQ load order for WotLK (later patches override earlier)
MPQ_LOAD_ORDER = [
    "common.MPQ",
    "common-2.MPQ",
    "expansion.MPQ",
    "lichking.MPQ",
    "patch.MPQ",
    "patch-2.MPQ",
    "patch-3.MPQ",
]


def extract_character_models(data_dir: str, output_dir: str):
    """Extract all race/gender base models from MPQ archives."""
    chars_dir = os.path.join(output_dir, "characters")
    os.makedirs(chars_dir, exist_ok=True)

    mpq_files = []
    for mpq_name in MPQ_LOAD_ORDER:
        mpq_path = os.path.join(data_dir, mpq_name)
        if os.path.exists(mpq_path):
            mpq_files.append(mpq_path)

    if not mpq_files:
        print(f"ERROR: No MPQ files found in {data_dir}")
        return

    print(f"Found {len(mpq_files)} MPQ archives")
    manifest = {}

    for model_key, m2_path in RACE_MODELS.items():
        print(f"\nExtracting: {model_key}")
        m2_data = None
        skin_data = None

        # Build skin path (same name but .skin extension, first skin = 00)
        skin_path = m2_path.replace(".m2", "00.skin")

        # Search archives in reverse order (patches first)
        for mpq_path in reversed(mpq_files):
            try:
                with MPQArchive(mpq_path) as mpq:
                    if m2_data is None:
                        result = mpq.read_file(m2_path)
                        if result:
                            m2_data = result
                            print(f"  M2 found in {os.path.basename(mpq_path)} ({len(m2_data)} bytes)")

                    if skin_data is None:
                        result = mpq.read_file(skin_path)
                        if result:
                            skin_data = result
                            print(f"  Skin found in {os.path.basename(mpq_path)} ({len(skin_data)} bytes)")
            except OSError as e:
                print(f"  Warning: {e}")
                continue

            if m2_data and skin_data:
                break

        if not m2_data:
            print(f"  SKIP: M2 not found")
            continue

        # Parse M2
        header = _read_m2_header(m2_data)
        if not header:
            print(f"  SKIP: Invalid M2 header")
            continue

        print(f"  Vertices: {header['nVertices']}, Textures: {header['nTextures']}")

        raw_verts = _read_m2_vertices(m2_data, header)
        if raw_verts.shape[0] == 0:
            print(f"  SKIP: No vertices")
            continue

        positions, normals, uvs = _parse_vertices(raw_verts)

        # Get submeshes from skin file
        submeshes = None
        if skin_data:
            submeshes = _read_skin_file(skin_data)
            if submeshes:
                total_tris = sum(len(sm["indices"]) // 3 for sm in submeshes)
                print(f"  Submeshes: {len(submeshes)}, Total triangles: {total_tris}")

        if not submeshes:
            print("  Warning: No skin data, generating single submesh")
            n_verts = positions.shape[0]
            n_tris = n_verts - (n_verts % 3)
            submeshes = [{"geosetId": 0, "indices": np.arange(n_tris, dtype=np.uint32)}]

        # Clip indices to valid vertex range
        max_idx = positions.shape[0] - 1
        for sm in submeshes:
            sm["indices"] = np.clip(sm["indices"], 0, max_idx)

        # Try to find skin texture
        # M2 texture type 1 = character skin, resolved by convention:
        #   Character\{Race}\{Gender}\{Race}{Gender}Skin{Color:02d}.blp
        texture_img = None
        tex_info = _read_texture_info(m2_data, header)

        # First try to find the actual skin texture (type 1) by convention path
        m2_dir = "\\".join(m2_path.split("\\")[:-1])
        base_name = m2_path.split("\\")[-1].replace(".m2", "")
        # Default skin color 00
        skin_tex_candidates = [
            f"{m2_dir}\\{base_name}Skin00_00.blp",
            f"{m2_dir}\\{base_name}Skin00.blp",
        ]
        # Also add specific race skin paths
        race_part = model_key.split("_")[0].capitalize()
        gender_part = model_key.split("_")[1].capitalize()
        skin_tex_candidates.extend([
            f"Character\\{race_part}\\{gender_part}\\{race_part}{gender_part}Skin00_00.blp",
            f"Character\\{race_part}\\{gender_part}\\{race_part}{gender_part}Skin00.blp",
        ])

        for skin_tex_path in skin_tex_candidates:
            for mpq_path in reversed(mpq_files):
                try:
                    with MPQArchive(mpq_path) as mpq:
                        blp_data = mpq.read_file(skin_tex_path)
                        if blp_data:
                            texture_img = decode_blp(blp_data)
                            if texture_img and texture_img.size[0] >= 64:
                                print(f"  Skin texture: {skin_tex_path} ({texture_img.size[0]}x{texture_img.size[1]})")
                                break
                            texture_img = None
                except OSError:
                    continue
            if texture_img:
                break

        # Fallback: try hardcoded filename textures (type 0) but skip tiny glow textures
        if not texture_img:
            for tex in tex_info:
                if tex["filename"] and tex["type"] == 0:
                    blp_path = tex["filename"]
                    for mpq_path in reversed(mpq_files):
                        try:
                            with MPQArchive(mpq_path) as mpq:
                                blp_data = mpq.read_file(blp_path)
                                if blp_data:
                                    candidate = decode_blp(blp_data)
                                    if candidate and candidate.size[0] >= 64:
                                        texture_img = candidate
                                        print(f"  Texture: {blp_path} ({texture_img.size[0]}x{texture_img.size[1]})")
                                        break
                        except OSError:
                            continue
                    if texture_img:
                        break

        # Map submesh index -> texture type (skin=1, hair=6, etc.)
        submesh_tex_types = {}
        if skin_data and m2_data:
            submesh_tex_types = _read_skin_batches(skin_data, m2_data, header)
            tex_type_summary = {}
            for sm_idx, tt in submesh_tex_types.items():
                label = {0: "env", 1: "skin", 2: "cape", 6: "hair", 8: "skin_extra"}.get(tt, f"type{tt}")
                tex_type_summary[label] = tex_type_summary.get(label, 0) + 1
            print(f"  Texture types: {tex_type_summary}")

        # Build GLB
        output_path = os.path.join(chars_dir, f"{model_key}.glb")
        try:
            build_glb(positions, normals, uvs, submeshes, texture_img, output_path,
                       submesh_tex_types=submesh_tex_types)
            manifest[model_key] = f"characters/{model_key}.glb"
        except Exception as e:
            print(f"  ERROR building GLB: {e}")

    # Write manifest
    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest written: {manifest_path}")
    print(f"Extracted {len(manifest)}/{len(RACE_MODELS)} models")


def main():
    parser = argparse.ArgumentParser(description="Extract WotLK character models to glTF")
    parser.add_argument("--data-dir", default="../Data", help="Path to WoW Data directory with MPQ files")
    parser.add_argument("--output-dir", default="../frontend/public/models", help="Output directory for models")
    args = parser.parse_args()

    data_dir = os.path.abspath(args.data_dir)
    output_dir = os.path.abspath(args.output_dir)

    print("=" * 60)
    print("WotLK Model Extraction Pipeline")
    print("=" * 60)
    print(f"Data dir: {data_dir}")
    print(f"Output dir: {output_dir}")

    if not os.path.isdir(data_dir):
        print(f"ERROR: Data directory not found: {data_dir}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    extract_character_models(data_dir, output_dir)

    print("\nDone!")


if __name__ == "__main__":
    main()
