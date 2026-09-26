# CLAUDE.md - instrukcje dla Claude Code w tym repo

Robot zbierajacy szyszki: hoverboard + ramie SO-101 (lerobot) + RealSense D415 + Raspberry Pi 5.
Piec osob, jeden robot, hackaton. Ten plik czyta kazda sesja Claude Code; ludzie czytaja README.md.

## Zanim cokolwiek zrobisz

1. Przeczytaj `docs/STATUS.md` (stan projektu, jeden ekran) i sprawdz, na jakim branchu jestes (`git branch --show-current`).
   Praca idzie na branchu `<nick>/<opis>`, nigdy bezposrednio na `master`.
2. Zanim dotkniesz sprzetu albo kodu sterowania, przeczytaj `docs/HARDWARE.md` (pulapki) i `docs/RUNBOOK.md` (kolejnosc narzedzi).
3. Szczegoly zasad pracy: `docs/CONTRIBUTING.md`. Historia prob: `docs/LOG.md`.

## Zasady kodu

- Glowny stos to `pinecone_bot/` (config, detektor, kamera, sterowniki bazy, ramie, `brain.py` = maszyna stanow, symulator).
  Sterowanie jest deterministyczne: bez ML, bez LLM, bez promptow w petli. Nie proponuj IK, SLAM, ROS ani uczenia polityk,
  dopoki deterministyczna petla nie dziala na sprzecie (patrz `docs/RUNBOOK.md`, sekcja "Czego nie robic").
- Kazda zmiana w `pinecone_bot/` ma test w `tests/`. Uruchom `python -m pytest tests -q` (venv: `.venv`).
  Zmiany w `brain.py` sprawdz tez symulacja: `python -m pinecone_bot.main --sim --seconds 200`.
- Wszystkie pliki czystym ASCII: polskie komentarze i dokumentacja BEZ ogonkow ("predkosc" zamiast wersji z ogonkami).
  Wyjatek: teksty widoczne dla uzytkownika w `frontend.html`. Bez em-dash, bez strzalek unicode (uzywaj "-" i "->").
- Stare skrypty leza w `legacy/` i sa odlozone celowo (`legacy/README.md`). Nie przenos ich z powrotem, nie buduj na nich.
- `arm_control.py` importuje lerobot, ktorego nie ma na laptopie: importuj go leniwie (jak `pinecone_bot/arm.py`).
- Zadnych hasel, tokenow ani adresow prywatnych w repo.
- Jeden plik konfiguracji robota: `pinecone_config.json` (`pinecone_bot/config.py`). Wartosci zmierzone na sprzecie
  wpisuja narzedzia z `tools/`; nie zgaduj ich w kodzie.

## Sprzet (gdy sesja ma dostep do Pi)

- NIGDY nie uruchamiaj `lerobot calibrate` ani nie edytuj pliku kalibracji serw: nadpisze recznie poprawiony offset barku
  (szczegoly w `docs/HARDWARE.md`).
- Na Pi jedzie tylko `master` (`deploy/push_to_pi.sh`). Nie edytuj kodu na Pi; hotfix = branch `pi/hotfix-<opis>` i PR.
- Pierwsze uruchomienie nowego kodu z `--real` tylko z czlowiekiem trzymajacym wylacznik. Najpierw `--dry-run`.
- Jedna osoba przy robocie naraz; pole "Robot" w `docs/STATUS.md`.

## Koniec sesji (obowiazkowe)

1. Zaktualizuj `docs/STATUS.md`: "Dziala", "Nie dziala / nie sprawdzone", "Nastepne 3 kroki", "Robot".
2. Dopisz wpis na koncu `docs/LOG.md` wedlug szablonu z gory pliku (kto, zrobione, otwarte, nastepny krok, sprzet).
3. Commit i push brancha; PR do `master` z wypelnionym szablonem. Nie merguj sam: 1 review + zielony check `tests`.
4. Nie commituj plikow generowanych: `pinecone_log.csv`, `frames/`, `cel.json`, `__pycache__`, `.venv`.

## Skroty

```
python -m pytest tests -q                      # testy bez sprzetu
python -m pinecone_bot.main --sim --show       # symulacja z podgladem
python -m pinecone_bot.main --dry-run          # prawdziwa kamera, komendy tylko drukowane
python -m pinecone_bot.main --real             # robot jedzie (wylacznik w rece)
deploy/push_to_pi.sh                           # kod na Pi (z mastera)
```
