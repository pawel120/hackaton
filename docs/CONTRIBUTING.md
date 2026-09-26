# Jak pracujemy (5 osob, jeden robot, hackaton)

Krotko: GitHub Flow. `master` zawsze dziala. Zadanie = issue. Branch per zadanie. PR z jednym review
i zielonymi testami. Koniec sesji = 3 linijki w `docs/STATUS.md` i wpis w `docs/LOG.md`.

## 1. Start sesji (2 minuty)

```
git checkout master
git pull
```

1. Przeczytaj `docs/STATUS.md` (jeden ekran: co dziala, co nie, nastepne kroki, kto ma robota).
2. Wez zadanie z tablicy Projects (kolumna Todo -> przesun do "W toku", przypisz siebie).
   Nie ma zadania? Zaloz issue z szablonu "Zadanie" (cel + kryterium "zrobione" + obszar).
3. Zaloz branch:

```
git checkout -b <nick>/<krotki-opis>      # np. franek/calibrate-target
```

## 2. W trakcie

- Zadania na 1-3 godziny, nie na caly dzien. Duze zadanie = kilka issue.
- Commituj czesto, pushuj czesto (`git push -u origin <branch>`): to backup, gdyby laptop padl.
- Zmiana w `pinecone_bot/` = test w `tests/`. `python -m pytest tests -q` przed pushem.
- Kod i dokumentacja czystym ASCII (polskie komentarze bez ogonkow). Wyjatek: teksty UI w `frontend.html`.
- Zadnych hasel, tokenow, kluczy w repo. Haslo do Pi zostaje w glowach.
- Szukasz, jak cos dziala na sprzecie? `docs/HARDWARE.md` (pulapki) i `docs/LOG.md` (co juz probowano).

## 3. Pull request

1. Przed PR dociagnij master, zeby konflikty rozwiazac u siebie, nie w GitHubie:

```
git fetch origin
git rebase origin/master        # albo: git merge origin/master
```

2. Otworz PR do `master`. Szablon wypelnia sie sam: co, jak sprawdzone, czy dotknieto sprzetu, checklista.
3. **Warunki merge:** 1 review od kogos innego (moze byc szybkie, chodzi o drugie oczy na wspolnym kodzie)
   + zielony check `tests` (GitHub Actions, pytest bez sprzetu).
4. Merge przez **"Squash and merge"** (jeden commit na zadanie, czysta historia), potem usun branch.
5. Po merge kazdy przy nastepnej okazji robi `git pull` na masterze. Na Pi: `deploy/push_to_pi.sh` z mastera.

## 4. Koniec sesji (5 minut, obowiazkowe)

1. `docs/STATUS.md`: popraw sekcje "Dziala", "Nie dziala", "Nastepne 3 kroki", "Robot". Trzy linijki wystarcza.
2. `docs/LOG.md`: dopisz wpis na koncu wedlug szablonu (kto, co zrobione, co nie, nastepny krok, czy sprzet).
3. Push brancha albo PR. Nic nie zostaje tylko na laptopie.
4. Przesun swoje issue na tablicy (Review / Zrobione).

Zasada: czego nie ma w STATUS, LOG albo issue, tego nie bylo.

## 5. Robot i Raspberry Pi

- **Jedna osoba przy robocie naraz.** Wpisz siebie w STATUS w polu "Robot (kto ma sprzet, do kiedy)".
- Na Pi zawsze jedzie `master`: `deploy/push_to_pi.sh` (ostrzega, gdy wysylasz inny branch).
- Nie edytuj kodu bezposrednio na Pi. Jesli musisz (hotfix przy robocie), zrob z tego commit na branchu
  `pi/hotfix-<opis>` i PR jak kazdy inny; nie zostawiaj zmian tylko na Pi.
- Wylacznik awaryjny w rece przy kazdym pierwszym uruchomieniu nowego kodu na `--real`.
- Nigdy `lerobot calibrate` (nadpisze poprawiony offset barku, patrz `docs/HARDWARE.md`).

## 6. Obszary i wlasciciele

Wpisane w tabeli na dole `docs/STATUS.md`: baza/hover, ramie, wizja+kalibracja, integracja+docs, elektryka.
Wlasciciel obszaru robi review PR-ow z tego obszaru. `pinecone_bot/brain.py` i `arm_control.py` to kod wspolny:
review od kogos spoza autora zawsze.

## 7. Jednorazowe ustawienia (pawel120, wlasciciel repo)

1. **Branch protection na `master`:** Settings -> Branches -> Add rule -> `master`:
   Require a pull request before merging (1 approval), Require status checks to pass (`tests`).
2. **Tablica Projects:** Projects -> New project -> Board; kolumny Todo / W toku / Review / Zrobione;
   dodac istniejace issue (#7 mapa, #8 zasilanie, #15 poprawki); link wkleic do `README.md` i `docs/STATUS.md`.
   (Token uzywany z laptopa nie ma zakresu `project`, wiec tablicy nie da sie zalozyc skryptem.)
3. Wlaczyc GitHub Actions dla repo, jesli sa wylaczone (Settings -> Actions).

## 8. Konwencje nazw

- Branche: `<nick>/<opis-z-myslnikami>`, hotfixy z Pi: `pi/hotfix-<opis>`.
- Commity: pierwsza linia po angielsku lub polsku, tryb rozkazujacy, do 70 znakow, np. `Add lane search pattern`.
- Issue: tytul zaczyna sie od obszaru, np. `ramie: nagrac grasp_near i grasp_far`.
- Pliki ruchow ramienia: `motions/<nazwa>.json`, nazwy `grasp_*`, `drop_*`, `home`.
