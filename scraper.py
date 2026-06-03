"""
TH18 CoC Base Link Scraper → Discord
Uses ntscraper (no login needed) to search Twitter for "th18",
extracts link.clashofclans.com URLs and posts them to Discord.
"""

import json
import os
import re
import time
import requests
from datetime import datetime
from ntscraper import Nitter

# ─── CONFIG ────────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
SEARCH_QUERY        = "th18 link.clashofclans.com"
TWEET_COUNT         = 100   # how many tweets to fetch
SEEN_FILE           = "seen_links.json"
# ───────────────────────────────────────────────────────────────────────────────

COC_LINK_PATTERN = re.compile(
    r"https?://link\.clashofclans\.com/[^\s\"'>)\]]+", re.IGNORECASE
)


def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def scrape_coc_links() -> list:
    results = []
    seen_coc = set()

    print(f"[{datetime.now():%H:%M:%S}] Searching for: {SEARCH_QUERY}")

    try:
        scraper = Nitter(log_level=1, skip_instance_check=False)
        tweets = scraper.get_tweets(SEARCH_QUERY, mode="term", number=TWEET_COUNT)

        if not tweets or "tweets" not in tweets:
            print("  No tweets returned.")
            return results

        print(f"  Got {len(tweets['tweets'])} tweets")

        for tweet in tweets["tweets"]:
            try:
                # Get tweet text
                text = tweet.get("text", "")

                # Get links from tweet links list
                links_in_tweet = tweet.get("links", [])
                all_text = text + " " + " ".join(links_in_tweet)

                # Extract CoC links
                coc_links = COC_LINK_PATTERN.findall(all_text)

                # Also check for t.co expanded links
                for link in links_in_tweet:
                    if "clashofclans" in link.lower():
                        coc_links.append(link)

                if not coc_links:
                    continue

                tweet_url = tweet.get("link", "")
                author = tweet.get("user", {}).get("name", "Unknown")
                handle = tweet.get("user", {}).get("username", "")

                for coc_link in coc_links:
                    coc_link = coc_link.rstrip(".,)\"'")
                    if coc_link not in seen_coc:
                        seen_coc.add(coc_link)
                        results.append({
                            "coc_link": coc_link,
                            "tweet_url": tweet_url,
                            "author": f"{author} (@{handle})"
                        })

            except Exception as e:
                continue

    except Exception as e:
        print(f"  Scraper error: {e}")
        # Fallback: try searching with just the CoC link domain
        try:
            print("  Trying fallback search...")
            scraper2 = Nitter(log_level=1, skip_instance_check=False)
            tweets2 = scraper2.get_tweets("th18 clashofclans", mode="term", number=TWEET_COUNT)
            if tweets2 and "tweets" in tweets2:
                for tweet in tweets2["tweets"]:
                    text = tweet.get("text", "")
                    links_in_tweet = tweet.get("links", [])
                    all_text = text + " " + " ".join(links_in_tweet)
                    coc_links = COC_LINK_PATTERN.findall(all_text)
                    for link in links_in_tweet:
                        if "clashofclans" in link.lower():
                            coc_links.append(link)
                    if not coc_links:
                        continue
                    tweet_url = tweet.get("link", "")
                    author = tweet.get("user", {}).get("name", "Unknown")
                    handle = tweet.get("user", {}).get("username", "")
                    for coc_link in coc_links:
                        coc_link = coc_link.rstrip(".,)\"'")
                        if coc_link not in seen_coc:
                            seen_coc.add(coc_link)
                            results.append({
                                "coc_link": coc_link,
                                "tweet_url": tweet_url,
                                "author": f"{author} (@{handle})"
                            })
        except Exception as e2:
            print(f"  Fallback also failed: {e2}")

    print(f"  Found {len(results)} CoC base links.")
    return results


def post_to_discord(items: list):
    if not items:
        print("No new CoC links to post.")
        # Post a status message so you know it ran
        requests.post(DISCORD_WEBHOOK_URL, json={
            "embeds": [{
                "title": "TH18 Scraper ran — no new links found",
                "description": f"Ran at {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC",
                "color": 0x888888
            }]
        })
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = {
        "embeds": [{
            "title": f"\U0001f3f0 TH18 Base Links \u2014 {now}",
            "description": f"Found **{len(items)} new Clash of Clans base link(s)**",
            "color": 0xE8D44D,
            "footer": {"text": "th18 scraper • link.clashofclans.com"}
        }]
    }
    r = requests.post(DISCORD_WEBHOOK_URL, json=header)
    if r.status_code not in (200, 204):
        print(f"  Discord error: {r.status_code} {r.text}")
        return
    time.sleep(0.5)

    for item in items:
        embed = {
            "embeds": [{
                "description": (
                    f"**Posted by:** {item['author']}\n"
                    f"**Tweet:** {item['tweet_url']}\n\n"
                    f"\U0001f517 `{item['coc_link']}`\n\n"
                    f"[Open in Clash of Clans]({item['coc_link']})"
                ),
                "color": 0x2ECC71,
            }]
        }
        requests.post(DISCORD_WEBHOOK_URL, json=embed)
        time.sleep(0.8)

    print(f"  Posted {len(items)} links to Discord.")


def main():
    print(f"\n{'='*55}")
    print(f"  TH18 CoC Scraper \u2014 {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'='*55}")

    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set!")
        return

    seen = load_seen()
    all_items = scrape_coc_links()
    new_items = [item for item in all_items if item["coc_link"] not in seen]
    print(f"  New (not yet posted): {len(new_items)}")
    post_to_discord(new_items)
    seen.update(item["coc_link"] for item in new_items)
    save_seen(seen)
    print("  Done.\n")


if __name__ == "__main__":
    main()
