#!/usr/bin/env python3
"""Skanuje lokalne FLAC/MP3, dopasowuje utwory w katalogu YouTube Music
i dodaje je do playlisty oraz (opcjonalnie) oznacza jako polubione.

Uruchomienie bez argumentów otwiera okno (GUI).

Wymagania (tylko przy uruchamianiu jako .py):
    pip install ytmusicapi mutagen

Autoryzacja (jednorazowo):
    W oknie: przycisk "Utwórz z nagłówków..." - wklej nagłówki żądania /browse
    z music.youtube.com (DevTools -> Network). Powstaje browser.json
    (TRZYMAJ PRYWATNIE - to pełny dostęp do konta).

Użycie z linii poleceń (opcjonalnie):
    python local_to_ytmusic.py "D:/Muzyka" --dry-run
    python local_to_ytmusic.py "D:/Muzyka" --like --playlist "Moja kolekcja"
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import queue
import re
import sys
import threading
import time
import unicodedata
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from mutagen import File as MutagenFile
from mutagen import MutagenError
from mutagen.easyid3 import EasyID3
from ytmusicapi import LikeStatus, YTMusic
from ytmusicapi.auth.browser import setup_browser

APP_NAME = "Local → YouTube Music"
AUDIO_EXT: frozenset[str] = frozenset({".flac", ".mp3"})
CACHE_NAME = "ytm_cache.json"
REPORT_NAME = "ytm_not_found.csv"
AUTH_NAME = "browser.json"
SETTINGS_NAME = "ytm_settings.json"
BATCH_SIZE = 50
PLAYLIST_LIMIT = 5000  # limit YouTube na jedną playlistę
DEFAULT_DELAY_S = 1.0
DEFAULT_WORKERS = 4
MAX_WORKERS = 8
SEARCH_RETRIES = 3
MAX_FAILS_IN_ROW = 10
LATER_ROUNDS = 2       # ile razy na końcu ponowić nieudane polubienia
LATER_PAUSE_S = 60     # przerwa przed każdą rundą ponawiania

log = logging.getLogger("ytm")


def app_dir() -> Path:
    """Folder programu: obok .exe (PyInstaller) albo obok skryptu .py."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


# --------------------------------------------------------------------------
# Logika
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Track:
    artist: str
    title: str

    @property
    def key(self) -> str:
        return f"{self.artist.lower()}|{self.title.lower()}"

    @property
    def query(self) -> str:
        return f"{self.artist} {self.title}".strip()


@dataclass
class Config:
    folder: Path
    auth: Path
    out_dir: Path
    playlist: str = ""
    like: bool = False
    dry_run: bool = False
    delay: float = DEFAULT_DELAY_S
    workers: int = DEFAULT_WORKERS

    @property
    def cache_file(self) -> Path:
        return self.out_dir / CACHE_NAME

    @property
    def report_file(self) -> Path:
        return self.out_dir / REPORT_NAME


class Stopped(Exception):
    """Użytkownik przerwał pracę."""


class TooManyFailures(Exception):
    """Zbyt wiele błędów z rzędu przy zmianach na koncie."""


def _first(tags: object, name: str) -> str:
    """Zwraca pierwszą wartość tagu (EasyID3 / Vorbis) albo pusty string."""
    try:
        value = tags.get(name)  # type: ignore[attr-defined]
    except (KeyError, ValueError):
        return ""
    if isinstance(value, list) and value:
        return str(value[0]).strip()
    return ""


# Numer ścieżki na początku nazwy: "01 - ", "01. ", "1_", "01) " albo "01 ".
# Wymaga separatora (lub zera wiodącego), żeby nie obcinać "50 Cent", "2Pac".
_TRACKNO_RE = re.compile(r"^(?:\d{1,3}\s*[.\-_)]\s*|0\d\s+)")


def read_track(path: Path) -> Track | None:
    """Czyta artystę/tytuł z tagów; fallback: nazwa pliku 'Artysta - Tytuł'."""
    artist = title = ""
    try:
        audio = MutagenFile(path, easy=True)
        if audio is not None and audio.tags is not None:
            artist = _first(audio.tags, "artist")
            title = _first(audio.tags, "title")
    except (MutagenError, OSError) as exc:
        # Uszkodzony strumień MP3 - spróbuj odczytać same tagi ID3.
        try:
            if path.suffix.lower() != ".mp3":
                raise exc
            id3 = EasyID3(path)
            artist, title = _first(id3, "artist"), _first(id3, "title")
        except (MutagenError, OSError):
            log.warning("Błąd tagów %s: %s", path.name, exc)

    if not (artist and title):
        stem = _TRACKNO_RE.sub("", path.stem)
        if " - " in stem:
            f_artist, f_title = (p.strip() for p in stem.split(" - ", 1))
            artist = artist or f_artist
            title = title or f_title
        elif not title:
            title = stem.strip()

    return Track(artist, title) if title else None


def scan(root: Path, stop: threading.Event | None = None) -> list[Track]:
    seen: dict[str, Track] = {}
    for path in root.rglob("*"):
        if stop is not None and stop.is_set():
            raise Stopped
        if path.suffix.lower() in AUDIO_EXT and path.is_file():
            track = read_track(path)
            if track and track.key not in seen:
                seen[track.key] = track
    return list(seen.values())


def load_cache(path: Path) -> dict[str, str | None]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            log.warning("Uszkodzony cache - zaczynam od nowa.")
    return {}


def save_cache(path: Path, cache: dict[str, str | None]) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def _norm(text: str) -> str:
    """Małe litery, bez akcentów i znaków niealfanumerycznych."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[\W_]", "", text)


def find_video_id(yt: YTMusic, track: Track) -> str | None:
    """Szuka utworu (filtr 'songs'); akceptuje wynik z pasującym artystą."""
    results = yt.search(track.query, filter="songs", limit=5)
    want = _norm(track.artist)
    for res in results:
        vid = res.get("videoId")
        if not vid:
            continue
        if not want:
            return vid
        got = _norm(" ".join(a.get("name", "") for a in res.get("artists") or []))
        if got and (want in got or got in want):
            return vid
    return None


def part_name(base: str, n: int) -> str:
    """Nazwa n-tej części: 'Baza', 'Baza 2', 'Baza 3'..."""
    return base if n == 1 else f"{base} {n}"


def create_playlist(yt: YTMusic, name: str) -> str:
    result = yt.create_playlist(name, "Import z lokalnej kolekcji", "PRIVATE")
    if not isinstance(result, str):
        raise RuntimeError(f"Nie udało się utworzyć playlisty: {result}")
    log.info("Utworzono playlistę '%s'", name)
    return result


def load_playlist_parts(yt: YTMusic, base: str) -> tuple[list[list], set[str]]:
    """Istniejące części playlisty: [[nazwa, id, liczba_utworów], ...] + ich videoId."""
    library = {}
    for pl in yt.get_library_playlists(limit=None):
        library.setdefault(pl.get("title"), pl.get("playlistId"))
    parts: list[list] = []
    existing: set[str] = set()
    n = 1
    while (pid := library.get(part_name(base, n))) is not None:
        pl = yt.get_playlist(pid, limit=None)
        ids = [t.get("videoId") for t in pl.get("tracks") or [] if t.get("videoId")]
        count = max(len(ids), int(pl.get("trackCount") or 0))
        existing.update(ids)
        parts.append([part_name(base, n), pid, count])
        log.info("Playlista '%s': %d utworów", part_name(base, n), count)
        n += 1
    return parts, existing


AUTH_HINT = (
    "Plik autoryzacji nie zawiera nagłówka 'authorization: SAPISIDHASH ...'.\n"
    "Skopiuj nagłówki żądania POST /browse z music.youtube.com (będąc zalogowanym) "
    "i utwórz plik ponownie przyciskiem 'Utwórz z nagłówków...'."
)


HELP_TEXT = """\
JAK UTWORZYĆ PLIK AUTORYZACJI (browser.json)
============================================
Plik robisz raz. Potem program go zapamiętuje.

