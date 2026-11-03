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
DEFAULT_DELAY_S = 1.0

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

    @property
    def cache_file(self) -> Path:
        return self.out_dir / CACHE_NAME

    @property
    def report_file(self) -> Path:
        return self.out_dir / REPORT_NAME


class Stopped(Exception):
    """Użytkownik przerwał pracę."""


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


def get_or_create_playlist(yt: YTMusic, name: str) -> str:
    for pl in yt.get_library_playlists(limit=None):
        if pl.get("title") == name:
            return str(pl["playlistId"])
    result = yt.create_playlist(name, "Import z lokalnej kolekcji", "PRIVATE")
    if not isinstance(result, str):
        raise RuntimeError(f"Nie udało się utworzyć playlisty: {result}")
    log.info("Utworzono playlistę '%s'", name)
    return result


AUTH_HINT = (
    "Plik autoryzacji nie zawiera nagłówka 'authorization: SAPISIDHASH ...'.\n"
    "Skopiuj nagłówki żądania POST /browse z music.youtube.com (będąc zalogowanym) "
    "i utwórz plik ponownie przyciskiem 'Utwórz z nagłówków...'."
)


def auth_problem(path: Path) -> str | None:
    """Zwraca opis problemu z plikiem browser.json albo None, gdy jest OK."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"Nie można odczytać pliku autoryzacji: {exc}"
    if not isinstance(data, dict):
        return "Nieprawidłowy format pliku autoryzacji."
    headers = {str(k).lower(): str(v) for k, v in data.items()}
    if "SAPISIDHASH" not in headers.get("authorization", ""):
        return AUTH_HINT
    if "__Secure-3PAPISID" not in headers.get("cookie", ""):
        return ("W cookie brakuje '__Secure-3PAPISID' - zaloguj się na "
                "music.youtube.com i skopiuj nagłówki ponownie.")
    return None


ProgressCb = Callable[[str, int, int], None]


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

    yt = YTMusic(str(cfg.auth))
    cache = load_cache(cfg.cache_file)
    found: list[str] = []
    missing: list[Track] = []
    stopped = False

    try:
        for i, track in enumerate(tracks, 1):
            check_stop()
            progress("Wyszukiwanie", i, len(tracks))
            if track.key not in cache:
                try:
                    cache[track.key] = find_video_id(yt, track)
                except Exception as exc:  # błędy sieci/API - pomiń, nie cache'uj
                    log.warning("Wyszukiwanie nieudane '%s': %s", track.query, exc)
                    continue
                time.sleep(cfg.delay)
                if i % 25 == 0:
                    save_cache(cfg.cache_file, cache)
            vid = cache[track.key]
            if vid:
                found.append(vid)
            else:
                missing.append(track)
            log.info("[%d/%d] %s %s", i, len(tracks), "OK " if vid else "---", track.query)
    except (Stopped, KeyboardInterrupt):
        stopped = True
        log.warning("Przerwano - zapisuję postęp.")
    finally:
        save_cache(cfg.cache_file, cache)

    with cfg.report_file.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["artist", "title"])
        writer.writerows((t.artist, t.title) for t in missing)

    log.info("Dopasowano: %d | brak: %d (-> %s)", len(found), len(missing), cfg.report_file)

    # Po przerwaniu nie zmieniamy konta na podstawie niepełnych wyników.
    if stopped:
        return 130
    if cfg.dry_run:
        log.info("Tryb testowy - nic nie zmieniono na koncie.")
        return 0
    if not found:
        return 0

    unique = list(dict.fromkeys(found))
    try:
        if cfg.playlist:
            pid = get_or_create_playlist(yt, cfg.playlist)
            existing = {t.get("videoId") for t in yt.get_playlist(pid, limit=None)["tracks"]}
            new_ids = [v for v in unique if v not in existing]
            log.info("Do dodania na playlistę: %d (już było: %d)",
                     len(new_ids), len(unique) - len(new_ids))
            for start in range(0, len(new_ids), BATCH_SIZE):
                check_stop()
                progress("Playlista", start, len(new_ids))
                batch = new_ids[start:start + BATCH_SIZE]
                try:
                    resp = yt.add_playlist_items(pid, batch, duplicates=False)
                    if isinstance(resp, dict) and resp.get("status") not in (None, "STATUS_SUCCEEDED"):
                        log.error("Partia %d: odpowiedź %s", start, resp.get("status"))
                    else:
                        log.info("Playlista: +%d", len(batch))
                except Exception as exc:
                    log.error("Błąd dodawania partii %d: %s", start, exc)
                time.sleep(cfg.delay)

        if cfg.like:
            for n, vid in enumerate(unique, 1):
                check_stop()
                progress("Polubienia", n, len(unique))
                try:
                    yt.rate_song(vid, LikeStatus.LIKE)
                except Exception as exc:
                    log.warning("Like nieudany %s: %s", vid, exc)
                if n % 50 == 0:
                    log.info("Polubiono %d", n)
                time.sleep(cfg.delay)
    except (Stopped, KeyboardInterrupt):
        log.warning("Przerwano.")
        return 130

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
    root.minsize(640, 520)

    v_folder = tk.StringVar(value=st.get("folder", ""))
    v_auth = tk.StringVar(value=st.get("auth", str(base / AUTH_NAME)))
    v_out = tk.StringVar(value=st.get("out_dir", str(base)))
    v_playlist = tk.StringVar(value=st.get("playlist", ""))
    v_like = tk.BooleanVar(value=st.get("like", False))
    v_dry = tk.BooleanVar(value=st.get("dry_run", True))
    v_delay = tk.StringVar(value=str(st.get("delay", DEFAULT_DELAY_S)))
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

    def create_auth() -> None:
        win = tk.Toplevel(root)
        win.title("Autoryzacja YouTube Music")
        win.transient(root)
        win.grab_set()
        ttk.Label(
            win, justify="left", wraplength=560,
            text=(
                "1. Zaloguj się na music.youtube.com w Chrome/Edge/Firefox.\n"
                "2. F12 → zakładka Network (Sieć) → odśwież stronę.\n"
                "3. Wpisz w filtr 'browse', kliknij żądanie POST /browse.\n"
                "4. Skopiuj całe 'Request Headers' (Nagłówki żądania) i wklej poniżej.\n\n"
                "Plik browser.json daje pełny dostęp do konta - nie udostępniaj go."
            ),
        ).pack(padx=10, pady=(10, 4), anchor="w")
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
                headers = json.loads(setup_browser(headers_raw=raw))
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
            messagebox.showinfo(APP_NAME, f"Zapisano:\n{target}", parent=win)
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

    r += 1
    btns = ttk.Frame(frm)
    btns.grid(row=r, column=0, columnspan=3, sticky="ew", pady=4)
    b_start = ttk.Button(btns, text="Start")
    b_stop = ttk.Button(btns, text="Stop", state="disabled")
    b_report = ttk.Button(btns, text="Otwórz raport braków")
    b_folder = ttk.Button(btns, text="Otwórz folder wyników")
    b_start.pack(side="left")
    b_stop.pack(side="left", padx=6)
    b_folder.pack(side="right")
    b_report.pack(side="right", padx=6)

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
        cfg = Config(
            folder=Path(v_folder.get().strip()),
            auth=Path(v_auth.get().strip()),
            out_dir=Path(v_out.get().strip() or base),
            playlist=v_playlist.get().strip(),
            like=v_like.get(),
            dry_run=v_dry.get(),
            delay=delay,
        )
        if not v_folder.get().strip() or not cfg.folder.is_dir():
            messagebox.showerror(APP_NAME, "Wybierz istniejący folder z muzyką.")
            return
        if not cfg.auth.is_file():
            messagebox.showerror(
                APP_NAME,
                "Brak pliku autoryzacji.\nUżyj przycisku 'Utwórz z nagłówków...'.",
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
        b_stop.config(state="normal")
        pbar.config(value=0)

        def progress(stage: str, i: int, n: int) -> None:
            events.put(("progress", (stage, i, n)))

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
                    stage, i, n = payload
                    pbar.config(maximum=max(n, 1), value=i)
                    v_status.set(f"{stage}: {i}/{n}")
                elif kind == "done":
                    b_start.config(state="normal")
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
                 delay=args.delay)
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
