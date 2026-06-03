"""
TH18 CoC Base Link Scraper → Discord
Uses twitterapi.io to search Twitter Latest tab for "th18",
extracts link.clashofclans.com URLs and posts them to Discord.
"""

import json
import os
import re
import time
import requests
from datetime import datetime

# ─── CONFIG ────────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
TWITTER_API_KEY     = os.environ.get("TWITTER_API_KEY", "")
SEARCH_QUERY        = "th18 link.clashofclans.com"
MAX_TWEETS          = 100
SEEN_FILE           = "seen_links.json"
# ───────────────────────────────────────────────────────────────────────────────

COC_LINK_PATTERN = re.compile(
    r"https?://link\.clashofclans\.com/[^\s\"'>)\]\\]+", re.IGNORECASE
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

    cursor = None
    fetched = 0

    while fetched < MAX_TWEETS:
        params = {
            "query": SEARCH_QUERY,
            "queryType": "Latest",
        }
        if cursor:
            params["cursor"] = cursor

        try:
            r = requests.get(
                "https://api.twitterapi.io/twitter/tweet/advanced_search",
                headers={"X-API-Key": TWITTER_API_KEY},
                params=params,
                timeout=15
            )

            if r.status_code != 200:
                print(f"  API error: {r.status_code} — {r.text}")
                break

            data = r.json()
            tweets = data.get("tweets", [])

            if not tweets:
                print("  No more tweets.")
                break

            print(f"  Got {len(tweets)} tweets (total so far: {fetched + len(tweets)})")

            for tweet in tweets:
                try:
                    text = tweet.get("text", "")

                    # Get expanded URLs
                    expanded_urls = []
                    for url_obj in tweet.get("entities", {}).get("urls", []):
                        exp = url_obj.get("expanded_url", "")
                        if exp:
                            expanded_urls.append(exp)

                    all_text = text + " " + " ".join(expanded_urls)
                    coc_links = COC_LINK_PATTERN.findall(all_text)

                    # Also check expanded URLs directly
                    for u in expanded_urls:
                        if "clashofclans" in u.lower() and u not in coc_links:
                            coc_links.append(u)

                    if not coc_links:
                        continue

                    author = tweet.get("author", {})
                    screen_name = author.get("userName", "unknown")
                    name = author.get("name", "Unknown")
                    tweet_id = tweet.get("id", "")
                    tweet_url = f"https://x.com/{screen_name}/status/{tweet_id}"

                    for coc_link in coc_links:
                        coc_link = coc_link.rstrip(".,)\"'\\")
                        if coc_link not in seen_coc:
                            seen_coc.add(coc_link)
                            results.append({
                                "coc_link": coc_link,
                                "tweet_url": tweet_url,
                                "author": f"{name} (@{screen_name})"
                            })

                except Exception:
                    continue

            fetched += len(tweets)
            cursor = data.get("next_cursor")
            if not cursor:
                break

            time.sleep(1)

        except Exception as e:
            print(f"  Request error: {e}")
            break

    print(f"  Found {len(results)} CoC base links total.")
    return results


def post_to_discord(items: list):
    if not items:
        print("No new CoC links to post.")
        requests.post(DISCORD_WEBHOOK_URL, json={
            "embeds": [{
                "title": "TH18 Scraper ran — no new CoC links found",
                "description": f"Ran at {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC",
                "color": 0x888888
            }]
        })
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    requests.post(DISCORD_WEBHOOK_URL, json={
        "embeds": [{
            "title": f"\U0001f3f0 TH18 Base Links \u2014 {now}",
            "description": f"Found **{len(items)} new Clash of Clans base link(s)**",
            "color": 0xE8D44D,
            "footer": {"text": "th18 scraper \u2022 link.clashofclans.com"}
        }]
    })
    time.sleep(0.5)

    for item in items:
        requests.post(DISCORD_WEBHOOK_URL, json={
            "embeds": [{
                "description": (
                    f"**Posted by:** {item['author']}\n"
                    f"**Tweet:** {item['tweet_url']}\n\n"
                    f"\U0001f517 `{item['coc_link']}`\n\n"
                    f"[Open in Clash of Clans]({item['coc_link']})"
                ),
                "color": 0x2ECC71,
            }]
        })
        time.sleep(0.8)

    print(f"  Posted {len(items)} links to Discord.")


def main():
    print(f"\n{'='*55}")
    print(f"  TH18 CoC Scraper \u2014 {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'='*55}")

    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set!")
        return
    if not TWITTER_API_KEY:
        print("TWITTER_API_KEY not set!")
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
