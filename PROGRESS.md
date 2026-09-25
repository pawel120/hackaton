# Progress log

Wspólny log sesji na tym repo. Każda nowa sesja/agent dopisuje sekcję na
dole z datą, co zrobiła i w jakim stanie to zostawiła. Nie nadpisuj
cudzych wpisów.

## NASTĘPNY KROK (aktualne na 2026-09-25, koniec sesji "replay chwytu + naprawa kalibracji barku")

Ramię odtwarza ręcznie nagrany chwyt szyszki (`replay_csv.py
demo2_fixed.csv`) bez jazdy "naokoło". Przyczyna wcześniejszych
porażek znaleziona i naprawiona (patrz wpis sesji na dole) — **teza
"ID serw są zamienione" z poprzedniej sesji była BŁĘDNA.**

**Najważniejsze na start następnej sesji (w tej kolejności):**
1. `./arm.sh home` — `HOME_POSE` przepisany pod nową kalibrację (ramię
   złożone, bark −85°, łokieć 99°). Sprawdzić, że dojeżdża bez szarpania.
2. Chwyt z nagrania: `python replay_csv.py demo2_fixed.csv --port
   /dev/robot-arm --start 9.5 --end 23`. Działa tylko dla tej samej
   pozycji szyszki co przy nagraniu. Nowe nagranie: `record_demo.py`
   (startuje z home), potem `replay_csv.py <plik> --start/--end`.
3. IK (`approach_and_grasp.py`): zera barku/łokcia po nowej kalibracji
   NIE są sprawdzone względem zer URDF — najpierw zweryfikować (np.
   `./arm.sh straight` i porównać z pozą zerową URDF), dopiero potem chwyt.
4. Zmierzyć realnie przejazd na krok (`drive_step.py`) miarką i wpisać do
   `auto_collect.py` (teraz szacunek ~1 m/s przy PWM 150).
5. Internet na Pi (patrz "Jak się połączyć") — bez niego `git pull` na Pi
   nie działa, pliki idą przez `scp`.

**NIE uruchamiać `lerobot calibrate`** — nadpisze ręcznie poprawiony
offset barku (id2) i zakres znów przejdzie przez zero enkodera. Backup
pliku sprzed poprawki: `~/so101.json.bak-204746` na Pi.

### Jak się połączyć z Pi (stan na koniec sesji)

- Kabel ethernet laptop↔Pi (adapter USB-Ethernet w laptopie). Pi ma
  **statyczne IP `192.168.137.5`** (ustawione przez nmcli na
  "Wired connection 1"), laptop `192.168.137.1` (Windows ICS).
- `ssh robot@192.168.137.5` — user `robot`, hasło znasz. `robot.local`
  (mDNS) działa z git-bash, ale NIE z PowerShell — w PowerShell używaj IP.
- Terminale użytkownika na Windows działają jako konto `slawe`, narzędzia
  Claude jako `pawel` — dlatego klucz SSH działa u Claude'a, a u ciebie
  pyta o hasło. Nie ruszać ACL `~/.ssh/id_ed25519` (icacls je psuło).
- Pliki z laptopa na Pi: `scp plik.py robot@192.168.137.5:~/hackaton/`
  (w PowerShell na laptopie, NIE w sesji SSH).
- WiFi Pi: NIE działa (handshake WPA do hotspotu iPhone pada). Profile
  WiFi usunięte. Pi nie ma internetu.

### Jak odpalać (w sesji SSH na Pi)

```bash
cd ~/hackaton && source .venv/bin/activate
./arm.sh status | home | straight | open | close | move shoulder_pan=10
python rs_mjpeg_server.py          # podgląd na żywo: http://192.168.137.5:8080/ (Ctrl+C = stop)
python scan_cones.py --json cel.json
python approach_and_grasp.py --no-drive                       # dry-run planu
python approach_and_grasp.py --no-drive --port /dev/robot-arm # NA ŻYWO
python drive_step.py --port /dev/robot-drive --speed 150 --duration 0.05   # jeden krok kołami
python auto_collect.py --drive-port /dev/robot-drive --arm-port /dev/robot-arm --dry-run
python record_demo.py --seconds 25 --out demo.csv   # nagranie ręcznego ruchu (torque off)
python replay_demo.py --port /dev/robot-arm [--dry-run]
```
Kamera na wyłączność: zatrzymaj `rs_mjpeg_server.py` przed skanem.
Porty: `/dev/robot-arm` (ramię), `/dev/robot-drive` (Xiao), udev działa.

## Poprzedni NASTĘPNY KROK (sesja "szyszki: detekcja + dystans", częściowo nieaktualny)

Cel ogólny: pick-and-place dowolnych, nieoznaczonych obiektów z podłogi
ramieniem SO-101, z kamerą D415 na platformie robota, docelowo wszystko
na Raspberry Pi 5 (8 GB) zamiast Windows PC.

Stan:
- Ramię: skalibrowane (serwa), sterowanie działa fizycznie
  (`arm_control.py`: status/move/home/straight/open/close/gong/dance).
- **Wizja: DZIAŁA i jest zmierzona.** `detect_floor_objects.py` +
  `scan_cones.py` wykrywają szyszki po głębi i podają dystans w układzie
  robota (do przodu / w bok / kąt). Na torze: 5 szyszek, rozrzut
  0.0–1.4 mm przy 15–20 klatkach. Issue #4 zamknięte przez PR #5.
  `detect_object.py` (HSV) został, ale do szyszek nie nadaje się —
  brązu w obrazie nie ma, patrz pułapki.