1. Otwórz Chrome, Edge albo Firefox i wejdź na https://music.youtube.com
   Zaloguj się na konto, na które ma trafić muzyka.

2. Naciśnij F12 (narzędzia deweloperskie) i przejdź do zakładki
   "Network" (po polsku: "Sieć").

3. Odśwież stronę (F5) albo kliknij w YouTube Music "Biblioteka",
   żeby pojawiły się żądania.

4. W polu filtra (Filter) wpisz:  browse
   Kliknij żądanie "browse?..." z metodą POST i statusem 200.
   (Kolumnę Metoda/Method widać po najechaniu albo w szczegółach.)

5. W prawym panelu otwórz zakładkę "Headers" (Nagłówki)
   i znajdź sekcję "Request Headers" (Nagłówki żądania).
   (Jeśli skopiujesz przy okazji "General" albo "Response Headers",
   program sam je odfiltruje.)
     - Chrome/Edge: zaznacz myszką całą sekcję Request Headers
       (od pierwszej do ostatniej linii) i skopiuj Ctrl+C.
       Można też włączyć przełącznik "Raw" i skopiować całość.
     - Firefox: w "Request Headers" włącz przełącznik "Raw"
       (Nieprzetworzone), zaznacz wszystko i skopiuj Ctrl+C.

6. W tym programie kliknij "Utwórz z nagłówków...", wklej (Ctrl+V)
   i kliknij "Zapisz". Plik zapisze się w ścieżce z pola
   "Plik autoryzacji" (domyślnie obok programu).

Skopiowane nagłówki MUSZĄ zawierać m.in.:
   authorization: SAPISIDHASH ...
   cookie: ... __Secure-3PAPISID=... ...
Jeśli program zgłasza, że ich brakuje: skopiowano złe żądanie
(np. GET zamiast POST) albo nie jesteś zalogowany.

WAŻNE
 - browser.json daje pełny dostęp do konta YouTube. Nie wysyłaj go
   nikomu i nie wrzucaj do internetu.
 - Plik działa, dopóki nie wylogujesz się z YouTube w tej
   przeglądarce. Po wylogowaniu zrób go ponownie.


JAK UŻYWAĆ PROGRAMU
===================
Folder z muzyką   - folder z plikami FLAC/MP3. Podfoldery są
                    przeszukiwane automatycznie.
Plik autoryzacji  - browser.json (patrz wyżej).
Folder wyników    - tu trafia cache (ytm_cache.json) i raport utworów
                    nieznalezionych (ytm_not_found.csv).
Playlista         - nazwa playlisty. Jeśli nie istnieje, zostanie
                    utworzona (prywatna). Puste = bez playlisty.
                    YouTube mieści max 5000 utworów na playlistę -
                    nadmiar trafia automatycznie do "Nazwa 2",
                    "Nazwa 3" itd. Utwory już obecne są pomijane.
Polub             - oznacza dopasowane utwory jako "Lubię to".
Tylko test        - tylko skanuje i szuka, nic nie zmienia na koncie.
                    Nie wymaga pliku autoryzacji. Zalecane na start.
Opóźnienie        - przerwa po każdym zapytaniu w każdym wątku
                    (sekundy). Nie schodź poniżej 1 s.
Wątki             - ile wyszukiwań naraz (1-8, domyślnie 4).
                    Więcej = szybciej, ale YouTube może zacząć
                    ograniczać zapytania - program wtedy sam robi
                    przerwę i ponawia. Wyszukiwanie odbywa się BEZ
                    logowania, więc nie obciąża Twojego konta.
                    Playlista i polubienia idą po kolei, z konta.

Czas (orientacyjnie, 7000 utworów, 4 wątki):
  wyszukiwanie ok. 1 h, playlista kilka minut,
  polubienia ok. 2,5-4 h (YouTube pozwala lubić tylko po jednym).
  Już polubione utwory są pomijane.

Błędy: YouTube co jakiś czas odrzuca pojedyncze zapytanie. Program
ponawia od razu (do 3 prób), a utwory, które dalej nie przeszły,
odkłada i ponawia na końcu (2 rundy, co 60 s). Jeśli coś zostanie,
wystarczy później kliknąć Start ponownie.

Artysta i tytuł są brane z tagów. Gdy ich brak, z nazwy pliku
w formacie "Artysta - Tytuł" (numer ścieżki z przodu jest pomijany).

POPRAW NIEROZPOZNANE
Po wyszukiwaniu kliknij "Popraw nierozpoznane...". Dla każdego
utworu, którego program nie znalazł:
  - popraw tekst w polu "Szukaj" (np. sam tytuł, inna pisownia)
    i naciśnij Enter,
  - zmień typ na "Filmy" lub "Wszystko", jeśli utworu nie ma jako
    "utwór" (np. teledyski, nagrania koncertowe),
  - "Odsłuchaj w przeglądarce" - sprawdź, czy to ten kawałek,
  - "Użyj zaznaczonego" (albo dwuklik) - przypisz i przejdź dalej,
  - albo znajdź sam na YouTube i wklej link w "Lub wklej link".
"Pomiń" przechodzi dalej bez przypisania. Poprawki zapisują się od
razu - potem kliknij Start, żeby je polubić / dodać do playlisty
(reszta jest pomijana, więc idzie szybko).

