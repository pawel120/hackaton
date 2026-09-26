# STATUS - na czym stoimy

Jeden ekran. Aktualizuje go KAZDY PR (checkbox w szablonie PR). Historia jest w `docs/LOG.md`,
zadania i przypisania na tablicy Projects (link nizej). Czego nie ma tutaj albo w issue, nie istnieje.

**Stan na:** 2026-09-26 po poludniu (kamera na maszcie, ramie podlaczone; `pinecone_bot --real` jeszcze nie odpalony)
**Robot (kto ma sprzet, do kiedy):** wolny
**Tablica zadan:** TODO wkleic link do GitHub Projects (zaklada pawel120, patrz docs/CONTRIBUTING.md)

## Dziala

- Ramie SO-101: skalibrowane po naprawie barku, `./arm.sh home|status|open|close`. NIE uruchamiac `lerobot calibrate`.
- Podwozie: Xiao + panel webowy (`python web_control.py`, WASD, osemka, pokrycie), `drive_step.py` do pojedynczych krokow.
- Kamera D415: podglad `rs_mjpeg_server.py` (glebia 424x240 -> mniejszy MinZ, bliski dywan ma ciagla glebie), detekcja szyszek z glebi (`scan_cones.py`, rozrzut < 2 mm).
- Nowy stos `pinecone_bot` (PR #14 + poprawki PR #16): symulacja na laptopie zbiera 5/5 szyszek, 66 testow zielonych.
  Ramie odtwarza nagrane punkty, baza ustawia szyszke z obrazu, maszyna stanow, szukanie pasami. Bez IK, bez ML.
- Detektor HSV dostrojony na prawdziwych szyszkach na sztucznej trawie (lo [130,35,30], hi [179,100,125], min_area 120): 3/3 szyszki, 0 falszywych na trawie.
- Panel webowy ramienia `tools/arm_web.py` (port 8010): jog kazdego stawu o 1/5/10, HOME, chwytak, ruchy z `motions/`, STOP.
  Jazda + ramie w jednym miejscu: sekcja ramienia w panelu jazdy (:8000, `frontend.html`), glowny STOP zatrzymuje tez ramie.
  Dwa procesy na Pi: `web_control.py` i `tools/arm_web.py` (UI ramienia wspolne: `arm_panel.js`).
  Logika w `pinecone_bot/arm_panel.py` (kolejka, zakres z kalibracji, limit kroku), 22 testy; sprawdzony w przegladarce na atrapie (`--fake`).
  `--no-home`: bez HOME przy starcie, HOME i `motions/` wylaczone, tylko jog i chwytak (kamera siedzi teraz na ramieniu - HOME w nia uderzy).
- `motions/grasp_mid.json`: chwyt z `demo2_fixed.csv` (aktualna kalibracja). `home.json`, `drop_box.json` (placeholder).
- Kamera na maszcie (zamontowana 2026-09-26), ramie podlaczone i jezdzi z panelu.
- `tools/calibrate_target.py --headless`: kalibracja `target_row`/`cx` bez okna OpenCV (Pi nie ma pulpitu). `main.py` loguje
  komunikaty ramienia/kamery na konsole. Config ma profil na pierwszy `--real` (spin_drive, timeout 30 s, retries 1, AWB lock).
  Kolejnosc komend na dzien zbierania: `docs/RUNBOOK.md`, sekcja "Dzien zbierania".

## Nie dziala / nie sprawdzone

- `pinecone_bot` NIE JECHAL jeszcze na sprzecie. Wszystko ponizej to pierwsze uruchomienie (docs/RUNBOOK.md).
- HSV sprawdzone w jednym swietle; auto white balance kamery przez ~1 s po starcie daje zielona trawe i 0 detekcji (zablokowac AWB/ekspozycje w camera.py).
- `lsusb` zglasza kamere jako D435 (8086:0b07), docs mowia D415 - sprawdzic model.
- Czy z masztu widac punkt chwytu `grasp_mid` (RUNBOOK "Dzien zbierania" pkt 3) - nie sprawdzone.
- `cx` i `target_row` NIE zmierzone (w configu wartosci domyslne 320/360). Bez tego ALIGN puszcza chwyt w zlym miejscu.
- `home.json` i `grasp_mid.json` nie odtworzone przez `pinecone_bot` na sprzecie po przemontowaniu kamery (arm_play, pkt 2).
- `drop_box.json` to placeholder (pan +90 w lewo): sprawdzic tor przy maszcie albo nagrac.
- Hotspot: ping do Pi skacze do 240 ms i gubi pakiety, heartbeat panelu jazdy (1 s) co chwile wpada w failsafe (robot staje na chwile).
- Chwyty `grasp_near`, `grasp_far`, `drop_box` nie nagrane (config ma na razie tylko `grasp_mid`).
- Znak skretu Xiao i mapowanie PWM -> m/s niezmierzone (`cfg.base.xiao_*`, `cfg.control.steer_sign`).
- Bipropellant na plycie hovera: wlasciciele mowia, ze jest, kod dzis jedzie przez Xiao. Test nie zrobiony:
  `python tools/bip_probe.py --port /dev/ttyAMA0` (nie rusza silnikow, sprawdza ASCII i protokol binarny na 3 baudach).
- Pi nie ma internetu (WiFi nie dziala), kod wchodzi przez `deploy/push_to_pi.sh` / scp.
- Zasilanie z akumulatora 12 V: issue #8, nie zaczete.

## Nastepne 3 kroki (w tej kolejnosci)

Pelna lista komend: `docs/RUNBOOK.md`, sekcja "Dzien zbierania".

1. Na Pi: zatrzymac panele (`fuser -k 8000/tcp 8010/tcp 8080/tcp`), `base_test turn/forward` (znak skretu),
   `arm_play --motion home`, potem `grasp_mid` z szyszka 17 cm przed chwytakiem, tasma w miejscu chwytu; `drop_box` dry-run + na zywo.
2. `tools/calibrate_target.py --headless --grasp grasp_mid --set-cx --write` z szyszka na tasmie,
   potem `python -m pinecone_bot.main --dry-run --seconds 120` i sprawdzenie znakow `v`/`w` (RUNBOOK pkt 5).
3. `python -m pinecone_bot.main --real --seconds 120`: 4 testy (szyszka na tasmie; 0.8 m przed robotem; poza kadrem; trzy szyszki).
   Wynik i `pinecone_log.csv` do STATUS/LOG. Dopiero potem `grasp_near`/`grasp_far` i pasy `lanes` na demo.

## Blokery

- Brak zmierzonego `cx`/`target_row` (krok 2) - `--real` bez tego nie ma sensu.
- Branch protection na master i tablica Projects: do zrobienia przez pawel120 (docs/CONTRIBUTING.md).

## Kto co robi (obszary; wpiszcie nazwiska)

| Obszar | Osoba | Biezace issue |
|---|---|---|
| baza / hover (Xiao, bipropellant, base_test) | ? | |
| ramie (nagrania chwytow, record_waypoints) | ? | |
| wizja + kalibracja (kamera, HSV, calibrate_target) | ? | |
| integracja + docs (brain, testy, STATUS/LOG) | ? | |
| elektryka (zasilanie 12 V, e-stop) | ? | #8 |