- **Dojazd i chwyt: kod gotowy, ZERO testów na sprzęcie.**
  `drive_to_target.py` (PR #9) i `approach_and_grasp.py` (PR #10) czytają
  `cel.json` z wizji. Oba mają dry-run jako domyślny i odmawiają ruchu
  bez jawnego portu. Ani ramię, ani platforma nie były podłączone przy
  ich pisaniu.
- Kalibracja kamera→ramię: nadal tylko PLAN (Claude Doc
  https://claude.ai/code/artifact/44f74190-82ad-4315-a878-07329119a2a7).
  `approach_and_grasp.py` używa OSZACOWANIA z montażu i mówi o tym przy
  każdym uruchomieniu.

Najważniejsze dalej (w tej kolejności):
1. **Zmierzyć stałe jazdy**: `python drive_to_target.py --calibrate`,
   zmierzyć miarką przejazd i obrót, wpisać do `drive_calibration.json`
   i ustawić `"measured": true`. Dopóki tego nie ma, skrypt nie pojedzie
   do celu. Spodziewany błąd dojazdu po kalibracji: **5–8 cm**.
2. **Sprawdzić znaki i offsety przegubów lerobota** przed PIERWSZYM
   ruchem ramienia z planu (`arm_control.py status` w pozie z wypisu,
   poprawić `arm_camera_transform.json`). Przy złym znaku plan czyta się
   bez zarzutu i wysyła ramię w drugą stronę.
3. **Zmierzyć, ile chwytak sięga przed obiektyw kamery** i ustawić na tej
   podstawie `--standoff` — ta sama liczba w `drive_to_target.py` i
   `approach_and_grasp.py`, inaczej plan chwytu opisuje inne miejsce niż
   to, gdzie stanie platforma. Teraz w obu jest 0.12 m (placeholder).
4. Kalibracja kamera→baza (Kabsch) — po niej chwyt przestaje być
   przybliżeniem.
5. Pi 5: instalacja stosu, build `pyrealsense2` ze źródeł.

Rozważyć (propozycja z sesji dojazdu, nie decyzja): **drugi skan po
obrocie, przed jazdą**. Na 0.5 m kamera jeszcze widzi, więc korekta kąta
jest darmowa i zamyka pętlę tam, gdzie błąd open-loop jest największy.

Pytania do użytkownika na starcie następnej sesji (nie zgaduj):
- Czy stałe kalibracji jazdy zostały zmierzone? Jaki wyszedł realny błąd
  dojazdu na 0.5 m?
- Ile chwytak sięga przed obiektyw kamery (do `--standoff`)?
- Czy zespół zatwierdził plan kalibracji kamera→ramię? Komentarze?
- Czy ramię SO-101 stoi na tej samej platformie co kamera, i w jakiej
  odległości/orientacji od niej (do transformaty)?
- Czy wchodzimy w odłożone przypadki: inne obiekty na torze (liście,
  patyki), detekcja w trakcie jazdy, zasięg powyżej 1 m?
- Czy włączać filtry głębi (`--filters`)? Poprawiają pokrycie, ale w
  połowie przebiegów gubiły najbliższą szyszkę (patrz pułapki) — zostały
  domyślnie wyłączone, decyzja do rewizji przy innych obiektach.
- Czy jest ramię leader SO-101 (teleop / nagrywanie demonstracji)?
- Czy robimy plan B z uczeniem (ACT) — jest GPU do treningu?
- Pi 5: jaka rola (centralny kontroler wszystkiego czy tylko
  kamera+ramię)? Czy ma już system/sieć/zdalny dostęp? Czy repo jest na
  nim sklonowane? Jak podsystemy mają się komunikować (jeden proces vs
  serwisy po sieci)?

## Sprzęt

- **Robot-hoverboard**: 2x silnik hoverboardu, sterownik H-bridge (PWM+DIR)
  na `LEFT_PWM_PIN/LEFT_DIR_PIN/RIGHT_PWM_PIN/RIGHT_DIR_PIN` (D0-D3),
  Seeed Xiao RP2040 jako kontroler, USB-serial do PC (Windows, COM9 —
  numer portu może się zmienić po replugu).
- **Kamera**: Intel RealSense D415, USB.
- **Ramię**: SO-101 (TheRobotStudio/Hugging Face lerobot), serwa Feetech
  STS3215, URDF w `so101_urdf/so101_new_calib.urdf`. Kontroler przez
  adapter USB CH343 (VID:PID 1A86:55D3) — na tym PC **COM10**. Kalibracja
  serw zapisana poza repo:
  `~/.cache/huggingface/lerobot/calibration/robots/so_follower/so101.json`
  (id ramienia `so101`).
- Kamera D415: serial 105422060821, firmware 5.17.0.10. Montaż docelowy:
  platforma robota, 12 cm nad ziemią.
- Platforma obliczeniowa: Raspberry Pi 5 8 GB. Jetson Nano P3450 odrzucony
  (patrz pułapki).
- **Nowość (2026-09-25)**: doszło Raspberry Pi 5 — plan połączenia
  ramienia, kamery i robota-auta w jeden spójny system (prawdopodobnie
  Pi 5 jako centralny kontroler zamiast/obok Windows PC).

## Struktura repo

- `web_control.py` + `frontend.html` — panel webowy do sterowania
  robotem-hoverboardem (WASD, tryb "osemka", tryb "pokrycie"/lawnmower,
  nagrywanie i odtwarzanie sekwencji ruchów). Serwer: HTTP :8000,
  WebSocket :8765. Odpalenie: `python web_control.py`.
- `xiao_send_pwm.ino` — firmware na Xiao RP2040, protokół
  `a<speed> b<steer>\n` po serialu, watchdog 500ms, flagi `SWAP_LR` /
  `INVERT_DIR` do korekty montażu (patrz sekcja niżej).
- `keyboard_control.py`, `makarena.py`, `figure_eight.py` — starsze,
  samodzielne skrypty terminalowe (przed powstaniem panelu webowego);
  panel webowy jest teraz głównym sposobem sterowania.
- `recordings/*.json` — zapisane sekwencje ruchów z panelu webowego.
- `arm_control.py` — sterowanie ramieniem SO-101 przez lerobot.
  CLI: `python arm_control.py calibrate|status|home|straight|move
  joint=val ...|open|close|gong|dance`. Moduł do importu: `make_arm()`,
  `read_joint_positions()`, `move_to()`, `go_home()`.
- `detect_object.py` — detekcja obiektu przez RealSense + deprojekcja
  do współrzędnych 3D. Szuka po KOLORZE (próg HSV) — do szyszek się nie
  nadaje, patrz pułapki. `--white-balance` / `--exposure` zamrażają
  obraz, żeby progi dobrane raz trafiały następnego dnia.
- `detect_floor_objects.py` — detekcja DOWOLNYCH obiektów po GŁĘBI:
  płaszczyzna ziemi (RANSAC), co nad nią wystaje, bramka wymiarowa.
  Zwraca pozycję w układzie robota: do przodu / w bok / kąt. Preset
  `--target szyszka` nastrojony na zmierzonych szyszkach.
  `--mode depth|color|both`, `--laser-power`, `--open-kernel`.
  Do importu: `FloorObjectDetector`, `detect_objects(frames)`.
- `scan_cones.py` — skan na POSTOJU: mediana z N klatek + rozrzut w mm,
  zapis celu do `cel.json` (ignorowany przez gita, to artefakt).
- `drive_to_target.py` + `drive_calibration.json` — dojazd platformy do
  celu z `cel.json`. Obrót w miejscu, potem jazda prosto. Odmawia jazdy
  na niezmierzonej kalibracji; `--calibrate` robi przejazd wzorcowy.
- `approach_and_grasp.py` + `arm_camera_transform.json` — cel z
  `cel.json` na kąty przegubów (ikpy + URDF), sześć kroków chwytu.
  `--dry-run` domyślny.
- `sample_colors.py` — mierzy HSV celu i tła, do dobrania progów koloru
  pod aktualne światło zamiast zgadywania.
- `test_detect_gates.py`, `test_drive_plan.py`, `test_grasp_plan.py` —
  testy bez sprzętu, zwykły python (bez pytest): `python <plik>`.
- `so101_urdf/` — model URDF ramienia (do IK, np. przez `ikpy`).
- `constraints.txt` — pin `numpy==2.5.3` dla pip; `lerobot` na Python
  3.14 próbuje przebudować numpy ze źródła i pada (brak wheela + za
  stary GCC w systemie) — instalować z `--no-deps` i doinstalowywać
  brakujące moduły ręcznie, albo `-c constraints.txt --only-binary=:all:`.

## Ważne pułapki / lessons learned

- **Dwa mnożące się suwaki prędkości** (LIMIT PRĘDKOŚCI × prędkość
  trybu auto) potrafią zejść do wartości za niskiej żeby fizycznie
  ruszyć silniki (martwa strefa PWM). Przy "robot nic nie robi" zawsze
  sprawdź realny `pwm_speed`/`pwm_steer`, nie tylko czy komenda leci.
- **Sterowanie różnicowe**: `steer` musi być wyraźnie mniejsze niż
  `speed`, inaczej jedno koło idzie na minus i robot wiruje w miejscu
  zamiast jechać łukiem.
- **Robot montowany "do góry nogami"** względem oryginalnego założenia
  wymaga `SWAP_LR=true` i `INVERT_DIR=true` w firmware (zamiana L/R +
  odwrócenie kierunku obu silników).
- **COM port bywa niestabilny** po zawieszeniu USB CDC (Windows error
  31, "urządzenie nie działa") — zwykle pomaga fizyczny replug kabla,
  programowy disable/enable urządzenia wymaga uprawnień admina.
- **Nie rób ciężkiego re-renderu całego DOM co każdy tick WebSocketa**
  (było 30ms) — realne kliknięcia myszką/palcem w taki element się
  gubią, mimo że automatyzacja (precyzyjny klik) działa bez zarzutu.
  Rób diff/porównanie i przebudowuj tylko gdy dane faktycznie się
  zmieniły.
- Trzymaj `state.playback_name`/podobne pola trybu w spójności przy
  KAŻDEJ zmianie trybu (`set_mode`), nie tylko przy naturalnym
  zakończeniu — inaczej UI pokazuje duchy poprzedniego stanu.
- **lerobot 0.6.1: nie ma modułu `so101_follower`.** SO-100/101 scalone
  w `SOFollower`; import:
  `from lerobot.robots.so_follower.so_follower import SO101Follower` i
  `from lerobot.robots.so_follower.config_so_follower import SO101FollowerConfig`.
- **Brakujące zależności lerobot (instalacja `--no-deps`)**, w tej
  kolejności wychodziły: `huggingface_hub`, `feetech-servo-sdk` (tylko
  sdist — BEZ `--only-binary=:all:`, inaczej "No matching distribution"),
  `deepdiff` → `cachebox` (jest wheel cp314). Zawsze z `-c constraints.txt`.
- **Ramię niewidoczne jako COM** = kabel USB kontrolera niepodłączony albo
  brak zasilania serw. Porty Bluetooth COM3/5/7/8 to nie ramię.
- **"There is no status packet!" na magistrali Feetech przy szybkich
  pętlach ruchu.** Przyczyna: `max_relative_target` w configu sprawia, że
  KAŻDY `send_action` robi dodatkowy `sync_read` Present_Position — przy
  komendach co 0.25 s zapycha to bus. `sync_write` nie czeka na
  odpowiedź, więc błąd wychodzi dopiero później (np. w `disconnect`),
  co myli przy diagnozie. Rozwiązanie w pętlach: własne ograniczenie
  kroku w Pythonie + `arm.config.max_relative_target = None` na czas
  pętli (tak robi `dance()`/`gong()`).
- **Gwałtowne losowe ruchy = ochrona przeciążeniowa STS3215**, serwa
  przestają odpowiadać. Pomaga tylko odłączenie i ponowne podłączenie
  USB/zasilania kontrolera. Duże zakresy — tylko z małym krokiem na tick.
- **Zero stopni w lerobot ≠ zero w URDF (prawdopodobnie).** lerobot
  liczy `deg = (raw - (range_min+range_max)/2) * 360/4095`, czyli 0° to
  środek zakresu nagranego przy kalibracji serw, a nie poza zerowa URDF.
  Przed FK/IK trzeba zmierzyć offset i znak każdego przegubu (plan
  kalibracji, krok 1). Po `arm_control.py calibrate` kąty się zmieniają.
- **Jetson Nano P3450 nie nadaje się**: max JetPack 4.6 = Ubuntu 18.04 +
  Python 3.6, a lerobot wymaga Pythona 3.10+. Wybrane Raspberry Pi 5.
- **Kamera 12 cm nad ziemią**: D415 ma martwą strefę głębi — wg pamięci
  ok. 45 cm przy 1280×720, ok. 30 cm przy 640×480 (NIE zmierzone). Obiekty
  bliżej kamery nie dostaną XYZ. Sprawdzić przed ustaleniem zasięgu
  chwytania.
- **Bibliotek pod Python 3.14 Windows** (sprawdzone `pip download
  --only-binary`): są `mujoco`, `roboticstoolbox-python`, `open3d 0.20`,
  `ultralytics`, `torch`; NIE MA `pin` (pinocchio, więc wbudowane w lerobot
  `RobotKinematics`/placo nie działa), `pybullet`, `pyroki`.
- **`opencv-python` + `opencv-python-headless` zainstalowane razem** =
  `cv2.imshow` pada (`The function is not implemented. Rebuild the
  library with Windows, GTK+ 2.x or Cocoa support`), bo headless
  nadpisuje binaria GUI w tym samym namespace `cv2`. Fix: odinstalować
  oba i postawić od nowa tylko `opencv-python` (lerobot ciągnie
  `opencv-python-headless` jako zależność — konflikt nawracający przy
  `pip install lerobot`, sprawdzać po każdym takim instalu).
- **D415 znika z `rs.context().query_devices()` po nieczystym zamknięciu
  procesu** (crash przed `pipeline.stop()`, albo proces zabity przez
  `taskkill`) — Windows/librealsense zostawia uchwyt USB w złym stanie.
  Objaw: `RuntimeError: No device connected` albo `HResult 0x800703e3`
  przy `pipeline.start()`, mimo że kamera fizycznie podłączona. Fix:
  sprawdzić `tasklist | grep python` i dobić wiszące `python.exe`
  (zombie trzymają handle nawet gdy skrypt "już wyszedł" wg statusu
  procesu-wrappera); jeśli to nie pomoże — fizyczny replug USB. Zawsze
  zamykać stream przez `finally: pipeline.stop()`, nigdy Ctrl+C na
  goło/kill -9.
- **Martwa strefa D415 — ZMIERZONA, 640×480: 0.27 m.** Wcześniejszy wpis
  mówił "wg pamięci ok. 30 cm, NIE zmierzone" — teraz jest pomiar: ziemia
  jest mierzona od 0.27 m (dolne wiersze kadru) do ~1.1 m przy kamerze
  poziomo 10 cm nad podłożem. To jest powód, dla którego pozycję celu
  trzeba **zapamiętać z dystansu i dojechać z pamięci** — na dystansie
  chwytania szyszki już nie widać.
- **Lewa piąta kadru nie ma głębi.** Pokrycie wg kolumn: 0–64 px → 9.8%,
  64–128 px → 3.8%, środek → 25–34%. Prawy obiektyw nie widzi tego, co
  lewy łapie przy swojej lewej krawędzi, więc stereo nie ma czego
  dopasować. Podbicie lasera tego NIE naprawia (9.8% → 4.4%) — brakuje
  drugiego punktu widzenia, nie światła. Nie celować w obiekt lewą
  krawędzią kadru.
- **Niskie pokrycie głębią przy ziemi to GEOMETRIA, nie ciemność.**
  Najpierw wyszło mi, że zmrok psuje głębię (87% → 31%) — to był błąd
  pomiaru: porównywałem środkowe kolumny całej wysokości kadru z samym
  dolnym pasem, a ten przy kamerze 10 cm nad ziemią patrzy na podłoże
  bliżej niż 0.3 m, czyli w martwą strefę. Rzetelny pomiar, wiersz po
  wierszu: 78.7% przy medianie 0.39 m, 74.6% przy 0.33 m, 47.2% przy
  0.27 m, **2.4% niżej**. W środkowych kolumnach łącznie 71.3%.
  Rozstrzygające: `gain` sensora głębi stoi na **16 przy zakresie
  16–248**, czyli auto-ekspozycja zeszła na absolutne minimum
  wzmocnienia — sensor ma nadmiar światła, nie niedobór. **Nie trzeba
  czekać na dzień.** Projektor IR domyślnie 150 z 360; podbicie pomaga
  (31.0% → 35.8% na murawie), ale to nie jest to, co ogranicza.
- **Filtry głębi poprawiają pokrycie i pogarszają detekcję.** Mierzone
  parami na tych samych klatkach (żeby dryf sceny się zniósł): filtr
  przestrzenny + czasowy dają 22.30% → 24.44% pokrycia w pasie
  0.3–1.0 m, poprawa w 30 klatkach na 30 — ten efekt jest pewny. Ale
  liczba wykrytych szyszek na tym nie zyskuje: ta sama nieruchoma scena,
  po cztery skany, bez filtrów 5 szyszek w 4/4 przebiegach, z filtrami
  spadek do 4 w 2/4 — i zawsze gubiona była NAJBLIŻSZA (0.372 m).
  Wygładzanie zjada małe obiekty. **Więcej pikseli głębi nie znaczy
  więcej wykrytych obiektów.** `hole_filling_filter` odpada z definicji
  — on nie uzupełnia dziur pomiarami, tylko zmyśla głębię z sąsiadów, a
  detekcja decyduje „obiekt czy nie" dokładnie na tych danych.
- **Otwarcie morfologiczne jądrem 5×5 zjada małe obiekty.** Ta sama
  szyszka mierzy 2.2 cm wysokości przy progu 0.6 cm i 1.0 cm przy progu
  0.8 cm — nie dlatego, że zmierzono ją inaczej, tylko dlatego, że z
  cieńszego paska erozja zostawia sam dół. Przy celach 20–50 px jądro 3×3
  jest bezpieczniejsze. Objaw skrajny: klaster w ogóle nie powstaje, więc
  liczniki odrzuceń pokazują zera i "nie ma czego tłumaczyć".
- **Piksele bez głębi deprojektują się do (0,0,0)**, czyli do pozornej
  odległości równej offsetowi płaszczyzny. Domknięcie morfologiczne
  zalepia nimi dziury w obiekcie. Geometrię (centroid, wysokość,
  szerokość) liczyć WYŁĄCZNIE z pikseli faktycznie nad płaszczyzną,
  inaczej wysokości wychodzą absurdalne (61 cm przy limicie 40 cm), a
  szerokość chwytu skacze między 14 a 44 cm na nieruchomej scenie.
- **Offset dopasowanej płaszczyzny to zmierzona wysokość kamery** —
  porównanie go z wysokością montażu jest darmowym testem, czy RANSAC
  złapał ZIEMIĘ, a nie ścianę albo blat. Wyłapało przestawioną kamerę
  dwa razy w jednej sesji. Bez tego wszystkie dystanse liczą się od złej
  płaszczyzny i wyglądają wiarygodnie.
- **Kolor: w kadrze nie ma żadnego brązu.** Zmierzone HSV (OpenCV, 0–179)
  na szyszkach i murawie o zmierzchu: murawa H≈90 (cyjan), szyszki H≈148
  (fiolet), ogony rozkładów zachodzą na siebie. Rozdziela je JASNOŚĆ:
  szyszki V≈94, murawa V≈152. Próg na jasność działa, ale jest kruchy —
  słońce albo cień go przesuwa. Przed strojeniem progów HSV zamrozić
  balans bieli i ekspozycję (`detect_object.py --white-balance
  --exposure`), inaczej progi dobrane dziś nie trafią jutro.
- **Laptop z portami USB 2.0 Type-A cofa D415 do USB 2.1** i obcina tryby
  (848×480 tylko 10/6 Hz, koloru w tej rozdzielczości nie ma wcale).
  To nie jest wina kabla — na MSI Modern 14 B10MW oba porty Type-A są
  fizycznie 2.0, USB 3 jest tylko na Type-C. 640×480@30 działa i daje
  realnie 18–22 fps, co do skanu na postoju w zupełności wystarcza.

## Log sesji

### 2026-09-25 — sesja Claude (hoverboard control panel)

- Setup od zera: `makarena.py` (gamepad) → `keyboard_control.py`
  (WASD, bo brak pada) → `web_control.py` + `frontend.html` (pełny
  panel webowy, bo terminal był niewygodny).
- Napisany `xiao_send_pwm.ino` od zera (generyczny H-bridge PWM+DIR,
  różnicowy mix speed+steer, watchdog).
- Dodane tryby auto: "osemka" (figure-eight) i "pokrycie"
  (boustrophedon/lawnmower — jedzie rząd, obraca się ~180° w miejscu w
  dwóch krokach, jedzie rząd wstecz, powtarza).
- Dodany moduł nagrywania/odtwarzania sekwencji ruchów (zapis do
  `recordings/*.json`, przetrwa restart serwera).
- Wszystkie parametry (prędkości, czasy, siła skrętu) dostrajalne na
  żywo suwakami w przeglądarce, bez edycji kodu.
- Naprawione po drodze: skalowanie limitu prędkości nie obejmowało
  steer w manualu; race condition przy broadcastcie do wielu klientów;
  DOM re-render 30x/s gubił kliknięcia na liście nagrań;
  `playback_name` nie czyścił się przy zmianie trybu.
- Repo GitHub utworzone (`pawel120/hackaton`, prywatne), inne sesje
  dorzuciły równolegle `detect_object.py` i rozbudowany
  `arm_control.py` — scalone w jednym branchu `master`.
- Stan na koniec sesji: panel webowy działa end-to-end (potwierdzone
  fizycznym ruchem robota), COM9 bywa niestabilny po odłączeniu USB.
- **Nie zrobione / do zrobienia**: integracja ramię+kamera+auto w
  jeden system (właśnie doszło Raspberry Pi 5 do tego celu), IK dla
  SO-101 (ikpy + URDF, niesprawdzone końca), `lerobot` install na
  Python 3.14 wymaga obejścia (patrz `constraints.txt`).

### 2026-09-25 — sesja Claude (ramię SO-101 + kamera, planowanie pick-and-place)

- Dokończona instalacja lerobot na Python 3.14 (doinstalowane
  `huggingface_hub`, `feetech-servo-sdk`, `deepdiff`, `cachebox`); import
  `SO101Follower` działa (nowa ścieżka, patrz pułapki).
- Wykryte: D415 przez `pyrealsense2` OK; ramię na COM10 (CH343).
- Pobrany URDF SO-101 z TheRobotStudio/SO-ARM100 do
  `so101_urdf/so101_new_calib.urdf`; `ikpy` go ładuje (5 przegubów +
  `gripper_frame_joint` jako końcówka, chwytak poza łańcuchem IK).
- Napisany `arm_control.py` (CLI + funkcje do importu). Użytkownik zrobił
  kalibrację serw, ruch potwierdzony fizycznie (`move shoulder_pan=20`
  → odczyt 19.38°). `HOME_POSE` = poza zaraz po kalibracji.
- Dodane komendy demo: `straight` (wszystko 0°, chwytak otwarty),
  `gong` (powolny zamach + szybkie uderzenie jednym przegubem),
  `dance` (losowe ruchy ~90% zakresu, mały krok). Po drodze naprawione
  zapychanie magistrali (patrz pułapki); retry odczytu pozycji,
  `disconnect` nie wywala programu.
- Decyzje: kamera stała względem ramienia (eye-to-hand), najpierw na
  maszcie, potem ustalone: platforma robota 12 cm nad ziemią. Obiekty do
  podnoszenia nieoznaczone → detekcja po głębi zamiast po kolorze.
  Platforma: Raspberry Pi 5 8 GB zamiast Jetson Nano P3450.
- Research bibliotek (lerobot + ACT/SmolVLA, ikpy vs roboticstoolbox,
  mujoco, open3d, ultralytics; co ma wheele pod py3.14 — patrz pułapki).
  Rekomendacja: klasyczny pipeline (głębia → kalibracja → IK) jako
  główny, ACT (imitation learning) jako plan B.
- GitHub: issue #1 (detekcja + deprojekcja 3D, zrobione przez Tomka w
  PR #2 jako `detect_object.py`), issue #4 (detekcja dowolnych obiektów
  po głębi, open3d, przypisane TomkeMonke).
- Plan kalibracji kamera→ramię (marker ArUco na chwytaku, 15–20 póz,
  Kabsch, cel RMS < 10 mm) jako Claude Doc na 1 stronę A4 do
  zatwierdzenia przez zespół (link w "NASTĘPNY KROK").
- **Nie zrobione**: weryfikacja zer/kierunków przegubów lerobot vs URDF,
  FK/IK na prawdziwym ramieniu, marker i skrypt kalibracji kamera→ramię,
  pętla pick-and-place, cokolwiek na Pi 5. `dance` na pełnym zakresie
  nie było sprawdzone do końca po ostatniej poprawce (ostatnie
  uruchomienie padło w `go_home` na zgubionym pakiecie — od tego czasu
  jest retry, nieprzetestowany). `gong` i `straight` nieprzetestowane
  fizycznie (brak potwierdzenia od użytkownika).

### 2026-09-25 — sesja Claude (podgląd na żywo RealSense D415)

- Cel: prosty live preview (`rs_preview.py`) color+depth side-by-side
  z `pyrealsense2` + `cv2.imshow`, do wizualnej kontroli co widzi kamera.
  RealSense Viewer (osobna appka Intela) NIE jest zainstalowany i nie
  jest potrzebny — `pyrealsense2` ma librealsense wbudowane.
- Napisany `rs_preview.py`: color+depth align, colormapa JET, FPS co 30
  klatek w konsoli, wyjście `q`/ESC, `pipeline.stop()` w `finally`.
- Napotkane i naprawione po drodze (patrz pułapki): konflikt
  `opencv-python` / `opencv-python-headless` (reinstall samego
  `opencv-python`); D415 znikająca z enumeracji USB po zombie procesach
  pythona (`taskkill` wiszących `python.exe`).
- Potwierdzone: kamera wykrywana (`rs.context().query_devices()` → 1,
  D415, serial 105422060821), skrypt odpala się bez wyjątku po
  posprzątaniu procesów.
- **Nie zrobione / niepotwierdzone**: użytkownik nie potwierdził jeszcze
  wizualnie że okno faktycznie pokazuje obraz (proces działał bez
  crasha, ale brak feedbacku "widzę obraz" na koniec sesji) — na
  starcie następnej sesji zapytać czy `rs_preview.py` faktycznie
  pokazuje live podgląd, czy nadal łapie `No device connected` po
  replugu (jeśli tak, sprawdzić Menedżer Urządzeń / port USB, może hub
  zamiast bezpośredniego portu USB3).

### 2026-09-25 — sesja Claude (Raspberry Pi 5: architektura + setup zdalnego sterowania)

- Decyzje: Pi 5 jedzie na robocie, urządzenia po USB (D415 USB3, ramię
  CH343, Xiao), operator przez WiFi (panel webowy). Bluetooth odrzucony
  jako szkielet systemu (za mała przepustowość dla kamery, za duże
  opóźnienia dla magistrali Feetech). System: Raspberry Pi OS Lite 64-bit
  na pendrivie USB (brak karty SD), venv z `uv` + Python 3.12, bez Dockera
  na start, autostart przez systemd, hotspot WiFi z Pi na demo.
- Poradnik setupu Pi (Claude Doc):
  https://claude.ai/code/artifact/247e71b9-5b39-4ffb-8170-e355db9fd56b
  (instalacja, lerobot, RealSense ze źródeł jeśli brak wheela, udev
  `/dev/robot-arm` i `/dev/robot-drive`, systemd, hotspot,
  checklista, diagnostyka). IMU BNO085 było w planie, ale odpadło.
- Kod: porty ze zmiennych `ROBOT_DRIVE_PORT` / `ROBOT_ARM_PORT` (domyślnie
  `COM9` / `COM10`, Windows bez zmian); `web_control.py` nasłuchuje na
  `0.0.0.0` (`ROBOT_HOST`); **failsafe operatora**: brak wiadomości z
  przeglądarki przez 0,5 s (albo zero klientów) = natychmiastowy stop,
  tryb manual, koniec nagrywania/odtwarzania. Frontend wysyła ping co
  200 ms i puszcza klawisze przy `visibilitychange`. Nowy
  `requirements-pi.txt` (NIE używać `constraints.txt` na Pi).
- Failsafe sprawdzony lokalnie klientem websockets bez Xiao (ping → jedzie,
  brak pingu → `failsafe=True`, speed 0, manual). **Nie sprawdzony na
  fizycznym robocie.**
- GitHub: issue #7 (mapowanie ogrodu RealSense/RTAB-Map, odłożone, najpierw
  test na laptopie), issue #8 (zasilanie z akumulatora 12 V, osoba od
  elektroniki; baterie AA 1,5 V nie nadają się do zasilania Pi).
