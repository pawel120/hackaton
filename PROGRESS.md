# Progress log

Wspolny log sesji na tym repo. Kazda nowa sesja/agent dopisuje sekcje na
dole z data, co zrobila i w jakim stanie to zostawila. Nie nadpisuj
cudzych wpisow.

## NASTEPNY KROK (aktualne na 2026-09-25, koniec sesji "replay chwytu + naprawa kalibracji barku")

Ramie odtwarza recznie nagrany chwyt szyszki (`replay_csv.py
demo2_fixed.csv`) bez jazdy "naokolo". Przyczyna wczesniejszych
porazek znaleziona i naprawiona (patrz wpis sesji na dole) - **teza
"ID serw sa zamienione" z poprzedniej sesji byla BLEDNA.**

**Najwazniejsze na start nastepnej sesji (w tej kolejnosci):**
1. `./arm.sh home` - `HOME_POSE` przepisany pod nowa kalibracje (ramie
   zlozone, bark -85 st, lokiec 99 st).
2. **Chwyt z kamera jeszcze NIE trafil** (5 prob, patrz wpis "Chwyt z
   kamera: skan -> podjazd -> replay" na dole). Procedura jest gotowa, brakuje
   dokladnosci podjazdu na slepo i potwierdzenia, gdzie chwytak laduje w bok.
   Nastepna proba: w pauzie (`--pause-at 14.8 --pause 10`) zmierzyc
   suwmiarka, gdzie sa szczeki wzgledem szyszki (przod/tyl, lewo/prawo),
   i z tego poprawic kotwice (17 cm) oraz znak/skale obrotu podstawy.
3. Skalibrowac krok kol: `drive_step.py` jest mocno nieliniowy (nizej).
   Najlepiej zmierzyc kamera kilka krokow 0.1 s na szyszce 0.4-0.6 m.
4. IK (`approach_and_grasp.py`): zera barku/lokcia po nowej kalibracji
   NIE sa sprawdzone wzgledem zer URDF.
5. Internet na Pi (patrz "Jak sie polaczyc") - bez niego `git pull` na Pi
   nie dziala, pliki ida przez `scp`.

**NIE uruchamiac `lerobot calibrate`** - nadpisze recznie poprawiony
offset barku (id2) i zakres znow przejdzie przez zero enkodera. Backup
pliku sprzed poprawki: `~/so101.json.bak-204746` na Pi.

### Jak sie polaczyc z Pi (stan na koniec sesji)

- Kabel ethernet laptop<->Pi (adapter USB-Ethernet w laptopie). Pi ma
  **statyczne IP `192.168.137.5`** (ustawione przez nmcli na
  "Wired connection 1"), laptop `192.168.137.1` (Windows ICS).
- `ssh robot@192.168.137.5` - user `robot`, haslo znasz. `robot.local`
  (mDNS) dziala z git-bash, ale NIE z PowerShell - w PowerShell uzywaj IP.
- Terminale uzytkownika na Windows dzialaja jako konto `slawe`, narzedzia
  Claude jako `pawel` - dlatego klucz SSH dziala u Claude'a, a u ciebie
  pyta o haslo. Nie ruszac ACL `~/.ssh/id_ed25519` (icacls je psulo).
- Pliki z laptopa na Pi: `scp plik.py robot@192.168.137.5:~/hackaton/`
  (w PowerShell na laptopie, NIE w sesji SSH).
- WiFi Pi: NIE dziala (handshake WPA do hotspotu iPhone pada). Profile
  WiFi usuniete. Pi nie ma internetu.

### Jak odpalac (w sesji SSH na Pi)

```bash
cd ~/hackaton && source .venv/bin/activate
./arm.sh status | home | straight | open | close | move shoulder_pan=10
python rs_mjpeg_server.py          # podglad na zywo: http://192.168.137.5:8080/ (Ctrl+C = stop)
python scan_cones.py --json cel.json
python approach_and_grasp.py --no-drive                       # dry-run planu
python approach_and_grasp.py --no-drive --port /dev/robot-arm # NA ZYWO
python drive_step.py --port /dev/robot-drive --speed 150 --duration 0.05   # jeden krok kolami
python auto_collect.py --drive-port /dev/robot-drive --arm-port /dev/robot-arm --dry-run
python record_demo.py --seconds 25 --out demo.csv   # nagranie recznego ruchu (torque off)
python replay_demo.py --port /dev/robot-arm [--dry-run]
```
Kamera na wylacznosc: zatrzymaj `rs_mjpeg_server.py` przed skanem.
Porty: `/dev/robot-arm` (ramie), `/dev/robot-drive` (Xiao), udev dziala.

## Poprzedni NASTEPNY KROK (sesja "szyszki: detekcja + dystans", czesciowo nieaktualny)

Cel ogolny: pick-and-place dowolnych, nieoznaczonych obiektow z podlogi
ramieniem SO-101, z kamera D415 na platformie robota, docelowo wszystko
na Raspberry Pi 5 (8 GB) zamiast Windows PC.

Stan:
- Ramie: skalibrowane (serwa), sterowanie dziala fizycznie
  (`arm_control.py`: status/move/home/straight/open/close/gong/dance).
- **Wizja: DZIALA i jest zmierzona.** `detect_floor_objects.py` +
  `scan_cones.py` wykrywaja szyszki po glebi i podaja dystans w ukladzie
  robota (do przodu / w bok / kat). Na torze: 5 szyszek, rozrzut
  0.0-1.4 mm przy 15-20 klatkach. Issue #4 zamkniete przez PR #5.
  `detect_object.py` (HSV) zostal, ale do szyszek nie nadaje sie -
  brazu w obrazie nie ma, patrz pulapki.
- **Dojazd i chwyt: kod gotowy, ZERO testow na sprzecie.**
  `drive_to_target.py` (PR #9) i `approach_and_grasp.py` (PR #10) czytaja
  `cel.json` z wizji. Oba maja dry-run jako domyslny i odmawiaja ruchu
  bez jawnego portu. Ani ramie, ani platforma nie byly podlaczone przy
  ich pisaniu.
- Kalibracja kamera->ramie: nadal tylko PLAN (Claude Doc
  https://claude.ai/code/artifact/44f74190-82ad-4315-a878-07329119a2a7).
  `approach_and_grasp.py` uzywa OSZACOWANIA z montazu i mowi o tym przy
  kazdym uruchomieniu.

Najwazniejsze dalej (w tej kolejnosci):
1. **Zmierzyc stale jazdy**: `python drive_to_target.py --calibrate`,
   zmierzyc miarka przejazd i obrot, wpisac do `drive_calibration.json`
   i ustawic `"measured": true`. Dopoki tego nie ma, skrypt nie pojedzie
   do celu. Spodziewany blad dojazdu po kalibracji: **5-8 cm**.
2. **Sprawdzic znaki i offsety przegubow lerobota** przed PIERWSZYM
   ruchem ramienia z planu (`arm_control.py status` w pozie z wypisu,
   poprawic `arm_camera_transform.json`). Przy zlym znaku plan czyta sie
   bez zarzutu i wysyla ramie w druga strone.
3. **Zmierzyc, ile chwytak siega przed obiektyw kamery** i ustawic na tej
   podstawie `--standoff` - ta sama liczba w `drive_to_target.py` i
   `approach_and_grasp.py`, inaczej plan chwytu opisuje inne miejsce niz
   to, gdzie stanie platforma. Teraz w obu jest 0.12 m (placeholder).
4. Kalibracja kamera->baza (Kabsch) - po niej chwyt przestaje byc
   przyblizeniem.
5. Pi 5: instalacja stosu, build `pyrealsense2` ze zrodel.

Rozwazyc (propozycja z sesji dojazdu, nie decyzja): **drugi skan po
obrocie, przed jazda**. Na 0.5 m kamera jeszcze widzi, wiec korekta kata
jest darmowa i zamyka petle tam, gdzie blad open-loop jest najwiekszy.

Pytania do uzytkownika na starcie nastepnej sesji (nie zgaduj):
- Czy stale kalibracji jazdy zostaly zmierzone? Jaki wyszedl realny blad
  dojazdu na 0.5 m?
- Ile chwytak siega przed obiektyw kamery (do `--standoff`)?
- Czy zespol zatwierdzil plan kalibracji kamera->ramie? Komentarze?
- Czy ramie SO-101 stoi na tej samej platformie co kamera, i w jakiej
  odleglosci/orientacji od niej (do transformaty)?
- Czy wchodzimy w odlozone przypadki: inne obiekty na torze (liscie,
  patyki), detekcja w trakcie jazdy, zasieg powyzej 1 m?
- Czy wlaczac filtry glebi (`--filters`)? Poprawiaja pokrycie, ale w
  polowie przebiegow gubily najblizsza szyszke (patrz pulapki) - zostaly
  domyslnie wylaczone, decyzja do rewizji przy innych obiektach.
- Czy jest ramie leader SO-101 (teleop / nagrywanie demonstracji)?
- Czy robimy plan B z uczeniem (ACT) - jest GPU do treningu?
- Pi 5: jaka rola (centralny kontroler wszystkiego czy tylko
  kamera+ramie)? Czy ma juz system/siec/zdalny dostep? Czy repo jest na
  nim sklonowane? Jak podsystemy maja sie komunikowac (jeden proces vs
  serwisy po sieci)?

## Sprzet

- **Robot-hoverboard**: 2x silnik hoverboardu, sterownik H-bridge (PWM+DIR)
  na `LEFT_PWM_PIN/LEFT_DIR_PIN/RIGHT_PWM_PIN/RIGHT_DIR_PIN` (D0-D3),
  Seeed Xiao RP2040 jako kontroler, USB-serial do PC (Windows, COM9 -
  numer portu moze sie zmienic po replugu).
- **Kamera**: Intel RealSense D415, USB.
- **Ramie**: SO-101 (TheRobotStudio/Hugging Face lerobot), serwa Feetech
  STS3215, URDF w `so101_urdf/so101_new_calib.urdf`. Kontroler przez
  adapter USB CH343 (VID:PID 1A86:55D3) - na tym PC **COM10**. Kalibracja
  serw zapisana poza repo:
  `~/.cache/huggingface/lerobot/calibration/robots/so_follower/so101.json`
  (id ramienia `so101`).
- Kamera D415: serial 105422060821, firmware 5.17.0.10. Montaz docelowy:
  platforma robota, 12 cm nad ziemia.
- Platforma obliczeniowa: Raspberry Pi 5 8 GB. Jetson Nano P3450 odrzucony
  (patrz pulapki).
- **Nowosc (2026-09-25)**: doszlo Raspberry Pi 5 - plan polaczenia
  ramienia, kamery i robota-auta w jeden spojny system (prawdopodobnie
  Pi 5 jako centralny kontroler zamiast/obok Windows PC).

## Struktura repo

- `web_control.py` + `frontend.html` - panel webowy do sterowania
  robotem-hoverboardem (WASD, tryb "osemka", tryb "pokrycie"/lawnmower,
  nagrywanie i odtwarzanie sekwencji ruchow). Serwer: HTTP :8000,
  WebSocket :8765. Odpalenie: `python web_control.py`.
- `xiao_send_pwm.ino` - firmware na Xiao RP2040, protokol
  `a<speed> b<steer>\n` po serialu, watchdog 500ms, flagi `SWAP_LR` /
  `INVERT_DIR` do korekty montazu (patrz sekcja nizej).
- `keyboard_control.py`, `makarena.py`, `figure_eight.py` - starsze,
  samodzielne skrypty terminalowe (przed powstaniem panelu webowego);
  panel webowy jest teraz glownym sposobem sterowania.
- `recordings/*.json` - zapisane sekwencje ruchow z panelu webowego.
- `arm_control.py` - sterowanie ramieniem SO-101 przez lerobot.
  CLI: `python arm_control.py calibrate|status|home|straight|move
  joint=val ...|open|close|gong|dance`. Modul do importu: `make_arm()`,
  `read_joint_positions()`, `move_to()`, `go_home()`.
- `detect_object.py` - detekcja obiektu przez RealSense + deprojekcja
  do wspolrzednych 3D. Szuka po KOLORZE (prog HSV) - do szyszek sie nie
  nadaje, patrz pulapki. `--white-balance` / `--exposure` zamrazaja
  obraz, zeby progi dobrane raz trafialy nastepnego dnia.
- `detect_floor_objects.py` - detekcja DOWOLNYCH obiektow po GLEBI:
  plaszczyzna ziemi (RANSAC), co nad nia wystaje, bramka wymiarowa.
  Zwraca pozycje w ukladzie robota: do przodu / w bok / kat. Preset
  `--target szyszka` nastrojony na zmierzonych szyszkach.
  `--mode depth|color|both`, `--laser-power`, `--open-kernel`.
  Do importu: `FloorObjectDetector`, `detect_objects(frames)`.
- `scan_cones.py` - skan na POSTOJU: mediana z N klatek + rozrzut w mm,
  zapis celu do `cel.json` (ignorowany przez gita, to artefakt).
- `drive_to_target.py` + `drive_calibration.json` - dojazd platformy do
  celu z `cel.json`. Obrot w miejscu, potem jazda prosto. Odmawia jazdy
  na niezmierzonej kalibracji; `--calibrate` robi przejazd wzorcowy.
- `approach_and_grasp.py` + `arm_camera_transform.json` - cel z
  `cel.json` na katy przegubow (ikpy + URDF), szesc krokow chwytu.
  `--dry-run` domyslny.
- `sample_colors.py` - mierzy HSV celu i tla, do dobrania progow koloru
  pod aktualne swiatlo zamiast zgadywania.
- `test_detect_gates.py`, `test_drive_plan.py`, `test_grasp_plan.py` -
  testy bez sprzetu, zwykly python (bez pytest): `python <plik>`.
- `so101_urdf/` - model URDF ramienia (do IK, np. przez `ikpy`).
- `bag_to_rtabmap.py` - nagranie RealSense (`.db3`/`.bag`) na zestaw RGB-D
  dla RTAB-Map: `rgb/*.jpg`, `depth/*.png` (16-bit mm, zarejestrowana do
  koloru), `calib/rs_color.yaml`, `stamps.txt`. `--probe` wypisuje sama
  kalibracje z bagu, `--resume` dokancza przerwany eksport. Issue #7.
- `render_map_preview.py` - podglad chmury `.ply` z RTAB-Map bez open3d:
  poziomuje mape do podlogi (RANSAC), widok z gory kolorowany wysokoscia
  + widok z ukosa.
- `constraints.txt` - pin `numpy==2.5.3` dla pip; `lerobot` na Python
  3.14 probuje przebudowac numpy ze zrodla i pada (brak wheela + za
  stary GCC w systemie) - instalowac z `--no-deps` i doinstalowywac
  brakujace moduly recznie, albo `-c constraints.txt --only-binary=:all:`.

## Wazne pulapki / lessons learned

- **Dwa mnozace sie suwaki predkosci** (LIMIT PREDKOSCI x predkosc
  trybu auto) potrafia zejsc do wartosci za niskiej zeby fizycznie
  ruszyc silniki (martwa strefa PWM). Przy "robot nic nie robi" zawsze
  sprawdz realny `pwm_speed`/`pwm_steer`, nie tylko czy komenda leci.
- **Sterowanie roznicowe**: `steer` musi byc wyraznie mniejsze niz
  `speed`, inaczej jedno kolo idzie na minus i robot wiruje w miejscu
  zamiast jechac lukiem.
- **Robot montowany "do gory nogami"** wzgledem oryginalnego zalozenia
  wymaga `SWAP_LR=true` i `INVERT_DIR=true` w firmware (zamiana L/R +
  odwrocenie kierunku obu silnikow).
- **COM port bywa niestabilny** po zawieszeniu USB CDC (Windows error
  31, "urzadzenie nie dziala") - zwykle pomaga fizyczny replug kabla,
  programowy disable/enable urzadzenia wymaga uprawnien admina.
- **Nie rob ciezkiego re-renderu calego DOM co kazdy tick WebSocketa**
  (bylo 30ms) - realne klikniecia myszka/palcem w taki element sie
  gubia, mimo ze automatyzacja (precyzyjny klik) dziala bez zarzutu.
  Rob diff/porownanie i przebudowuj tylko gdy dane faktycznie sie
  zmienily.
- Trzymaj `state.playback_name`/podobne pola trybu w spojnosci przy
  KAZDEJ zmianie trybu (`set_mode`), nie tylko przy naturalnym
  zakonczeniu - inaczej UI pokazuje duchy poprzedniego stanu.
- **lerobot 0.6.1: nie ma modulu `so101_follower`.** SO-100/101 scalone
  w `SOFollower`; import:
  `from lerobot.robots.so_follower.so_follower import SO101Follower` i
  `from lerobot.robots.so_follower.config_so_follower import SO101FollowerConfig`.
- **Brakujace zaleznosci lerobot (instalacja `--no-deps`)**, w tej
  kolejnosci wychodzily: `huggingface_hub`, `feetech-servo-sdk` (tylko
  sdist - BEZ `--only-binary=:all:`, inaczej "No matching distribution"),
  `deepdiff` -> `cachebox` (jest wheel cp314). Zawsze z `-c constraints.txt`.
- **Ramie niewidoczne jako COM** = kabel USB kontrolera niepodlaczony albo
  brak zasilania serw. Porty Bluetooth COM3/5/7/8 to nie ramie.
- **"There is no status packet!" na magistrali Feetech przy szybkich
  petlach ruchu.** Przyczyna: `max_relative_target` w configu sprawia, ze
  KAZDY `send_action` robi dodatkowy `sync_read` Present_Position - przy
  komendach co 0.25 s zapycha to bus. `sync_write` nie czeka na
  odpowiedz, wiec blad wychodzi dopiero pozniej (np. w `disconnect`),
  co myli przy diagnozie. Rozwiazanie w petlach: wlasne ograniczenie
  kroku w Pythonie + `arm.config.max_relative_target = None` na czas
  petli (tak robi `dance()`/`gong()`).
- **Gwaltowne losowe ruchy = ochrona przeciazeniowa STS3215**, serwa
  przestaja odpowiadac. Pomaga tylko odlaczenie i ponowne podlaczenie
  USB/zasilania kontrolera. Duze zakresy - tylko z malym krokiem na tick.
- **Zero stopni w lerobot != zero w URDF (prawdopodobnie).** lerobot
  liczy `deg = (raw - (range_min+range_max)/2) * 360/4095`, czyli 0 st to
  srodek zakresu nagranego przy kalibracji serw, a nie poza zerowa URDF.
  Przed FK/IK trzeba zmierzyc offset i znak kazdego przegubu (plan
  kalibracji, krok 1). Po `arm_control.py calibrate` katy sie zmieniaja.
- **Jetson Nano P3450 nie nadaje sie**: max JetPack 4.6 = Ubuntu 18.04 +
  Python 3.6, a lerobot wymaga Pythona 3.10+. Wybrane Raspberry Pi 5.
- **Kamera 12 cm nad ziemia**: D415 ma martwa strefe glebi - wg pamieci
  ok. 45 cm przy 1280x720, ok. 30 cm przy 640x480 (NIE zmierzone). Obiekty
  blizej kamery nie dostana XYZ. Sprawdzic przed ustaleniem zasiegu
  chwytania.
- **Bibliotek pod Python 3.14 Windows** (sprawdzone `pip download
  --only-binary`): sa `mujoco`, `roboticstoolbox-python`, `open3d 0.20`,
  `ultralytics`, `torch`; NIE MA `pin` (pinocchio, wiec wbudowane w lerobot
  `RobotKinematics`/placo nie dziala), `pybullet`, `pyroki`.
- **`opencv-python` + `opencv-python-headless` zainstalowane razem** =
  `cv2.imshow` pada (`The function is not implemented. Rebuild the
  library with Windows, GTK+ 2.x or Cocoa support`), bo headless
  nadpisuje binaria GUI w tym samym namespace `cv2`. Fix: odinstalowac
  oba i postawic od nowa tylko `opencv-python` (lerobot ciagnie
  `opencv-python-headless` jako zaleznosc - konflikt nawracajacy przy
  `pip install lerobot`, sprawdzac po kazdym takim instalu).
- **D415 znika z `rs.context().query_devices()` po nieczystym zamknieciu
  procesu** (crash przed `pipeline.stop()`, albo proces zabity przez
  `taskkill`) - Windows/librealsense zostawia uchwyt USB w zlym stanie.
  Objaw: `RuntimeError: No device connected` albo `HResult 0x800703e3`
  przy `pipeline.start()`, mimo ze kamera fizycznie podlaczona. Fix:
  sprawdzic `tasklist | grep python` i dobic wiszace `python.exe`
  (zombie trzymaja handle nawet gdy skrypt "juz wyszedl" wg statusu
  procesu-wrappera); jesli to nie pomoze - fizyczny replug USB. Zawsze
  zamykac stream przez `finally: pipeline.stop()`, nigdy Ctrl+C na
  golo/kill -9.
- **Martwa strefa D415 - ZMIERZONA, 640x480: 0.27 m.** Wczesniejszy wpis
  mowil "wg pamieci ok. 30 cm, NIE zmierzone" - teraz jest pomiar: ziemia
  jest mierzona od 0.27 m (dolne wiersze kadru) do ~1.1 m przy kamerze
  poziomo 10 cm nad podlozem. To jest powod, dla ktorego pozycje celu
  trzeba **zapamietac z dystansu i dojechac z pamieci** - na dystansie
  chwytania szyszki juz nie widac.
- **Lewa piata kadru nie ma glebi.** Pokrycie wg kolumn: 0-64 px -> 9.8%,
  64-128 px -> 3.8%, srodek -> 25-34%. Prawy obiektyw nie widzi tego, co
  lewy lapie przy swojej lewej krawedzi, wiec stereo nie ma czego
  dopasowac. Podbicie lasera tego NIE naprawia (9.8% -> 4.4%) - brakuje
  drugiego punktu widzenia, nie swiatla. Nie celowac w obiekt lewa
  krawedzia kadru.
- **Niskie pokrycie glebia przy ziemi to GEOMETRIA, nie ciemnosc.**
  Najpierw wyszlo mi, ze zmrok psuje glebie (87% -> 31%) - to byl blad
  pomiaru: porownywalem srodkowe kolumny calej wysokosci kadru z samym
  dolnym pasem, a ten przy kamerze 10 cm nad ziemia patrzy na podloze
  blizej niz 0.3 m, czyli w martwa strefe. Rzetelny pomiar, wiersz po
  wierszu: 78.7% przy medianie 0.39 m, 74.6% przy 0.33 m, 47.2% przy
  0.27 m, **2.4% nizej**. W srodkowych kolumnach lacznie 71.3%.
  Rozstrzygajace: `gain` sensora glebi stoi na **16 przy zakresie
  16-248**, czyli auto-ekspozycja zeszla na absolutne minimum
  wzmocnienia - sensor ma nadmiar swiatla, nie niedobor. **Nie trzeba
  czekac na dzien.** Projektor IR domyslnie 150 z 360; podbicie pomaga
  (31.0% -> 35.8% na murawie), ale to nie jest to, co ogranicza.
- **Filtry glebi poprawiaja pokrycie i pogarszaja detekcje.** Mierzone
  parami na tych samych klatkach (zeby dryf sceny sie zniosl): filtr
  przestrzenny + czasowy daja 22.30% -> 24.44% pokrycia w pasie
  0.3-1.0 m, poprawa w 30 klatkach na 30 - ten efekt jest pewny. Ale
  liczba wykrytych szyszek na tym nie zyskuje: ta sama nieruchoma scena,
  po cztery skany, bez filtrow 5 szyszek w 4/4 przebiegach, z filtrami
  spadek do 4 w 2/4 - i zawsze gubiona byla NAJBLIZSZA (0.372 m).
  Wygladzanie zjada male obiekty. **Wiecej pikseli glebi nie znaczy
  wiecej wykrytych obiektow.** `hole_filling_filter` odpada z definicji
  - on nie uzupelnia dziur pomiarami, tylko zmysla glebie z sasiadow, a
  detekcja decyduje "obiekt czy nie" dokladnie na tych danych.
- **Otwarcie morfologiczne jadrem 5x5 zjada male obiekty.** Ta sama
  szyszka mierzy 2.2 cm wysokosci przy progu 0.6 cm i 1.0 cm przy progu
  0.8 cm - nie dlatego, ze zmierzono ja inaczej, tylko dlatego, ze z
  cienszego paska erozja zostawia sam dol. Przy celach 20-50 px jadro 3x3
  jest bezpieczniejsze. Objaw skrajny: klaster w ogole nie powstaje, wiec
  liczniki odrzucen pokazuja zera i "nie ma czego tlumaczyc".
- **Piksele bez glebi deprojektuja sie do (0,0,0)**, czyli do pozornej
  odleglosci rownej offsetowi plaszczyzny. Domkniecie morfologiczne
  zalepia nimi dziury w obiekcie. Geometrie (centroid, wysokosc,
  szerokosc) liczyc WYLACZNIE z pikseli faktycznie nad plaszczyzna,
  inaczej wysokosci wychodza absurdalne (61 cm przy limicie 40 cm), a
  szerokosc chwytu skacze miedzy 14 a 44 cm na nieruchomej scenie.
- **Offset dopasowanej plaszczyzny to zmierzona wysokosc kamery** -
  porownanie go z wysokoscia montazu jest darmowym testem, czy RANSAC
  zlapal ZIEMIE, a nie sciane albo blat. Wylapalo przestawiona kamere
  dwa razy w jednej sesji. Bez tego wszystkie dystanse licza sie od zlej
  plaszczyzny i wygladaja wiarygodnie.
- **Kolor: w kadrze nie ma zadnego brazu.** Zmierzone HSV (OpenCV, 0-179)
  na szyszkach i murawie o zmierzchu: murawa H~90 (cyjan), szyszki H~148
  (fiolet), ogony rozkladow zachodza na siebie. Rozdziela je JASNOSC:
  szyszki V~94, murawa V~152. Prog na jasnosc dziala, ale jest kruchy -
  slonce albo cien go przesuwa. Przed strojeniem progow HSV zamrozic
  balans bieli i ekspozycje (`detect_object.py --white-balance
  --exposure`), inaczej progi dobrane dzis nie trafia jutro.
- **Laptop z portami USB 2.0 Type-A cofa D415 do USB 2.1** i obcina tryby
  (848x480 tylko 10/6 Hz, koloru w tej rozdzielczosci nie ma wcale).
  To nie jest wina kabla - na MSI Modern 14 B10MW oba porty Type-A sa
  fizycznie 2.0, USB 3 jest tylko na Type-C. 640x480@30 dziala i daje
  realnie 18-22 fps, co do skanu na postoju w zupelnosci wystarcza.
- **Bag z D415 ma zepsute ekstrinsyki depth->color** (obrot
  `[1,0,0,0,0,0,0,0,0]`, `get_depth_scale()` z playbacku = 0.0), wiec
  `rs.align()` na playbacku zwraca PUSTA glebie (0.00% pikseli). Prawdziwe
  wartosci sa w topicach bagu (`Color_0/tf/ref_0`: kolor 14.99 mm w bok od
  glebi); `bag_to_rtabmap.py` rejestruje glebie sam. Wiadomosci w `.db3` sa
  spakowane zstd (magic `28 b5 2f fd`) - do czytania sqlite wprost trzeba
  `pip install zstandard`.
- **Playback z `set_real_time(False)` oddaje te sama klatke koloru z nowa
  glebia** - w nagraniu 20260925_190138 bylo tak w 714 z 2611 par
  (rozsynchronizowane pary). Pomijac, gdy `color.get_frame_number()` sie nie
  zmienil. Timeout `try_wait_for_frames` to tez NIE koniec pliku (przy
  zajetym dysku staje na sekundy) - pytac `playback.current_status()`.
- **RTAB-Map win64 (0.23.8) pada na starcie z 0xC0000135** (brak DLL, bez
  komunikatu): dolaczony `kinect20.dll` chce VC++ 2012 (`msvcr110.dll`,
  `msvcp110.dll`). Wystarczy wrzucic 64-bitowe wersje do `bin/` (na tym
  laptopie skopiowane z `Microsoft Office\root\vfs\System`).
- **`Odom/ResetCountdown 0` (domyslne) = po pierwszym zgubieniu odometria
  juz nie wraca** i reszta nagrania nie trafia do mapy (u nas od 22 s z 98).
  Z `1` kazde zgubienie to nowa sesja, a sesje skleja tylko loop closure -
  wiec nagranie reczne musi wracac w juz widziane miejsca.

## Log sesji

### 2026-09-25 - sesja Claude (hoverboard control panel)

- Setup od zera: `makarena.py` (gamepad) -> `keyboard_control.py`
  (WASD, bo brak pada) -> `web_control.py` + `frontend.html` (pelny
  panel webowy, bo terminal byl niewygodny).
- Napisany `xiao_send_pwm.ino` od zera (generyczny H-bridge PWM+DIR,
  roznicowy mix speed+steer, watchdog).
- Dodane tryby auto: "osemka" (figure-eight) i "pokrycie"
  (boustrophedon/lawnmower - jedzie rzad, obraca sie ~180 st w miejscu w
  dwoch krokach, jedzie rzad wstecz, powtarza).
- Dodany modul nagrywania/odtwarzania sekwencji ruchow (zapis do
  `recordings/*.json`, przetrwa restart serwera).
- Wszystkie parametry (predkosci, czasy, sila skretu) dostrajalne na
  zywo suwakami w przegladarce, bez edycji kodu.
- Naprawione po drodze: skalowanie limitu predkosci nie obejmowalo
  steer w manualu; race condition przy broadcastcie do wielu klientow;
  DOM re-render 30x/s gubil klikniecia na liscie nagran;
  `playback_name` nie czyscil sie przy zmianie trybu.
- Repo GitHub utworzone (`pawel120/hackaton`, prywatne), inne sesje
  dorzucily rownolegle `detect_object.py` i rozbudowany
  `arm_control.py` - scalone w jednym branchu `master`.
- Stan na koniec sesji: panel webowy dziala end-to-end (potwierdzone
  fizycznym ruchem robota), COM9 bywa niestabilny po odlaczeniu USB.
- **Nie zrobione / do zrobienia**: integracja ramie+kamera+auto w
  jeden system (wlasnie doszlo Raspberry Pi 5 do tego celu), IK dla
  SO-101 (ikpy + URDF, niesprawdzone konca), `lerobot` install na
  Python 3.14 wymaga obejscia (patrz `constraints.txt`).

### 2026-09-25 - sesja Claude (ramie SO-101 + kamera, planowanie pick-and-place)

- Dokonczona instalacja lerobot na Python 3.14 (doinstalowane
  `huggingface_hub`, `feetech-servo-sdk`, `deepdiff`, `cachebox`); import
  `SO101Follower` dziala (nowa sciezka, patrz pulapki).
- Wykryte: D415 przez `pyrealsense2` OK; ramie na COM10 (CH343).
- Pobrany URDF SO-101 z TheRobotStudio/SO-ARM100 do
  `so101_urdf/so101_new_calib.urdf`; `ikpy` go laduje (5 przegubow +
  `gripper_frame_joint` jako koncowka, chwytak poza lancuchem IK).
- Napisany `arm_control.py` (CLI + funkcje do importu). Uzytkownik zrobil
  kalibracje serw, ruch potwierdzony fizycznie (`move shoulder_pan=20`
  -> odczyt 19.38 st). `HOME_POSE` = poza zaraz po kalibracji.
- Dodane komendy demo: `straight` (wszystko 0 st, chwytak otwarty),
  `gong` (powolny zamach + szybkie uderzenie jednym przegubem),
  `dance` (losowe ruchy ~90% zakresu, maly krok). Po drodze naprawione
  zapychanie magistrali (patrz pulapki); retry odczytu pozycji,
  `disconnect` nie wywala programu.
- Decyzje: kamera stala wzgledem ramienia (eye-to-hand), najpierw na
  maszcie, potem ustalone: platforma robota 12 cm nad ziemia. Obiekty do
  podnoszenia nieoznaczone -> detekcja po glebi zamiast po kolorze.
  Platforma: Raspberry Pi 5 8 GB zamiast Jetson Nano P3450.
- Research bibliotek (lerobot + ACT/SmolVLA, ikpy vs roboticstoolbox,
  mujoco, open3d, ultralytics; co ma wheele pod py3.14 - patrz pulapki).
  Rekomendacja: klasyczny pipeline (glebia -> kalibracja -> IK) jako
  glowny, ACT (imitation learning) jako plan B.
- GitHub: issue #1 (detekcja + deprojekcja 3D, zrobione przez Tomka w
  PR #2 jako `detect_object.py`), issue #4 (detekcja dowolnych obiektow
  po glebi, open3d, przypisane TomkeMonke).
- Plan kalibracji kamera->ramie (marker ArUco na chwytaku, 15-20 poz,
  Kabsch, cel RMS < 10 mm) jako Claude Doc na 1 strone A4 do
  zatwierdzenia przez zespol (link w "NASTEPNY KROK").
- **Nie zrobione**: weryfikacja zer/kierunkow przegubow lerobot vs URDF,
  FK/IK na prawdziwym ramieniu, marker i skrypt kalibracji kamera->ramie,
  petla pick-and-place, cokolwiek na Pi 5. `dance` na pelnym zakresie
  nie bylo sprawdzone do konca po ostatniej poprawce (ostatnie
  uruchomienie padlo w `go_home` na zgubionym pakiecie - od tego czasu
  jest retry, nieprzetestowany). `gong` i `straight` nieprzetestowane
  fizycznie (brak potwierdzenia od uzytkownika).

### 2026-09-25 - sesja Claude (podglad na zywo RealSense D415)

- Cel: prosty live preview (`rs_preview.py`) color+depth side-by-side
  z `pyrealsense2` + `cv2.imshow`, do wizualnej kontroli co widzi kamera.
  RealSense Viewer (osobna appka Intela) NIE jest zainstalowany i nie
  jest potrzebny - `pyrealsense2` ma librealsense wbudowane.
- Napisany `rs_preview.py`: color+depth align, colormapa JET, FPS co 30
  klatek w konsoli, wyjscie `q`/ESC, `pipeline.stop()` w `finally`.
- Napotkane i naprawione po drodze (patrz pulapki): konflikt
  `opencv-python` / `opencv-python-headless` (reinstall samego
  `opencv-python`); D415 znikajaca z enumeracji USB po zombie procesach
  pythona (`taskkill` wiszacych `python.exe`).
- Potwierdzone: kamera wykrywana (`rs.context().query_devices()` -> 1,
  D415, serial 105422060821), skrypt odpala sie bez wyjatku po
  posprzataniu procesow.
- **Nie zrobione / niepotwierdzone**: uzytkownik nie potwierdzil jeszcze
  wizualnie ze okno faktycznie pokazuje obraz (proces dzialal bez
  crasha, ale brak feedbacku "widze obraz" na koniec sesji) - na
  starcie nastepnej sesji zapytac czy `rs_preview.py` faktycznie
  pokazuje live podglad, czy nadal lapie `No device connected` po
  replugu (jesli tak, sprawdzic Menedzer Urzadzen / port USB, moze hub
  zamiast bezposredniego portu USB3).

### 2026-09-25 - sesja Claude (Raspberry Pi 5: architektura + setup zdalnego sterowania)

- Decyzje: Pi 5 jedzie na robocie, urzadzenia po USB (D415 USB3, ramie
  CH343, Xiao), operator przez WiFi (panel webowy). Bluetooth odrzucony
  jako szkielet systemu (za mala przepustowosc dla kamery, za duze
  opoznienia dla magistrali Feetech). System: Raspberry Pi OS Lite 64-bit
  na pendrivie USB (brak karty SD), venv z `uv` + Python 3.12, bez Dockera
  na start, autostart przez systemd, hotspot WiFi z Pi na demo.
- Poradnik setupu Pi (Claude Doc):
  https://claude.ai/code/artifact/247e71b9-5b39-4ffb-8170-e355db9fd56b
  (instalacja, lerobot, RealSense ze zrodel jesli brak wheela, udev
  `/dev/robot-arm` i `/dev/robot-drive`, systemd, hotspot,
  checklista, diagnostyka). IMU BNO085 bylo w planie, ale odpadlo.
- Kod: porty ze zmiennych `ROBOT_DRIVE_PORT` / `ROBOT_ARM_PORT` (domyslnie
  `COM9` / `COM10`, Windows bez zmian); `web_control.py` nasluchuje na
  `0.0.0.0` (`ROBOT_HOST`); **failsafe operatora**: brak wiadomosci z
  przegladarki przez 0,5 s (albo zero klientow) = natychmiastowy stop,
  tryb manual, koniec nagrywania/odtwarzania. Frontend wysyla ping co
  200 ms i puszcza klawisze przy `visibilitychange`. Nowy
  `requirements-pi.txt` (NIE uzywac `constraints.txt` na Pi).
- Failsafe sprawdzony lokalnie klientem websockets bez Xiao (ping -> jedzie,
  brak pingu -> `failsafe=True`, speed 0, manual). **Nie sprawdzony na
  fizycznym robocie.**
- GitHub: issue #7 (mapowanie ogrodu RealSense/RTAB-Map, odlozone, najpierw
  test na laptopie), issue #8 (zasilanie z akumulatora 12 V, osoba od
  elektroniki; baterie AA 1,5 V nie nadaja sie do zasilania Pi).
