# Rozwiązywanie problemów

---

## Szybka lista kontrolna

Przed zagłębieniem się w konkretne problemy, sprawdź podstawy:

- [ ] Plik `.env` istnieje w głównym folderze z poprawnymi danymi bazy
- [ ] MySQL/MariaDB działa i jest osiągalny
- [ ] Modele postaci wyekstrahowane (sprawdź czy `frontend/public/models/manifest.json` istnieje)
- [ ] Backend uruchomiony (`curl http://127.0.0.1:8000/api/characters` zwraca JSON)
- [ ] Frontend uruchomiony (http://localhost:5173 ładuje się w przeglądarce)
- [ ] `Data/` zawiera archiwa MPQ WoW 3.3.5a

---

## Problemy przy uruchomieniu

### `start.sh` kończy się błędem: "sudo not found" lub "apt-get not found"

**Przyczyna:** Skrypt nie może zainstalować brakujących pakietów systemowych.

**Rozwiązanie:**
Bez sudo, zainstaluj zależności jako root:
```bash
su -c "apt-get install -y python3 python3-venv python3-dev build-essential cmake git nodejs npm"
```
Na systemach innych niż Debian/Ubuntu, zainstaluj równoważne pakiety ręcznie:
- Python 3.8+, python3-venv, python3-dev
- gcc, g++, make, cmake, git
- Node.js 18+, npm

---

### `start.sh` kończy się: "Failed to clone StormLib"

**Przyczyna:** Brak połączenia z internetem lub GitHub jest niedostępny.

**Rozwiązanie (offline):** Zbuduj StormLib na maszynie z dostępem do internetu i skopiuj `libstorm.so` do `tools/`:
```bash
git clone https://github.com/ladislav-zezula/StormLib.git
cmake -S StormLib -B StormLib/build -DBUILD_SHARED_LIBS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build StormLib/build --parallel $(nproc)
cp StormLib/build/libstorm.so /ścieżka/do/armory/tools/
```

---

### `start.sh` kończy się: "Backend crashed on startup. Check logs/backend.log"

Sprawdź log natychmiast:
```bash
cat logs/backend.log
```

Częste przyczyny:
| Komunikat w logu | Rozwiązanie |
|------------------|-------------|
| `Can't connect to MySQL server` | MySQL nie działa lub zły host w `.env` |
| `Access denied for user` | Zły `DB_USER`/`DB_PASS` w `.env` |
| `Unknown database` | Zły `DB_NAME` lub `WORLD_DB_NAME` |
| `ModuleNotFoundError` | `backend/venv` uszkodzony — usuń go i uruchom ponownie `start.sh` |
| `Address already in use` | Port 8000 zajęty przez inny proces |

---

### `npm install` nie działa

```bash
cd frontend
npm install
```

Częste przyczyny:
| Błąd | Rozwiązanie |
|------|-------------|
| `EACCES: permission denied` | Nie uruchamiaj jako root; napraw uprawnienia npm |
| `ENOENT: package.json not found` | Musisz być w folderze `frontend/` |
| `engine "node" is incompatible` | Node < 18; pozwól `start.sh` zaktualizować przez NodeSource |

---

## Błędy bazy danych

### "Postać nie znaleziona" mimo że istnieje

**Przyczyna:** Nazwa postaci jest **case-sensitive** i musi dokładnie zgadzać się z bazą danych.

```bash
mysql -u acore -p acore_characters \
  -e "SELECT name FROM characters WHERE name LIKE 'arthas%';"
```

---

### Sloty wyposażenia są puste (postać ładuje się bez ekwipunku)

**Przyczyna 1:** Postać naprawdę nie ma wyposażonych przedmiotów.
```sql
SELECT ci.slot, ii.itemEntry
FROM character_inventory ci
JOIN item_instance ii ON ci.item = ii.guid
WHERE ci.guid = GUID_POSTACI AND ci.bag = 0;
```

**Przyczyna 2:** `WORLD_DB_NAME` jest nieprawidłowy — JOIN do `item_template` nie powiedzie się cicho.
```bash
mysql -u acore -p -e "SHOW DATABASES LIKE '%world%';"
# Zaktualizuj WORLD_DB_NAME w .env
```

---

## Problemy z modelem 3D

### Ostrzeżenie "No extracted character models found" przy starcie

**Rozwiązanie:** Uruchom pipeline ekstrakcji:
```bash
tools/venv/bin/python tools/extract_models.py \
  --data-dir ./Data \
  --output-dir ./frontend/public/models
```

Upewnij się że `Data/` istnieje i zawiera pliki `.MPQ` WoW 3.3.5a.

---

### Przeglądarka modeli pokazuje fallback / error boundary

**Przyczyna 1:** Brak pliku GLB postaci.
```bash
ls frontend/public/models/characters/
# Powinno wyświetlić 20 plików .glb
```

**Przyczyna 2:** WebGL niedostępne w przeglądarce (niektóre VM/headless).

**Przyczyna 3:** Wyjątek podczas konfiguracji sceny Three.js. Otwórz konsolę dewelopera (F12 → Konsola) i poszukaj błędu.

---

### Postać jest szara / brak tekstur

**Przyczyna:** Ładowanie tekstury skóry nie powiodło się.
```bash
curl http://127.0.0.1:8000/api/model-texture/NazwaPostaci
# Powinno zwrócić PNG, nie błąd JSON
```

Jeśli zwraca błąd:
- Sprawdź czy `Data/` zawiera lokalne MPQ (np. `enUS/locale-enUS.MPQ`)
- Sprawdź `logs/backend.log` pod kątem wyjątków Python z `gear_compositor.py`
- Usuń cache i spróbuj ponownie: `rm -rf frontend/public/models/cache/*`

---

### Broń / naramienniki / hełm nie pojawiają się w widoku 3D

**Przyczyna 1:** Model przedmiotu nie istnieje w MPQ (własne/zmodowane przedmioty bez bazowego M2).

**Przyczyna 2:** Błąd w czasie wyodrębniania GLB.
```bash
curl "http://127.0.0.1:8000/api/item-model/DISPLAY_ID"
```

**Przyczyna 3:** Brak danych punktu przyczepu dla tej kombinacji rasy/płci.
```bash
cat frontend/public/models/attachments.json | python3 -m json.tool | grep -A5 "human_male"
```

---

### Włosy widoczne przez hełm

**Przyczyna:** `HelmetGeosetVisData.dbc` nie mógł być załadowany (brak lokalizacyjnego MPQ).

Sprawdź `logs/backend.log` pod kątem błędów gdy wywoływany jest endpoint geosetek.

---

## Problemy z wydajnością

### Pierwsze żądanie tekstury jest bardzo wolne (10–30 sekund)

**Przyczyna:** Archiwa MPQ są otwierane po raz pierwszy. Kolejne żądania są szybkie dzięki trwałej puli.

`start.sh` wywołuje `_warmup_mpq_pool()` przy starcie backendu by wstępnie otworzyć wszystkie archiwa. Jeśli jest wolno, sprawdź czy `Data/` zawiera wszystkie oczekiwane pliki MPQ.

---

## Lokalizacja plików logów

| Plik | Jak podglądać |
|------|---------------|
| `logs/backend.log` | `tail -f logs/backend.log` |
| `logs/frontend.log` | `tail -f logs/frontend.log` |

---

## Resetowanie stanu

### Wyczyść wszystkie wygenerowane cache
```bash
rm -rf frontend/public/models/cache/*
touch  frontend/public/models/cache/.gitkeep
```

### Usuń środowiska Python (wymusza ponowną instalację)
```bash
rm -rf backend/venv tools/venv
./start.sh   # tworzy automatycznie
```

### Usuń node_modules frontendu (wymusza ponowną instalację)
```bash
rm -rf frontend/node_modules
./start.sh   # instaluje automatycznie
```

### Usuń wszystkie wyekstrahowane modele (wymusza ponowną ekstrakcję)
```bash
rm -rf frontend/public/models/characters/
rm  -f frontend/public/models/manifest.json
rm  -f frontend/public/models/attachments.json
# Następnie uruchom ponownie extract_models.py
```

---

## Zgłaszanie błędów

Przy zgłaszaniu błędu dołącz:

1. Wyjście `./start.sh` (pełna sesja terminala)
2. Zawartość `logs/backend.log`
3. Błędy w konsoli przeglądarki (F12 → zakładka Konsola)
4. System operacyjny i dystrybucję (`lsb_release -a`)
5. Wersję Python (`python3 --version`)
6. Wersję Node (`node --version`)
