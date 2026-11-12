# Changelog

Wszystkie zmiany w programie / All notable changes.

## 1.2.0 – 2026-11-12
*Wersja angielska / English version*

**PL**
- Przełącznik języka **PL / EN** w prawym górnym rogu okna. Po zmianie okno przebudowuje się w nowym języku, a ustawienia zostają.
- Przetłumaczone jest wszystko: okna, przyciski, komunikaty, log i cała Pomoc.
- Przy pierwszym uruchomieniu program wybiera język Windows.
- Wiersz poleceń: nowa opcja `--lang pl|en`.
- README: angielska część z angielskimi nazwami przycisków i zrzutami ekranu.

**EN**
- **PL / EN** language switch in the top-right corner of the window. After switching, the window is rebuilt in the new language and the settings are kept.
- Everything is translated: windows, buttons, messages, the log and the whole Help.
- On first run the app follows your Windows language.
- Command line: new `--lang pl|en` option.
- README: English section with English button names and screenshots.

## 1.1.0 – 2026-11-12
*Ikona programu / App icon*

**PL**
- Program ma własną ikonę z nutą: w pliku exe, na pasku zadań i w oknach programu.

**EN**
- The app has its own music-note icon: on the exe file, in the taskbar and in the app windows.

## 1.0.0 – 2026-11-05
*Pierwsze publiczne wydanie / First public release*

**PL**
- Przy problemach YouTube program **sam zwalnia** (opóźnienie rośnie do 5 s).
- Gdy sesja wygaśnie w trakcie, program **prosi o nowe nagłówki i pracuje dalej** od miejsca przerwania; nagłówki z innego konta są odrzucane.
- Instrukcja z **oknem incognito**, dzięki czemu `browser.json` działa dłużej.
- Numer wersji w tytule okna i opcja `--version`.
- README po polsku i angielsku, zrzuty ekranu, licencja MIT, skrypt `build.bat`.

**EN**
- The app **slows down automatically** when YouTube has problems (delay grows up to 5 s).
- If the session expires mid-run, the app **asks for new headers and continues** where it left off; headers from a different account are rejected.
- Guide now uses an **incognito window**, so `browser.json` lasts longer.
- Version number in the window title and a `--version` option.
- README in Polish and English, screenshots, MIT license, `build.bat`.

## 0.9.1 – 2026-11-04
*Lepsza instrukcja nagłówków / Better header guide*

**PL**
- Instrukcja: przy otwartym F12 wejdź w **Polubione utwory**, wtedy zawsze pojawi się żądanie `browse`.
- Filtr `youtubei` tylko wtedy, gdy `browse` dalej nie ma.

**EN**
- Guide: with F12 open, go to **Liked songs** so the `browse` request always appears.
- Use the `youtubei` filter only if `browse` is still missing.

## 0.9.0 – 2026-11-04
*Wykrywanie wygasłej sesji / Expired session detection*

**PL**
- Gdy YouTube wyloguje plik autoryzacji (HTTP 401), program kończy pracę jednym jasnym komunikatem „SESJA WYGASŁA” zamiast serii błędów.

**EN**
- When YouTube logs out the auth file (HTTP 401), the app stops with one clear "SESJA WYGASŁA" (session expired) message instead of a flood of errors.

## 0.8.1 – 2026-11-04
*Poprawka statusu / Status fix*

**PL**
- Podczas pobierania listy polubionych (1–2 min) pasek pokazuje, co program robi, zamiast mylącego „zakończono”.

**EN**
- While fetching the liked list (1–2 min) the status bar shows what is happening instead of a misleading "finished".

## 0.8.0 – 2026-11-04
*Czytelne liczniki i weryfikacja / Clear counters, verification*

**PL**
- Postęp jako „przetworzono / polubione / do ponowienia” zamiast mylącego „polubiono”.
- Na końcu weryfikacja na koncie: **SPRAWDZONE NA KONCIE: polubione X z Y**.
- Automatyczne ponawianie zapytań przy błędach sieci.

**EN**
- Progress shown as processed / liked / to retry instead of a misleading "liked".
- Final check on the account: **SPRAWDZONE NA KONCIE: polubione X z Y** (verified on account).
- Requests are retried automatically on network errors.

## 0.7.0 – 2026-11-04
*Ponawianie polubień / Like retries*

**PL**
- Nieudane polubienia są odkładane i ponawiane na końcu (2 rundy co 60 s).
- Pojedyncze błędy nie zatrzymują już programu.

**EN**
- Failed likes are deferred and retried at the end (2 rounds, 60 s apart).
- Single errors no longer stop the program.

## 0.6.0 – 2026-11-04
*Popraw nierozpoznane / Fix unrecognized tracks*

