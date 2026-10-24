"""State that survives between GitHub Actions runs (committed to the repo under data/).

data/state.json  - last processed tweet id + every layout already posted (no reposts, ever)
data/bases.json  - rolling feed of the newest bases, newest first (for a future app / website)
"""

import json
import os

STATE_FILE = os.path.join("data", "state.json")
FEED_FILE = os.path.join("data", "bases.json")
MAX_SEEN = 50_000
MAX_FEED = 300


def _read(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)  # atomic: a crash never leaves half-written JSON


def load_state(path=STATE_FILE):
    state = _read(path, {})
    return {"last_tweet_id": int(state.get("last_tweet_id", 0)), "seen": list(state.get("seen", []))}


def save_state(state, path=STATE_FILE):
    state["seen"] = state["seen"][-MAX_SEEN:]
    _write(path, state)


def append_feed(new_bases, path=FEED_FILE):
    feed = _read(path, [])
    newest_first = sorted(new_bases, key=lambda b: int(b["tweet_id"] or 0), reverse=True)
    _write(path, (newest_first + feed)[:MAX_FEED])
