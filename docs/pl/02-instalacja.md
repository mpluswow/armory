# Instalacja

## Wymagania systemowe

Aplikacja działa na **systemach Linux** (zalecany Debian/Ubuntu). Windows i macOS nie są testowane.

### Minimalne oprogramowanie systemowe

| Zależność | Minimalna wersja | Uwagi |
|-----------|-----------------|-------|
| Python | 3.8 | Wymagany moduł `venv` (`python3-venv`) |
| Node.js | 18 | Vite 7 wymaga Node ≥ 18. Domyślny pakiet apt Ubuntu jest często za stary — `start.sh` obsługuje to automatycznie przez NodeSource |
| npm | 8 | Dostarczany razem z Node.js |
| gcc / g++ | dowolna | Wymagane do zbudowania StormLib (`build-essential`) |
| cmake | 3.x | Wymagane do zbudowania StormLib |
| git | dowolna | Wymagane do sklonowania StormLib jeśli trzeba go zbudować |
| MySQL / MariaDB | 5.7 / 10.3 | Działająca baza danych AzerothCore |

> `start.sh` sprawdza wszystkie powyższe i instaluje brakujące automatycznie na systemach Debian/Ubuntu przy użyciu `apt-get`. Wymagany jest dostęp `sudo`.

---

## Szybki start

Pełny przepływ dla pierwszego uruchomienia.

### Krok 1 — Sklonuj repozytorium

```bash
git clone <adres-repo> armory
cd armory
```

### Krok 2 — Skonfiguruj bazę danych

```bash
cp .env.example .env
nano .env   # lub dowolny edytor
```

Uzupełnij dane logowania do bazy AzerothCore:

```env
DB_HOST=localhost
DB_USER=acore
DB_PASS=twoje_haslo
DB_NAME=acore_characters
WORLD_DB_NAME=acore_world
CORS_ORIGINS=http://localhost:5173
```

Wszystkie dostępne ustawienia opisane są w [Konfiguracji](03-konfiguracja.md).

### Krok 3 — Wyekstrahuj modele postaci (jednorazowo, wymaga plików MPQ)

Twój folder `Data/` z WoW 3.3.5a (zawierający pliki `.MPQ`) musi znajdować się w `armory/Data/`.

```bash
# start.sh stworzy to venv za ciebie, ale do ręcznej ekstrakcji:
python3 -m venv tools/venv
tools/venv/bin/pip install -r tools/requirements.txt

tools/venv/bin/python tools/extract_models.py \
  --data-dir ./Data \
  --output-dir ./frontend/public/models
```

Polecenie generuje:
- `frontend/public/models/characters/*.glb` — 20 modeli postaci (10 ras × 2 płcie)
- `frontend/public/models/manifest.json` — indeks modeli
- `frontend/public/models/attachments.json` — pozycje punktów przyczepu

To jednorazowy krok. Powtórz tylko jeśli chcesz zregenerować modele.

### Krok 4 — Uruchom aplikację

```bash
chmod +x start.sh
./start.sh
```

Otwórz **http://localhost:5173** w przeglądarce.

---

## Co robi `start.sh` automatycznie

Przy pierwszym uruchomieniu `start.sh` wykonuje pełną konfigurację przed startem serwerów. Przy kolejnych uruchomieniach wykrywa co jest już zainstalowane i pomija te kroki.

### Krok 1 — Python
- Sprawdza `python3` → instaluje jeśli brak
- Sprawdza `python3-venv` → instaluje jeśli brak
- Sprawdza `python3-dev` (nagłówki rozszerzeń C) → instaluje jeśli brak

### Krok 2 — Narzędzia do budowania
- Sprawdza `gcc` (build-essential) → instaluje jeśli brak
- Sprawdza `cmake` → instaluje jeśli brak
- Sprawdza `git` → instaluje jeśli brak
- Sprawdza `curl` i `lsof` → instaluje jeśli brak
- `apt-get update` uruchamia się tylko raz i tylko jeśli coś brakuje

### Krok 3 — Node.js
- Odczytuje zainstalowaną wersję Node.js
- Jeśli < 18 lub brak: dodaje repozytorium NodeSource i instaluje **Node.js 20 LTS**
- Rozwiązuje typowy problem, gdy Ubuntu dostarcza Node 12 lub 14

