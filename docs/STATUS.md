# STATUS - na czym stoimy

Jeden ekran. Aktualizuje go KAZDY PR (checkbox w szablonie PR). Historia jest w `docs/LOG.md`,
zadania i przypisania na tablicy Projects (link nizej). Czego nie ma tutaj albo w issue, nie istnieje.

**Stan na:** 2026-09-26 rano (przed pierwszym kontaktem `pinecone_bot` ze sprzetem)
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

## Nie dziala / nie sprawdzone

- `pinecone_bot` NIE JECHAL jeszcze na sprzecie. Wszystko ponizej to pierwsze uruchomienie (docs/RUNBOOK.md).
- HSV sprawdzone w jednym swietle; auto white balance kamery przez ~1 s po starcie daje zielona trawe i 0 detekcji (zablokowac AWB/ekspozycje w camera.py).
- `lsusb` zglasza kamere jako D435 (8086:0b07), docs mowia D415 - sprawdzic model.
- Kamera stoi za nisko: miejsce chwytu (17 cm przed kamera) jest w martwej strefie glebi (~31 cm). Trzeba przestawic.
- Panel ramienia (`tools/arm_web.py`) NIE sprawdzony na prawdziwym ramieniu (pierwsze uruchomienie: czlowiek przy ramieniu, STOP pod reka).
- Chwyty `grasp_near`, `grasp_far`, `drop_box` nie nagrane (config ma na razie tylko `grasp_mid`).
- Znak skretu Xiao i mapowanie PWM -> m/s niezmierzone (`cfg.base.xiao_*`, `cfg.control.steer_sign`).
- Bipropellant na plycie hovera: wlasciciele mowia, ze jest, kod dzis jedzie przez Xiao. Test nie zrobiony:
  `python tools/bip_probe.py --port /dev/ttyAMA0` (nie rusza silnikow, sprawdza ASCII i protokol binarny na 3 baudach).
- Pi nie ma internetu (WiFi nie dziala), kod wchodzi przez `deploy/push_to_pi.sh` / scp.
- Zasilanie z akumulatora 12 V: issue #8, nie zaczete.

## Nastepne 3 kroki (w tej kolejnosci)

1. Kamera na maszt: wysokosc i kat z `tools/camera_geometry.py` (np. 0.45 m, 38 st, 10 cm za osia kol);
   potem `tools/snap_frames.py` + `tools/calibrate_hsv.py` na prawdziwej trawie.
2. Na Pi: `python tools/arm_web.py` (panel ramienia, :8010), sprawdzic jog/HOME/STOP. Potem nagrac `grasp_near`, `grasp_far`, `drop_box` (`tools/record_waypoints.py`; panel pomaga ustawic poze), skalibrowac `target_row` (`tools/calibrate_target.py`).
3. `tools/base_test.py` (znak skretu, PWM), potem `python -m pinecone_bot.main --dry-run`, potem `--real` z wylacznikiem w rece.

## Blokery

- Merge PR #16 (poprawki z issue #15) - bez tego `--real` konczy sie bledem przy chwycie near/far.
- Branch protection na master i tablica Projects: do zrobienia przez pawel120 (docs/CONTRIBUTING.md).

## Kto co robi (obszary; wpiszcie nazwiska)

| Obszar | Osoba | Biezace issue |
|---|---|---|
| baza / hover (Xiao, bipropellant, base_test) | ? | |
| ramie (nagrania chwytow, record_waypoints) | ? | |
| wizja + kalibracja (kamera, HSV, calibrate_target) | ? | |
| integracja + docs (brain, testy, STATUS/LOG) | ? | |
| elektryka (zasilanie 12 V, e-stop) | ? | #8 |