- Stan na koniec: pendrive Kingston DataTraveler 3.0 64 GB gotowy do
  wgrania systemu Imagerem. Na Pi nic jeszcze nie jest zainstalowane.
- Pulapka: przed failsafe'em zerwanie WiFi zostawialo robota jadacego z
  ostatnia komenda (watchdog Xiao chroni tylko lacze Pi-Xiao, nie
  operator-Pi). Tryby auto tez jechaly bez operatora.

### 2026-09-25 - sesja Claude (Tomek: wykrywanie szyszek po glebi + dystans, dojazd, plan chwytu)

Zamkniecie issue #4 i zbudowanie calego lancucha od kamery do katow
przegubow. Cztery PR-y z forka `TomkeMonke/hackaton` (brak uprawnien do
pushu na `pawel120/hackaton`): **#5** wizja, **#9** platforma, **#10**
ramie, **#11** ten wpis.

**Zrobione:**
- `detect_floor_objects.py` - detekcja DOWOLNYCH obiektow po glebi:
  RANSAC plaszczyzny ziemi (+ douczenie SVD na inlierach), maska tego co
  nad nia wystaje, `cv2.connectedComponentsWithStats` zamiast DBSCAN.
  **Swiadomie bez `open3d`**: glebia z D415 jest ZORGANIZOWANA (to obraz,
  sasiedztwo pikseli juz jest sasiedztwem w przestrzeni), wiec
  etykietowanie spojnych obszarow kosztuje ulamek ms, a DBSCAN po ~300
  tys. luznych punktow setki ms na klatke. Zmierzone **22.2 fps** end to
  end. Zero nowych zaleznosci.
