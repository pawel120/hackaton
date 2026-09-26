# PANEL - jak odpalic panel jazdy i ramienia

Krok po kroku: laptop -> siec -> SSH na Pi -> dwa serwery -> przegladarka.
Sprawdzone na sprzecie 2026-09-26. Szczegoly instalacji Pi: `docs/SETUP.md`,
pulapki sprzetu: `docs/HARDWARE.md`.

## Jak to jest zbudowane

Na Pi chodza DWA osobne procesy, kazdy w swoim terminalu SSH:

| Proces | Co robi | Porty |
|---|---|---|
| `web_control.py` | panel jazdy (WASD), serwuje `frontend.html` | 8000 (HTTP), 8765 (WebSocket) |
| `tools/arm_web.py` | serwer ramienia SO-101 | 8010 |

Strona `http://<IP_PI>:8000` pokazuje jazde i sekcje ramienia. Sekcja ramienia
gada z `arm_web.py` na :8010, wiec bez drugiego procesu widac komunikat
"Serwer ramienia nie dziala". Dwa procesy celowo: blad magistrali serw nie
zatrzymuje jazdy.

Autostartu nie ma: `systemctl status robot-web` mowi "could not be found"
(krok 7 `deploy/setup_pi.sh` nie byl robiony). Oba serwery odpalamy recznie.

## 0. Zanim zaczniesz

- Wpisz sie w pole "Robot" w `docs/STATUS.md`. Jedna osoba przy robocie naraz.
- Pi zasilaj z zasilacza, nie z powerbanka. Na powerbanku odpada pendrive, z ktorego
  Pi startuje (objaw: SSH konczy sie na `kex_exchange_identification`, panel daje 404).
- Robot na podlodze z miejscem dookola, ktos trzyma wylacznik.
- Kamera siedzi na ramieniu: HOME ramienia moze w nia uderzyc (patrz krok 4).

## 1. Siec: laptop i Pi w jednej sieci

Wybierz jedna droge.

**A) Hotspot iPhone (bez kabla, robot moze jezdzic)**

1. iPhone: Ustawienia -> Osobisty hotspot, siec "iPhone pawel".
   **Maximize Compatibility = ON**, inaczej Pi sie nie podlaczy (potrzebuje WPA2, 2.4 GHz).
   Trzymaj ten ekran otwarty, iPhone wylacza pusty hotspot.
2. Laptop do tego samego hotspotu.
3. Wlacz Pi, odczekaj ok. 60 s. Na ekranie hotspotu powinny byc 2 polaczenia.
4. IP Pi (DHCP, 2026-09-26 bylo `172.20.10.4`). Jesli nie odpowiada, skan w git-bash:

   ```bash
   for i in $(seq 1 14); do ping -n 1 -w 300 172.20.10.$i | grep -q TTL && echo 172.20.10.$i; done
   ```

   `.1` to iPhone, jeden z pozostalych to laptop (`ipconfig`), reszta to Pi.

Hotspot ma skoki opoznien (do 240 ms). Panel jazdy wtedy na chwile staje (failsafe),
po failsafe trzeba wcisnac klawisz od nowa. 2026-09-26 przy duzym opoznieniu robot
wjechal w ramie: przy lagach puszczaj klawisze i uzyj STOP.

**B) Kabel ethernet (stabilnie, ale robot na smyczy)**

1. Kabel laptop <-> Pi (adapter USB-Ethernet), na Windows wlaczony ICS
   (laptop dostaje `192.168.137.1`).
2. Pi ma stale IP **`192.168.137.5`**.

Obie drogi moga dzialac naraz. Ponizej `<IP_PI>` = `172.20.10.4` albo `192.168.137.5`.

`robot.local` dziala tylko z git-bash i nie zawsze (potrafi dac adres IPv6).
Pewniej podawac IP wprost.

## 2. Terminal 1: SSH i panel jazdy

Na laptopie (git-bash albo PowerShell):

```bash
ssh robot@<IP_PI>
```

User `robot`, haslo znasz. Na Pi:

```bash
cd ~/hackaton && source .venv/bin/activate
ROBOT_DRIVE_PORT=/dev/robot-drive ROBOT_ARM_PORT=/dev/robot-arm python web_control.py
```

Dziala, gdy wypisze:

```
Frontend: http://localhost:8000 (listening on 0.0.0.0)
WebSocket control on ws://localhost:8765
Drive serial port: /dev/robot-drive
```