- Stan na koniec: pendrive Kingston DataTraveler 3.0 64 GB gotowy do
  wgrania systemu Imagerem. Na Pi nic jeszcze nie jest zainstalowane.
- Pułapka: przed failsafe'em zerwanie WiFi zostawiało robota jadącego z
  ostatnią komendą (watchdog Xiao chroni tylko łącze Pi–Xiao, nie
  operator–Pi). Tryby auto też jechały bez operatora.

### 2026-09-25 — sesja Claude (Tomek: wykrywanie szyszek po głębi + dystans, dojazd, plan chwytu)

Zamknięcie issue #4 i zbudowanie całego łańcucha od kamery do katów
przegubów. Cztery PR-y z forka `TomkeMonke/hackaton` (brak uprawnień do
pushu na `pawel120/hackaton`): **#5** wizja, **#9** platforma, **#10**
ramię, **#11** ten wpis.

**Zrobione:**
- `detect_floor_objects.py` — detekcja DOWOLNYCH obiektów po głębi:
  RANSAC płaszczyzny ziemi (+ douczenie SVD na inlierach), maska tego co
  nad nią wystaje, `cv2.connectedComponentsWithStats` zamiast DBSCAN.
  **Świadomie bez `open3d`**: głębia z D415 jest ZORGANIZOWANA (to obraz,
  sąsiedztwo pikseli już jest sąsiedztwem w przestrzeni), więc
  etykietowanie spójnych obszarów kosztuje ułamek ms, a DBSCAN po ~300
  tys. luźnych punktów setki ms na klatkę. Zmierzone **22.2 fps** end to
  end. Zero nowych zależności.