- **Preset `szyszka`** - bramka wymiarowa nastrojona na ZMIERZONYCH
  szyszkach na waszej murawie (nie na wymiarach z ksiazki): 0.5-6 cm
  szerokosci, 2-10 cm dlugosci, 0.8-9 cm nad ziemia, wypelnienie >= 0.4.
  Kolorem sie ich nie wylowi - patrz pulapki.
- **Wyniki w ukladzie ROBOTA, nie kamery**: `forward_m`, `lateral_m`,
  `ground_distance_m`, `bearing_deg`, wyprowadzone z dopasowanej
  plaszczyzny, wiec krzywo przykrecony uchwyt kompensuje sie sam.
- `scan_cones.py` - skan na POSTOJU: mediana z N klatek + rozrzut w mm.
  Zapisuje `cel.json`. Na torze: 5 szyszek, kazda widziana w 15/15
  klatkach, **rozrzut 0.0-1.4 mm**.
- `drive_to_target.py` + `approach_and_grasp.py` - dojazd i plan chwytu,
  oba czytaja `cel.json`. Szczegoly w #9 i #10.
- Testy bez sprzetu: `test_detect_gates.py`, `test_drive_plan.py`,
  `test_grasp_plan.py` - razem 28, zwykly python, bez pytest.

**Decyzje:**
- **Postoj-skan-zapamietaj-jedz**, nie ciagle sledzenie. Wymusza to
  martwa strefa 0.27 m (patrz pulapki) - przy chwytaniu szyszki nie widac.
