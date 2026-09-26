# RUNBOOK - jak odpalic robota

Krok po kroku na dzien ze sprzetem. Stan projektu jest w `docs/STATUS.md`, setup w `docs/SETUP.md`,
pulapki sprzetowe w `docs/HARDWARE.md`. Ten plik opisuje stos `pinecone_bot`; stary panel webowy
do recznej jazdy odpala sie osobno (`python web_control.py`).

## Dzien zbierania: pierwszy `--real` krok po kroku (2026-09-26)

Kamera jest na maszcie, ramie podlaczone, HSV dostrojone. Zostaly pomiary, ktore lacza te trzy rzeczy.
Wszystko ponizej dzieje sie na Pi przez SSH (Pi OS Lite, brak pulpitu: NIE uzywac `--show` ani okien OpenCV;
`calibrate_target.py` ma do tego `--headless`). Czlowiek z wylacznikiem przy robocie przez caly czas.

Config `pinecone_config.json` ma profil na pierwszy test: `search_pattern: spin_drive` (obrot w miejscu,
kawalek prosto, od nowa), `search_timeout_s: 30` (po 30 s bez szyszki DONE), `retries: 1`, `camera.lock_auto: true`
(AWB zamrozone po rozgrzewce). Pasy kosiarki (`lanes`) wracaja na demo.

0. **Porty i procesy.** `--real` sam otwiera kamere, `/dev/robot-drive` i `/dev/robot-arm`, wiec panele musza stac:
   `fuser -k 8000/tcp 8010/tcp 8080/tcp` (web_control, arm_web, rs_mjpeg_server; NIE `pkill -f`, pulapka 31).
   Zamkniecie `arm_web.py` zdejmuje torque - ktos trzyma ramie. Kod z mastera: `deploy/push_to_pi.sh`,
   na Pi `python -m pytest tests -q`.
1. **Baza (2 min, bez kamery).** `python tools/base_test.py --driver xiao --port /dev/robot-drive turn --seconds 2 --w 0.4`:
   ma skrecic W LEWO, jesli w prawo -> `control.steer_sign: -1`. Potem `forward --seconds 2 --v 0.15` z miarka;
   jesli robot jedzie wyraznie szybciej/wolniej niz 0.15 m/s, popraw `base.xiao_pwm_max` (patrz "Na Raspberry Pi", pkt 7).
   Na pierwszy test wystarczy zgodnosc znaku i "nie za szybko".
2. **Ramie (bez bazy).** `python tools/arm_play.py --motion home --dry-run`, potem bez `--dry-run` (reka na wylaczniku).
   Nastepnie `python tools/arm_play.py --motion grasp_mid` z szyszka 17 cm przed chwytakiem (pan -13.6 st, ok. 6 cm w lewo od osi):
   w logu ma byc "chwytak trzyma (odczyt > 6)". Zaznacz tasma miejsce, w ktorym szyszka lezala - to jest punkt chwytu.
   `drop_box.json` to placeholder (pan +90 w lewo na wysokosci home, otworz, wroc): `--motion drop_box --dry-run`,
   sprawdz, czy po lewej nie ma masztu/kabla, potem na zywo z szyszka w chwytaku. Jesli tor koliduje, nagraj wlasny:
   `python tools/record_waypoints.py --name drop_box --note "..."`.
3. **Kamera widzi punkt chwytu?** `python rs_mjpeg_server.py`, podglad `http://192.168.137.5:8080/`: szyszka na tasmie
   z pkt 2 ma byc w kadrze, cala, w dolnej polowie obrazu. Nie ma jej -> kamera nizej/bardziej w dol
   (`python tools/camera_geometry.py`). Wylacz serwer (`fuser -k 8080/tcp`), kamera musi byc wolna.
4. **Kalibracja celu (headless).** Szyszka DOKLADNIE na tasmie z pkt 2, nic innego brazowego w kadrze:
   `python tools/calibrate_target.py --headless` (sam pomiar: px, py, rozrzut). Rozrzut < 2 px? Zapisz:
   `python tools/calibrate_target.py --headless --grasp grasp_mid --set-cx --write`
   (`target_row` = wiersz szyszki, `cx` = jej kolumna; chwyt jest z boku osi, wiec `cx` NIE musi byc 320).