**PL**
- Nowe okno **Popraw nierozpoznane...**: nieznalezione utwory poprawiasz ręcznie, po kolei.
- Własny tekst wyszukiwania, typ wyników (Utwory / Filmy / Wszystko), odsłuch w przeglądarce, wklejenie linku YouTube.
- Chwilowe błędy YouTube przy zmianach na koncie są ponawiane.

**EN**
- New **Popraw nierozpoznane...** (Fix unrecognized) window: fix unmatched tracks by hand, one by one.
- Custom search text, result type (Songs / Videos / All), preview in the browser, paste a YouTube link.
- Transient YouTube errors are retried when changing the account.

## 0.5.0 – 2026-11-04
*Duże kolekcje i konta marki / Large collections, brand accounts*

**PL**
- Playlisty powyżej 5000 utworów (limit YouTube) są dzielone na części „Nazwa 2”, „Nazwa 3”…
- Przed zmianami program sprawdza logowanie i pokazuje nazwę konta.
- Obsługa kont marki / kanałów: zmiany trafiają na kanał wybrany w przeglądarce.
- Wklejone nagłówki są czyszczone ze zbędnych pól.
- Po 10 błędach z rzędu program przerywa zamiast generować tysiące błędów.

**EN**
- Playlists above 5000 tracks (YouTube limit) are split into parts "Name 2", "Name 3"…
- Checks the login and shows the account name before making changes.
- Brand accounts / channels: changes go to the channel selected in the browser.
- Pasted headers are cleaned of unneeded fields.
- Stops after 10 errors in a row instead of producing thousands of errors.

## 0.4.0 – 2026-11-03
*Szybsze wyszukiwanie / Faster search*

**PL**
- Wyszukiwanie równoległe: nowe ustawienie **Wątki** (1–8, domyślnie 4).
- Wspólne tempo zapytań dla wszystkich wątków i pauza, gdy YouTube jest przeciążony.
- Nieudane wyszukiwania są ponawiane (3 próby), nie trafiają do cache i wracają przy następnym uruchomieniu.
- Już polubione utwory są pomijane.

**EN**
- Parallel search: new **Wątki** (Threads) setting (1–8, default 4).
- Shared request pacing across threads and a pause when YouTube is overloaded.
- Failed searches are retried (3 attempts), are not cached and come back on the next run.
- Already liked tracks are skipped.

## 0.3.0 – 2026-11-03
*Pomoc w programie / Built-in help*

**PL**
- Okno **Pomoc** (i przyciski **?**) z instrukcją krok po kroku, jak zrobić `browser.json`.
- Przycisk otwierający music.youtube.com.

**EN**
- **Pomoc** (Help) window and **?** buttons with step-by-step `browser.json` instructions.
- Button that opens music.youtube.com.

## 0.2.0 – 2026-11-03
*Okno programu i exe / GUI and exe*

**PL**
- Okno programu: wybór folderów, opcje playlisty, polubień i trybu testowego, log na żywo, Start/Stop.
- Ustawienia są zapamiętywane między uruchomieniami.
- Tworzenie `browser.json` z nagłówków wklejonych z przeglądarki (**Utwórz z nagłówków...**).
- Jeden plik exe, bez instalowania Pythona.
- Odczyt tagów także z uszkodzonych plików MP3; numer ścieżki w nazwie pliku jest pomijany.
- Przyciski **Otwórz raport braków** i **Otwórz folder wyników**.

**EN**
- GUI window: folder pickers, playlist / like / dry-run options, live log, Start/Stop.
- Settings are remembered between runs.
- Creates `browser.json` from request headers pasted from the browser (**Utwórz z nagłówków...**).
- Single-file exe, no Python needed.
- Reads tags from damaged MP3 files too; a leading track number in the file name is ignored.
- Buttons to open the missing-tracks report and the output folder.

## 0.1.0 – 2026-11-03
*Skrypt wiersza poleceń / Command-line script*

**PL**
- Pierwsza wersja: skrypt wiersza poleceń (wymaga Pythona).
- Skanuje folder z FLAC/MP3, czyta artystę i tytuł z tagów albo z nazwy pliku `Artysta - Tytuł`.
- Wyszukuje utwory w YouTube Music, dodaje je do playlisty i opcjonalnie polubia (`--like`).
- Cache wyników wyszukiwania i raport nieznalezionych utworów (CSV), tryb `--dry-run`.

**EN**
- First version: a command-line script (requires Python).
- Scans a FLAC/MP3 folder, reads artist and title from tags or from an `Artist - Title` file name.
- Searches YouTube Music, adds tracks to a playlist and optionally likes them (`--like`).
- Search cache, CSV report of unmatched tracks, `--dry-run` mode.
