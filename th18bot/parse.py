"""Turn raw tweets into verified Clash of Clans base records.

The layout link itself says which Town Hall it is for:
    https://link.clashofclans.com/en?action=OpenLayout&id=TH18%3AHV%3AAAAA...
                                                          ^^^^ level
So we trust the link, not the tweet text, to decide if a base is TH18.
"""

import re
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

COC_LINK_RE = re.compile(r"https?://link\.clashofclans\.com/[^\s\"'<>)\]\\]+", re.IGNORECASE)
LEVEL_RE = re.compile(r"^(TH|BH)(\d+):", re.IGNORECASE)
TRAILING_JUNK = ".,;:!?)\"'\\…"


def _query_params(url: str) -> dict:
    # Manual split + unquote (not parse_qs) so a literal '+' in the layout id survives.
    params = {}
    for pair in urlparse(url).query.split("&"):
        key, _, value = pair.partition("=")
        if key:
            params[key.lower()] = unquote(value)
    return params


def layout_from_link(link: str):
    """Return (layout_id, level) e.g. ("TH18:HV:AAAA...", "TH18"), or None if not a base link."""
    link = link.rstrip(TRAILING_JUNK)
    params = _query_params(link)
    if params.get("action", "").lower() != "openlayout":
        return None
    layout_id = params.get("id", "").strip()
    match = LEVEL_RE.match(layout_id)
    if not match:
        return None
    return layout_id, f"{match.group(1).upper()}{int(match.group(2))}"


def _links_in(tweet: dict) -> list:
    text = tweet.get("text") or ""
    expanded = [u.get("expanded_url") or "" for u in (tweet.get("entities") or {}).get("urls") or []]
    found = COC_LINK_RE.findall(text + " " + " ".join(expanded))
    found += [u for u in expanded if "link.clashofclans.com" in u.lower()]
    return [u.rstrip(TRAILING_JUNK) for u in found]


def _first_photo(tweet: dict):
    for media in (tweet.get("extendedEntities") or {}).get("media") or []:
        if media.get("type") == "photo" and media.get("media_url_https"):
            return media["media_url_https"]
    return None


def _created_at_iso(raw):
    if not raw:
        return None
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(raw.replace("Z", "+0000"), fmt).astimezone(timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def bases_from_tweet(tweet: dict, levels: set) -> list:
    """All distinct base layouts in one tweet whose level is in `levels` (e.g. {"TH18"})."""
    if tweet.get("retweeted_tweet"):
        return []
    author = tweet.get("author") or {}
    handle = author.get("userName") or "unknown"
    tweet_id = str(tweet.get("id") or "")
    out, seen = [], set()
    for link in _links_in(tweet):
        info = layout_from_link(link)
        if not info:
            continue
        layout_id, level = info
        if level not in levels or layout_id in seen:
            continue
        seen.add(layout_id)
        out.append({
            "layout_id": layout_id,
            "level": level,
            "link": link,
            "image": _first_photo(tweet),
            "tweet_id": tweet_id,
            "tweet_url": tweet.get("url") or f"https://x.com/{handle}/status/{tweet_id}",
            "author_name": author.get("name") or handle,
            "author_handle": handle,
            "text": (tweet.get("text") or "")[:280],
            "likes": tweet.get("likeCount") or 0,
            "created_at": _created_at_iso(tweet.get("createdAt")),
        })
    return out