- **Preset `szyszka`** — bramka wymiarowa nastrojona na ZMIERZONYCH
  szyszkach na waszej murawie (nie na wymiarach z książki): 0.5–6 cm
  szerokości, 2–10 cm długości, 0.8–9 cm nad ziemią, wypełnienie ≥ 0.4.
  Kolorem się ich nie wyłowi — patrz pułapki.
- **Wyniki w układzie ROBOTA, nie kamery**: `forward_m`, `lateral_m`,
  `ground_distance_m`, `bearing_deg`, wyprowadzone z dopasowanej
  płaszczyzny, więc krzywo przykręcony uchwyt kompensuje się sam.
- `scan_cones.py` — skan na POSTOJU: mediana z N klatek + rozrzut w mm.
  Zapisuje `cel.json`. Na torze: 5 szyszek, każda widziana w 15/15
  klatkach, **rozrzut 0.0–1.4 mm**.
- `drive_to_target.py` + `approach_and_grasp.py` — dojazd i plan chwytu,
  oba czytają `cel.json`. Szczegóły w #9 i #10.
- Testy bez sprzętu: `test_detect_gates.py`, `test_drive_plan.py`,
  `test_grasp_plan.py` — razem 28, zwykły python, bez pytest.

**Decyzje:**
- **Postój-skan-zapamiętaj-jedź**, nie ciągłe śledzenie. Wymusza to
  martwa strefa 0.27 m (patrz pułapki) — przy chwytaniu szyszki nie widać.