- Zasieg skanu **0.3-1.0 m** (ustalony z zespolem). Zmierzone: na 1.06 m
  rozrzut to nadal ~1 mm, wiec podniesienie do 1.2-1.5 m jest bezpieczne.
- Detekcja po GLEBI jako podstawowa, kolor jako opcja (`--mode
  depth|color|both`). Uzasadnienie w pulapkach.
- Wykrycia migoczace sa odrzucane: skan zglasza tylko cele widziane w
  >=60% klatek. Dlatego podglad na zywo pokazuje wiecej niz skan.

**NIE dokonczone / swiadomie odlozone:**
- **Nic nie sprawdzone na sprzecie poza kamera.** Ani ramie, ani
  platforma nie byly podlaczone (zero portow COM na tej maszynie).
  Dojazd i chwyt sa przetestowane wylacznie w dry-run.
- **Kalibracja kamera->baza ramienia** - `approach_and_grasp.py` uzywa
  OSZACOWANIA z montazu. To wasz osobny task (plan w Claude Doc).
- **Stale kalibracji jazdy niezmierzone** - `drive_to_target.py`
  ODMAWIA jazdy, dopoki ktos ich nie zmierzy przez `--calibrate`.
- **Znaki/offsety przegubow lerobota niesprawdzone** - przy zlym znaku
  plan czyta sie bez zarzutu i wysyla ramie w druga strone.
