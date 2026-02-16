from fastapi import APIRouter, HTTPException, Query
from cachetools import TTLCache

from services.character import get_character, list_characters

router = APIRouter(prefix="/api")

_cache: TTLCache = TTLCache(maxsize=256, ttl=30)


@router.get("/character")
async def character(name: str = Query(..., min_length=1)):
    name = name.strip()
    cached = _cache.get(name.lower())
    if cached is not None:
        return cached

    data = await get_character(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f'Character "{name}" not found')

    _cache[name.lower()] = data
    return data


@router.get("/characters")
async def characters(limit: int = Query(100, ge=1, le=500)):
    return await list_characters(limit)
