"""Shared last step for every way a base enters the system (scraper, manual add):
fingerprint its pictures -> flag reused pictures -> post to Discord -> save state, feed, catalog.
"""

from th18bot import catalog, discord, store


def fingerprint_all(bases, embedder, fetch=None):
    """Attach prints and mark bases whose picture already belongs to a different known base."""
    index = catalog.Index(catalog.load())
    records = {}
    for b in bases:
        rec = catalog.fingerprint_base(b, embedder, fetch)
        if b.get("paired", True):
            for p in rec["prints"]:
                hit = index.search({"phash": p["phash"]}, top_k=1, exclude_layout=b["layout_id"])["same_picture"]
                if hit:
                    b["repeat_of"] = rec["repeat_of"] = hit[0]["link"]
                    break
        records[b["layout_id"]] = rec
    return records


def publish(bases, webhook, state, records, last_tweet_id=None):
    """Post in groups of 10. Progress is saved even if Discord fails halfway (no double posts)."""
    posted = []
    try:
        for group in discord.chunks(bases):
            discord.send_message(webhook, [discord.build_embed(b) for b in group])
            posted += group
    finally:
        state["seen"] += [b["layout_id"] for b in posted]
        if last_tweet_id is not None and len(posted) == len(bases):
            state["last_tweet_id"] = max(state["last_tweet_id"], last_tweet_id)
        store.save_state(state)
        if posted:
            store.append_feed(posted)
            catalog.append([records.get(b["layout_id"], b) for b in posted])
    return posted
