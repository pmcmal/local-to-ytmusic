#!/usr/bin/env python3
"""Skanuje lokalne FLAC/MP3, dopasowuje utwory w katalogu YouTube Music
i dodaje je do playlisty oraz (opcjonalnie) oznacza jako polubione.

Wymagania:
    pip install ytmusicapi mutagen

Autoryzacja (jednorazowo):
    ytmusicapi browser      # wklej nagłówki żądania /browse z music.youtube.com
    -> powstaje browser.json (TRZYMAJ PRYWATNIE - to pełny dostęp do konta)

Użycie:
    python local_to_ytmusic.py "D:/Muzyka" --dry-run
    python local_to_ytmusic.py "D:/Muzyka" --like --playlist "Moja kolekcja"
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen import MutagenError
from ytmusicapi import LikeStatus, YTMusic

AUDIO_EXT: frozenset[str] = frozenset({".flac", ".mp3"})
CACHE_FILE = Path("ytm_cache.json")
REPORT_FILE = Path("ytm_not_found.csv")
BATCH_SIZE = 50
DELAY_S = 1.0

log = logging.getLogger("ytm")


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


def _first(tags: object, name: str) -> str:
    """Zwraca pierwszą wartość tagu (EasyID3 / Vorbis) albo pusty string."""
    try:
        value = tags.get(name)  # type: ignore[attr-defined]
    except (KeyError, ValueError):
        return ""
    if isinstance(value, list) and value:
        return str(value[0]).strip()
    return ""


def read_track(path: Path) -> Track | None:
    """Czyta artystę/tytuł z tagów; fallback: nazwa pliku 'Artysta - Tytuł'."""
    artist = title = ""
    try:
        audio = MutagenFile(path, easy=True)
        if audio is not None and audio.tags is not None:
            artist = _first(audio.tags, "artist")
            title = _first(audio.tags, "title")
    except MutagenError as exc:
        log.warning("Błąd tagów %s: %s", path.name, exc)

    if not (artist and title):
        stem = re.sub(r"^\d+[\s.\-_]*", "", path.stem)  # usuń numer ścieżki
        if " - " in stem:
            artist, title = (p.strip() for p in stem.split(" - ", 1))
        elif not title:
            title = stem.strip()

    return Track(artist, title) if title else None


def scan(root: Path) -> list[Track]:
    seen: dict[str, Track] = {}
    for path in root.rglob("*"):
        if path.suffix.lower() in AUDIO_EXT and path.is_file():
            track = read_track(path)
            if track and track.key not in seen:
                seen[track.key] = track
    return list(seen.values())


def load_cache() -> dict[str, str | None]:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("Uszkodzony cache - zaczynam od nowa.")
    return {}


def save_cache(cache: dict[str, str | None]) -> None:
    CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def _norm(text: str) -> str:
    return re.sub(r"[^\w]", "", text.lower())


def find_video_id(yt: YTMusic, track: Track) -> str | None:
    """Szuka utworu (filtr 'songs'); akceptuje wynik z pasującym artystą."""
    results = yt.search(track.query, filter="songs", limit=5)
    want = _norm(track.artist)
    for res in results:
        artists = " ".join(a.get("name", "") for a in res.get("artists") or [])
        if not want or want in _norm(artists) or _norm(artists) in want:
            return res.get("videoId")
    return None


def get_or_create_playlist(yt: YTMusic, name: str) -> str:
    for pl in yt.get_library_playlists(limit=None):
        if pl.get("title") == name:
            return str(pl["playlistId"])
    result = yt.create_playlist(name, "Import z lokalnej kolekcji", "PRIVATE")
    if not isinstance(result, str):
        raise RuntimeError(f"Nie udało się utworzyć playlisty: {result}")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("folder", type=Path)
    ap.add_argument("--auth", type=Path, default=Path("browser.json"))
    ap.add_argument("--playlist", default="", help="nazwa playlisty docelowej")
    ap.add_argument("--like", action="store_true", help="polub dopasowane")
    ap.add_argument("--dry-run", action="store_true", help="tylko skan + szukanie")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not args.folder.is_dir():
        log.error("Folder nie istnieje: %s", args.folder)
        return 1
    if not args.auth.exists():
        log.error("Brak %s - uruchom najpierw: ytmusicapi browser", args.auth)
        return 1

    tracks = scan(args.folder)
    log.info("Unikalnych utworów: %d", len(tracks))

    yt = YTMusic(str(args.auth))
    cache = load_cache()
    found: list[str] = []
    missing: list[Track] = []

    try:
        for i, track in enumerate(tracks, 1):
            if track.key not in cache:
                try:
                    cache[track.key] = find_video_id(yt, track)
                except Exception as exc:  # błędy sieci/API - pomiń, nie cache'uj
                    log.warning("Wyszukiwanie nieudane '%s': %s", track.query, exc)
                    continue
                time.sleep(DELAY_S)
                if i % 25 == 0:
                    save_cache(cache)
            vid = cache[track.key]
            (found.append(vid) if vid else missing.append(track))
            log.info("[%d/%d] %s %s", i, len(tracks), "OK " if vid else "---",
                     track.query)
    except KeyboardInterrupt:
        log.warning("Przerwano - zapisuję postęp.")
    finally:
        save_cache(cache)

    with REPORT_FILE.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["artist", "title"])
        writer.writerows((t.artist, t.title) for t in missing)

    log.info("Dopasowano: %d | brak: %d (-> %s)", len(found), len(missing),
             REPORT_FILE)

    if args.dry_run or not found:
        return 0

    if args.playlist:
        pid = get_or_create_playlist(yt, args.playlist)
        existing = {
            t.get("videoId") for t in yt.get_playlist(pid, limit=None)["tracks"]
        }
        new_ids = [v for v in dict.fromkeys(found) if v not in existing]
        for start in range(0, len(new_ids), BATCH_SIZE):
            batch = new_ids[start:start + BATCH_SIZE]
            try:
                yt.add_playlist_items(pid, batch, duplicates=False)
                log.info("Playlista: +%d", len(batch))
            except Exception as exc:
                log.error("Błąd dodawania partii %d: %s", start, exc)
            time.sleep(DELAY_S)

    if args.like:
        for n, vid in enumerate(dict.fromkeys(found), 1):
            try:
                yt.rate_song(vid, LikeStatus.LIKE)
            except Exception as exc:
                log.warning("Like nieudany %s: %s", vid, exc)
            if n % 50 == 0:
                log.info("Polubiono %d", n)
            time.sleep(DELAY_S)

    log.info("Gotowe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
