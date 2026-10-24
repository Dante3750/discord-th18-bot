"""twitterapi.io advanced search, written to spend as few credits as possible.

Cost model (as of Oct 2026): 15 credits per tweet returned, 15 credits minimum per call.
So: search narrowly, and stop paging as soon as we reach tweets we've already processed.
"""

import time
import requests

API_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"
FREE_TIER_DELAY_S = 5.5  # free accounts are limited to roughly one request every 5 seconds


class TwitterAPIError(RuntimeError):
    pass


def _get(session, api_key, params, retries=3):
    for attempt in range(retries):
        r = session.get(API_URL, headers={"X-API-Key": api_key}, params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
            time.sleep(FREE_TIER_DELAY_S * (attempt + 2))
            continue
        # 401 = bad key, 402 = out of credits. Fail loudly so GitHub emails you.
        raise TwitterAPIError(f"twitterapi.io {r.status_code}: {r.text[:300]}")


def search_new_tweets(api_key, query, stop_at_id=0, max_pages=5, session=None, delay=FREE_TIER_DELAY_S):
    """Newest-first tweets matching `query` whose id is greater than `stop_at_id`."""
    session = session or requests.Session()
    tweets, cursor = [], None
    for page in range(max_pages):
        params = {"query": query, "queryType": "Latest"}
        if cursor:
            params["cursor"] = cursor
        data = _get(session, api_key, params)
        batch = data.get("tweets") or []
        reached_old = False
        for tweet in batch:
            if int(tweet.get("id") or 0) <= stop_at_id:
                reached_old = True
                break
            tweets.append(tweet)
        cursor = data.get("next_cursor")
        if reached_old or not batch or not cursor or not data.get("has_next_page", True):
            break
        time.sleep(delay)
    return tweets
