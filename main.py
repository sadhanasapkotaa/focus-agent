import argparse
import json
from pathlib import Path

from core.guard import ProcessGuard
from core.state import load_state
from modes.wqu import WQUMode
from modes.coursera import CourseraMode
from modes.shows import ShowsMode
from modes.auto import AutoMode
from modes.revision import RevisionMode
from modes.dsa import DSAMode


CONFIG_PATH = Path("config.json")


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


MODES = {
    "wqu": WQUMode,
    "coursera": CourseraMode,
    "revision": RevisionMode,
    "shows": ShowsMode,
    "dsa": DSAMode,
    "auto": AutoMode,
}


def main():
    parser = argparse.ArgumentParser(description="Laptop Agent Service")
    parser.add_argument("mode", choices=list(MODES.keys()) + ["status"],
                        help="Which mode to run")
    parser.add_argument("--no-guard", action="store_true",
                        help="Disable the process guard for this run")
    parser.add_argument("--session-minutes", type=int, default=0,
                        help="Keep reopening the mode until this many "
                             "minutes elapse. 0 = run once.")
    args = parser.parse_args()

    config = load_config()

    if args.mode == "status":
        print(json.dumps(load_state(), indent=2))
        return

    guard = None
    if (config.get("guard_enabled", True)
            and not args.no_guard
            and args.mode != "auto"):
        guard = ProcessGuard(
            allowed=set(config["allowed_processes"]),
            kill_list=set(config["kill_processes"]),
            poll_seconds=config.get("poll_seconds", 3),
        )
        guard.start()

    try:
        mode_cls = MODES[args.mode]
        if args.mode in ("coursera", "wqu", "revision", "shows", "dsa"):
            mode = mode_cls(config, guard=guard,
                            session_minutes=args.session_minutes)
        elif args.mode == "auto":
            mode = mode_cls(config, guard=guard)
        else:
            mode = mode_cls(config)
        mode.run()
    finally:
        if guard:
            guard.stop()


if __name__ == "__main__":
    main()