### Krok 4 — StormLib (`libstorm.so`)
- Sprawdza czy `tools/libstorm.so` istnieje i ładuje się poprawnie przez ctypes
- Jeśli nie ładuje się (brak pliku lub zła architektura CPU): **klonuje StormLib z GitHuba, uruchamia cmake + make, kopiuje wynik** — w pełni automatyczne, bez interakcji użytkownika
- Instaluje `zlib1g-dev` i `libbz2-dev` jako zależności przed kompilacją

### Krok 5 — Wirtualne środowiska Python
- Tworzy `tools/venv` jeśli brak → instaluje `Pillow`, `numpy`, `pygltflib`
- Tworzy `backend/venv` jeśli brak → instaluje `fastapi`, `uvicorn[standard]`, `aiomysql`, `pydantic-settings`, `python-dotenv`, `cachetools`
- Instaluje `libjpeg-dev`, `libpng-dev`, `zlib1g-dev` przed Pillow na wypadek braku kół (wheels)

### Krok 6 — Frontend
- Uruchamia `npm install` w `frontend/` jeśli brak `node_modules/`

### Sprawdzenia przed startem
- Weryfikuje istnienie `.env` — kończy z instrukcjami jeśli brak
- Ostrzega (nie przerywa) jeśli brak `manifest.json` (brak wyekstrahowanych modeli)
- Zabija procesy używające portów 8000 i 5173

### Uruchomienie serwerów
- Startuje backend uvicorn w tle, czeka do 10 sekund aż przyjmie połączenia
- Startuje frontend Vite w tle
- Wyświetla adresy URL i czeka (Ctrl+C zatrzymuje oba)

---

## Ręczna konfiguracja (bez `start.sh`)

Jeśli wolisz ręczną konfigurację lub używasz systemu innego niż Debian/Ubuntu:

### 1. Zainstaluj zależności systemowe

**Debian/Ubuntu:**
```bash
sudo apt-get update
sudo apt-get install -y \
  python3 python3-venv python3-dev \
  build-essential cmake git \
  curl lsof \
  libjpeg-dev libpng-dev zlib1g-dev libbz2-dev
```

**Node.js 20 LTS (przez NodeSource):**
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 2. Zbuduj StormLib (jeśli `libstorm.so` nie ładuje się)

```bash
git clone --depth=1 https://github.com/ladislav-zezula/StormLib.git /tmp/StormLib
cmake -S /tmp/StormLib -B /tmp/StormLib/build \
  -DBUILD_SHARED_LIBS=ON \
  -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/StormLib/build --parallel $(nproc)
cp /tmp/StormLib/build/libstorm.so tools/libstorm.so
```

### 3. Venv narzędzi

```bash
python3 -m venv tools/venv
tools/venv/bin/pip install -r tools/requirements.txt
```

### 4. Venv backendu

```bash
python3 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt
```

### 5. Frontend

```bash
cd frontend && npm install && cd ..
```

### 6. Skopiuj i edytuj `.env`

```bash
cp .env.example .env
# Uzupełnij .env danymi bazy danych
```

### 7. Wyekstrahuj modele

```bash
tools/venv/bin/python tools/extract_models.py \
  --data-dir ./Data \
  --output-dir ./frontend/public/models
```

### 8. Uruchom serwery

Terminal 1 (backend):
```bash
cd backend
../venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

Terminal 2 (frontend):
```bash
cd frontend
npx vite --host 0.0.0.0 --port 5173
```

---

## Zmiana portów

```bash
BACKEND_PORT=8080 FRONTEND_PORT=3000 ./start.sh
```

---

## Weryfikacja instalacji

Po udanym uruchomieniu `./start.sh`, sprawdź każdą warstwę:

```bash
# Backend działa
curl http://127.0.0.1:8000/api/characters

# Dane postaci
curl "http://127.0.0.1:8000/api/character?name=NazwaPostaci"
```

Następnie otwórz **http://localhost:5173** i wyszukaj postać ze swojego serwera.

---

## Pliki logów

Oba serwery zapisują logi do `logs/`:

| Plik | Zawartość |
|------|-----------|
| `logs/backend.log` | Log dostępu Uvicorn + wyjątki Python |
| `logs/frontend.log` | Wyniki budowania Vite + komunikaty HMR |

```bash
tail -f logs/backend.log    # podgląd backendu na żywo
tail -f logs/frontend.log   # podgląd frontendu na żywo
```