**Nie wciskaj nic wiecej i nie zamykaj tego terminala.** Ctrl+C = panel wylaczony.
(Linia "Arm panel ... http://127.0.0.1:8010" to tylko informacja, ignoruj adres 127.0.0.1.)

## 3. Terminal 2: SSH i serwer ramienia

Nowe okno terminala na laptopie:

```bash
ssh robot@<IP_PI>
```

Na Pi:

```bash
cd ~/hackaton && source .venv/bin/activate
python tools/arm_web.py --port /dev/robot-arm --no-home
```

- `--no-home`: ramie stoi tam, gdzie jest; dziala jog przegubow i chwytak,
  HOME i ruchy z `motions/` wylaczone. **Uzywaj tego, dopoki kamera siedzi na ramieniu.**
- Bez `--no-home` ramie **zaraz po starcie samo jedzie do HOME**. Tylko gdy nic
  nie stoi mu na drodze i nikt nie trzyma rak przy ramieniu.
- Panel blokuje jog przegubu, ktory stoi poza zakresem kalibracji (np. `shoulder_lift`).
- NIGDY `lerobot calibrate` (nadpisze poprawiony offset barku, `docs/HARDWARE.md`).

## 4. Przegladarka na laptopie

Adres wpisujesz w pasku adresu przegladarki (Chrome/Edge) na laptopie,
**nie w terminalu Pi**:

- `http://<IP_PI>:8000` - jazda + ramie w jednym miejscu (glowny STOP zatrzymuje oba)
- `http://<IP_PI>:8010` - sam panel ramienia

Jazda tylko przy wcisnietym klawiszu (WASD).

## 5. Konczenie pracy

1. Robot stoi, klawisze puszczone.
2. Ramie w bezpiecznej pozycji (HOME albo recznie podparte).
3. Terminal 2 (`arm_web.py`): Ctrl+C. **Torque serw sie wylacza i ramie opada.**
4. Terminal 1 (`web_control.py`): Ctrl+C, silniki staja.
5. Zwolnij pole "Robot" w `docs/STATUS.md`.

Tip: zeby serwery przezyly zerwanie SSH (hotspot), odpal je w `tmux`
(jest na Pi): `tmux new -s panel`, odlaczenie Ctrl+B potem D, powrot `tmux attach -t panel`.
Bez tmux zerwane SSH zabija proces.

## Gdy cos nie dziala

| Objaw | Przyczyna | Co zrobic |
|---|---|---|
| `bash: $'\302\226...ping': command not found` | przy wklejaniu z czatu doszly niewidoczne znaki | wpisz komende recznie |
| `-bash: http://...: No such file or directory` | adres wpisany w terminal Pi | adres idzie do przegladarki na laptopie |
| strona :8000 sie nie laduje | `web_control.py` nie chodzi (Ctrl+C) albo zle IP | krok 2; `ping <IP_PI>` z laptopa |
| "Serwer ramienia nie dziala (na Pi: python tools/arm_web.py)" | nie chodzi `arm_web.py` | krok 3 w drugim terminalu |
| `Address already in use` | stary proces trzyma port | `pgrep -af "web_control\|arm_web"`, potem `kill <PID>` (nie `pkill -f`: przez SSH potrafi zabic wlasna sesje) |
| Pi nie ma w sieci po wlaczeniu | hotspot bez Maximize Compatibility / zasilanie | krok 1; wylacz i wlacz hotspot; zasilacz zamiast powerbanka; kabel (droga B) |
| SSH: `kex_exchange_identification` | odpadl pendrive (zasilanie) | wylacz i wlacz zasilanie Pi |
| robot nie jedzie, `/dev/robot-drive` jest | Xiao zawieszony na USB (zapis 512 ms, watchdog tnie silniki) | wyjmij USB Xiao na ok. 5 s (RESET nie pomaga) |
| robot co chwile staje | opoznienie hotspotu -> failsafe | normalne; wcisnij klawisz od nowa albo kabel |
| `Full found motor list: {}` | skan serw z zlym portem/baudem | `./arm.sh status` pokaze, czy ramie odpowiada |

## Szybki test przed panelem (opcjonalnie)

```bash
./arm.sh status                 # 6 przegubow z katami = ramie odpowiada
python -m pytest tests -q       # ok. 60 s na Pi, test_sim jest wolny - nie przerywaj
```

Plik `tests/test_calibrate_target.py` na Pi jest pozostaloscia z niezmergowanego brancha
(`push_to_pi.sh` przez `scp` nie usuwa starych plikow). Pomijaj:
`python -m pytest tests -q --ignore=tests/test_calibrate_target.py`.
