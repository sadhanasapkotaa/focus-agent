# focus-agent

A scheduled study-lockdown agent for Linux. During configured time slots it opens
an allow-listed browser (or a video player) for the active mode and kills
distracting processes, then releases the machine when the slot ends.

## How it works
- `modes/auto.py` reads the `schedule` in `config.json` and runs the active mode
  in a subprocess, so a slot boundary can kill the whole process tree.
- `core/guard.py` polls running processes and kills anything in `kill_processes`.
- `core/browser.py` runs Playwright with a per-mode profile and blocks
  navigation to anything outside that mode's `allow_list`.
- Modes: `dsa`, `wqu`, `coursera`, `revision`, `shows`.

## Install (Debian/Ubuntu)
Download the `.deb` from the latest release, then:

    sudo apt install ./focus-agent_0.1.0.deb
    systemctl --user enable --now focus-agent

Config is copied to `~/.local/share/focus-agent/config.json` on first run.
Edit the schedule, allow-lists, `revision_url` and `shows_roots` there.
Logs go to `~/.local/share/focus-agent/logs/`. Check state with `focus-agent status`.
Requires Google Chrome (`browser.executable_path` in the config).

## Build the package
    packaging/build-deb.sh 0.1.0    # outputs dist/focus-agent_0.1.0.deb

## Run from source
    pip install -r requirements.txt && playwright install chromium
    python3 main.py auto