- Zasięg skanu **0.3–1.0 m** (ustalony z zespołem). Zmierzone: na 1.06 m
  rozrzut to nadal ~1 mm, więc podniesienie do 1.2–1.5 m jest bezpieczne.
- Detekcja po GŁĘBI jako podstawowa, kolor jako opcja (`--mode
  depth|color|both`). Uzasadnienie w pułapkach.
- Wykrycia migoczące są odrzucane: skan zgłasza tylko cele widziane w
  ≥60% klatek. Dlatego podgląd na żywo pokazuje więcej niż skan.

**NIE dokończone / świadomie odłożone:**
- **Nic nie sprawdzone na sprzęcie poza kamerą.** Ani ramię, ani
  platforma nie były podłączone (zero portów COM na tej maszynie).
  Dojazd i chwyt są przetestowane wyłącznie w dry-run.
- **Kalibracja kamera→baza ramienia** — `approach_and_grasp.py` używa
  OSZACOWANIA z montażu. To wasz osobny task (plan w Claude Doc).
- **Stałe kalibracji jazdy niezmierzone** — `drive_to_target.py`
  ODMAWIA jazdy, dopóki ktoś ich nie zmierzy przez `--calibrate`.
- **Znaki/offsety przegubów lerobota niesprawdzone** — przy złym znaku
  plan czyta się bez zarzutu i wysyła ramię w drugą stronę.