Cache: utwory już wyszukane nie są szukane ponownie przy kolejnym
uruchomieniu. Usuń ytm_cache.json, żeby wyszukać wszystko od nowa.
Stop przerywa pracę i zapisuje postęp (bez zmian na koncie, jeśli
przerwano w trakcie wyszukiwania).
"""


# Nagłówki ŻĄDANIA potrzebne do pracy na koncie. Wszystko inne (sekcja
# "General" i "Response Headers" skopiowane z Chrome, np. "Request URL",
# "Status Code", "date", "server") powoduje odrzucenie przez Google (HTTP 400).
AUTH_HEADERS = frozenset({
    "accept", "accept-language", "authorization", "content-type", "cookie",
    "origin", "referer", "user-agent", "x-goog-authuser", "x-goog-pageid",
    "x-goog-visitor-id", "x-origin", "x-youtube-bootstrap-logged-in",
    "x-youtube-client-name", "x-youtube-client-version",
})


def clean_headers(data: dict) -> dict[str, str]:
    return {str(k).strip().lower(): str(v).strip() for k, v in data.items()
            if str(k).strip().lower() in AUTH_HEADERS}


def load_auth(path: Path) -> str:
    """Oczyszczone nagłówki z browser.json jako JSON dla YTMusic()."""
    return json.dumps(clean_headers(json.loads(path.read_text(encoding="utf-8"))))


def account_label(yt: YTMusic) -> str:
    info = yt.get_account_info()
    return f"{info.get('accountName', '?')} ({info.get('channelHandle') or 'bez nazwy kanału'})"


def auth_problem(path: Path) -> str | None:
    """Zwraca opis problemu z plikiem browser.json albo None, gdy jest OK."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"Nie można odczytać pliku autoryzacji: {exc}"
    if not isinstance(data, dict):
        return "Nieprawidłowy format pliku autoryzacji."
    headers = clean_headers(data)
    if "SAPISIDHASH" not in headers.get("authorization", ""):
        return AUTH_HINT
    if "__Secure-3PAPISID" not in headers.get("cookie", ""):
        return ("W cookie brakuje '__Secure-3PAPISID' - zaloguj się na "
                "music.youtube.com i skopiuj nagłówki ponownie.")
    return None


class RetryingYTMusic(YTMusic):
    """YTMusic, który ponawia pojedyncze zapytania odrzucone chwilowo przez YouTube
    (pusta/HTML odpowiedź, HTTP 429/5xx, zerwane połączenie). Dzięki temu np. długa
    lista polubionych (dziesiątki stron) nie pada przez jedną złą stronę."""

    REQUEST_TRIES = 4

    def _send_request(self, endpoint: str, body: dict, additionalParams: str = "") -> dict:
        for attempt in range(1, self.REQUEST_TRIES + 1):
            try:
                return super()._send_request(endpoint, body, additionalParams)
            except Exception as exc:
                transient = isinstance(exc, (json.JSONDecodeError, OSError)) or any(
                    f"HTTP {c}" in str(exc) for c in (429, 500, 502, 503, 504))
                if not transient or attempt == self.REQUEST_TRIES:
                    raise
                time.sleep(1.5 * attempt)
        raise RuntimeError("unreachable")


class Throttle:
    """Wspólna dla wątków pauza, gdy YouTube zaczyna odrzucać zapytania."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._until = 0.0

    def wait(self, stop: threading.Event) -> None:
        while True:
            with self._lock:
                remaining = self._until - time.monotonic()
            if remaining <= 0:
                return
            if stop.wait(min(remaining, 0.5)):
                raise Stopped

    def penalize(self, seconds: float) -> None:
        with self._lock:
            self._until = max(self._until, time.monotonic() + seconds)


_local = threading.local()


def _search_client() -> YTMusic:
    """Osobny, niezalogowany klient na wątek - wyszukiwanie nie obciąża konta."""
    yt = getattr(_local, "yt", None)
    if yt is None:
        yt = _local.yt = RetryingYTMusic()
    return yt


def search_one(track: Track, delay: float, stop: threading.Event,
               throttle: Throttle) -> str | None:
    for attempt in range(1, SEARCH_RETRIES + 1):
        throttle.wait(stop)
        if stop.is_set():
            raise Stopped
        try:
            vid = find_video_id(_search_client(), track)
        except Exception as exc:
            if attempt == SEARCH_RETRIES:
                raise
            limited = "HTTP 429" in str(exc)
            pause = (60 if limited else 10) * attempt
            log.warning("%s '%s' - pauza %d s, ponawiam (%d/%d)",
                        "YouTube ogranicza zapytania" if limited else f"Błąd ({exc})",
                        track.query, pause, attempt, SEARCH_RETRIES - 1)
            throttle.penalize(pause)
            continue
        stop.wait(delay)
        return vid
    return None


def with_retry(fn: Callable, stop: threading.Event, what: str, attempts: int = 3):
    """YouTube co jakiś czas odrzuca pojedyncze zapytanie - ponów z przerwą."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == attempts:
                raise
            pause = 5 * attempt
            log.info("%s: chwilowy błąd (%s) - ponawiam za %d s", what, exc, pause)
            if stop.wait(pause):
                raise Stopped from exc
    return None


ProgressCb = Callable[..., None]  # (etap, przetworzono, z_ilu, [dodatkowy_opis])


