"""
Handles:
  - scanning multiple root folders
  - sorting folders alphabetically, then videos alphabetically
  - playing them one by one with resumable index
"""
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".flv", ".wmv"}


def _natural_key(s: str):
    import re
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def build_playlist(roots: List[str]) -> List[Path]:
    """
    Returns videos sorted by: folder path (alphabetical) -> filename (alphabetical).
    Recurses into subfolders. Skips roots that don't exist.
    """
    videos: List[Tuple[str, str, Path]] = []
    for root in roots:
        root_path = Path(root).expanduser().resolve()
        if not root_path.exists():
            continue
        for dirpath, _dirs, files in os.walk(root_path):
            for f in files:
                if Path(f).suffix.lower() in VIDEO_EXTS:
                    full = Path(dirpath) / f
                    videos.append((str(dirpath), f, full))

    videos.sort(key=lambda t: (_natural_key(t[0]), _natural_key(t[1])))
    return [v[2] for v in videos]


def default_player_cmd(path: Path) -> list[str]:
    if sys.platform == "darwin":
        return ["open", str(path)]
    if sys.platform.startswith("win"):
        return ["cmd", "/c", "start", "", str(path)]
    for candidate in ("mpv", "vlc", "xdg-open"):
        from shutil import which
        if which(candidate):
            return [candidate, str(path)]
    return ["xdg-open", str(path)]


def play_from(playlist: List[Path], start_index: int = 0) -> int:
    """
    Blocking play. Returns the index the user stopped at.
    """
    if not playlist:
        print("[player] Playlist empty.")
        return 0
    idx = max(0, min(start_index, len(playlist) - 1))
    while idx < len(playlist):
        video = playlist[idx]
        print(f"[player] ({idx+1}/{len(playlist)}) {video.name}")
        try:
            proc = subprocess.Popen(default_player_cmd(video))
            proc.wait()
        except KeyboardInterrupt:
            print("\n[player] Interrupted.")
            return idx
        except Exception as e:
            print(f"[player] Failed to play {video}: {e}")
        idx += 1
    print("[player] Finished playlist.")
    return idx