- Odlozone na zyczenie zespolu: inne obiekty na torze (liscie, patyki),
  detekcja w trakcie jazdy, zasieg powyzej 1 m.
- Szyszka przy lewej krawedzi kadru nie jest wykrywana - patrz pulapki,
  to ograniczenie stereo, nie progow.

### 2026-09-25 - sesja Claude (Pi 5: pierwsze uruchomienie calosci + proby chwytu)

**Stos na Pi (venv `.venv`, Python 3.12) - co i jak zainstalowane:**
- `torch` CPU-only z `--index-url https://download.pytorch.org/whl/cpu`
  (zwykly `torch` z PyPI na aarch64 ciagnie ~2 GB paczek CUDA i pada na
  timeoucie - Pi nie ma GPU NVIDIA).
- `lerobot==0.6.1` z `--no-deps`, potem recznie: `draccus mergedeep
  typing_inspect mypy_extensions tqdm huggingface_hub feetech-servo-sdk
  deepdiff cachebox orderly-set flit_core`. Czesc offline: `pip download`
  na Windows (`--platform manylinux2014_aarch64 --python-version 312
  --implementation cp --abi cp312 --only-binary=:all:` dla binarnych,
  sdist dla czystego Pythona), `scp` na Pi, `uv pip install --no-deps
  --no-build-isolation <plik>`.
