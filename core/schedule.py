from datetime import datetime, time as dtime
from typing import Optional


def _parse(hhmm: str) -> dtime:
    h, m = hhmm.split(":")
    return dtime(int(h), int(m))


def current_slot(schedule: list, now: Optional[datetime] = None):
    """
    Return the schedule entry whose [start, end) window contains `now`,
    or None. Handles windows crossing midnight (e.g. 22:00 -> 02:00).
    """
    now = now or datetime.now()
    t = now.time()
    for entry in schedule:
        start = _parse(entry["start"])
        end = _parse(entry["end"])
        if start <= end:
            if start <= t < end:
                return entry
        else:  # crosses midnight
            if t >= start or t < end:
                return entry
    return None


def seconds_until_next_slot(schedule: list, now: Optional[datetime] = None) -> int:
    """
    Seconds until the next schedule boundary (any start or end time).
    Used by the daemon to sleep efficiently instead of polling.
    """
    now = now or datetime.now()
    t = now.time()
    boundaries = []
    for entry in schedule:
        boundaries.append(_parse(entry["start"]))
        boundaries.append(_parse(entry["end"]))
    boundaries.sort()

    # seconds from midnight now
    now_s = t.hour * 3600 + t.minute * 60 + t.second
    for b in boundaries:
        b_s = b.hour * 3600 + b.minute * 60
        if b_s > now_s:
            return b_s - now_s
    # wrap to tomorrow
    first = boundaries[0]
    first_s = first.hour * 3600 + first.minute * 60
    return (24 * 3600 - now_s) + first_s