- Odłożone na życzenie zespołu: inne obiekty na torze (liście, patyki),
  detekcja w trakcie jazdy, zasięg powyżej 1 m.
- Szyszka przy lewej krawędzi kadru nie jest wykrywana — patrz pułapki,
  to ograniczenie stereo, nie progów.

### 2026-09-25 — sesja Claude (Pi 5: pierwsze uruchomienie całości + próby chwytu)

**Stos na Pi (venv `.venv`, Python 3.12) — co i jak zainstalowane:**
- `torch` CPU-only z `--index-url https://download.pytorch.org/whl/cpu`
  (zwykły `torch` z PyPI na aarch64 ciągnie ~2 GB paczek CUDA i pada na
  timeoucie — Pi nie ma GPU NVIDIA).
- `lerobot==0.6.1` z `--no-deps`, potem ręcznie: `draccus mergedeep
  typing_inspect mypy_extensions tqdm huggingface_hub feetech-servo-sdk
  deepdiff cachebox orderly-set flit_core`. Część offline: `pip download`
  na Windows (`--platform manylinux2014_aarch64 --python-version 312
  --implementation cp --abi cp312 --only-binary=:all:` dla binarnych,
  sdist dla czystego Pythona), `scp` na Pi, `uv pip install --no-deps
  --no-build-isolation <plik>`.
