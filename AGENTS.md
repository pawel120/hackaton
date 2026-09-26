# AGENTS.md - kiedy i jak uzywac subagentow w tym repo

Subagent to osobna, tansza sesja z wlasnym kontekstem. Oplaca sie tylko wtedy, gdy zadanie
da sie opisac jednym akapitem i sprawdzic testem bez rozmowy. Inaczej rob w glownej sesji.

## Kiedy TAK

- Sterownik z gotowym, opisanym protokolem (np. ramki bipropellant, ASCII do Xiao).
- Narzedzie CLI o jasnym zachowaniu (suwaki HSV, zrzut klatek, odtworzenie ruchu).
- Konwersja formatu danych, porzadki w plikach, README, usuniecie ogonkow.
- Testy do istniejacego modulu.

## Kiedy NIE

- Zmiany w pinecone_bot/brain.py (wspolna logika, decyzje projektowe) - glowna sesja.
- Cokolwiek, co wymaga sprzetu. Agent nie ma robota.
- Zadania zalezne od siebie nawzajem - rob po kolei w jednej sesji.

## Model dla agenta (zawsze podawaj jawnie)

- sonnet: domyslnie dla powyzszych "TAK".
- haiku: czysto mechaniczne (zamiana znakow, przeniesienie pliku, formatowanie).
- opus: gdy agent musi wybrac miedzy podejsciami.
- fable: nie, chyba ze glowna sesja nie umie tego zrobic sama.

## Szablon zlecenia (skopiuj i wypelnij, wszystkie punkty obowiazkowe)

    Repo: C:\...\hackaton. Venv: .venv\Scripts\python.exe. Nie commituj. Nie ruszaj plikow
    poza lista. Pliki czystym ASCII, polskie komentarze bez ogonkow.
    Przeczytaj najpierw: <2-4 pliki>.
    Interfejs, ktory masz zaimplementowac: <sygnatury funkcji/klas, skopiowane doslownie>.
    Fakty, ktorych nie wolno zgadywac: <protokol, jednostki, znaki, porty>.
    Pliki do utworzenia: <lista>.
    Testy, ktore maja przejsc (tests/test_<x>.py): <lista asercji, konkretnie>.
    Na koniec uruchom: .\.venv\Scripts\python.exe -m pytest tests/test_<x>.py -q
    i zamelduj wynik oraz liste zalozen, ktore trzeba sprawdzic na sprzecie.

## Odbior pracy agenta

1. Testy przechodza w glownej sesji (nie wierz meldunkowi, uruchom).
2. Nowe pliki sa ASCII: `python -c "import sys;print([l for l in open(sys.argv[1],'rb') if max(l)>127])" plik`.
3. Zalozenia z meldunku trafiaja do docs/HARDWARE.md albo do issue.
4. Jeden agent naraz, chyba ze zadania sa calkowicie niezalezne (rozne pliki, rozne moduly).

## Przyklady z tego repo

- base.py (Xiao + bipropellant + sim, 3 sterowniki jednego interfejsu): dobry kandydat, sonnet.
- arm.py + record_waypoints.py: dobry kandydat, sonnet; agent sam wykryl, ze grasp_mid.json
  jest sprzed naprawy barku - takie rzeczy z meldunku ida do HARDWARE.md.
- brain.py: NIE, robione w glownej sesji, poprawiane po symulacji.