- `pyrealsense2` - jest gotowy wheel arm64, budowa ze zrodel NIEPOTRZEBNA.
- `ikpy`, `opencv-python-headless`, `pyserial`, `websockets`, `scipy`.

**Nowe pliki:** `arm.sh` (skrot do `arm_control.py` na Pi),
`rs_mjpeg_server.py` (podglad kamery w przegladarce, Pi jest headless),
`rs_snapshot.py`, `drive_step.py` (krok kolami surowym protokolem Xiao,
omija `drive_to_target.py`), `auto_collect.py` (petla skan->krok->skan->
chwyt), `record_demo.py` / `replay_demo.py` / `demo.csv` (nagranie i
odtworzenie recznego chwytu).

**Zmiany:** nowa kalibracja serw; `HOME_POSE` = pozycja spoczynkowa po
tej kalibracji (ta sama w `approach_and_grasp.START_POSE_DEG`);
`approach_and_grasp.execute_plan` wysyla bezposrednie komendy
(`max_relative_target=None`, bez interpolacji, do 3 powtorek na krok).

**ZAMIANA ID SERW - BLEDNA DIAGNOZA (sprostowane w nastepnej sesji):**
uznalismy, ze id=2 to lokiec, a id=3 bark, i zamienilismy wpisy
`shoulder_lift`/`elbow_flex` w pliku kalibracji na Pi. lerobot ignoruje
jednak pole `id` z pliku (nazwy->ID sa na sztywno w `so_follower.py`),
wiec zamienily sie tylko offsety/zakresy miedzy przegubami - stad dalej
"zly kierunek". Patrz wpis "Replay chwytu + naprawa kalibracji barku".

