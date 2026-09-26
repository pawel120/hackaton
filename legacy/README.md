# legacy/

Skrypty zespolu odlozone na bok, bo zastapil je nowszy pipeline
(`pinecone_bot/`, `web_control.py`, `detect_floor_objects.py`, `scan_cones.py`).
Zostaja tu do wgladu i jako zrodlo danych/pomyslow - nie sa usuwane, bo:

- pokazuja podejscia, ktore dzialaly czesciowo i mogly by wrocic,
- `demo2_fixed.csv` jest zrodlem klatek kluczowych w `motions/grasp_mid.json`,
- kod wciaz sie uruchamia (dry-run/testy przechodza bez sprzetu).

Kazdy skrypt tu jest uruchamiany z katalogu glownego repo, np.:

    python legacy/ik_approach/test_drive_plan.py

## ik_approach/

Pipeline chwytu przez IK (inverse kinematics) na URDF ramienia SO-101, oparty
o transformate kamera -> baza ramienia, ktora jest OSZACOWANIEM Z MONTAZU,
nie pomiarem (`arm_camera_transform.json`, `"zmierzone": false`). Dopoki nie
powstanie zmierzona kalibracja kamera-ramie, plan chwytu z tego pipeline'u
jest tylko tak dobry jak to oszacowanie - dlatego zespol przeszedl na
nagrania (`arm_recordings/`) jako pewniejsze zrodlo ruchu.

- `approach_and_grasp.py` - liczy plan chwytu z zapamietanej pozycji
  (`cel.json` ze `scan_cones.py`) przez IK na `so101_urdf/`. Domyslnie
  dry-run, ruch wymaga `--port`.
  Uruchomienie: `python legacy/ik_approach/approach_and_grasp.py --no-drive`
- `arm_camera_transform.json` - transformata kamera -> baza ramienia
  (oszacowana, nie zmierzona). Czytana przez `approach_and_grasp.py`.
- `test_grasp_plan.py` - testy planu chwytu bez sprzetu, zwykly python.
  Uruchomienie: `python legacy/ik_approach/test_grasp_plan.py`
  (wymaga `ikpy`; bez niego `ModuleNotFoundError` juz przy imporcie).
- `drive_to_target.py` - dojazd platformy (obrot + jazda prosto, open-loop)
  do zapamietanej pozycji, przez pakiet `makarena` (POZA tym repo). Slepa
  jazda liczona z czasu, bez odometrii/sprzezenia zwrotnego.
  Uruchomienie: `python legacy/ik_approach/drive_to_target.py --standoff 0.15`
- `drive_calibration.json` - stale jazdy (m/s, st/s) dla `drive_to_target.py`,
  domyslnie ZGADNIETE ("measured": false) - do zmierzenia miarka.
- `test_drive_plan.py` - testy planu dojazdu bez sprzetu, zwykly python.
  Uruchomienie: `python legacy/ik_approach/test_drive_plan.py`

## arm_recordings/

Reczne demonstracje ruchu ramienia (torque off, czlowiek fizycznie prowadzi
ramie) i ich odtwarzanie - zapasowa sciezka obok IK, gdy transformata
kamera-ramie jest niepewna. Nagrania dzialaja tylko dla TEJ SAMEJ pozycji
szyszki co podczas nagrywania (odtworzenie trasy, nie ogolny chwyt).

**`demo2_fixed.csv` jest zrodlem klatek kluczowych w `motions/grasp_mid.json`**
(aktualny ruch chwytu uzywany przez `pinecone_bot/`).

- `record_demo.py` - nagrywa pozycje wszystkich przegubow, gdy czlowiek
  recznie porusza ramieniem.
  Uruchomienie: `python legacy/arm_recordings/record_demo.py --seconds 25 --out demo.csv`
- `replay_csv.py` - odtwarza cala trajektorie z CSV klatka po klatce (gesta,
  ~10 klatek/s) - obecnie preferowany sposob odtwarzania nagrania.
  Uruchomienie: `python legacy/arm_recordings/replay_csv.py legacy/arm_recordings/demo2_fixed.csv --dry-run`
- `replay_demo.py` - NIEAKTUALNE: kilka recznie wybranych punktow sprzed
  `fix_shoulder_offset.py`, jada zle po korekcie kalibracji. Zostawione, bo
  `pinecone_bot` (`driver: subprocess`) potrafi je odpalic jako fallback.
  Uruchomienie: `python legacy/arm_recordings/replay_demo.py --port /dev/robot-arm --dry-run`
- `fix_shoulder_offset.py` - jednorazowa (juz wykonana, 2026-09-25) poprawka
  kalibracji barku/lokcia; liczy tez `demo2_fixed.csv` z `demo2.csv`.
  Uruchomienie: `python legacy/arm_recordings/fix_shoulder_offset.py`
- `demo.csv` - pierwsze nagranie reczne, sprzed korekty kalibracji.
- `demo2.csv` - drugie nagranie reczne, przed przeliczeniem kalibracji.
- `demo2_fixed.csv` - `demo2.csv` przeliczone do nowej (aktualnej)
  kalibracji barku/lokcia. Uzywane jako zrodlo `motions/grasp_mid.json`.

## drive/

Starsze skrypty sterowania platforma po surowym protokole Xiao
(`xiao_send_pwm.ino`), sprzed `web_control.py` (ktory ma teraz wlasny
interfejs webowy nad tym samym protokolem).

- `makarena.py` - sterowanie platforma gamepadem.
  Uruchomienie: `python legacy/drive/makarena.py`
- `figure_eight.py` - autonomiczna jazda po "osemce" (do testu napedu).
  Uruchomienie: `python legacy/drive/figure_eight.py`
- `keyboard_control.py` - sterowanie platforma z klawiatury (W/S/A/D).
  Uruchomienie: `python legacy/drive/keyboard_control.py`

## vision/

Starsze/pomocnicze skrypty wizyjne sprzed detektora glebi
(`detect_floor_objects.py`), oparte na progowaniu koloru HSV bez uzycia
glebi z kamery.

- `detect_object.py` - detekcja obiektu po kolorze HSV + deprojekcja do
  punktu 3D z RealSense. Do szyszek sie nie nadaje (za male roznice koloru
  od tla) - zastapiony detektorem glebi.
  Uruchomienie: `python legacy/vision/detect_object.py --color red`
- `sample_colors.py` - mierzy rozklady HSV celu i tla pod maska detektora
  glebi, do dobrania progu `COLOR_GATE` w `detect_floor_objects.py`. Nadal
  przydatny narzedziowo przy zmianie oswietlenia.
  Uruchomienie: `python legacy/vision/sample_colors.py`
