# Setup

Dwie osobne sciezki: laptop (rozwoj, symulator, testy) i Raspberry Pi 5
(prawdziwy sprzet: kamera + ramie + hoverboard). Traps i wytlumaczenia
"dlaczego tak" - patrz docs/HARDWARE.md.

## Laptop (Windows/Linux/Mac)

Wymagany Python 3.12. Na tym laptopie z Windowsem Python zostal
zainstalowany przez `winget install Python.Python.3.12`, a git przez
Git for Windows (dlatego np. mDNS/`*.local` dziala z git-bash, a nie z
PowerShell - patrz nizej).

```
python -m venv .venv
```

Aktywacja venv:
- PowerShell: `.\.venv\Scripts\Activate.ps1`
- git-bash: `source .venv/Scripts/activate`
- Linux/Mac: `source .venv/bin/activate`

Instalacja zaleznosci (stos `pinecone_bot` - kamera + symulator +
testy, bez sprzetu ramienia/kol):

```
pip install -r requirements-pinecone.txt
```

Testy (60+ testow, bez sprzetu):

```
python -m pytest tests -q
```

Symulator (kamera pinhole + naped roznicowy, podglad w oknie):

```
python -m pinecone_bot.main --sim --show
```

Jesli zamiast `pinecone_bot` pracujesz nad starszym stosem
(`arm_control.py`, IK, detekcja po glebi) - dodatkowo potrzebny
`requirements-arm.txt` (ciagnie `lerobot` + `torch`, ciezkie i wolne):

```
pip install -r requirements-arm.txt -c constraints.txt
```

`constraints.txt` pinuje `numpy==2.5.3` - na Python 3.14 `lerobot` bez
tego probuje przebudowac numpy ze zrodla i pada (brak gotowego kola +
za stary GCC w systemie). Jesli `pip install lerobot` mimo to pada,
instaluj `--no-deps` i doinstaluj brakujace zaleznosci recznie (w
kolejnosci, w jakiej sie ujawniaja): `huggingface_hub`,
`feetech-servo-sdk` (tylko sdist - BEZ `--only-binary=:all:`, inaczej
"No matching distribution"), `deepdiff`, `cachebox`. Zawsze z
`-c constraints.txt`. Po kazdym `pip install lerobot` sprawdz, czy nie
wrocil konflikt `opencv-python` / `opencv-python-headless` (patrz
docs/HARDWARE.md, pulapka 25) - jesli tak, odinstaluj oba i zainstaluj
od nowa tylko `opencv-python`.

## Raspberry Pi 5

### Jak sie polaczyc z Pi

- Kabel ethernet laptop<->Pi (adapter USB-Ethernet w laptopie). Pi ma
  **statyczne IP `192.168.137.5`** (ustawione przez `nmcli` na "Wired
  connection 1"), laptop `192.168.137.1` (Windows ICS - Internet
  Connection Sharing).
- `ssh robot@192.168.137.5` - user `robot`, haslo znasz (nie w tym
  pliku). `robot.local` (mDNS) dziala z git-bash, ale NIE z PowerShell -
  w PowerShell uzywaj IP wprost.
- Pliki z laptopa na Pi: `scp plik.py robot@192.168.137.5:~/hackaton/`
  - **w PowerShell na laptopie, NIE z wnetrza sesji SSH na Pi** (Pi nie
  ma internetu, wiec `scp`/`git pull` z Pi w strone swiata nie zadziala
  - patrz nizej). Dla stosu `pinecone_bot` jest gotowy skrypt
  `deploy/push_to_pi.sh` (kopiuje `pinecone_bot/`, `tools/`, `motions/`,
  `tests/`, `requirements-pinecone.txt` i lokalny `pinecone_config.json`
  jesli istnieje; rsync gdy dostepny, inaczej `scp -r`):

  ```
  PI_HOST=robot@192.168.137.5 bash deploy/push_to_pi.sh
  ```

- **WiFi na Pi NIE dziala** (handshake WPA do hotspotu iPhone pada,
  profile WiFi zostaly usuniete) - Pi nie ma internetu. Stad `git pull`
  na Pi nie dziala - wszystkie pliki ida przez `scp`/`push_to_pi.sh` z
  laptopa.

### Instalacja od zera: `deploy/setup_pi.sh`

Uruchom NA Pi, jako zwykly user (NIE root/sudo), z katalogu glownego
repo:

```
bash deploy/setup_pi.sh
```

Bezpieczny do wielokrotnego uruchomienia - kazdy krok pomija to, co
juz jest zrobione. Robi po kolei:

1. Pakiety systemowe (`apt-get`: git, curl, build-essential, cmake,
   pkg-config, libusb, libssl, libudev, python3-dev, htop, tmux).
2. Dodaje uzytkownika do grupy `dialout` (dostep do portow
   szeregowych) i usuwa `modemmanager`, jesli jest zainstalowany (probuje
   odpytywac komendami AT nowe urzadzenia `ttyACM` i potrafi porwac
   Xiao/ramie).
3. Instaluje `deploy/99-robot.rules` do `/etc/udev/rules.d/` (stabilne
   nazwy `/dev/robot-arm` i `/dev/robot-drive`) plus regulki RealSense z
   repo IntelRealSense/librealsense, `udevadm control --reload-rules` +
   `trigger`.
