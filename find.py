"""Find a base from a screenshot.

    python find.py screenshot.jpg            # local file
    python find.py https://.../image.jpg     # image URL (e.g. copied from Discord)
    python find.py IMAGE --discord           # also post the answer to DISCORD_WEBHOOK_URL

Prints JSON: {"same_picture": [...], "similar": [...]} - both empty means "not in the collection".
"""

import argparse
import json
import os
import sys

from th18bot import catalog, discord, vision


def find(image_ref, embedder=None, fetch=None, top_k=5):
    if image_ref.startswith(("http://", "https://")):
        data = (fetch or vision.download)(image_ref)
    else:
        with open(image_ref, "rb") as f:
            data = f.read()
    query = vision.fingerprint(vision.open_image(data), embedder)
    return catalog.Index(catalog.load()).search(query, top_k=top_k)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--discord", action="store_true")
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args(argv)

    embedder = vision.make_embedder(os.environ.get("VISION", "1") != "0")
    result = find(args.image, embedder, top_k=args.top)
    print(json.dumps(result, indent=1))

    if args.discord:
        webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
        if not webhook:
            print("DISCORD_WEBHOOK_URL not set"); return 1
        thumb = args.image if args.image.startswith("http") else None
        discord.send_message(webhook, [discord.build_find_embed(thumb, result)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
