# Konfiguracja

Cała konfiguracja aplikacji przechowywana jest w jednym pliku `.env` w głównym folderze projektu. Skopiuj szablon aby zacząć:

```bash
cp .env.example .env
```

---

## Zmienne środowiskowe

### Ustawienia bazy danych

| Zmienna | Domyślna | Opis |
|---------|----------|------|
| `DB_HOST` | `localhost` | Adres hosta serwera MySQL/MariaDB |
| `DB_USER` | `acore` | Nazwa użytkownika MySQL |
| `DB_PASS` | _(pusta)_ | Hasło MySQL |
| `DB_NAME` | `acore_characters` | Nazwa bazy danych postaci |
| `WORLD_DB_NAME` | `acore_world` | Nazwa bazy danych świata (szablony przedmiotów) |

#### Typowe warianty nazw baz AzerothCore

Różne instalacje AzerothCore używają różnych konwencji nazewnictwa:

| Konfiguracja | `DB_NAME` | `WORLD_DB_NAME` |
|-------------|-----------|-----------------|
| Domyślna AzerothCore | `acore_characters` | `acore_world` |
| Alternatywny prefiks | `ac_characters` | `ac_world` |
| Nazwy ogólne | `characters` | `world` |

Aby sprawdzić jakie bazy istnieją na Twoim serwerze:
```bash
mysql -u acore -p -e "SHOW DATABASES;"
```

---

### Ustawienia CORS

| Zmienna | Domyślna | Opis |
|---------|----------|------|
| `CORS_ORIGINS` | `http://localhost:5173` | Lista dozwolonych adresów frontendu (rozdzielana przecinkami) |

Backend akceptuje tylko żądania `GET` i ogranicza wywołania cross-origin do wymienionych adresów. Domyślna wartość działa gdy oba serwisy uruchomione są na tej samej maszynie z domyślnymi portami.

**Wiele adresów:**
```env
CORS_ORIGINS=http://localhost:5173,http://192.168.1.50:5173
```

**Frontend na publicznym adresie IP:**
```env
CORS_ORIGINS=http://twoj-serwer.pl:5173
```

> **Uwaga bezpieczeństwa**: Backend domyślnie nasłuchuje tylko na `127.0.0.1`, więc nie jest bezpośrednio dostępny z zewnątrz maszyny nawet przy liberalnym CORS.

---

## Konfiguracja portów

Porty ustawia się przez zmienne środowiskowe przy uruchamianiu, nie w `.env`:

```bash
BACKEND_PORT=8000 FRONTEND_PORT=5173 ./start.sh   # wartości domyślne
BACKEND_PORT=8080 FRONTEND_PORT=3000 ./start.sh   # własne porty
```

Przy zmianie portów zaktualizuj też `CORS_ORIGINS` żeby pasowało do nowego portu frontendu:
```env
CORS_ORIGINS=http://localhost:3000
```

Oraz zaktualizuj `vite.config.ts` jeśli zmieniasz port backendu (cel proxy jest hardcoded na `:8000`):
```typescript
proxy: {
  '/api': {
    target: 'http://127.0.0.1:8000',  // Zmień jeśli BACKEND_PORT ≠ 8000
    changeOrigin: true,
  },
},
```

---

## Pełny plik `.env.example`

```env
# ── Baza danych ───────────────────────────────────────────────────────
DB_HOST=localhost
DB_USER=acore
DB_PASS=changeme
DB_NAME=acore_characters
WORLD_DB_NAME=acore_world

# ── CORS ──────────────────────────────────────────────────────────────
# Adresy dozwolone do wywoływania API backendu (rozdzielane przecinkami)
CORS_ORIGINS=http://localhost:5173
```

---

## Jak ładowane są ustawienia

`backend/config.py` używa [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/):

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

Ścieżka `../\.env` jest względna do folderu `backend/`, wskazując na główny folder projektu. Można też ustawić dowolną zmienną jako prawdziwą zmienną środowiskową — zmienne środowiskowe mają pierwszeństwo przed plikiem `.env`.

```bash
DB_PASS=nadpisanie ./start.sh   # nadpisuje wartość z .env
```

---

## Pula połączeń z bazą danych

Backend używa **asynchronicznej puli połączeń** przez `aiomysql`, konfigurowanej przy starcie:

| Ustawienie | Wartość |
|------------|---------|
| Minimalna liczba połączeń | 2 |
| Maksymalna liczba połączeń | 10 |
| Zestaw znaków | utf8mb4 |
| Typ kursora | DictCursor (wiersze jako słowniki) |
| Autocommit | True (operacje tylko do odczytu) |

Pula tworzona jest w handlerze `lifespan` w `main.py` i zamykana gracefully przy wyłączeniu.

---

## Folder danych MPQ

Folder `Data/` musi znajdować się w głównym folderze projektu i zawierać archiwa MPQ WoW 3.3.5a. Pipeline ekstrakcji przeszukuje archiwa w tej kolejności (z `tools/extract_models.py`):

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

Pliki wcześniejsze w kolejności ładowania mają pierwszeństwo nad plikami o tej samej ścieżce wewnętrznej w późniejszych archiwach (odzwierciedla sposób ładowania zasobów przez klienta WoW).

---

## Folder cache modeli

Tekstury i modele generowane w czasie rzeczywistym są przechowywane w:

```
frontend/public/models/cache/
```

Ten folder jest serwowany jako pliki statyczne przez Vite i dostępny bezpośrednio z przeglądarki po wygenerowaniu przez backend. Cache nie jest czyszczony automatycznie. Usuń zawartość jeśli chcesz wymusić regenerację (np. po ponownej ekstrakcji modeli lub aktualizacji `gear_compositor.py`):

```bash
rm -rf frontend/public/models/cache/*
touch  frontend/public/models/cache/.gitkeep
```
