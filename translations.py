"""Angielskie tłumaczenia tekstów programu.

Kluczem jest oryginalny polski tekst z local_to_ytmusic.py (dokładnie ten sam,
łącznie z odstępami i znakami \\n). Brak klucza = zostaje tekst polski.
Szablony z {} są wypełniane przez .format() po tłumaczeniu.
"""

EN: dict[str, str] = {
    # --- skanowanie, wyszukiwanie, playlisty -------------------------------
    "Błąd tagów %s: %s": "Tag error %s: %s",
    "Uszkodzony cache - zaczynam od nowa.": "Damaged cache - starting over.",
    "Import z lokalnej kolekcji": "Imported from a local collection",
    "Nie udało się utworzyć playlisty: {}": "Could not create the playlist: {}",
    "Utworzono playlistę '%s'": "Created playlist '%s'",
    "Playlista '%s': %d utworów": "Playlist '%s': %d tracks",
    "%s '%s' - pauza %d s, ponawiam (%d/%d)": "%s '%s' - pausing %d s, retrying (%d/%d)",
    "YouTube ogranicza zapytania": "YouTube is rate-limiting requests",
    "Błąd ({})": "Error ({})",
    "%s: chwilowy błąd (%s) - ponawiam za %d s": "%s: temporary error (%s) - retrying in %d s",

    # --- plik autoryzacji ---------------------------------------------------
    "Plik autoryzacji nie zawiera nagłówka 'authorization: SAPISIDHASH ...'.\n"
    "Skopiuj nagłówki żądania POST /browse z music.youtube.com (będąc zalogowanym) "
    "i utwórz plik ponownie przyciskiem 'Utwórz z nagłówków...'.":
        "The auth file has no 'authorization: SAPISIDHASH ...' header.\n"
        "Copy the request headers of POST /browse from music.youtube.com (while logged in) "
        "and create the file again with the 'Create from headers...' button.",
    "bez nazwy kanału": "no channel name",
    "Nie można odczytać pliku autoryzacji: {}": "Cannot read the auth file: {}",
    "Nieprawidłowy format pliku autoryzacji.": "Invalid auth file format.",
    "W cookie brakuje '__Secure-3PAPISID' - zaloguj się na "
    "music.youtube.com i skopiuj nagłówki ponownie.":
        "The cookie is missing '__Secure-3PAPISID' - log in to "
        "music.youtube.com and copy the headers again.",

    # --- przebieg importu (log) --------------------------------------------
    "Folder nie istnieje: %s": "Folder does not exist: %s",
    "Brak pliku autoryzacji: %s": "Auth file missing: %s",
    "Skanuję %s ...": "Scanning %s ...",
    "Przerwano skanowanie.": "Scanning stopped.",
    "Unikalnych utworów: %d": "Unique tracks: %d",
    "Już w cache: %d | do wyszukania: %d (wątki: %d)":
        "Already cached: %d | to search: %d (threads: %d)",
    "Wyszukiwanie": "Searching",
    "Wyszukiwanie nieudane '%s': %s": "Search failed '%s': %s",
    "Przerwano - zapisuję postęp.": "Stopped - saving progress.",
    "Dopasowano: %d | brak: %d (-> %s)": "Matched: %d | missing: %d (-> %s)",
    "Nieudane wyszukiwania: %d - zostaną ponowione przy następnym uruchomieniu.":
        "Failed searches: %d - they will be retried on the next run.",
    "Tryb testowy - nic nie zmieniono na koncie.": "Dry run - nothing was changed on the account.",
    "YouTube ma problemy - zwalniam: opóźnienie %g s":
        "YouTube is having problems - slowing down: delay %g s",
    "Nowe nagłówki też nie działają ({}). Skopiuj je ponownie.":
        "The new headers don't work either ({}). Copy them again.",
    "To inne konto: {}. Potrzebne: {}. Przełącz konto na music.youtube.com "
    "i skopiuj nagłówki ponownie.":
        "That's a different account: {}. Needed: {}. Switch the account on "
        "music.youtube.com and copy the headers again.",
    "Nowa sesja OK - konto: %s. Kontynuuję.": "New session OK - account: %s. Continuing.",
    "SESJA WYGASŁA (HTTP 401) - YouTube wylogował plik autoryzacji.":
        "SESSION EXPIRED (HTTP 401) - YouTube logged out the auth file.",
    "Sesja YouTube wygasła - YouTube wylogował plik autoryzacji. "
    "Wklej nowe nagłówki, a program będzie kontynuował.":
        "The YouTube session expired - YouTube logged out the auth file. "
        "Paste new headers and the app will continue.",
    "Konto: %s": "Account: %s",
    "Logowanie do konta nie działa - sesja wygasła albo plik jest zły "
    "(%s). Kliknij 'Utwórz z nagłówków...' i wklej świeże nagłówki "
    "z music.youtube.com - instrukcja pod przyciskiem '?'.":
        "Account login doesn't work - the session expired or the file is wrong "
        "(%s). Click 'Create from headers...' and paste fresh headers "
        "from music.youtube.com - instructions under the '?' button.",
    "Logowanie do konta nie działa - sesja wygasła albo plik jest zły. "
    "Wklej nowe nagłówki.":
        "Account login doesn't work - the session expired or the file is wrong. "
        "Paste new headers.",
    "Playlisty": "Playlists",
    "Do dodania na playlistę: %d (już było: %d)": "To add to the playlist: %d (already there: %d)",
    "Tworzenie '{}'": "Creating '{}'",
    "Playlista": "Playlist",
    "Playlista '{}'": "Playlist '{}'",
    "'%s': partia odrzucona (%s)": "'%s': batch rejected (%s)",
    "'%s': +%d (razem %d)": "'%s': +%d (total %d)",
    "'%s': błąd dodawania partii: %s": "'%s': error adding batch: %s",
    "Pobieram listę polubionych z konta (to trwa 1-2 min, program pracuje)...":
        "Fetching the liked list from the account (takes 1-2 min, the app is working)...",
    "Pobieranie polubionych": "Fetching liked songs",
    "Nie udało się pobrać polubionych (%s) - lubię wszystkie.":
        "Could not fetch liked songs (%s) - liking all.",
    "Do polubienia: %d (już polubione: %d)": "To like: %d (already liked: %d)",
    "Polubienia": "Likes",
    "polubione: {}  |  do ponowienia: {}  |  opóźnienie: {:g} s":
        "liked: {}  |  to retry: {}  |  delay: {:g} s",
    "Like nieudany %s: %s - ponowię później": "Like failed %s: %s - will retry later",
    "Przetworzono %d z %d  |  polubione: %d  |  do ponowienia: %d":
        "Processed %d of %d  |  liked: %d  |  to retry: %d",
    "polubione: {}  |  do ponowienia: {}": "liked: {}  |  to retry: {}",
    "Ponawiam %d nieudanych polubień za %d s (runda %d/%d)...":
        "Retrying %d failed likes in %d s (round %d/%d)...",
    "Ponawianie (runda {}/{})": "Retrying (round {}/{})",
    "polubione łącznie: {}": "liked in total: {}",
    "Ponowiony like OK: %s": "Retried like OK: %s",
    "Ponowiony like nieudany %s: %s": "Retried like failed %s: %s",
    "Przetworzono wszystkie: %d  |  YouTube przyjął polubienia: %d  |  nieudane: %d":
        "Processed all: %d  |  likes accepted by YouTube: %d  |  failed: %d",
    "Sprawdzam polubione na koncie (to trwa 1-2 min, program pracuje)...":
        "Checking liked songs on the account (takes 1-2 min, the app is working)...",
    "Sprawdzanie polubionych": "Checking liked songs",
    "SPRAWDZONE NA KONCIE: polubione %d z %d utworów z kolekcji%s":
        "VERIFIED ON ACCOUNT: liked %d of %d tracks from the collection%s",
    "  |  brakuje: {} - kliknij Start ponownie później": "  |  missing: {} - click Start again later",
    "  - komplet.": "  - complete.",
    "Nie udało się sprawdzić polubionych na koncie: %s": "Could not check liked songs on the account: %s",
    "Sprawdzanie na koncie - zakończone": "Account check - finished",
    "Przerwano.": "Stopped.",
    "SESJA WYGASŁA - YouTube wylogował plik autoryzacji (HTTP 401). "
    "Zrób nowy plik: kliknij 'Utwórz z nagłówków...' i wklej świeże "
    "nagłówki z music.youtube.com, potem Start (zrobione są pomijane).":
        "SESSION EXPIRED - YouTube logged out the auth file (HTTP 401). "
        "Make a new file: click 'Create from headers...' and paste fresh "
        "headers from music.youtube.com, then Start (completed work is skipped).",
    "%d błędów z rzędu - przerywam. Sprawdź połączenie i plik "
    "autoryzacji, potem uruchom ponownie (zrobione rzeczy są pomijane).":
        "%d errors in a row - stopping. Check your connection and the auth "
        "file, then run again (completed work is skipped).",
    "Gotowe.": "Done.",
    "Błąd: %s": "Error: %s",
    "Ręcznie przypisano: %s -> %s": "Assigned manually: %s -> %s",

    # --- okno główne -------------------------------------------------------
    "Gotowy.": "Ready.",
    "Wszystkie": "All files",
    "Folder z muzyką:": "Music folder:",
    "Wybierz...": "Browse...",
    "Plik autoryzacji:": "Auth file:",
    "Utwórz z nagłówków...": "Create from headers...",
    "Folder wyników:": "Output folder:",
    "Playlista (opcjonalnie):": "Playlist (optional):",
    "Polub dopasowane utwory": "Like matched tracks",
    "Tylko test (nic nie zmieniaj na koncie)": "Dry run (change nothing on the account)",
    "Opóźnienie [s]:": "Delay [s]:",
    "Wątki:": "Threads:",
    "Otwórz raport braków": "Open missing report",
    "Popraw nierozpoznane...": "Fix unrecognized...",
    "Otwórz folder wyników": "Open output folder",
    "Pomoc": "Help",
    "Opóźnienie musi być liczbą.": "Delay must be a number.",
    "Wątki: liczba od 1 do {}.": "Threads: a number from 1 to {}.",
    "Wybierz istniejący folder z muzyką.": "Choose an existing music folder.",
    "Brak pliku autoryzacji.\nUżyj przycisku 'Utwórz z nagłówków...'.\n\n"
    "(W trybie 'Tylko test' plik nie jest potrzebny.)":
        "No auth file.\nUse the 'Create from headers...' button.\n\n"
        "(In 'Dry run' mode the file is not needed.)",
    "Nie podano playlisty ani polubień - zostanie wykonane tylko "
    "wyszukiwanie. Kontynuować?":
        "No playlist or likes selected - only the search will run. Continue?",
    "Zatrzymywanie...": "Stopping...",
    "Nie ma jeszcze:\n{}": "Doesn't exist yet:\n{}",
    "{} - przetworzono {}/{}": "{} - processed {}/{}",
    "Sesja wygasła - wklej nowe nagłówki (praca wstrzymana)":
        "Session expired - paste new headers (work paused)",
    "Błąd - zobacz log.": "Error - see the log.",
    "Praca trwa. Przerwać i zamknąć?": "Work in progress. Stop and close?",
    "Zmień język po zakończeniu pracy (albo kliknij Stop).":
        "Change the language after the work finishes (or click Stop).",

    # --- okno pomocy -------------------------------------------------------
    "Pomoc - {}": "Help - {}",
    "Otwórz music.youtube.com": "Open music.youtube.com",
    "Zamknij": "Close",

    # --- okno "Popraw nierozpoznane" ---------------------------------------
    "Najpierw uruchom wyszukiwanie (Start) - lista nierozpoznanych powstanie po nim.":
        "Run the search first (Start) - it creates the list of unrecognized tracks.",
    "Brak nierozpoznanych utworów.": "No unrecognized tracks.",
    "Popraw nierozpoznane": "Fix unrecognized tracks",
    "Utwory": "Songs",
    "Filmy": "Videos",
    "Wszystko": "All",
    "Szukaj:": "Search:",
    "Szukaj": "Search",
    "Artysta": "Artist",
    "Tytuł": "Title",
    "Album": "Album",
    "Czas": "Time",
    "Typ": "Type",
    "✓ Użyj zaznaczonego": "✓ Use selected",
    "▶ Odsłuchaj w przeglądarce": "▶ Listen in browser",
    "← Poprzedni": "← Previous",
    "Pomiń →": "Skip →",
    "Usuń przypisanie": "Remove assignment",
    "Lub wklej link YouTube:": "Or paste a YouTube link:",
    "Użyj linku": "Use link",
    "Poprawki zapisują się od razu. Kliknij potem Start w "
    "głównym oknie, żeby je polubić / dodać do playlisty.":
        "Fixes are saved immediately. Then click Start in the "
        "main window to like them / add them to the playlist.",
    "Nierozpoznane: {}  |  poprawione: {}  |  zostało: {}":
        "Unrecognized: {}  |  fixed: {}  |  left: {}",
    "Przypisano: {}": "Assigned: {}",
    "Szukam...": "Searching...",
    "utwór": "song",
    "film": "video",
    "Błąd wyszukiwania: {} - spróbuj ponownie.": "Search error: {} - try again.",
    "Brak wyników - zmień zapytanie albo typ (Filmy / Wszystko).":
        "No results - change the query or the type (Videos / All).",
    "Wyników: {}. Dwuklik lub '✓ Użyj' = przypisz.":
        "Results: {}. Double-click or '✓ Use' = assign.",
    "  (obecnie przypisano: {})": "  (currently assigned: {})",
    "Nie można zapisać cache:\n{}": "Cannot save the cache:\n{}",
    "Usunięto przypisanie.": "Assignment removed.",
    "Zaznacz wynik na liście.": "Select a result in the list.",
    "Nie rozpoznano linku.\nPrzykład: "
    "https://music.youtube.com/watch?v=dQw4w9WgXcQ":
        "Link not recognized.\nExample: "
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ",

    # --- okno autoryzacji --------------------------------------------------
    "Autoryzacja YouTube Music": "YouTube Music authorization",
    "Rada: żeby sesja nie wygasała, skopiuj nagłówki z OKNA INCOGNITO "
    "(Ctrl+Shift+N), a po zapisaniu zamknij to okno (nie wylogowuj się). "
    "Otwarta karta YouTube co kilka minut wymienia logowanie i stary "
    "plik przestaje działać.":
        "Tip: to keep the session from expiring, copy the headers from an INCOGNITO "
        "WINDOW (Ctrl+Shift+N) and close that window after saving (don't log out). "
        "An open YouTube tab rotates the login every few minutes and the old "
        "file stops working.",
    "Wklej poniżej nagłówki żądania POST /browse z music.youtube.com "
    "(F12 → Network → filtr 'browse' → Headers → Request Headers).\n"
    "Przy otwartym F12 wejdź w YT Music w 'Polubione utwory' - wtedy "
    "pojawi się 'browse'. Tylko gdy dalej go nie ma: filtr 'youtubei' "
    "i dowolne żądanie POST.\n"
    "Dokładna instrukcja: przycisk ?\n\n"
    "Plik browser.json daje pełny dostęp do konta - nie udostępniaj go.":
        "Paste the request headers of POST /browse from music.youtube.com below "
        "(F12 → Network → filter 'browse' → Headers → Request Headers).\n"
        "With F12 open, go to 'Liked songs' in YT Music - then "
        "'browse' appears. Only if it is still missing: filter 'youtubei' "
        "and any POST request.\n"
        "Detailed guide: the ? button\n\n"
        "The browser.json file gives full access to your account - don't share it.",
    "Wklej nagłówki.": "Paste the headers.",
    "Nie udało się:\n{}": "Failed:\n{}",
    "Nie można zapisać:\n{}": "Cannot save:\n{}",
    "Zapisano:\n{}\n\nAle test logowania się nie udał ({}).\nSkopiuj nagłówki ponownie.":
        "Saved:\n{}\n\nBut the login test failed ({}).\nCopy the headers again.",
    "Zapisano:\n{}\n\nZalogowano jako:\n{}\n\nJeśli to nie to konto - przełącz "
    "konto na music.youtube.com i skopiuj nagłówki ponownie.":
        "Saved:\n{}\n\nLogged in as:\n{}\n\nIf this is the wrong account, switch "
        "the account on music.youtube.com and copy the headers again.",
    "\n\nProgram kontynuuje pracę.": "\n\nThe app continues working.",
    "Zapisz": "Save",
    "Anuluj": "Cancel",
    " (przerwij pracę)": " (stop the work)",

    # --- wiersz poleceń ----------------------------------------------------
    "Przenosi lokalne FLAC/MP3 do YouTube Music (polubienia i playlisty).":
        "Moves local FLAC/MP3 files to YouTube Music (likes and playlists).",
    "folder na cache i raport": "folder for the cache and report",
    "nazwa playlisty docelowej": "target playlist name",
    "polub dopasowane": "like matched tracks",
    "tylko skan + szukanie": "scan + search only",
    "równoległe wyszukiwania (1-{})": "parallel searches (1-{})",
    "język komunikatów": "message language",
}