**Nie zrobione:** chwyt po poprawce ID; potwierdzenie wzrokowe zamiany;
kalibracja kamera->ramie; internet na Pi; `teleop_mirror.py` (nie z tej
sesji) - niezacommitowany, lezy lokalnie.

**Pulapki z tej sesji:**
- **Nie wyciagac pendrive'a z dzialajacego Pi** - to dysk systemowy;
  SSH umiera ("kex_exchange_identification"), siec jeszcze odpowiada.
- **Pi 5 + D415 na slabym zasilaniu** znika z sieci; na powerbanku dziala.
- **Siec `hacker-bloc` ma tylko IPv6**, GitHub tylko IPv4 -> ani `git
  pull`, ani ICS dla Pi. Hotspot telefonu daje IPv4.
- **`pkill -f nazwa` przez SSH zabija sam siebie**, gdy nazwa jest w
  tresci komendy (exit 255). Uzyj `fuser -k 8080/tcp` albo PID.
- **Interpolowane ruchy (`move_to` steps>1) zapychaja magistrale**
  ("There is no status packet!") przy duzych katach - bezposrednie
  `send_action` z `max_relative_target=None` + powtorki sa niezawodne.
- ~~Ostrzezenia "clamped" z katami zmieniajacymi znak przy +-180 st to
  zawijanie reprezentacji, nie zly kierunek.~~ BLAD: to byl objaw zakresu
  barku przechodzacego przez zero enkodera (patrz nastepna sesja).
- **Kazde `connect()` na chwile wylacza torque** (`configure()`) - ramie
  moze opasc pod grawitacja miedzy wywolaniami. Rob sekwencje w jednym
  polaczeniu.
- **`scan_cones.py` bez szyszki nadpisuje `cel.json` pusta lista** -
  zapisz dobry skan zanim podjedziesz w martwa strefe.
- **`cel.json` pole `angle_deg` to obrot chwytaka**, kierunek do celu to
  `bearing_deg`.
- **`drive_to_target.py` na Pi nie dziala**: wymaga pakietu `makarena`
  spoza repo (sciezka `C:\Users\Modern 14\makarena`) i odmawia jazdy
  bez zmierzonej kalibracji. Zamiast niego `drive_step.py`.

## 2026-09-25 - Replay chwytu + naprawa kalibracji barku

**Co bylo zle:** kazda proba (home, replay_demo, IK) jechala barkiem w
zla strone. Dwie przyczyny naraz:
1. **lerobot adresuje serwa po nazwie ze sztywnej listy**
   (`lerobot/robots/so_follower/so_follower.py`: `shoulder_lift`=id2,
   `elbow_flex`=id3). Pole `"id"` w `so101.json` jest IGNOROWANE. "Zamiana
   ID" z poprzedniej sesji zamienila tylko offsety/zakresy -> kazdy z dwoch
   przegubow byl normalizowany zakresem drugiego. Nie naprawiac mapowania
   przez edycje JSON-a.
2. **Fizyczny zakres id2 (shoulder_lift) przechodzil przez zero enkodera**
   (Present 4095->0). Serwo w trybie pozycji nie przejdzie przez 0, wiec
   do celu po drugiej stronie jechalo "naokolo", w podloge. Widac to w
   nagraniu: opadajacy bark -82 -> -151 -> **+139** -> 128.

**Naprawa (bez recznej kalibracji, policzone z nagrania `demo2.csv`):**
`fix_shoulder_offset.py` - id2: `Homing_Offset` 1977 (== -2119, przesuniecie
+1418 tickow), limity 1006..3089 (srodek ~2047, bez przejscia przez zero);
id3: przywrocone rejestry sprzed sesji (1159, 1168..3423). Zapisane w EEPROM
serw i w `so101.json` na Pi. Tworzy tez `demo2_fixed.csv` (nagranie
przeliczone do nowej kalibracji).

**Nowe pliki:** `replay_csv.py` (odtwarza cala trajektorie z CSV klatka po
klatce w tempie nagrania - male kroki, bez interpolacji miedzy dalekimi
punktami), `fix_shoulder_offset.py`, `demo2.csv` / `demo2_fixed.csv`.
`HOME_POSE` / `START_POSE_DEG` = pierwsza klatka `demo2_fixed.csv`.
`replay_demo.py` + `demo.csv` oznaczone jako nieaktualne.

