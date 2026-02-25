# Configuration

All runtime configuration lives in a single `.env` file in the project root. Copy the template to get started:

```bash
cp .env.example .env
```

---

## Environment Variables

### Database Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | Hostname or IP of the MySQL/MariaDB server |
| `DB_USER` | `acore` | MySQL username |
| `DB_PASS` | _(empty)_ | MySQL password |
| `DB_NAME` | `acore_characters` | Characters database name |
| `WORLD_DB_NAME` | `acore_world` | World (item templates) database name |

#### Common AzerothCore Database Name Variants

Different AzerothCore setups use different naming conventions. Adjust to match yours:

| Setup | `DB_NAME` | `WORLD_DB_NAME` |
|-------|-----------|-----------------|
| Default AzerothCore | `acore_characters` | `acore_world` |
| Alternative prefix | `ac_characters` | `ac_world` |
| Generic names | `characters` | `world` |

To check which databases exist on your server:
```bash
mysql -u acore -p -e "SHOW DATABASES;"
```

---

### CORS Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed frontend origins |

The backend only accepts `GET` requests and restricts cross-origin calls to the listed origins. The default value works when both services run on the same machine with default ports.

**Multiple origins:**
```env
CORS_ORIGINS=http://localhost:5173,http://192.168.1.50:5173
```

**If you expose the frontend on a public IP:**
```env
CORS_ORIGINS=http://your-server.example.com:5173
```

> **Security note**: The backend listens only on `127.0.0.1` by default, so it is not directly reachable from outside the machine even if CORS is permissive.

---

## Port Configuration

Ports are set via shell environment variables when launching, not in `.env`:

```bash
BACKEND_PORT=8000 FRONTEND_PORT=5173 ./start.sh   # defaults
BACKEND_PORT=8080 FRONTEND_PORT=3000 ./start.sh   # custom ports
```

When you change ports, also update `CORS_ORIGINS` to match the new frontend port:
```env
CORS_ORIGINS=http://localhost:3000
```

And update `vite.config.ts` if changing the backend port (the proxy target is hardcoded to `:8000`):
```typescript
proxy: {
  '/api': {
    target: 'http://127.0.0.1:8000',  // Change if BACKEND_PORT ≠ 8000
    changeOrigin: true,
  },
},
```

---

## Full `.env.example`

```env
# ── Database ──────────────────────────────────────────────────────────
DB_HOST=localhost
DB_USER=acore
DB_PASS=changeme
DB_NAME=acore_characters
WORLD_DB_NAME=acore_world

# ── CORS ──────────────────────────────────────────────────────────────
# Origins allowed to call the backend API (comma-separated)
CORS_ORIGINS=http://localhost:5173
```

---

## How Settings Are Loaded

`backend/config.py` uses [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/):

```python
class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_USER: str = "acore"
    DB_PASS: str = ""
    DB_NAME: str = "acore_characters"
    WORLD_DB_NAME: str = "acore_world"
    CORS_ORIGINS: str = "http://localhost:5173"

    model_config = {"env_file": "../.env", "env_file_encoding": "utf-8"}
```

The path `../\.env` is relative to the `backend/` directory, resolving to the project root. You can also set any variable as a real shell environment variable — shell variables take precedence over the `.env` file.

```bash
DB_PASS=override ./start.sh   # overrides .env value
```

---

## Database Connection Pool

The backend uses an **async connection pool** via `aiomysql` configured at startup:

| Setting | Value |
|---------|-------|
| Min connections | 2 |
| Max connections | 10 |
| Character set | utf8mb4 |
| Cursor type | DictCursor (rows as dicts) |
| Autocommit | True (read-only operations) |

The pool is created in `main.py`'s `lifespan` handler and torn down gracefully on shutdown.

---

## MPQ Data Directory

The `Data/` folder must sit at the project root and contain your WoW 3.3.5a MPQ archives. The extraction pipeline searches for archives in this order (from `tools/extract_models.py`):

```
Data/
├── patch-3.MPQ
├── patch-2.MPQ
├── patch.MPQ
├── Expansion.MPQ
├── Lichking.MPQ
├── common.MPQ
├── common-2.MPQ
└── enUS/
    ├── patch-enUS-3.MPQ
    ├── patch-enUS-2.MPQ
    ├── patch-enUS.MPQ
    └── locale-enUS.MPQ
```

Files earlier in the load order override files with the same internal path in later archives (mirrors how the WoW client loads assets).

---

## Model Cache Directory

Runtime-generated textures and item models are cached in:

```
frontend/public/models/cache/
```

This directory is served as static files by Vite and is accessed directly by the browser after the backend has generated and written the file. The cache is not cleared automatically; delete the contents if you want to force regeneration (e.g., after re-extracting models or updating gear_compositor.py).

```bash
rm -rf frontend/public/models/cache/*
touch  frontend/public/models/cache/.gitkeep
```