HELP_EN = """\
HOW TO CREATE THE AUTH FILE (browser.json)
==========================================
You do this once. The app remembers the file afterwards.

1. Open an INCOGNITO WINDOW (Chrome/Edge: Ctrl+Shift+N, Firefox: private
   window Ctrl+Shift+P) and go to https://music.youtube.com
   Log in to the account the music should go to (if you have several
   channels, switch to the right one). Why incognito - see step 5.

2. Press F12 (developer tools) and open the "Network" tab.

3. With F12 open, go to your LIKED SONGS in YouTube Music:
   "Library" -> "Liked songs" (or the "Liked" playlist).
   This always creates a "browse" request.
   (Just refreshing the page with F5 often does NOT create it, and the
   Network list only shows requests made AFTER F12 was opened.)

4. In the filter box (Filter) type:  browse
   Click the "browse?..." request with method POST and status 200.
   (The Method column shows on hover or in the details.)
   Make sure "All" or "Fetch/XHR" is selected above the list,
   not e.g. "Img" or "JS".

   ONLY if "browse" is still missing: type  youtubei  in the filter
   and take any POST request from the list (e.g. "next" after clicking
   a song) - it has the same login headers and works too.

5. In the right panel open the "Headers" tab and find the
   "Request Headers" section.
   (If you also copy "General" or "Response Headers", the app filters
   them out.)
     - Chrome/Edge: select the whole Request Headers section with the
       mouse (first to last line) and copy with Ctrl+C.
       You can also turn on the "Raw" switch and copy everything.
     - Firefox: in "Request Headers" turn on the "Raw" switch,
       select everything and copy with Ctrl+C.

   BEST DONE IN AN INCOGNITO WINDOW (Ctrl+Shift+N); after saving the
   file, close that window (don't log out - just close it).
   An open YouTube tab rotates the login every few minutes and then
   the copied file stops working ("SESSION EXPIRED"). A closed incognito
   window no longer rotates anything, so the file keeps working.
   If the session expires during work, the app opens a window to paste
   new headers by itself and continues after you save.

6. In this app click "Create from headers...", paste (Ctrl+V)
   and click "Save". The file is saved to the path in the
   "Auth file" field (next to the app by default).

The copied headers MUST include, among others:
   authorization: SAPISIDHASH ...
   cookie: ... __Secure-3PAPISID=... ...
If the app says they are missing: the wrong request was copied
(e.g. GET instead of POST) or you are not logged in.

IMPORTANT
 - browser.json gives full access to your YouTube account. Never send
   it to anyone and never upload it to the internet.
 - The file stops working after you log out of YouTube in that browser
   or when the browser rotates the login (an open YouTube tab).
   That's why it's best to make it in an incognito window and then close it.


HOW TO USE THE APP
==================
Music folder      - folder with FLAC/MP3 files. Subfolders are
                    searched automatically.
Auth file         - browser.json (see above).
Output folder     - the cache (ytm_cache.json) and the report of
                    unmatched tracks (ytm_not_found.csv) go here.
Playlist          - playlist name. If it doesn't exist, it is created
                    (private). Empty = no playlist.
                    YouTube allows max 5000 tracks per playlist -
                    the rest goes automatically to "Name 2",
                    "Name 3" etc. Tracks already there are skipped.
Like              - marks matched tracks as "Liked".
Dry run           - only scans and searches, changes nothing on the
                    account. Needs no auth file. Recommended first.
Delay             - pause after each request in each thread
                    (seconds). Don't go below 1 s.
Threads           - parallel searches (1-8, default 4).
                    More = faster, but YouTube may start limiting
                    requests - the app then pauses and retries by
                    itself. Searching is done WITHOUT logging in, so
                    it doesn't load your account.
                    Playlist and likes run one by one, on the account.

Time (approx., 7000 tracks, 4 threads):
  search about 1 h, playlist a few minutes,
  likes about 2.5-4 h (YouTube only allows liking one at a time).
  Already liked tracks are skipped.

Errors: YouTube rejects a single request now and then. The app
retries right away (up to 3 attempts), and tracks that still fail are
put aside and retried at the end (2 rounds, 60 s apart). On errors it
raises the delay by itself (up to 5 s). If something is left, just
click Start again later. For a large collection a delay of 3 s is
recommended.

At the end the app fetches the liked list from the account and shows
"VERIFIED ON ACCOUNT: liked X of Y" - that is the real result.

Artist and title come from the tags. If they are missing, from the
file name in the format "Artist - Title" (a leading track number is
ignored).

FIX UNRECOGNIZED
After searching click "Fix unrecognized...". For each track the app
didn't find:
  - edit the text in the "Search" field (e.g. title only, different
    spelling) and press Enter,
  - switch the type to "Videos" or "All" if the track isn't available
    as a "song" (e.g. music videos, live recordings),
  - "Listen in browser" - check that it's the right track,
  - "Use selected" (or double-click) - assign it and move on,
  - or find it yourself on YouTube and paste the link in "Or paste".
"Skip" moves on without assigning. Fixes are saved immediately -
then click Start to like them / add them to the playlist (the rest is
skipped, so it's quick).

Cache: tracks already searched are not searched again on the next
run. Delete ytm_cache.json to search everything again.
Stop interrupts the work and saves progress (no account changes if
stopped during the search).
"""