- `pyrealsense2` — jest gotowy wheel arm64, budowa ze źródeł NIEPOTRZEBNA.
- `ikpy`, `opencv-python-headless`, `pyserial`, `websockets`, `scipy`.

**Nowe pliki:** `arm.sh` (skrót do `arm_control.py` na Pi),
`rs_mjpeg_server.py` (podgląd kamery w przeglądarce, Pi jest headless),
`rs_snapshot.py`, `drive_step.py` (krok kołami surowym protokołem Xiao,
omija `drive_to_target.py`), `auto_collect.py` (pętla skan→krok→skan→
chwyt), `record_demo.py` / `replay_demo.py` / `demo.csv` (nagranie i
odtworzenie ręcznego chwytu).

**Zmiany:** nowa kalibracja serw; `HOME_POSE` = pozycja spoczynkowa po
tej kalibracji (ta sama w `approach_and_grasp.START_POSE_DEG`);
`approach_and_grasp.execute_plan` wysyła bezpośrednie komendy
(`max_relative_target=None`, bez interpolacji, do 3 powtórek na krok).

**ZAMIANA ID SERW — BŁĘDNA DIAGNOZA (sprostowane w następnej sesji):**
uznaliśmy, że id=2 to łokieć, a id=3 bark, i zamieniliśmy wpisy
`shoulder_lift`/`elbow_flex` w pliku kalibracji na Pi. lerobot ignoruje
jednak pole `id` z pliku (nazwy→ID są na sztywno w `so_follower.py`),
więc zamieniły się tylko offsety/zakresy między przegubami — stąd dalej
"zły kierunek". Patrz wpis "Replay chwytu + naprawa kalibracji barku".

