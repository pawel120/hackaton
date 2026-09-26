# Praca z Claude Code na tym repo (tanio i skutecznie)

Zasada naczelna: JEDNA SESJA = JEDNA RZECZ. Sesja rosnie w kontekst i kazda kolejna
odpowiedz niesie caly jej bagaz. Krotkie sesje po jednym kroku sa kilka razy tansze
niz jedna dluga.

## Jak zaczac sesje (powiedz to Claude'owi w pierwszej wiadomosci)

1. "Przeczytaj CLAUDE.md i docs/STATUS.md. Dzis robimy tylko: <jeden krok z 'Nastepne 3 kroki'>."
2. Podaj kryterium "zrobione" jednym zdaniem, np. "calibrate_target zapisuje target_row do
   pinecone_config.json i test w tests/ przechodzi".
3. Nie pros o plan calego projektu. Plan jest w docs/RUNBOOK.md i docs/STATUS.md.

## Czego NIE robic (to sa najdrozsze rzeczy)

- Nie kaz Claude'owi "przejrzec repo" ani "zrozumiec projekt". Od tego jest CLAUDE.md + STATUS.md.
- Nie pobieraj plikow z GitHuba przez fetch/WWW. Repo jest sklonowane, Claude czyta lokalnie.
- Nie wlaczaj trybu planowania (plan mode) do zadan ponizej pol dnia. Wystarczy:
  "przeczytaj X i Y, powiedz w 10 zdaniach co proponujesz", potem "rob".
- Nie odpalaj trzech agentow naraz na zadania, ktore od siebie zaleza. Potem trzeba je sklejac.
- Nie pros o "uruchom na Pi i sprawdz". Ty odpalasz, wklejasz traceback + jedno zdanie co widziales.
- Nie opisuj slowami, co robot zrobil. Wklej 30 linii z pinecone_log.csv z okolicy problemu.

## Co robic

- Zadania na 1-3 godziny. Wieksze = kilka issue i kilka sesji.
- Kazda zmiana w pinecone_bot/ ma test. Test jest kryterium odbioru, takze dla agentow.
- Symulacja przed sprzetem: `python -m pinecone_bot.main --sim`. Bledy znaku, zapetlenia,
  migotanie detekcji wychodza tu w 30 s, na trawie kosztuja godzine i baterie.
- Przy sprzecie petla: uruchom -> wklej blad -> poprawka -> uruchom. Nic wiecej.
- Koniec sesji: STATUS.md (3 linijki), LOG.md (wpis), push. Nowa sesja startuje z tego, nie z pamieci.

## Model

- Glowna sesja: domyslny model.
- Agenty (patrz AGENTS.md): sonnet do zadan z gotowym protokolem/testem, opus gdy trzeba
  podjac decyzje projektowa. Fable tylko wyjatkowo.

## Jak wyglada dobra pierwsza wiadomosc

    Przeczytaj CLAUDE.md i docs/STATUS.md. Dzis tylko krok "kalibracja target_row na Pi".
    Kryterium: tools/calibrate_target.py na prawdziwej kamerze zapisuje cx i target_row
    dla grasp_mid do pinecone_config.json. Nie ruszaj brain.py ani base.py.
    Ja odpalam na Pi i wklejam bledy.
