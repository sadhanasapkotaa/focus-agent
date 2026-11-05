from core.player import build_playlist, play_from
from core.state import load_state, update_mode


class ShowsMode:
    """
    Reward mode: plays the shows/movies playlist from configured roots.
    Resumes from last index.
    """
    name = "shows"

    def __init__(self, config: dict):
        self.config = config
        self.roots = config.get("shows_roots", ["./Shows", "./Movies"])

    def run(self):
        state = load_state()[self.name]
        playlist = build_playlist(self.roots)
        if not playlist:
            print(f"[shows] No videos found under {self.roots}")
            return
        start = int(state.get("last_video_index", 0))
        if start >= len(playlist):
            start = 0
        print(f"[shows] {len(playlist)} videos. Resuming at index {start}.")
        stopped_at = play_from(playlist, start)
        update_mode(self.name, last_video_index=stopped_at)
        print(f"[shows] Saved resume index: {stopped_at}")