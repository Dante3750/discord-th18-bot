"""
TH18 CoC Base Finder -> Discord (+ data/bases.json feed)

1. Search X/Twitter (twitterapi.io) for new tweets with a link.clashofclans.com layout link.
2. Keep only links whose layout id really is TH18 (read from the link, not the tweet text).
3. Post bases never posted before to Discord, 10 per message, with the tweet's image.
4. Save state + feed under data/ (the GitHub workflow commits them back to the repo).

Env vars:
  TWITTER_API_KEY      required
  DISCORD_WEBHOOK_URL  required unless DRY_RUN=1
  TH_LEVELS            default "TH18"  (comma list, e.g. "TH18,TH17")
  SEARCH_QUERY         override the default search query
  MAX_PAGES            default 5 (safety cap on credits per run)
  REQUIRE_IMAGE        default 1 (skip tweets with a link but no picture; 0 = keep them)
  VISION               default 1 (0 = skip the AI model; picture hashes still saved)
  DRY_RUN=1            print what would be posted, change nothing
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from th18bot import pipeline, store, vision
from th18bot.parse import bases_from_tweet
from th18bot.twitter import search_new_tweets


def default_query(levels):
    words = []
    for level in levels:
        n = level[2:]
        words += [level.lower(), f'"th {n}"', f"#{level.lower()}", f'"town hall {n}"']
    since = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
    return f"({' OR '.join(words)}) url:link.clashofclans.com filter:images -filter:retweets since:{since}"


def main() -> int:
    api_key = os.environ.get("TWITTER_API_KEY", "")
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    dry_run = os.environ.get("DRY_RUN") == "1"
    levels = {s.strip().upper() for s in os.environ.get("TH_LEVELS", "TH18").split(",") if s.strip()}
    query = os.environ.get("SEARCH_QUERY") or default_query(sorted(levels))
    max_pages = int(os.environ.get("MAX_PAGES", "5"))
    require_image = os.environ.get("REQUIRE_IMAGE", "1") != "0"

    if not api_key:
        print("TWITTER_API_KEY not set"); return 1
    if not webhook and not dry_run:
        print("DISCORD_WEBHOOK_URL not set"); return 1

    state = store.load_state()
    seen = set(state["seen"])
    print(f"query: {query}\nlast tweet id: {state['last_tweet_id']}  known layouts: {len(seen)}")

    tweets = search_new_tweets(api_key, query, stop_at_id=state["last_tweet_id"], max_pages=max_pages)
    print(f"new tweets: {len(tweets)}  (~{max(15, len(tweets) * 15)} credits)")

    fresh, batch_ids = [], set()
    for tweet in reversed(tweets):  # oldest first, so the newest base ends up at the bottom in Discord
        for base in bases_from_tweet(tweet, levels, require_image=require_image):
            if base["layout_id"] not in seen and base["layout_id"] not in batch_ids:
                batch_ids.add(base["layout_id"])
                fresh.append(base)
    print(f"new {'/'.join(sorted(levels))} bases: {len(fresh)}")

    if dry_run:
        for b in fresh:
            print(f"  {b['level']}  @{b['author_handle']}  {b['link']}")
        summary(f"Dry run: {len(tweets)} new tweets, {len(fresh)} new bases would be posted")
        return 0

    records = pipeline.fingerprint_all(fresh, vision.make_embedder(os.environ.get("VISION", "1") != "0"))
    last_id = max(int(t["id"]) for t in tweets) if tweets else None
    posted = pipeline.publish(fresh, webhook, state, records, last_tweet_id=last_id)
    summary(f"{len(tweets)} new tweets, posted {len(posted)} new bases")
    return 0


def summary(msg):
    """One-line result, shown on the GitHub run page."""
    print(msg)
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::notice title=TH18 scraper::{msg}")


if __name__ == "__main__":
    sys.exit(main())