4. Instaluje `uv` (menedzer Pythona), jesli go jeszcze nie ma.
5. Tworzy venv Python 3.12 (`uv venv --python 3.12 .venv`) i instaluje
   `requirements-pi.txt`. **To najdluzszy krok - `lerobot` ciagnie
   PyTorch, moze potrwac dlugo.** Na koniec odinstalowuje
   `opencv-python` (na Pi, ktore jest headless/bez ekranu, zostaje tylko
   `opencv-python-headless` z `requirements-pi.txt` - inaczej konflikt,
   patrz docs/HARDWARE.md pulapka 25).
6. `pyrealsense2` (bindingi Pythona do RealSense): najpierw probuje
   gotowego kola (`uv pip install pyrealsense2`). Jesli nie ma kola pod
   ta architekture/Pythona, wypisuje instrukcje budowy librealsense ze
   zrodel (patrz sekcja "Kamera RealSense D415" w starszym poradniku
   setupu) i konczy krok bez bledu - reszta stosu dziala bez kamery.
7. Autostart panelu webowego: wypelnia `deploy/robot-web.service`
   (User, WorkingDirectory) i instaluje jako `systemd` unit
   `robot-web.service`, `enable` + `restart`. Uruchamia
   `web_control.py` z portami `ROBOT_DRIVE_PORT=/dev/robot-drive`,
   `ROBOT_ARM_PORT=/dev/robot-arm`. `KillSignal=SIGINT`, zeby przy
   stopie zadzialaly bloki `finally` (stop silnikow, `pipeline.stop()`
   kamery).
8. Na koniec wypisuje adres panelu (`http://<hostname>.local:8000` albo
   po IP), jak podejrzec logi (`journalctl -u robot-web -f`), status
   (`systemctl status robot-web`), zawartosc `/dev/robot-*` i
   ostrzezenie, jesli brakuje pliku kalibracji ramienia (trzeba
   skopiowac z laptopa, patrz docs/HARDWARE.md - kalibracja jest poza
   repo).

**NIE uruchamiac `lerobot calibrate` na Pi** - nadpisze recznie
poprawiony offset barku, patrz docs/HARDWARE.md (pulapka 1).

### Ktory plik requirements czego dotyczy

- `requirements-pi.txt` - GLOWNY plik dla Pi. `lerobot==0.6.1`,
  `pyserial`, `websockets`, `ikpy`, `opencv-python-headless`. Uzywany
  przez `deploy/setup_pi.sh`. NIE uzywac tu `constraints.txt` - jest
  tylko na Windows/Python 3.14 (patrz nizej).
- `requirements-pinecone.txt` - zaleznosci nowego stosu `pinecone_bot/`
  (numpy, opencv-python, pyserial, pytest). Wystarcza do pracy na
  laptopie (symulator + testy, bez sprzetu). Czesc dla Pi (kamera,
  ramie) jest opisana w komentarzu w tym pliku jako "juz w
  `requirements-pi.txt`, nie duplikowac tutaj".
- `requirements-arm.txt` - starszy stos sterowania ramieniem
  (`arm_control.py` + IK na URDF z `so101_urdf/`): `lerobot>=0.6.1`,
  `ikpy>=4.1.0`, plus bazowy `requirements.txt`. Instalowac z
  `-c constraints.txt` - ciagnie `torch`, ciezka i dluga instalacja.
  Potrzebny tylko na maszynie, ktora faktycznie steruje ramieniem.
- `constraints.txt` - pin `numpy==2.5.3`, tylko dla Windows/Python 3.14
  (patrz wyzej, sekcja Laptop).

### `arm.sh` - skrot do sterowania ramieniem na Pi

Na Pi jest skrypt `arm.sh` opakowujacy `arm_control.py` (patrz jego
CLI): `./arm.sh status | home | straight | open | close | move
joint=wartosc ...`.

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

Kamera na wylacznosc: zatrzymaj `rs_mjpeg_server.py` przed skanem
(jeden proces na raz trzyma urzadzenie D415).

Poradnik krok-po-kroku dla stosu `pinecone_bot` (kolejnosc narzedzi
`tools/snap_frames.py` -> `calibrate_hsv.py` -> `record_waypoints.py`
-> `calibrate_target.py` -> `base_test.py`, potem `--dry-run` / `--real`)
jest w `PINECONE_README.md` w korzeniu repo.

## Sprawdzenie, ze wszystko dziala

Na Pi, po `deploy/setup_pi.sh` i podlaczeniu sprzetu:

```
./arm.sh status
python rs_preview.py            # albo: python rs_mjpeg_server.py
python drive_step.py --port /dev/robot-drive --speed 120 --duration 0.05
python -m pytest tests -q
```

`./arm.sh status` powinno pokazac aktualne katy przegubow bez bledu
magistrali. `rs_preview.py`/`rs_mjpeg_server.py` powinno pokazac zywy
obraz koloru i glebi. `drive_step.py` z podanymi parametrami powinno
dac wyczuwalny, pojedynczy krok kolami do przodu (patrz
docs/HARDWARE.md pulapka 8 - krok jest nieliniowy, nie oczekuj
konkretnej odleglosci bez wlasnej kalibracji). `pytest` powinno przejsc
bez sprzetu (testy sa czysto programowe).