**Wynik:** `replay_csv.py demo2_fixed.csv --start 9.5 --end 23` przeszedl
cala trajektorie, koniec w pozycji z nagrania (+-1 st), bez bledow magistrali.

**Pulapki:**
- `record_demo.py` najpierw wysyla home - przy zlej kalibracji home nie
  dojezdza i nagranie startuje z innej pozy (tak bylo z `demo2.csv`,
  pierwsze ~4 s to opadanie ramienia; replay od `--start 9.5`).
- Przed zmiana rejestrow: `bus.disable_torque()` (zdejmuje tez `Lock`),
  inaczej zapis EEPROM nie wejdzie.
- `Homing_Offset` na Feetech ma zakres +-2047 - wieksze przesuniecia licz
  modulo 4096.

## 2026-09-25 - Chwyt z kamera: skan -> podjazd -> replay (nieudany, 5 prob)

**Pomysl:** bez IK. Jedyny pewny chwyt to nagranie `demo2_fixed.csv`
(klatka chwytu t=14.8 s: pan -13.6, bark 86.3, lokiec -3.6, nadgarstek
53.8, chwytak otwarty 45). Kamera mierzy szyszke, robot podjezdza tak,
zeby szyszka znalazla sie w punkcie chwytu, a roznice w bok nadrabia
obrot podstawy (`replay_csv.py --pan-offset`).

**Ustalenia (zmierzone):**
- **Punkt zamkniecia szczek jest 17 cm przed kamera** (suwmiarka,
  uzytkownik). Kamera widzi glebie dopiero od ~0.31 m, wiec szyszka w
  chwili chwytu jest ZAWSZE w martwej strefie - ostatni odcinek jedzie
  sie na slepo. Punktu chwytu nie da sie tez zobaczyc "na zywo": przy
  pozie chwytu ramie zaslania kamere (przedramie ~0.31 m przed obiektywem).
- **Szyszke widac na RGB, zanim zlapie ja glebia** (np. na ~0.3 m jest
  wyraznie w kadrze, a detektor glebi nic nie zglasza). Rozwiazanie
  uzytkownika: cofac, az glebia ja zmierzy, potem podjechac.
- **Krok kol `drive_step.py --speed 150` jest nieliniowy:** 0.05 s (jeden
  tick 80 ms) ~ 2.9 cm do przodu; 0.1 s ~ 12.5 cm (jeden pomiar!); do tylu
  0.05 s dawalo od 0.4 cm do kilku cm. Przy jezdzie lekko znosi w bok
  (raz 1.8 cm na jednym kroku).
- `scan_cones.py` lapie tez buty/fotel - w petlach filtr `forward < 0.8 m
  i |lateral| < 0.15 m`.

**Model obrotu podstawy (niezweryfikowany):** `pan = atan(lateral /
0.25 m)` (17 cm od kamery + ~8 cm kamera->os podstawy), ujemny pan = w
lewo; `--pan-offset = pan - (-13.6)`.

**Proby (wszystkie: chwytak wrocil pusty, odczyt ~2):**
| # | szyszka przed chwytem | pan | co widzial uzytkownik |
|---|---|---|---|
| 1 | 0.322 m, 1.9 cm L (bez podjazdu) | -9.9 | zahaczyl, przeciagnal |
| 2 | 0.306 m, 0.9 cm L (bez podjazdu) | -5.4 | chwytak zamykal sie PRZED szyszka |
| 3 | 0.306 m, 0.9 cm L (bez podjazdu) | -11.4 | j.w. |
| 4 | 0.310 m -> 5x0.05 s (~14.5 cm) | -2.7 | brak informacji |
| 5 | 0.542 -> 0.417 (zmierz.) -> 2x0.1 s na slepo | 0.0 | brak informacji |

Proby 1-3 byly oparte na zlej kotwicy (0.30 m, zgadnieta ze zdjecia);
dopiero pomiar suwmiarka dal 17 cm.

**Zmiany w kodzie:** `replay_csv.py` ma `--pause-at/--pause` (zatrzymanie
w wybranej klatce z trzymanym torque) i `--pan-offset` (obrot calego
ruchu w bok).

## 2026-09-25 - Mapa RTAB-Map z nagrania pokoju (issue #7, sesja Claude na laptopie)

**Wejscie:** `D:\HACKATHON\20260925_190138.db3` (4.7 GB) - rosbag2 z
RealSense D415, 1280x720 @30, 98.4 s, nagrane z reki (losowe chodzenie
po sali, ~0.9 m nad podloga). Bez IMU i bez odometrii kol.

**Wynik:** `D:\HACKATHON\20260925_190138_rtabmap\wynik\` -
`mapa_rtabmap.db`, `chmura_punktow.ply` (820 tys. pkt, voxel 1 cm),
`trajektoria.txt`, `podglad.png`. W jednej spojnej mapie jest **50 z 93
wezlow (54% nagrania)** - poczatek i koniec. Srodek (wezly 779-1648) to 4
osobne kawalki bez wizualnego pokrycia z reszta; `detectMoreLoopClosures`
sprawdzil wszystkie pary i nic nie znalazl. Przyczyna w nagraniu: dziury
1.2-1.6 s bez klatek (t = 62, 74, 85 s), szybkie obroty przy bluszczu, ta
czesc sali obejrzana raz. Na podgladzie widac podwojne sciany - resztkowe
niedopasowanie miedzy sklejonymi sesjami.

**Pipeline (bez ROS, bez GUI):** `bag_to_rtabmap.py` -> 1897 par RGB-D ->
`rtabmap-dataRecorder` (ini ze zrodlem "RGB-D images") -> `rtabmap-reprocess
-odom` -> `rtabmap-detectMoreLoopClosures` -> `rtabmap-export`. Calosc w
`run_rtabmap.cmd` w katalogu wyniku, ~20 min. RTAB-Map portable w
`D:\HACKATHON\tools\bin`.

**Strojenie odometrii (zmierzone):**
| konfiguracja | zgubione klatki | sesje | najwiekszy sklejony kawalek |
|---|---|---|---|
| domyslna (ResetCountdown 0) | od kl. 439 do konca | 1 | ~23% nagrania |
| ResetCountdown 1, MinInliers 12 | 59 | 22 | 2 pozy |
| + CorType 1 (KLT), MaxFeatures 2000 | 13 | 8 | **50/93 wezlow** <- wybrana |
| j.w. + ResetCountdown 15 | 81 | 6 | 37/87 wezlow |

**Nie zrobione:** mesh z tekstura, mapa 2D zajetosci (`rtabmap-export` jej
nie ma - do zrobienia w GUI `RTABMap.exe` -> Export 2D map albo z chmury),
nagranie na robocie zamiast z reki.

**Nastepny krok dla mapowania:** nagrac jeszcze raz, wolno (obroty
szczegolnie), z powrotem do miejsca startu na koncu (loop closure skleja
cala petle) i sprawdzic, czy nagranie nie gubi klatek (zapis na SSD).
Pipeline jest gotowy: `python bag_to_rtabmap.py NOWE.db3`, potem
`run_rtabmap.cmd` z poprawionymi sciezkami w `rtabmap_source.ini`.

