# Troubleshooting

---

## Quick Checklist

Before diving into specific issues, confirm these basics:

- [ ] `.env` file exists at project root with correct database credentials
- [ ] MySQL/MariaDB is running and reachable
- [ ] Character models extracted (check `frontend/public/models/manifest.json` exists)
- [ ] Backend started (`curl http://127.0.0.1:8000/api/characters` returns JSON)
- [ ] Frontend started (http://localhost:5173 loads in browser)
- [ ] `Data/` contains WoW 3.3.5a MPQ archives

---

## Startup Issues

### `start.sh` exits: "sudo not found" or "apt-get not found"

**Cause:** The script cannot install missing system packages.

**Fix:**
If you do not have sudo, install dependencies as root:
```bash
su -c "apt-get install -y python3 python3-venv python3-dev build-essential cmake git nodejs npm"
```
If you are not on Debian/Ubuntu, install the equivalent packages manually:
- Python 3.8+, python3-venv, python3-dev
- gcc, g++, make, cmake, git
- Node.js 18+, npm

---

### `start.sh` exits: "Failed to clone StormLib"

**Cause:** No internet connection, or GitHub is unreachable.

**Fix (offline):** Build StormLib on a machine with internet access and copy `libstorm.so` to `tools/`:
```bash
git clone https://github.com/ladislav-zezula/StormLib.git
cmake -S StormLib -B StormLib/build -DBUILD_SHARED_LIBS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build StormLib/build --parallel $(nproc)
cp StormLib/build/libstorm.so /path/to/armory/tools/
```

---

### `start.sh` exits: "Backend crashed on startup. Check logs/backend.log"

Check the log immediately:
```bash
cat logs/backend.log
```

Common causes:
| Log message | Fix |
|-------------|-----|
| `Can't connect to MySQL server` | MySQL not running or wrong host in `.env` |
| `Access denied for user` | Wrong `DB_USER`/`DB_PASS` in `.env` |
| `Unknown database` | Wrong `DB_NAME` or `WORLD_DB_NAME` |
| `ModuleNotFoundError` | `backend/venv` corrupted — delete it and re-run `start.sh` |
| `Address already in use` | Port 8000 is occupied by another process |

---

### `npm install` fails

```bash
cd frontend
npm install
```

Common causes:
| Error | Fix |
|-------|-----|
| `EACCES: permission denied` | Do not run `npm install` as root; fix npm permissions |
| `ENOENT: package.json not found` | You must be in the `frontend/` directory |
| `engine "node" is incompatible` | Node < 18; let `start.sh` upgrade it via NodeSource |

---

## Database Errors

### "Character not found" even though the character exists

**Cause:** The character name is **case-sensitive** and must match the database exactly.

```bash
# Check exact name in DB
mysql -u acore -p acore_characters \
  -e "SELECT name FROM characters WHERE name LIKE 'arthas%';"
```

---

### Equipment slots are empty (character loads but shows no gear)

**Cause 1:** The character genuinely has no equipped items.
```sql
SELECT ci.slot, ii.itemEntry
FROM character_inventory ci
JOIN item_instance ii ON ci.item = ii.guid
WHERE ci.guid = YOUR_CHAR_GUID AND ci.bag = 0;
```

**Cause 2:** `WORLD_DB_NAME` is wrong — the JOIN to `item_template` fails silently.
```bash
mysql -u acore -p -e "SHOW DATABASES LIKE '%world%';"
# Update WORLD_DB_NAME in .env to match
```

---

### Stats show "Stat 99" or unknown names

**Cause:** A `stat_type` ID is not in the application's mapping table in `services/character.py`.

**Fix:** Add the missing ID to the `STAT_TYPES` dictionary in `backend/services/character.py`.

---

## 3D Model Issues

### "No extracted character models found" warning on startup

**Fix:** Run the extraction pipeline:
```bash
tools/venv/bin/python tools/extract_models.py \
  --data-dir ./Data \
  --output-dir ./frontend/public/models
```

Make sure `Data/` exists and contains WoW 3.3.5a `.MPQ` files.

---

### Model viewer shows a fallback / error boundary

**Cause 1:** The character GLB file is missing.
```bash
ls frontend/public/models/characters/
# Should list 20 .glb files
```

**Cause 2:** WebGL is not available in the browser (some VMs/headless setups).

**Cause 3:** An exception was thrown during the Three.js scene setup. Open the browser developer console (F12 → Console) and look for the error.

---

### Character model is blank / grey / unlit

**Cause:** The skin texture failed to load. Check:
```bash
curl http://127.0.0.1:8000/api/model-texture/YourCharName
# Should return a PNG, not JSON error
```

If it returns an error:
- Check that `Data/` contains the locale MPQs (e.g., `enUS/locale-enUS.MPQ`)
- Check `logs/backend.log` for Python exceptions from `gear_compositor.py`
- Delete the cache and retry: `rm -rf frontend/public/models/cache/*`

---

### Weapons / shoulders / helm not appearing in 3D view

**Cause 1:** The item model is not in the MPQ (custom/modded items without a base M2).

**Cause 2:** A runtime error during GLB extraction. Check:
```bash
curl "http://127.0.0.1:8000/api/item-model/DISPLAY_ID"
# Replace DISPLAY_ID with the item's displayid from the character endpoint
```

**Cause 3:** Attachment point data is missing for this race/gender combination.
```bash
cat frontend/public/models/attachments.json | python3 -m json.tool | grep -A5 "human_male"
```

---

### Hair is visible through the helmet

**Cause:** `HelmetGeosetVisData.dbc` could not be loaded (missing locale MPQ).

Check `logs/backend.log` for errors when the geosets endpoint is called. This DBC is in the locale archive (`enUS/locale-enUS.MPQ`).

---

## Texture Issues

### Cape texture returns 404

This is expected if the character has no back item equipped (slot 14). It is also expected for some older or unusual capes that use a different texture system.

---

### Extra-skin texture returns 404

Expected for races with no extra skin layer. Only some races (e.g., Tauren, Undead) have `skin_extra` textures.

---

### Skin texture looks wrong (incorrect armour colours)

**Cause:** Stale cache from a previous equipment loadout.

**Fix:**
```bash
rm -rf frontend/public/models/cache/*.png
```
The next request regenerates all skin textures.

---

## Performance Issues

### First texture request is very slow (10–30 seconds)

**Cause:** MPQ archives are being opened for the first time. Subsequent requests are fast because the persistent pool keeps them open.

`start.sh` calls `_warmup_mpq_pool()` at backend startup to pre-open all archives. If it is slow, check that your `Data/` directory contains all expected MPQ files.

---

### The backend is slow in general

- Check that `cachetools` is installed — the TTLCache is what makes character lookups fast.
- Make sure the `Data/` directory is on a local SSD, not a network mount.
- If you have many characters, increase the cache size in `routes/characters.py`:
  ```python
  _cache: TTLCache = TTLCache(maxsize=512, ttl=60)
  ```

---

## Log Locations

| File | How to view |
|------|-------------|
| `logs/backend.log` | `tail -f logs/backend.log` |
| `logs/frontend.log` | `tail -f logs/frontend.log` |

---

## Resetting State

### Clear all generated caches
```bash
rm -rf frontend/public/models/cache/*
touch  frontend/public/models/cache/.gitkeep
```

### Delete Python venvs (forces reinstall)
```bash
rm -rf backend/venv tools/venv
./start.sh   # recreates automatically
```

### Delete frontend node_modules (forces reinstall)
```bash
rm -rf frontend/node_modules
./start.sh   # reinstalls automatically
```

### Delete all extracted models (forces re-extraction)
```bash
rm -rf frontend/public/models/characters/
rm  -f frontend/public/models/manifest.json
rm  -f frontend/public/models/attachments.json
# Then re-run extract_models.py
```

---

## Reporting Issues

When reporting a bug, include:

1. Output of `./start.sh` (the full terminal session)
2. Contents of `logs/backend.log`
3. Browser console errors (F12 → Console tab)
4. Your OS and distribution (`lsb_release -a`)
5. Python version (`python3 --version`)
6. Node version (`node --version`)
