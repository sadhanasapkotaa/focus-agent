import json
from pathlib import Path
from threading import Lock

STATE_FILE = Path("agent_state.json")
_lock = Lock()

DEFAULT_STATE = {
    "wqu": {
        "url": "https://learn.wqu.edu/",
        "last_course": None,
        "last_course_url": None,
        "last_seen_url": None,
        "last_video_index": 0,
        "completed": []
    },
    "coursera": {
        "url": "https://www.coursera.org/learn/home",
        "last_course": None,
        "last_course_url": None,
        "last_seen_url": None,
        "last_video_index": 0,
        "completed": []
    },
    "revision": {
        "url": None,
        "last_seen_url": None,
        "completed": []
    },
    "shows": {
        "url": "https://1shows.org/",
        "last_seen_url": None
    },
    "dsa": {
        "url": "https://claude.ai/",
        "last_seen_url": None
    }
}


def load_state() -> dict:
    if not STATE_FILE.exists():
        save_state(DEFAULT_STATE)
        return json.loads(json.dumps(DEFAULT_STATE))
    with open(STATE_FILE, "r") as f:
        data = json.load(f)
    for k, v in DEFAULT_STATE.items():
        data.setdefault(k, v)
    return data


def save_state(state: dict) -> None:
    with _lock:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)


def update_mode(mode: str, **kwargs) -> None:
    state = load_state()
    state.setdefault(mode, {}).update(kwargs)
    save_state(state)