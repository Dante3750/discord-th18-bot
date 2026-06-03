"""
TH18 CoC Base Link Scraper → Discord
Searches Twitter's Latest tab for "th18", extracts only
link.clashofclans.com URLs from tweet text, posts them to Discord.
"""

import time
import json
import os
import re
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

# ─── CONFIG ────────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
SEARCH_QUERY        = "th18"
MAX_SCROLLS         = 25
SEEN_FILE           = "seen_links.json"
# ───────────────────────────────────────────────────────────────────────────────

COC_LINK_PATTERN = re.compile(
    r"https?://link\.clashofclans\.com/[^\s\"'>)]+", re.IGNORECASE
)


def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def scrape_coc_links(query: str, max_scrolls: int) -> list:
    search_url = f"https://twitter.com/search?q={requests.utils.quote(query)}&f=live"
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        print(f"[{datetime.now():%H:%M:%S}] Searching Twitter for: {query}")
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(4)

        seen_coc = set()

        for i in range(max_scrolls):
            print(f"  Scroll {i+1}/{max_scrolls}...")
            tweets = page.query_selector_all('article[data-testid="tweet"]')
            for tweet in tweets:
                try:
                    text_el = tweet.query_selector('[data-testid="tweetText"]')
                    full_text = text_el.inner_text() if text_el else ""
                    inner_html = tweet.inner_html()
                    coc_links = COC_LINK_PATTERN.findall(full_text + " " + inner_html)
                    if not coc_links:
                        continue
                    tweet_link_el = tweet.query_selector('a[href*="/status/"]')
                    tweet_href = tweet_link_el.get_attribute("href") if tweet_link_el else ""
                    tweet_url = ("https://twitter.com" + tweet_href) if tweet_href.startswith("/") else tweet_href
                    author_el = tweet.query_selector('[data-testid="User-Name"] a')
                    author = author_el.inner_text() if author_el else "Unknown"
                    for coc_link in coc_links:
                        coc_link = coc_link.rstrip(".,)\"'")
                        if coc_link not in seen_coc:
                            seen_coc.add(coc_link)
                            results.append({
                                "coc_link": coc_link,
                                "tweet_url": tweet_url.split("?")[0],
                                "author": author.strip()
                            })
                except Exception:
                    continue

            page.evaluate("window.scrollBy(0, 1800)")
            time.sleep(2)

        browser.close()

    print(f"  Found {len(results)} CoC base links total.")
    return results


def post_to_discord(items: list, query: str):
    if not items:
        print("No new CoC links to post.")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = {
        "embeds": [{
            "title": f"\U0001f3f0 TH18 Base Links \u2014 {now}",
            "description": f"Found **{len(items)} new Clash of Clans base link(s)** from Twitter `{query}` Latest tab.",
            "color": 0xE8D44D,
            "footer": {"text": "link.clashofclans.com links only"}
        }]
    }
    r = requests.post(DISCORD_WEBHOOK_URL, json=header)
    if r.status_code not in (200, 204):
        print(f"  Discord error: {r.status_code}")
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

    print(f"  Posted {len(items)} CoC links to Discord.")


def main():
    print(f"\n{'='*55}")
    print(f"  TH18 CoC Base Scraper \u2014 {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'='*55}")

    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set!")
        return

    seen = load_seen()
    all_items = scrape_coc_links(SEARCH_QUERY, MAX_SCROLLS)
    new_items = [item for item in all_items if item["coc_link"] not in seen]
    print(f"  New (not yet posted): {len(new_items)}")
    post_to_discord(new_items, SEARCH_QUERY)
    seen.update(item["coc_link"] for item in new_items)
    save_seen(seen)
    print("  Done.\n")


if __name__ == "__main__":
    main()