def run_import(
    cfg: Config,
    stop: threading.Event | None = None,
    progress: ProgressCb | None = None,
) -> int:
    """Cały proces. Zwraca kod wyjścia (0 = OK)."""
    stop = stop or threading.Event()
    progress = progress or (lambda *_: None)

    def check_stop() -> None:
        if stop.is_set():
            raise Stopped

    if not cfg.folder.is_dir():
        log.error("Folder nie istnieje: %s", cfg.folder)
        return 1
    if not cfg.dry_run:  # wyszukiwanie działa bez konta; konto tylko do zmian
        if not cfg.auth.is_file():
            log.error("Brak pliku autoryzacji: %s", cfg.auth)
            return 1
        if problem := auth_problem(cfg.auth):
            log.error("%s", problem)
            return 1
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    log.info("Skanuję %s ...", cfg.folder)
    try:
        tracks = scan(cfg.folder, stop)
    except Stopped:
        log.warning("Przerwano skanowanie.")
        return 130
    log.info("Unikalnych utworów: %d", len(tracks))
    if not tracks:
        return 0

    cache = load_cache(cfg.cache_file)
    todo = [t for t in tracks if t.key not in cache]
    total = len(tracks)
    done = total - len(todo)
    log.info("Już w cache: %d | do wyszukania: %d (wątki: %d)", done, len(todo), cfg.workers)
    progress("Wyszukiwanie", done, total)

    throttle = Throttle()
    failed = 0
    stopped = False
    pool = ThreadPoolExecutor(max_workers=max(1, cfg.workers))
    try:
        futures = {pool.submit(search_one, t, cfg.delay, stop, throttle): t for t in todo}
        for n, fut in enumerate(as_completed(futures), 1):
            track = futures[fut]
            try:
                vid = fut.result()
            except Stopped:
                raise
            except Exception as exc:  # po ponowieniach - pomiń, nie cache'uj
                failed += 1
                log.warning("Wyszukiwanie nieudane '%s': %s", track.query, exc)
                vid = None
            else:
                cache[track.key] = vid
            log.info("[%d/%d] %s %s", done + n, total, "OK " if vid else "---", track.query)
            progress("Wyszukiwanie", done + n, total)
            if n % 50 == 0:
                save_cache(cfg.cache_file, cache)
            check_stop()
    except (Stopped, KeyboardInterrupt):
        stopped = True
        stop.set()
        log.warning("Przerwano - zapisuję postęp.")
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
        save_cache(cfg.cache_file, cache)

    found: list[str] = []
    missing: list[Track] = []
    for track in tracks:  # kolejność jak na dysku
        if track.key in cache:
            vid = cache[track.key]
            (found.append(vid) if vid else missing.append(track))

    with cfg.report_file.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["artist", "title"])
        writer.writerows((t.artist, t.title) for t in missing)

    log.info("Dopasowano: %d | brak: %d (-> %s)", len(found), len(missing), cfg.report_file)
    if failed:
        log.warning("Nieudane wyszukiwania: %d - zostaną ponowione przy następnym "
                    "uruchomieniu.", failed)

    # Po przerwaniu nie zmieniamy konta na podstawie niepełnych wyników.
    if stopped:
        return 130
    if cfg.dry_run:
        log.info("Tryb testowy - nic nie zmieniono na koncie.")
        return 0
    if not found:
        return 0

    unique = list(dict.fromkeys(found))
    yt = RetryingYTMusic(load_auth(cfg.auth))
    # Test logowania przed zmianami - zamiast tysięcy błędów jeden czytelny.
    try:
        log.info("Konto: %s", account_label(yt))
    except Exception as exc:
        log.error("Logowanie do konta nie działa (%s). Utwórz plik autoryzacji "
                  "ponownie - instrukcja pod przyciskiem '?'.", exc)
        return 1

    fails = 0

    def failure(msg: str, *args: object) -> None:
        """Liczy błędy z rzędu; po MAX_FAILS_IN_ROW przerywa zamiast mielić dalej."""
        nonlocal fails
        fails += 1
        log.warning(msg, *args)
        if fails >= MAX_FAILS_IN_ROW:
            raise TooManyFailures

    try:
        if cfg.playlist:
            # YouTube: max PLAYLIST_LIMIT utworów na playlistę -> kolejne części
            # "Nazwa 2", "Nazwa 3"... Utwory z istniejących części są pomijane.
            parts, existing = load_playlist_parts(yt, cfg.playlist)
            new_ids = [v for v in unique if v not in existing]
            log.info("Do dodania na playlistę: %d (już było: %d)",
                     len(new_ids), len(unique) - len(new_ids))
            pos = part_i = 0
            while pos < len(new_ids):
                check_stop()
                if part_i >= len(parts):
                    name = part_name(cfg.playlist, part_i + 1)
                    parts.append([name, create_playlist(yt, name), 0])
                name, pid, count = parts[part_i]
                space = PLAYLIST_LIMIT - count
                if space <= 0:
                    part_i += 1
                    continue
                progress("Playlista", pos, len(new_ids))
                batch = new_ids[pos:pos + min(BATCH_SIZE, space)]
                pos += len(batch)
                try:
                    resp = with_retry(lambda: yt.add_playlist_items(pid, batch, duplicates=False),
                                      stop, f"Playlista '{name}'")
                    if isinstance(resp, dict) and resp.get("status") not in (None, "STATUS_SUCCEEDED"):
                        failure("'%s': partia odrzucona (%s)", name, resp.get("status"))
                    else:
                        fails = 0
                        parts[part_i][2] += len(batch)
                        log.info("'%s': +%d (razem %d)", name, len(batch), parts[part_i][2])
                except (TooManyFailures, Stopped):
                    raise
                except Exception as exc:
                    failure("'%s': błąd dodawania partii: %s", name, exc)
                time.sleep(cfg.delay)
            progress("Playlista", len(new_ids), len(new_ids))

        if cfg.like:
            msg = "Pobieram listę polubionych z konta (to trwa 1-2 min, program pracuje)..."
            log.info(msg)
            progress(msg, 0, 0)
            try:
                liked = {t.get("videoId") for t in with_retry(
                    lambda: yt.get_liked_songs(limit=None), stop,  # type: ignore[arg-type]
                    "Pobieranie polubionych").get("tracks") or []}
            except Stopped:
                raise
            except Exception as exc:
                log.warning("Nie udało się pobrać polubionych (%s) - lubię wszystkie.", exc)
                liked = set()
            to_like = [v for v in unique if v not in liked]
            log.info("Do polubienia: %d (już polubione: %d)",
                     len(to_like), len(unique) - len(to_like))
            ok = 0
            later: list[str] = []  # nieudane - ponowione na końcu, po przerwie
            for n, vid in enumerate(to_like, 1):
                check_stop()
                progress("Polubienia", n - 1, len(to_like),
                         f"polubione: {ok}  |  do ponowienia: {len(later)}")
                try:
                    with_retry(lambda: yt.rate_song(vid, LikeStatus.LIKE), stop, f"Like {vid}")
                    ok += 1
                    fails = 0
                except Stopped:
                    raise
                except Exception as exc:
                    later.append(vid)
                    failure("Like nieudany %s: %s - ponowię później", vid, exc)
                if n % 50 == 0:
                    log.info("Przetworzono %d z %d  |  polubione: %d  |  do ponowienia: %d",
                             n, len(to_like), ok, len(later))
                time.sleep(cfg.delay)
            progress("Polubienia", len(to_like), len(to_like),
                     f"polubione: {ok}  |  do ponowienia: {len(later)}")

            for rnd in range(1, LATER_ROUNDS + 1):
                if not later:
                    break
                log.info("Ponawiam %d nieudanych polubień za %d s (runda %d/%d)...",
                         len(later), LATER_PAUSE_S, rnd, LATER_ROUNDS)
                if stop.wait(LATER_PAUSE_S):
                    raise Stopped
                fails = 0
                still: list[str] = []
                for n, vid in enumerate(later, 1):
                    check_stop()
                    progress(f"Ponawianie (runda {rnd}/{LATER_ROUNDS})", n - 1, len(later),
                             f"polubione łącznie: {ok}")
                    try:
                        with_retry(lambda: yt.rate_song(vid, LikeStatus.LIKE), stop, f"Like {vid}")
                        ok += 1
                        fails = 0
                        log.info("Ponowiony like OK: %s", vid)
                    except Stopped:
                        raise
                    except Exception as exc:
                        still.append(vid)
                        failure("Ponowiony like nieudany %s: %s", vid, exc)
                    time.sleep(cfg.delay)
                later = still

            log.info("Przetworzono wszystkie: %d  |  YouTube przyjął polubienia: %d  |  "
                     "nieudane: %d", len(to_like), ok, len(later))

            # Sprawdzenie na koncie: czy utwory faktycznie są na liście polubionych.
            msg = "Sprawdzam polubione na koncie (to trwa 1-2 min, program pracuje)..."
            log.info(msg)
            progress(msg, 0, 0)
            try:
                now = {t.get("videoId") for t in with_retry(
                    lambda: yt.get_liked_songs(limit=None), stop,  # type: ignore[arg-type]
                    "Sprawdzanie polubionych").get("tracks") or []}
                missing = [v for v in unique if v not in now]
                log.info("SPRAWDZONE NA KONCIE: polubione %d z %d utworów z kolekcji%s",
                         len(unique) - len(missing), len(unique),
                         f"  |  brakuje: {len(missing)} - kliknij Start ponownie później"
                         if missing else "  - komplet.")
            except Stopped:
                raise
            except Exception as exc:
                log.warning("Nie udało się sprawdzić polubionych na koncie: %s", exc)
            progress("Sprawdzanie na koncie - zakończone", 1, 1)
    except (Stopped, KeyboardInterrupt):
        log.warning("Przerwano.")
        return 130
    except TooManyFailures:
        log.error("%d błędów z rzędu - przerywam. Sprawdź połączenie i plik "
                  "autoryzacji, potem uruchom ponownie (zrobione rzeczy są pomijane).",
                  MAX_FAILS_IN_ROW)
        return 1

    log.info("Gotowe.")
    return 0


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------


