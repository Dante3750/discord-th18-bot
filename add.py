"""Add a base by hand (your own bases, or ones you found elsewhere).

    python add.py "https://link.clashofclans.com/en?action=OpenLayout&id=TH18%3A..." \
        --image https://.../pic.jpg --note "anti 3 star war base" --by Dante

It goes through the same path as scraped bases: TH check, duplicate check, fingerprint,
Discord post, saved in data/ (so screenshot search can find it).
"""

import argparse
import os
import sys
from datetime import datetime, timezone

from th18bot import pipeline, store, vision
from th18bot.parse import layout_from_link, tags_from_text


def make_base(link, images, note="", by="manual"):
    info = layout_from_link(link)
    if not info:
        raise ValueError("not a Clash of Clans base layout link")
    layout_id, level = info
    return {
        "layout_id": layout_id, "level": level, "link": link,
        "image": images[0] if images else None, "images": images, "paired": len(images) <= 1,
        "position": 1, "of": 1,
        "tweet_id": "", "tweet_url": None, "author_name": by, "author_handle": by,
        "text": note, "tags": tags_from_text(note), "likes": 0,
        "created_at": datetime.now(timezone.utc).isoformat(), "source": "manual",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("link")
    ap.add_argument("--image", action="append", default=[])
    ap.add_argument("--note", default="")
    ap.add_argument("--by", default="manual")
    args = ap.parse_args(argv)

    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook:
        print("DISCORD_WEBHOOK_URL not set"); return 1
    try:
        base = make_base(args.link.strip(), [u.strip() for u in args.image if u.strip()], args.note, args.by)
    except ValueError as e:
        print(f"error: {e}"); return 1

    state = store.load_state()
    if base["layout_id"] in set(state["seen"]):
        print("already in the collection, nothing to do"); return 0

    records = pipeline.fingerprint_all([base], vision.make_embedder(os.environ.get("VISION", "1") != "0"))
    pipeline.publish([base], webhook, state, records)
    print(f"added {base['level']} base")
    return 0


if __name__ == "__main__":
    sys.exit(main())
