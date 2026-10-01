"""
Spotify Playlist → 320 kbps MP3 Downloader
==========================================

Single-file Streamlit app. Given a PUBLIC Spotify playlist URL, it fetches
the full track list (paginated) via spotipy and downloads each track from
YouTube as a 320 kbps MP3 using yt-dlp + ffmpeg.

Prerequisites
-------------
- Python packages:  pip install streamlit spotipy yt-dlp
- ffmpeg on PATH:   brew install ffmpeg   |   sudo apt install ffmpeg
- A Spotify app (Client ID + Client Secret) from https://developer.spotify.com

Run
---
    streamlit run app.py

LEGAL: Only use this with content you have the right to download (your own
uploads, public-domain / CC-licensed material, etc.). Downloading commercial
music from YouTube generally violates YouTube's ToS and copyright law.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class Track:
    title: str
    artist: str
    album: str
    cover_url: Optional[str]
    duration_ms: int

    @property
    def duration_str(self) -> str:
        total = self.duration_ms // 1000
        return f"{total // 60}:{total % 60:02d}"

    @property
    def search_query(self) -> str:
        return f"{self.artist} - {self.title} audio"


# --------------------------------------------------------------------------- #
# Spotify helpers
# --------------------------------------------------------------------------- #

def extract_playlist_id(value: str) -> str:
    """Accept a full URL, a spotify: URI, or a bare base-62 ID."""
    value = value.strip()
    for pattern in (r"playlist/([A-Za-z0-9]+)", r"spotify:playlist:([A-Za-z0-9]+)"):
        m = re.search(pattern, value)
        if m:
            return m.group(1)
    return value


@st.cache_resource(show_spinner=False)
def get_spotify_client(client_id: str, client_secret: str) -> spotipy.Spotify:
    return spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret,
        ),
        requests_timeout=20,
        retries=3,
    )


def fetch_playlist(sp: spotipy.Spotify, playlist_id: str) -> tuple[dict, list[Track]]:
    """Fetch playlist metadata + every track, handling cursor pagination."""
    meta = sp.playlist(
        playlist_id,
        fields="name,description,images,owner(display_name),tracks(total)",
    )

    tracks: list[Track] = []
    page = sp.playlist_items(
        playlist_id,
        additional_types=["track"],
        fields=(
            "next,"
            "items(track(name,duration_ms,is_local,"
            "artists(name),album(name,images(url))))"
        ),
    )

    # Spotify caps page size at 100 -> loop until `next` is null.
    while page:
        for item in page.get("items", []):
            t = item.get("track")
            if not t or t.get("is_local"):
                continue
            artists = ", ".join(a["name"] for a in t.get("artists", [])) or "Unknown"
            album = t.get("album") or {}
            images = album.get("images") or []
            tracks.append(
                Track(
                    title=t["name"],
                    artist=artists,
                    album=album.get("name", ""),
                    cover_url=images[0]["url"] if images else None,
                    duration_ms=t.get("duration_ms", 0),
                )
            )
        page = sp.next(page) if page.get("next") else None

    return meta, tracks


# --------------------------------------------------------------------------- #
# yt-dlp helpers
# --------------------------------------------------------------------------- #

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(name: str, maxlen: int = 120) -> str:
    return _ILLEGAL.sub("_", name).strip().rstrip(".")[:maxlen] or "track"


def download_track(
    track: Track,
    output_dir: Path,
    progress_cb: Optional[Callable[[dict], None]] = None,
) -> Optional[Path]:
    """
    Search YouTube for `"{artist} - {title} audio"` and download the best
    audio stream, transcoding to 320 kbps MP3.

    Returns the produced MP3 path, or None if the download failed.
    """
    stem = safe_name(f"{track.artist} - {track.title}")
    outtmpl = str(output_dir / f"{stem}.%(ext)s")

    ydl_opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "default_search": "ytsearch1",   # take the first search hit
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "retries": 3,
        "socket_timeout": 30,
        "progress_hooks": [progress_cb] if progress_cb else [],
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(track.search_query, download=True)
    except Exception:
        return None

    mp3 = output_dir / f"{stem}.mp3"
    return mp3 if mp3.exists() else None


# --------------------------------------------------------------------------- #
# UI
# --------------------------------------------------------------------------- #

st.set_page_config(page_title="Spotify → MP3", page_icon="🎧", layout="wide")


def main() -> None:
    st.title("🎧 Spotify Playlist → MP3")
    st.caption(
        "Fetches a **public** Spotify playlist's track list and downloads each "
        "track from YouTube as a 320 kbps MP3. Use only for content you have "
        "the right to download."
    )

    if not shutil.which("ffmpeg"):
        st.error("`ffmpeg` was not found on your PATH. Install it and restart the app.")
        st.stop()

    # ---------------- Sidebar: credentials ---------------- #
    with st.sidebar:
        st.header("Configuration")
        client_id = st.text_input(
            "Spotify Client ID",
            value=os.environ.get("SPOTIFY_CLIENT_ID", ""),
        )
        client_secret = st.text_input(
            "Spotify Client Secret",
            value=os.environ.get("SPOTIFY_CLIENT_SECRET", ""),
            type="password",
        )
        st.caption(
            "Create an app at developer.spotify.com → Dashboard. The Client "
            "Credentials flow is sufficient for reading public playlists."
        )

    # ---------------- Playlist input ---------------- #
    url = st.text_input(
        "Spotify playlist URL or ID",
        placeholder="https://open.spotify.com/playlist/…",
    )

    can_fetch = bool(url and client_id and client_secret)
    if st.button("Fetch playlist", type="primary", disabled=not can_fetch):
        with st.spinner("Loading playlist…"):
            try:
                sp = get_spotify_client(client_id, client_secret)
                playlist_id = extract_playlist_id(url)
                meta, tracks = fetch_playlist(sp, playlist_id)
                st.session_state["meta"] = meta
                st.session_state["tracks"] = tracks
                st.session_state.pop("zip_bytes", None)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Failed to load playlist: {exc}")

    meta = st.session_state.get("meta")
    tracks: list[Track] | None = st.session_state.get("tracks")
    if not meta or not tracks:
        return

    # ---------------- Playlist header ---------------- #
    img_col, info_col = st.columns([1, 4])
    images = meta.get("images") or []
    if images:
        img_col.image(images[0]["url"], width=220)
    info_col.subheader(meta.get("name", "Playlist"))
    if meta.get("description"):
        info_col.write(meta["description"])
    info_col.write(
        f"**{len(tracks)} tracks** · "
        f"by {meta.get('owner', {}).get('display_name', 'unknown')}"
    )

    with st.expander(f"Track list ({len(tracks)})"):
        for i, t in enumerate(tracks, 1):
            st.markdown(
                f"`{i:>3}.` **{t.artist}** – {t.title}  ·  _{t.album}_  ·  {t.duration_str}"
            )

    # ---------------- Download ---------------- #
    if st.button("⬇️ Download all as MP3", type="primary"):
        out_root = Path(tempfile.mkdtemp(prefix="spotify_mp3_"))
        overall = st.progress(0.0, text="Starting…")
        status = st.status("Downloading…", expanded=True)
        results: list[tuple[Track, Optional[Path]]] = []

        for idx, track in enumerate(tracks):
            status.write(f"**{idx + 1}/{len(tracks)}** · {track.artist} – {track.title}")

            # Single reusable bar that reflects the current track's progress.
            bar_slot = st.empty()
            bar = bar_slot.progress(0.0)

            def hook(d: dict, _bar=bar) -> None:
                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    if total:
                        _bar.progress(min(d.get("downloaded_bytes", 0) / total, 1.0))
                elif d["status"] == "finished":
                    _bar.progress(1.0)

            path = download_track(track, out_root, progress_cb=hook)
            results.append((track, path))
            bar_slot.empty()

            overall.progress((idx + 1) / len(tracks), text=f"{idx + 1}/{len(tracks)}")

        successes = [p for _, p in results if p]
        status.update(
            label=f"Done — {len(successes)}/{len(tracks)} downloaded",
            state="complete" if successes else "error",
        )

        # Bundle everything into one ZIP.
        if successes:
            zip_path = out_root / "playlist.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in successes:
                    zf.write(p, arcname=p.name)
            st.session_state["zip_bytes"] = zip_path.read_bytes()

        failures = [t for t, p in results if not p]
        if failures:
            st.warning(
                "The following tracks could not be downloaded:\n\n"
                + "\n".join(f"- {t.artist} – {t.title}" for t in failures)
            )

    if "zip_bytes" in st.session_state:
        st.download_button(
            "📦 Download playlist ZIP",
            data=st.session_state["zip_bytes"],
            file_name=f"{safe_name(meta.get('name', 'playlist'))}.zip",
            mime="application/zip",
        )


if __name__ == "__main__":
    main()