def run_gui() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    base = app_dir()
    settings_file = base / SETTINGS_NAME

    def load_settings() -> dict:
        try:
            return json.loads(settings_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    st = load_settings()

    root = tk.Tk()
    root.title(APP_NAME)
    root.minsize(820, 520)

    v_folder = tk.StringVar(value=st.get("folder", ""))
    v_auth = tk.StringVar(value=st.get("auth", str(base / AUTH_NAME)))
    v_out = tk.StringVar(value=st.get("out_dir", str(base)))
    v_playlist = tk.StringVar(value=st.get("playlist", ""))
    v_like = tk.BooleanVar(value=st.get("like", False))
    v_dry = tk.BooleanVar(value=st.get("dry_run", True))
    v_delay = tk.StringVar(value=str(st.get("delay", DEFAULT_DELAY_S)))
    v_workers = tk.StringVar(value=str(st.get("workers", DEFAULT_WORKERS)))
    v_status = tk.StringVar(value="Gotowy.")

    frm = ttk.Frame(root, padding=10)
    frm.pack(fill="both", expand=True)
    frm.columnconfigure(1, weight=1)

    def browse_dir(var: tk.StringVar) -> None:
        d = filedialog.askdirectory(initialdir=var.get() or str(base))
        if d:
            var.set(os.path.normpath(d))

    def browse_auth() -> None:
        cur = Path(v_auth.get()) if v_auth.get() else base / AUTH_NAME
        f = filedialog.askopenfilename(
            initialdir=str(cur.parent if cur.parent.exists() else base),
            filetypes=[("JSON", "*.json"), ("Wszystkie", "*.*")],
        )
        if f:
            v_auth.set(os.path.normpath(f))

    help_win: list[tk.Toplevel] = []

    def show_help() -> None:
        if help_win and help_win[0].winfo_exists():
            help_win[0].lift()
            help_win[0].focus_force()
            return
        win = tk.Toplevel(root)
        win.title(f"Pomoc - {APP_NAME}")
        help_win[:] = [win]
        txt = scrolledtext.ScrolledText(win, width=78, height=34, wrap="word",
                                        font=("Consolas", 10))
        txt.insert("1.0", HELP_TEXT)
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        bar = ttk.Frame(win)
        bar.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Button(bar, text="Otwórz music.youtube.com",
                   command=lambda: webbrowser.open("https://music.youtube.com")
                   ).pack(side="left")
        ttk.Button(bar, text="Zamknij", command=win.destroy).pack(side="right")

    def open_fixer() -> None:
        """Ręczne poprawianie nierozpoznanych utworów, po kolei."""
        out = Path(v_out.get().strip() or base)
        report, cache_path = out / REPORT_NAME, out / CACHE_NAME
        if not report.is_file() or not cache_path.is_file():
            messagebox.showinfo(APP_NAME, "Najpierw uruchom wyszukiwanie (Start) - "
                                "lista nierozpoznanych powstanie po nim.")
            return
        with report.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh, delimiter=";"))[1:]
        items = [Track(r[0], r[1]) for r in rows if len(r) >= 2 and r[1].strip()]
        if not items:
            messagebox.showinfo(APP_NAME, "Brak nierozpoznanych utworów.")
            return
        cache = load_cache(cache_path)

        win = tk.Toplevel(root)
        win.title("Popraw nierozpoznane")
        win.geometry("1000x560")
        win.minsize(800, 450)
        win.transient(root)
        win.grab_set()

        v_info = tk.StringVar()
        v_query = tk.StringVar()
        v_filter = tk.StringVar(value="Utwory")
        v_link = tk.StringVar()
        v_st = tk.StringVar()
        filters = {"Utwory": "songs", "Filmy": "videos", "Wszystko": None}

        ttk.Label(win, textvariable=v_info, padding=(10, 8, 10, 0)).pack(anchor="w")
        pane = ttk.PanedWindow(win, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=10, pady=6)

        left = ttk.Frame(pane)
        lb = tk.Listbox(left, activestyle="dotbox", exportselection=False, width=42)
        lsb = ttk.Scrollbar(left, orient="vertical", command=lb.yview)
        lb.config(yscrollcommand=lsb.set)
        lb.pack(side="left", fill="both", expand=True)
        lsb.pack(side="right", fill="y")
        pane.add(left, weight=1)

        right = ttk.Frame(pane, padding=(8, 0, 0, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)
        pane.add(right, weight=3)

        lbl_cur = ttk.Label(right, text="", font=("Segoe UI", 11, "bold"))
        lbl_cur.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

        qrow = ttk.Frame(right)
        qrow.grid(row=1, column=0, columnspan=4, sticky="ew")
        qrow.columnconfigure(1, weight=1)
        ttk.Label(qrow, text="Szukaj:").grid(row=0, column=0, padx=(0, 4))
        e_query = ttk.Entry(qrow, textvariable=v_query)
        e_query.grid(row=0, column=1, sticky="ew")
        ttk.Combobox(qrow, textvariable=v_filter, values=list(filters), width=9,
                     state="readonly").grid(row=0, column=2, padx=4)
        b_search = ttk.Button(qrow, text="Szukaj")
        b_search.grid(row=0, column=3)

        cols = ("artist", "title", "album", "time", "type")
        tv = ttk.Treeview(right, columns=cols, show="headings", selectmode="browse")
        for c, label, w in zip(cols, ("Artysta", "Tytuł", "Album", "Czas", "Typ"),
                               (170, 230, 160, 55, 60)):
            tv.heading(c, text=label)
            tv.column(c, width=w, stretch=c in ("artist", "title", "album"))
        tv.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=6)
        tsb = ttk.Scrollbar(right, orient="vertical", command=tv.yview)
        tv.config(yscrollcommand=tsb.set)
        tsb.grid(row=2, column=3, sticky="ns", pady=6)

        acts = ttk.Frame(right)
        acts.grid(row=3, column=0, columnspan=4, sticky="ew")
        b_use = ttk.Button(acts, text="✓ Użyj zaznaczonego")
        b_play = ttk.Button(acts, text="▶ Odsłuchaj w przeglądarce")
        b_prev = ttk.Button(acts, text="← Poprzedni")
        b_next = ttk.Button(acts, text="Pomiń →")
        b_clear = ttk.Button(acts, text="Usuń przypisanie")
        b_use.pack(side="left")
        b_play.pack(side="left", padx=6)
        b_next.pack(side="right")
        b_prev.pack(side="right", padx=6)
        b_clear.pack(side="right")

        lrow = ttk.Frame(right)
        lrow.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        lrow.columnconfigure(1, weight=1)
        ttk.Label(lrow, text="Lub wklej link YouTube:").grid(row=0, column=0, padx=(0, 4))
        ttk.Entry(lrow, textvariable=v_link).grid(row=0, column=1, sticky="ew")
        b_link = ttk.Button(lrow, text="Użyj linku")
        b_link.grid(row=0, column=2, padx=(4, 0))

        ttk.Label(right, textvariable=v_st, foreground="#555").grid(
            row=5, column=0, columnspan=4, sticky="w", pady=(6, 0))

        bottom = ttk.Frame(win, padding=(10, 0, 10, 10))
        bottom.pack(fill="x")
        ttk.Label(bottom, text="Poprawki zapisują się od razu. Kliknij potem Start w "
                  "głównym oknie, żeby je polubić / dodać do playlisty.",
                  foreground="#555").pack(side="left")
        b_close = ttk.Button(bottom, text="Zamknij")
        b_close.pack(side="right")

        state = {"i": 0, "token": 0, "results": [], "client": None}
        results_q: queue.Queue = queue.Queue()

        def label_for(t: Track) -> str:
            mark = "✓ " if cache.get(t.key) else "   "
            return f"{mark}{t.artist} - {t.title}" if t.artist else f"{mark}{t.title}"

        def refresh_info() -> None:
            fixed = sum(1 for t in items if cache.get(t.key))
            v_info.set(f"Nierozpoznane: {len(items)}  |  poprawione: {fixed}  |  "
                       f"zostało: {len(items) - fixed}")

        for t in items:
            lb.insert("end", label_for(t))

        def update_row(i: int) -> None:
            lb.delete(i)
            lb.insert(i, label_for(items[i]))
            if cache.get(items[i].key):
                lb.itemconfig(i, foreground="#0a7d22")

        for i in range(len(items)):
            if cache.get(items[i].key):
                lb.itemconfig(i, foreground="#0a7d22")

        def select(i: int) -> None:
            if not items:
                return
            i = max(0, min(i, len(items) - 1))
            state["i"] = i
            lb.selection_clear(0, "end")
            lb.selection_set(i)
            lb.see(i)
            t = items[i]
            lbl_cur.config(text=f"{t.artist} - {t.title}" if t.artist else t.title)
            v_query.set(t.query)
            v_link.set("")
            vid = cache.get(t.key)
            v_st.set(f"Przypisano: https://music.youtube.com/watch?v={vid}" if vid else "")
            search()

        def search() -> None:
            q = v_query.get().strip()
            if not q:
                return
            state["token"] += 1
            token = state["token"]
            flt = filters[v_filter.get()]
            tv.delete(*tv.get_children())
            v_st.set("Szukam...")

            def work() -> None:
                try:
                    if state["client"] is None:
                        state["client"] = RetryingYTMusic()
                    res = state["client"].search(q, filter=flt, limit=20)
                    results_q.put((token, [r for r in res if r.get("videoId")], None))
                except Exception as exc:
                    results_q.put((token, [], exc))

            threading.Thread(target=work, daemon=True).start()

        def poll_results() -> None:
            try:
                while True:
                    token, res, err = results_q.get_nowait()
                    if token != state["token"]:
                        continue  # wynik starego wyszukiwania
                    state["results"] = res
                    tv.delete(*tv.get_children())
                    for n, r in enumerate(res):
                        artists = ", ".join(a.get("name", "") for a in r.get("artists") or [])
                        album = (r.get("album") or {}).get("name", "") if isinstance(r.get("album"), dict) else ""
                        tv.insert("", "end", iid=str(n), values=(
                            artists, r.get("title", ""), album, r.get("duration", ""),
                            {"song": "utwór", "video": "film"}.get(r.get("resultType"), r.get("resultType", ""))))
                    if err:
                        v_st.set(f"Błąd wyszukiwania: {err} - spróbuj ponownie.")
                    elif not res:
                        v_st.set("Brak wyników - zmień zapytanie albo typ (Filmy / Wszystko).")
                    else:
                        cur = cache.get(items[state["i"]].key)
                        v_st.set(f"Wyników: {len(res)}. Dwuklik lub '✓ Użyj' = przypisz."
                                 + (f"  (obecnie przypisano: {cur})" if cur else ""))
                        tv.selection_set("0")
                        tv.focus("0")
            except queue.Empty:
                pass
            if win.winfo_exists():
                win.after(100, poll_results)

        def assign(vid: str | None) -> None:
            t = items[state["i"]]
            cache[t.key] = vid
            try:
                save_cache(cache_path, cache)
            except OSError as exc:
                messagebox.showerror(APP_NAME, f"Nie można zapisać cache:\n{exc}", parent=win)
                return
            update_row(state["i"])
            refresh_info()
            if vid:
                log.info("Ręcznie przypisano: %s -> %s", t.query, vid)
                select(state["i"] + 1)
            else:
                v_st.set("Usunięto przypisanie.")

        def selected_vid() -> str | None:
            sel = tv.selection()
            if not sel:
                return None
            return state["results"][int(sel[0])].get("videoId")

        def use_selected() -> None:
            vid = selected_vid()
            if vid:
                assign(vid)
            else:
                v_st.set("Zaznacz wynik na liście.")

        def play() -> None:
            vid = selected_vid() or cache.get(items[state["i"]].key)
            if vid:
                webbrowser.open(f"https://music.youtube.com/watch?v={vid}")

        def use_link() -> None:
            text = v_link.get().strip()
            m_ = re.search(r"(?:v=|youtu\.be/|/watch/|/shorts/)([\w-]{11})", text) or \
                re.fullmatch(r"([\w-]{11})", text)
            if not m_:
                messagebox.showerror(APP_NAME, "Nie rozpoznano linku.\nPrzykład: "
                                     "https://music.youtube.com/watch?v=dQw4w9WgXcQ", parent=win)
                return
            assign(m_.group(1))

        def on_list_select(_e: object = None) -> None:
            sel = lb.curselection()
            if sel and sel[0] != state["i"]:
                select(sel[0])

        def close() -> None:
            # Raport braków = to, co nadal nie ma przypisania.
            try:
                with report.open("w", newline="", encoding="utf-8-sig") as fh:
                    w = csv.writer(fh, delimiter=";")
                    w.writerow(["artist", "title"])
                    w.writerows((t.artist, t.title) for t in items if not cache.get(t.key))
            except OSError:
                pass
            win.destroy()

        b_search.config(command=search)
        b_use.config(command=use_selected)
        b_play.config(command=play)
        b_prev.config(command=lambda: select(state["i"] - 1))
        b_next.config(command=lambda: select(state["i"] + 1))
        b_clear.config(command=lambda: assign(None))
        b_link.config(command=use_link)
        b_close.config(command=close)
        win.protocol("WM_DELETE_WINDOW", close)
        e_query.bind("<Return>", lambda _e: search())
        tv.bind("<Double-1>", lambda _e: use_selected())
        tv.bind("<Return>", lambda _e: use_selected())
        lb.bind("<<ListboxSelect>>", on_list_select)

        refresh_info()
        first = next((i for i, t in enumerate(items) if not cache.get(t.key)), 0)
        state["i"] = -1
        select(first)
        win.after(100, poll_results)

    def create_auth() -> None:
        win = tk.Toplevel(root)
        win.title("Autoryzacja YouTube Music")
        win.transient(root)
        win.grab_set()
        top = ttk.Frame(win)
        top.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(
            top, justify="left", wraplength=500,
            text=(
                "Wklej poniżej nagłówki żądania POST /browse z music.youtube.com "
                "(F12 → Network → filtr 'browse' → Headers → Request Headers).\n"
                "Dokładna instrukcja: przycisk ?\n\n"
                "Plik browser.json daje pełny dostęp do konta - nie udostępniaj go."
            ),
        ).pack(side="left", anchor="w")
        ttk.Button(top, text="?", width=3, command=show_help).pack(side="right", anchor="n")
        txt = scrolledtext.ScrolledText(win, width=80, height=16)
        txt.pack(padx=10, pady=4, fill="both", expand=True)

        def save() -> None:
            raw = txt.get("1.0", "end").strip()
            if not raw:
                messagebox.showwarning(APP_NAME, "Wklej nagłówki.", parent=win)
                return
            target = Path(v_auth.get() or base / AUTH_NAME)
            if target.suffix.lower() != ".json":
                target = target / AUTH_NAME if target.is_dir() else target.with_suffix(".json")
            try:
                headers = clean_headers(json.loads(setup_browser(headers_raw=raw)))
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Nie udało się:\n{exc}", parent=win)
                return
            if "SAPISIDHASH" not in str(headers.get("authorization", "")):
                messagebox.showerror(APP_NAME, AUTH_HINT, parent=win)
                return
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(headers, ensure_ascii=True, indent=4,
                                             sort_keys=True), encoding="utf-8")
            except OSError as exc:
                messagebox.showerror(APP_NAME, f"Nie można zapisać:\n{exc}", parent=win)
                return
            v_auth.set(str(target))
            try:
                who = account_label(RetryingYTMusic(json.dumps(headers)))
            except Exception as exc:
                messagebox.showwarning(
                    APP_NAME, f"Zapisano:\n{target}\n\nAle test logowania się nie "
                    f"udał ({exc}).\nSkopiuj nagłówki ponownie.", parent=win)
                return
            messagebox.showinfo(APP_NAME, f"Zapisano:\n{target}\n\nZalogowano jako:\n"
                                f"{who}\n\nJeśli to nie to konto - przełącz konto na "
                                "music.youtube.com i skopiuj nagłówki ponownie.", parent=win)
            win.destroy()

        bar = ttk.Frame(win)
        bar.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Button(bar, text="Zapisz", command=save).pack(side="right")
        ttk.Button(bar, text="Anuluj", command=win.destroy).pack(side="right", padx=6)

    r = 0
    ttk.Label(frm, text="Folder z muzyką:").grid(row=r, column=0, sticky="w", pady=3)
    ttk.Entry(frm, textvariable=v_folder).grid(row=r, column=1, sticky="ew", padx=6)
    ttk.Button(frm, text="Wybierz...", command=lambda: browse_dir(v_folder)).grid(row=r, column=2, sticky="ew")

    r += 1
    ttk.Label(frm, text="Plik autoryzacji:").grid(row=r, column=0, sticky="w", pady=3)
    ttk.Entry(frm, textvariable=v_auth).grid(row=r, column=1, sticky="ew", padx=6)
    ttk.Button(frm, text="Wybierz...", command=browse_auth).grid(row=r, column=2, sticky="ew")
    ttk.Button(frm, text="?", width=3, command=show_help).grid(row=r, column=3, padx=(4, 0))
    r += 1
    ttk.Button(frm, text="Utwórz z nagłówków...", command=create_auth).grid(row=r, column=2, sticky="ew")

    r += 1
    ttk.Label(frm, text="Folder wyników:").grid(row=r, column=0, sticky="w", pady=3)
    ttk.Entry(frm, textvariable=v_out).grid(row=r, column=1, sticky="ew", padx=6)
    ttk.Button(frm, text="Wybierz...", command=lambda: browse_dir(v_out)).grid(row=r, column=2, sticky="ew")

    r += 1
    ttk.Label(frm, text="Playlista (opcjonalnie):").grid(row=r, column=0, sticky="w", pady=3)
    ttk.Entry(frm, textvariable=v_playlist).grid(row=r, column=1, sticky="ew", padx=6)

    r += 1
    opts = ttk.Frame(frm)
    opts.grid(row=r, column=0, columnspan=3, sticky="w", pady=6)
    ttk.Checkbutton(opts, text="Polub dopasowane utwory", variable=v_like).pack(side="left")
    ttk.Checkbutton(opts, text="Tylko test (nic nie zmieniaj na koncie)",
                    variable=v_dry).pack(side="left", padx=16)
    ttk.Label(opts, text="Opóźnienie [s]:").pack(side="left", padx=(16, 4))
    ttk.Spinbox(opts, from_=0.0, to=10.0, increment=0.5, width=5,
                textvariable=v_delay).pack(side="left")
    ttk.Label(opts, text="Wątki:").pack(side="left", padx=(16, 4))
    ttk.Spinbox(opts, from_=1, to=MAX_WORKERS, increment=1, width=4,
                textvariable=v_workers).pack(side="left")

    r += 1
    btns = ttk.Frame(frm)
    btns.grid(row=r, column=0, columnspan=3, sticky="ew", pady=4)
    b_start = ttk.Button(btns, text="Start")
    b_stop = ttk.Button(btns, text="Stop", state="disabled")
    b_report = ttk.Button(btns, text="Otwórz raport braków")
    b_fix = ttk.Button(btns, text="Popraw nierozpoznane...", command=open_fixer)
    b_folder = ttk.Button(btns, text="Otwórz folder wyników")
    b_help = ttk.Button(btns, text="Pomoc", command=show_help)
    b_start.pack(side="left")
    b_stop.pack(side="left", padx=6)
    b_help.pack(side="right")
    b_folder.pack(side="right", padx=6)
    b_report.pack(side="right", padx=6)
    b_fix.pack(side="left", padx=(12, 0))

    r += 1
    pbar = ttk.Progressbar(frm, mode="determinate")
    pbar.grid(row=r, column=0, columnspan=3, sticky="ew", pady=(6, 2))
    r += 1
    ttk.Label(frm, textvariable=v_status).grid(row=r, column=0, columnspan=3, sticky="w")

    r += 1
    logbox = scrolledtext.ScrolledText(frm, height=14, state="disabled", wrap="none")
    logbox.grid(row=r, column=0, columnspan=3, sticky="nsew", pady=(6, 0))
    frm.rowconfigure(r, weight=1)

    events: queue.Queue = queue.Queue()

    class QueueHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            events.put(("log", self.format(record)))

    handler = QueueHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    log.handlers[:] = [handler]
    log.setLevel(logging.INFO)
    log.propagate = False

    stop_event = threading.Event()
    worker: list[threading.Thread] = []

    def save_settings() -> None:
        data = {
            "folder": v_folder.get(), "auth": v_auth.get(), "out_dir": v_out.get(),
            "playlist": v_playlist.get(), "like": v_like.get(),
            "dry_run": v_dry.get(), "delay": v_delay.get(),
            "workers": v_workers.get(),
        }
        try:
            settings_file.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
        except OSError:
            pass

    def start() -> None:
        try:
            delay = max(0.0, float(v_delay.get().replace(",", ".")))
        except ValueError:
            messagebox.showerror(APP_NAME, "Opóźnienie musi być liczbą.")
            return
        try:
            workers = min(MAX_WORKERS, max(1, int(v_workers.get())))
        except ValueError:
            messagebox.showerror(APP_NAME, f"Wątki: liczba od 1 do {MAX_WORKERS}.")
            return
        cfg = Config(
            folder=Path(v_folder.get().strip()),
            auth=Path(v_auth.get().strip()),
            out_dir=Path(v_out.get().strip() or base),
            playlist=v_playlist.get().strip(),
            like=v_like.get(),
            dry_run=v_dry.get(),
            delay=delay,
            workers=workers,
        )
        if not v_folder.get().strip() or not cfg.folder.is_dir():
            messagebox.showerror(APP_NAME, "Wybierz istniejący folder z muzyką.")
            return
        if not cfg.dry_run:
            if not cfg.auth.is_file():
                messagebox.showerror(
                    APP_NAME,
                    "Brak pliku autoryzacji.\nUżyj przycisku 'Utwórz z nagłówków...'.\n\n"
                    "(W trybie 'Tylko test' plik nie jest potrzebny.)",
                )
                return
            if problem := auth_problem(cfg.auth):
                messagebox.showerror(APP_NAME, problem)
                return
        if not cfg.dry_run and not cfg.playlist and not cfg.like:
            if not messagebox.askyesno(
                APP_NAME,
                "Nie podano playlisty ani polubień - zostanie wykonane tylko "
                "wyszukiwanie. Kontynuować?",
            ):
                return
        save_settings()
        stop_event.clear()
        b_start.config(state="disabled")
        b_fix.config(state="disabled")  # nie edytuj cache podczas pracy
        b_stop.config(state="normal")
        pbar.config(value=0)

        def progress(stage: str, i: int, n: int, extra: str = "") -> None:
            events.put(("progress", (stage, i, n, extra)))

        def work() -> None:
            try:
                code = run_import(cfg, stop_event, progress)
            except Exception as exc:
                log.exception("Błąd: %s", exc)
                code = 1
            events.put(("done", code))

        t = threading.Thread(target=work, daemon=True)
        worker[:] = [t]
        t.start()

    def stop() -> None:
        stop_event.set()
        b_stop.config(state="disabled")
        v_status.set("Zatrzymywanie...")

    def open_path(p: Path) -> None:
        if p.exists():
            os.startfile(p)  # type: ignore[attr-defined]
        else:
            messagebox.showinfo(APP_NAME, f"Nie ma jeszcze:\n{p}")

    b_start.config(command=start)
    b_stop.config(command=stop)
    b_report.config(command=lambda: open_path(Path(v_out.get() or base) / REPORT_NAME))
    b_folder.config(command=lambda: open_path(Path(v_out.get() or base)))

    def append_log(line: str) -> None:
        logbox.config(state="normal")
        logbox.insert("end", line + "\n")
        if int(logbox.index("end-1c").split(".")[0]) > 5000:
            logbox.delete("1.0", "1000.0")
        logbox.see("end")
        logbox.config(state="disabled")

    def poll() -> None:
        try:
            while True:
                kind, payload = events.get_nowait()
                if kind == "log":
                    append_log(payload)
                elif kind == "progress":
                    stage, i, n, extra = payload
                    pbar.config(maximum=max(n, 1), value=i)
                    if n == 0:  # etap bez licznika - sam opis
                        v_status.set(stage)
                    else:
                        v_status.set(f"{stage} - przetworzono {i}/{n}"
                                     + (f"  |  {extra}" if extra else ""))
                elif kind == "done":
                    b_start.config(state="normal")
                    b_fix.config(state="normal")
                    b_stop.config(state="disabled")
                    v_status.set({0: "Gotowe.", 130: "Przerwano."}.get(payload, "Błąd - zobacz log."))
        except queue.Empty:
            pass
        root.after(100, poll)

    def on_close() -> None:
        if worker and worker[0].is_alive():
            if not messagebox.askyesno(APP_NAME, "Praca trwa. Przerwać i zamknąć?"):
                return
            stop_event.set()
        save_settings()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(100, poll)
    root.mainloop()
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def run_cli(argv: list[str]) -> int:
    base = app_dir()
    ap = argparse.ArgumentParser(description=(__doc__ or APP_NAME).split("\n")[0])
    ap.add_argument("folder", type=Path)
    ap.add_argument("--auth", type=Path, default=base / AUTH_NAME)
    ap.add_argument("--out", type=Path, default=base, help="folder na cache i raport")
    ap.add_argument("--playlist", default="", help="nazwa playlisty docelowej")
    ap.add_argument("--like", action="store_true", help="polub dopasowane")
    ap.add_argument("--dry-run", action="store_true", help="tylko skan + szukanie")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY_S)
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                    help=f"równoległe wyszukiwania (1-{MAX_WORKERS})")
    args = ap.parse_args(argv)

    stream = sys.stderr or sys.stdout
    if stream is None:  # exe bez konsoli - loguj do pliku
        logging.basicConfig(filename=str(args.out / "ytm.log"), level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s",
                            stream=stream)

    cfg = Config(folder=args.folder, auth=args.auth, out_dir=args.out,
                 playlist=args.playlist, like=args.like, dry_run=args.dry_run,
                 delay=args.delay,
                 workers=min(MAX_WORKERS, max(1, args.workers)))
    try:
        return run_import(cfg)
    except Exception as exc:
        log.exception("Błąd: %s", exc)
        return 1


def main() -> int:
    if len(sys.argv) > 1:
        return run_cli(sys.argv[1:])
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