5. **Dry-run z prawdziwa kamera** (`python -m pinecone_bot.main --dry-run --seconds 120`): baza i ramie tylko drukuja.
   Przesuwaj szyszke reka i czytaj:
   - szyszka na lewo od `cx` -> `w` dodatnie; na prawo -> ujemne;
   - szyszka wyzej w obrazie niz `target_row` (dalej) -> `v` dodatnie; nizej (za blisko) -> `v` ujemne (cofanie);
   - szyszka na tasmie -> po ~3 klatkach `APPROACH -> ALIGN -> GRASP` i `arm: replay(grasp_mid)`, potem `replay(drop_box)`;
   - brak szyszki -> SEARCH drukuje `w=+0.35` (obrot), po 30 s DONE.
   Jesli znak `w` jest odwrotny do oczekiwanego, to blad kierunku kamery/`cx`, nie bazy - baza sprawdzona w pkt 1.
6. **`--real`, cztery testy, rosnaca trudnosc** (`python -m pinecone_bot.main --real --seconds 120`, po kazdym
   `cp pinecone_log.csv logs/test_N.csv`):
   1. szyszka na tasmie, robot stoi: sprawdza GRASP i DROP, baza prawie sie nie rusza;
   2. szyszka 0.8 m przed robotem, 20 cm w bok: sprawdza APPROACH/ALIGN (jedzie, staje, podnosi);
   3. szyszka poza kadrem, z boku: sprawdza SEARCH (obrot, potem podjazd);
   4. trzy szyszki w promieniu 1.5 m.
   Robot jedzie w zla strone albo nie hamuje -> wylacznik, Ctrl+C (zatrzymuje baze, ramie zostaje z torque do `close()`).
7. **Wynik do `docs/STATUS.md` i `docs/LOG.md`**: ktore z 4 testow przeszly, wartosci `cx`/`target_row`, `err_x`/`err_y`
   z CSV tuz przed GRASP przy nieudanych chwytach (sekcja "Strojenie" mowi, co z nimi zrobic).

Symulacja `--sim` z tym configiem NIE widzi szyszek (progi HSV sa pod prawdziwe szyszki, symulator maluje domyslny braz);
do sprawdzenia zmian w `brain.py` uzywaj `--sim` bez `--config`.

## Checklista na rano (pierwsze uruchomienie pinecone_bot na sprzecie)

Kolejnosc ma znaczenie: kazdy krok zapisuje cos, z czego korzysta nastepny.

