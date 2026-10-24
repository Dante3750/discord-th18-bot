"""Find a base from a screenshot.

    python find.py screenshot.jpg            # local file
    python find.py https://.../image.jpg     # image URL (e.g. copied from Discord)
    python find.py IMAGE --discord           # also post the answer to DISCORD_WEBHOOK_URL

Three-stage search:
  1. same_picture - perceptual hash: it's a repost of a picture we have
  2. same_base    - AI shortlist (DINOv2), each candidate confirmed by lining up the layout (SIFT)
  3. maybe        - shortlisted but not confirmed (shown as "looks similar", never as a match)
All empty = the base isn't in the collection.
"""

import argparse
import json
import os
import sys

from th18bot import catalog, discord, verify, vision


def find(image_ref, embedder=None, fetch=None, top_k=5, shortlist=30, verify_fn=None):
    fetch = fetch or vision.download
    if image_ref.startswith(("http://", "https://")):
        data = fetch(image_ref)
    else:
        with open(image_ref, "rb") as f:
            data = f.read()
    img = vision.open_image(data)
    found = catalog.Index(catalog.load()).search(vision.fingerprint(img, embedder), top_k=shortlist)

    confirmed, maybe = [], []
    try:
        feats = verify.features(img)
        verify_fn = verify_fn or verify.inliers
    except ImportError:  # OpenCV missing: can't confirm, everything stays "maybe"
        feats, verify_fn = None, None
    for cand in found["similar"]:
        points = 0
        if verify_fn:
            try:
                points = verify_fn(img, vision.open_image(fetch(cand["img"])), feats)
            except Exception as e:
                print(f"  could not check {cand['img']}: {e}")
        (confirmed if points >= verify.SAME_BASE_INLIERS else maybe).append({**cand, "points": points})

    confirmed.sort(key=lambda c: -c["points"])
    return {"same_picture": found["same_picture"][:top_k], "same_base": confirmed[:top_k], "maybe": maybe[:3]}


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