**Nie zrobione:** chwyt po poprawce ID; potwierdzenie wzrokowe zamiany;
kalibracja kamera→ramię; internet na Pi; `teleop_mirror.py` (nie z tej
sesji) — niezacommitowany, leży lokalnie.

**Pułapki z tej sesji:**
- **Nie wyciągać pendrive'a z działającego Pi** — to dysk systemowy;
  SSH umiera ("kex_exchange_identification"), sieć jeszcze odpowiada.
- **Pi 5 + D415 na słabym zasilaniu** znika z sieci; na powerbanku działa.
- **Sieć `hacker-bloc` ma tylko IPv6**, GitHub tylko IPv4 → ani `git
  pull`, ani ICS dla Pi. Hotspot telefonu daje IPv4.
- **`pkill -f nazwa` przez SSH zabija sam siebie**, gdy nazwa jest w
  treści komendy (exit 255). Użyj `fuser -k 8080/tcp` albo PID.
- **Interpolowane ruchy (`move_to` steps>1) zapychają magistralę**
  ("There is no status packet!") przy dużych kątach — bezpośrednie
  `send_action` z `max_relative_target=None` + powtórki są niezawodne.
- ~~Ostrzeżenia "clamped" z kątami zmieniającymi znak przy ±180° to
  zawijanie reprezentacji, nie zły kierunek.~~ BŁĄD: to był objaw zakresu
  barku przechodzącego przez zero enkodera (patrz następna sesja).
- **Każde `connect()` na chwilę wyłącza torque** (`configure()`) — ramię
  może opaść pod grawitacją między wywołaniami. Rób sekwencje w jednym
  połączeniu.
- **`scan_cones.py` bez szyszki nadpisuje `cel.json` pustą listą** —
  zapisz dobry skan zanim podjedziesz w martwą strefę.
- **`cel.json` pole `angle_deg` to obrót chwytaka**, kierunek do celu to
  `bearing_deg`.
- **`drive_to_target.py` na Pi nie działa**: wymaga pakietu `makarena`
  spoza repo (ścieżka `C:\Users\Modern 14\makarena`) i odmawia jazdy
  bez zmierzonej kalibracji. Zamiast niego `drive_step.py`.

## 2026-09-25 — Replay chwytu + naprawa kalibracji barku

**Co było źle:** każda próba (home, replay_demo, IK) jechała barkiem w
złą stronę. Dwie przyczyny naraz:
1. **lerobot adresuje serwa po nazwie ze sztywnej listy**
   (`lerobot/robots/so_follower/so_follower.py`: `shoulder_lift`=id2,
   `elbow_flex`=id3). Pole `"id"` w `so101.json` jest IGNOROWANE. "Zamiana
   ID" z poprzedniej sesji zamieniła tylko offsety/zakresy → każdy z dwóch
   przegubów był normalizowany zakresem drugiego. Nie naprawiać mapowania
   przez edycję JSON-a.
2. **Fizyczny zakres id2 (shoulder_lift) przechodził przez zero enkodera**
   (Present 4095→0). Serwo w trybie pozycji nie przejdzie przez 0, więc
   do celu po drugiej stronie jechało "naokoło", w podłogę. Widać to w
   nagraniu: opadający bark −82 → −151 → **+139** → 128.

**Naprawa (bez ręcznej kalibracji, policzone z nagrania `demo2.csv`):**
`fix_shoulder_offset.py` — id2: `Homing_Offset` 1977 (≡ −2119, przesunięcie
+1418 ticków), limity 1006..3089 (środek ~2047, bez przejścia przez zero);
id3: przywrócone rejestry sprzed sesji (1159, 1168..3423). Zapisane w EEPROM
serw i w `so101.json` na Pi. Tworzy też `demo2_fixed.csv` (nagranie
przeliczone do nowej kalibracji).

**Nowe pliki:** `replay_csv.py` (odtwarza całą trajektorię z CSV klatka po
klatce w tempie nagrania — małe kroki, bez interpolacji między dalekimi
punktami), `fix_shoulder_offset.py`, `demo2.csv` / `demo2_fixed.csv`.
`HOME_POSE` / `START_POSE_DEG` = pierwsza klatka `demo2_fixed.csv`.
`replay_demo.py` + `demo.csv` oznaczone jako nieaktualne.

**Wynik:** `replay_csv.py demo2_fixed.csv --start 9.5 --end 23` przeszedł
całą trajektorię, koniec w pozycji z nagrania (±1°), bez błędów magistrali.

**Pułapki:**
- `record_demo.py` najpierw wysyła home — przy złej kalibracji home nie
  dojeżdża i nagranie startuje z innej pozy (tak było z `demo2.csv`,
  pierwsze ~4 s to opadanie ramienia; replay od `--start 9.5`).
- Przed zmianą rejestrów: `bus.disable_torque()` (zdejmuje też `Lock`),
  inaczej zapis EEPROM nie wejdzie.
- `Homing_Offset` na Feetech ma zakres ±2047 — większe przesunięcia licz
  modulo 4096.