- [ ] `git pull` na laptopie (master z PR #14 i #16), `deploy/push_to_pi.sh`, na Pi `python -m pytest tests -q`.
- [ ] **Kamera na maszt, wyzej i za ramie**, patrzy w dol. Zmierz miarka, ile cm przed osia kol chwytak
      zamyka sie w `grasp_mid` (i gdzie beda near/far), potem `python tools/camera_geometry.py --grasp-forward 0.30,0.35,0.40 --cam-forward -0.10`
      (tabela wysokosc x kat; komorki OK = chwyty w kadrze i poza martwa strefa glebi). Startowy typ: 0.45 m, 38 st, 10 cm za osia.
      Po zamontowaniu sprawdz w `rs_mjpeg_server.py`, ze widac szyszke lezaca w miejscu, gdzie `grasp_mid` ja podnosi.
- [ ] `python tools/snap_frames.py --out frames/ --every 0.5 --seconds 20` na prawdziwej trawie z szyszkami.
- [ ] `python tools/calibrate_hsv.py --source frames/`, klawisz `s` zapisuje prog do `pinecone_config.json`.
- [ ] `python tools/arm_play.py --motion grasp_mid --port /dev/robot-arm --dry-run`, potem bez `--dry-run`
      z szyszka w miejscu chwytu: czy chwyt trafia i czy po zacisku `gripper` czyta powyzej 6?
- [ ] `python tools/record_waypoints.py --name grasp_near ...`, `grasp_far`, `drop_box` (pojemnik zamontowany?).
- [ ] `python tools/calibrate_target.py`: szyszka dokladnie w miejscu kazdego chwytu, `s` na chwyt, `c` na kolumne, `w` zapis.
- [ ] `python tools/base_test.py --driver xiao --port /dev/robot-drive turn --seconds 2 --w 0.5`:
      robot ma skrecic W LEWO. Skreca w prawo? `cfg.control.steer_sign = -1`.
- [ ] `base_test forward --seconds 2 --v 0.15` i pomiar miarka -> `cfg.base.xiao_pwm_min/max`; rozstaw kol -> `wheel_base_m`.
- [ ] `python -m pinecone_bot.main --dry-run` (kamera prawdziwa, komendy tylko drukowane): czy `v`/`w` maja sens?
- [ ] `python -m pinecone_bot.main --real` z wylacznikiem w rece, jedna szyszka, potem piec.
- [ ] Wynik (co zadzialalo, co nie, liczby) do `docs/STATUS.md` i `docs/LOG.md`.
- [ ] Jesli jest czas: `python tools/bip_probe.py --port /dev/ttyAMA0` (przejsciowka USB-UART na zlacze plytki bocznej
      hovera; nie rusza silnikow). Odpowiada? Sekcja "Hoverboard" nizej mowi, co przestawic w configu.

## Idea w 5 zdaniach

1. Ramie jest "glupie": powtarza nagrane wczesniej ruchy (waypointy) po
   nazwie, bez IK, bez planowania trajektorii.
2. Baza jest "sprytna": ustawia szyszke w dokladnie tym miejscu obrazu, w
   ktorym nagrany chwyt ja podnosi - obracajac sie, az kolumna szyszki w
   obrazie rowna sie `cfg.cx`, i jadac, az wiersz szyszki rowna sie
   `grasp.target_row` - wylacznie na podstawie obrazu kolorowego (glebia nie
   jest do tego uzywana).
3. Cala logika to prosta maszyna stanow: SEARCH (szukaj obracajac sie) ->
   APPROACH (jedz/obracaj sie regulatorem P) -> ALIGN (potwierdz na stojaco)
   -> GRASP (zamknij chwytak) -> DROP (wrzuc do pojemnika) -> RETRY (probuj
   ponownie) -> z powrotem do SEARCH.
4. Zero uczenia maszynowego, zero LLM, zero promptow - kazda decyzja jest
   zakodowana w `pinecone_bot/brain.py` i da sie ja przeczytac linijka po
   linijce.
5. Kazda klatka i kazda decyzja trafia do pliku CSV (`pinecone_log.csv`),
   wiec kazdy nieudany przejazd da sie odtworzyc z logu, bez zgadywania.

## Struktura

| Plik / katalog                  | Co robi |
|----------------------------------|---------|
| `pinecone_bot/config.py`         | Jeden dataclass `Config` z cala konfiguracja (progi HSV, gainy regulatora, porty, geometria symulatora). Zapis/odczyt z `pinecone_config.json`. |
| `pinecone_bot/brain.py`          | Maszyna stanow + regulator P. Caly "mozg" robota, patrz docstring na gorze pliku. |
| `pinecone_bot/detector.py`       | Detektor szyszek: prog HSV -> maska -> kontury -> lista `Detection`. |
| `pinecone_bot/camera.py`         | Zrodla obrazu: `RealSenseCamera` (D415), `FileCamera` (pliki/katalog/wideo do strojenia na sucho). |
| `pinecone_bot/base.py`           | Sterowniki podwozia: `sim`, `xiao` (Seeed Xiao + H-bridge), `bipropellant` (UART do plyty hoverboarda). |
| `pinecone_bot/arm.py`            | Odtwarzacz ruchow ramienia: `sim`, `waypoints` (prawdziwe SO-101 przez lerobot), `subprocess` (skrypt zespolu). |
| `pinecone_bot/sim.py`            | Symulator geometrii kamery + swiata, do rozwijania calej petli bez sprzetu. |
| `pinecone_bot/main.py`           | CLI: `--sim`, `--dry-run`, `--real`. |
| `tools/snap_frames.py`           | Zapis klatek z kamery do PNG (material do strojenia detektora). |
| `tools/calibrate_hsv.py`         | Interaktywne strojenie progu HSV, zapis do configu. |
| `tools/calibrate_target.py`      | Pomiar `cfg.cx` i `grasp.target_row` dla kazdego nagranego chwytu. |
| `tools/record_waypoints.py`      | Nagrywanie ruchu ramienia (waypointy) recznym ustawianiem serw. |
| `tools/arm_play.py`              | Odtworzenie jednego nagranego ruchu (do testu bez calej petli). |
| `tools/arm_web.py`               | Panel webowy ramienia na :8010 (jog stawow, HOME, chwytak, `motions/`, STOP); ta sama sekcja jest w panelu jazdy :8000. `--fake` bez sprzetu, `--no-home` bez HOME (kamera na ramieniu). |
| `tools/base_test.py`             | Reczny test podwozia: `forward` / `turn` / `square`, pomiar znaku skretu i mapowania PWM. |
| `motions/*.json`                 | Nagrane ruchy ramienia (`home`, `grasp_mid` - placeholder, `drop_box` - placeholder). |
| `tests/`                         | Testy jednostkowe `pinecone_bot/*` (bez sprzetu, bez kamery). |

## Na laptopie (bez sprzetu)

```
python -m venv .venv
.venv\Scripts\activate            # PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-pinecone.txt

python -m pinecone_bot.main --sim --show
python -m pytest tests -q
```

`--sim` uruchamia caly stos (kamera, detektor, regulator, maszyna stanow,
"ramie") na symulowanym swiecie z `pinecone_bot/sim.py` - dobre miejsce do
sprawdzenia zmian w `brain.py` bez czekania na sprzet. `--show` otwiera okno
podgladu (wymaga `opencv-python` z GUI, nie `-headless`).

## Na Raspberry Pi, w tej kolejnosci

1. **Zaleznosci.** `uv pip install --python .venv/bin/python -r requirements-pinecone.txt`
   w wenwie repo (lerobot i pyrealsense2 juz tam sa z `requirements-pi.txt`). Szczegoly
   pierwszej instalacji calego systemu: `deploy/setup_pi.sh`.
2. **Przemontowanie kamery.** Miejsce chwytu musi byc widoczne i dalej niz
   minimalna odleglosc pomiaru glebi D415: ok. 31 cm przy strumieniu koloru
   640x480, ok. 16 cm przy 424x240 (patrz `pinecone_bot/camera.py`, pomiar w
   `scan_cones.py`). Kamera ma stac wysoko, za ramieniem, patrzac w dol - nie
   nisko z przodu jak w starszych probach (tam martwa strefa glebi zjadala
   dystans chwytania).
3. **Zbierz klatki murawy i szyszek:**
   `python tools/snap_frames.py --out frames/ --every 0.5 --seconds 20`
4. **Strojenie progu HSV** i zapis do configu:
   `python tools/calibrate_hsv.py --source frames/`
   (klawisz `s` zapisuje `cfg.detector.hsv` i `min_area_px` do
   `pinecone_config.json`).
5. **Nagraj chwyty ramieniem:**
   ```
   python tools/record_waypoints.py --name grasp_near --port /dev/robot-arm
   python tools/record_waypoints.py --name grasp_mid --port /dev/robot-arm
   python tools/record_waypoints.py --name grasp_far --port /dev/robot-arm
   python tools/record_waypoints.py --name drop_box --port /dev/robot-arm
   ```
   `motions/grasp_mid.json` jest juz z aktualnej kalibracji (klatki z
   `legacy/arm_recordings/demo2_fixed.csv`, zacisk do 0), wiec na start
   wystarczy nagrac `grasp_near`, `grasp_far` i `drop_box`. Config na Pi
   (`pinecone_config.json`) ma na razie tylko `grasp_mid`; po nagraniu
   dopisz kolejne chwyty do listy `grasps` (target_row ustawi
   `calibrate_target.py`). Chwyt bez pliku ruchu jest pomijany przy starcie.
6. **Kalibracja celu** - poloz szyszke dokladnie tam, gdzie kazdy nagrany
   chwyt ja podnosi, i zmierz, gdzie ona wtedy lezy w obrazie:
   `python tools/calibrate_target.py`
   Dla kazdego chwytu (near/mid/far): wybierz go klawiszem `1`/`2`/`3`,
   poczekaj na ustabilizowana srednia, wcisnij `s`. Potem `c` zapisuje
   biezaca kolumne szyszki jako `cfg.cx` (srodek chwytaka w obrazie), `w`
   zapisuje wszystko do `pinecone_config.json`.
7. **Sprawdz podwozie** - znak skretu i mapowanie predkosci na PWM:
   ```
   python tools/base_test.py --driver xiao --port /dev/robot-drive forward --seconds 2 --v 0.15
   python tools/base_test.py --driver xiao --port /dev/robot-drive turn --seconds 2 --w 0.5
   python tools/base_test.py --driver xiao --port /dev/robot-drive square --side 1.0
   ```
   Wynik idzie recznie do `pinecone_config.json`: znak skretu ->
   `cfg.control.steer_sign`, zmierzone mapowanie PWM ->
   `cfg.base.xiao_pwm_min/xiao_pwm_max/xiao_steer_min/xiao_steer_max`,
   rozstaw kol z pomiaru fizycznego -> `cfg.base.wheel_base_m`.
   `base_test.py` niczego sam nie zapisuje - tylko pokazuje, co zmierzyc.
8. **Uruchomienie z prawdziwa kamera, bez ruchu** (drukuje komendy zamiast
   je wykonywac): `python -m pinecone_bot.main --dry-run --show`
   a po sprawdzeniu, ze regulator sie zachowuje sensownie:
   `python -m pinecone_bot.main --real`.
   Trzymaj wylacznik awaryjny w rece przy pierwszym `--real`.

Caly ten przebieg czyta i zapisuje jeden plik: `pinecone_config.json` w
katalogu repo (`pinecone_bot/config.py`, `Config.save`/`Config.load`; sciezke
mozna nadpisac zmienna `PINECONE_CONFIG` albo flaga `--config`). Kazde
narzedzie z `tools/` dotyka tylko tych pol configu, ktore mierzy - reszta
zostaje bez zmian.

## Hoverboard: xiao czy bipropellant

`cfg.base.driver` przelacza sterownik podwozia (`pinecone_bot/base.py`):

- **`xiao`** - dzisiejsza sciezka: Seeed Xiao RP2040 sterujacy H-bridge'em
  (`xiao_send_pwm.ino`), linie ASCII `a<speed> b<steer>\n` po USB-serial.
  Wymaga zmierzonego mapowania m/s -> PWM (`base_test.py`, patrz wyzej).

- **`bipropellant`** - alternatywa: bezposredni UART do plyty hoverboarda z
  firmwarem `bipropellant-hoverboard-firmware`, bez posredniczacego Xiao.
  Predkosci kol podaje sie wprost w mm/s, a odometria idzie z hallotronow
  na plycie (dokladniejsza niz nic, jak przy `xiao`, ktory odometrii nie ma).
  10-minutowy test, czy plyta w ogole mowi tym protokolem: podlacz
  przejsciowke USB-UART do zlacza na sideboard/mainboard hoverboarda,
  115200 bodow (jesli nie odpowiada, sprobuj 9600), wyslij `unlockASCII`,
  potem `?`. Jesli plyta odpowie, mozna przestawic `cfg.base.driver` na
  `bipropellant`.
  Zanim to pojedzie na sprzecie, zweryfikuj zalozenia opisane w komentarzach
  `pinecone_bot/base.py` (sekcja BIPROPELLANT):
  - znak skretu (`w` dodatnie ma skrecac w lewo, sprawdzic jak przy `xiao`);
  - kolejnosc indeksow kol w tablicach `[2]` (zakladane `[0]`=lewe,
    `[1]`=prawe - `BIP_LEFT`/`BIP_RIGHT`) i znak przyrostu odometrii halla
    dla kazdego kola (`BIP_HALL_SIGN`, zakladane, ze jazda do przodu
    zwieksza oba);
  - uklad ramki 0x09 (enable) / 0x0A (disable poweroff) - payload jako
    int32 LE, DO SPRAWDZENIA na konkretnym firmware zespolu;
  - predkosc portu (115200 vs 9600) i regula sumy kontrolnej ramki
    (`build_frame`: suma bajtow CI..CS musi wyjsc 0 mod 256);
  - `cfg.base.wheel_base_m` (rozstaw kol) - zmierzyc fizycznie, uzywane do
    przeliczenia (v, w) na predkosci kol w mm/s.

## Strojenie

Dwa gainy regulatora P w `cfg.control`:

- `kx` - rad/s obrotu na piksel bledu poziomego (`px - cfg.cx`). Za male:
  robot wolno centruje szyszke w kadrze. Za duze: oscyluje/przestrzela.
- `ky` - m/s do przodu na piksel bledu pionowego (`target_row - py`). Za
  male: wolny dojazd. Za duze: robot wjezdza za daleko, zanim regulator
  zdazy zahamowac.

Do tego `tol_x_px` / `tol_y_px` (tolerancja, w ktorej uznajemy "ustawiony")
i `settle_frames` (ile klatek z rzedu w tolerancji, zanim ALIGN potwierdzi
chwyt - za male drga na szumie detekcji, za duze wydluza kazde podejscie).

`pinecone_log.csv` (kolumny: `t, state, n_det, px, py, err_x, err_y, v, w,
collected`) pokazuje dokladnie, dlaczego chwyt sie nie udal: patrz na
`err_x`/`err_y` tuz przed przejsciem do stanu `GRASP` - jesli byly poza
tolerancja, ALIGN nie powinien byl puscic do GRASP (blad w kodzie), a jesli
byly w tolerancji, ale szyszka i tak nie trafila do chwytaka, to
`target_row` danego chwytu jest zle skalibrowany (wroc do
`tools/calibrate_target.py`).

## Szukanie szyszek (SEARCH): pasy jak kosiarka

Gdy nic nie widac, robot jedzie wzorcem z `cfg.control.search_pattern`:

- `lanes` (domyslne): najpierw pelny obrot w miejscu (kamera widzi ok. 1.5 m,
  wiec od razu lapie szyszki dookola), potem pasy jak kosiarka: prosto
  `lane_length_m`, obrot 90 st w lewo, prosto `lane_spacing_m`, znowu 90 st
  w lewo, prosto z powrotem, nastepny pas w prawo... Po `lane_count` pasach
  robot konczy (DONE). Robot MUSI startowac w rogu trawnika, przodem wzdluz
  dluzszego boku, tak by trawnik byl po jego lewej stronie.
- `spin_drive`: pelny obrot, kawalek prosto, od nowa. Bladzi losowo, konczy po
  `search_timeout_s` bez detekcji.

Czas wzorca biegnie tylko w SEARCH i nie zeruje sie po chwycie, wiec po
zebraniu szyszki robot wraca do pasow mniej wiecej tam, gdzie przerwal.
"Mniej wiecej", bo bez odometrii nie wie, gdzie stanal po podjezdzie.
Pasy sa liczone z czasu i zadanych predkosci (`search_drive_v`, `search_w`),
wiec na trawie trzeba je zmierzyc `tools/base_test.py` i wpisac. Z Xiao
(otwarte PWM) pasy beda krzywe; z bipropellantem (zamknieta petla predkosci,
odczyt halla) mozna je potem oprzec na odometrii. Na demo wystarczy
`lane_count` 2-3 i szyszki w zasiegu pierwszego obrotu.

## Czego nie robic

- Nie dodawac IK do ramienia na tym etapie - `approach_and_grasp.py` (stary
  skrypt zespolu z IK) zostaje odlozony na bok; ten stos celowo uzywa tylko
  nagranych waypointow.
- Nie wprowadzac ROS ani SLAM - caly stan robota to pozycja w obrazie plus
  prosta maszyna stanow, nic wiecej nie jest potrzebne do zbierania szyszek.
- Nie dodawac uczonych polityk (ACT, imitation learning itp.), dopoki ta
  deterministyczna petla nie dziala niezawodnie na sprzecie - to jest linia
  bazowa, do ktorej kazde pozniejsze podejscie z ML powinno sie porownywac.
