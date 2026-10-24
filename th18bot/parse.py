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


def _photos(tweet: dict) -> list:
    """Photo URLs in the order they appear in the tweet (X allows at most 4)."""
    return [
        m["media_url_https"]
        for m in (tweet.get("extendedEntities") or {}).get("media") or []
        if m.get("type") == "photo" and m.get("media_url_https")
    ]


def _created_at_iso(raw):
    if not raw:
        return None
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(raw.replace("Z", "+0000"), fmt).astimezone(timezone.utc).isoformat()
        except ValueError:
            continue
    return None


TAG_PATTERNS = {
    "war": r"\bwar\b|\bcwl\b",
    "cwl": r"\bcwl\b|clan war league",
    "legend": r"\blegends?\b",
    "anti-3-star": r"anti[\s-]*3|anti[\s-]*three",
    "anti-2-star": r"anti[\s-]*2|anti[\s-]*two",
    "farming": r"\bfarm(ing)?\b",
    "trophy": r"\btroph(y|ies)\b|\bpush(ing)?\b",
    "hybrid": r"\bhybrid\b",
}


def tags_from_text(text: str) -> list:
    low = (text or "").lower()
    return [tag for tag, pat in TAG_PATTERNS.items() if re.search(pat, low)]


def bases_from_tweet(tweet: dict, levels: set, require_image: bool = True) -> list:
    """All distinct base layouts in one tweet whose level is in `levels` (e.g. {"TH18"}).

    Image pairing for multi-base tweets ("5 links + 5 pics"):
      - same number of links and photos -> link N gets photo N (posters list them in order)
      - one link                        -> it gets the first photo
      - counts differ (e.g. 5 links, but X caps photos at 4) -> we can't know which photo
        is which base, so each base keeps all photos and is marked paired=False
    """
    if tweet.get("retweeted_tweet"):
        return []
    photos = _photos(tweet)
    if require_image and not photos:
        return []
    author = tweet.get("author") or {}
    handle = author.get("userName") or "unknown"
    tweet_id = str(tweet.get("id") or "")

    layouts, seen = [], set()  # every base link in the tweet, in order, any level
    for link in _links_in(tweet):
        info = layout_from_link(link)
        if info and info[0] not in seen:
            seen.add(info[0])
            layouts.append((link, *info))

    one_to_one = len(layouts) == len(photos) or len(layouts) == 1
    out = []
    for i, (link, layout_id, level) in enumerate(layouts):
        if level not in levels:
            continue
        if one_to_one and photos:
            image, images, paired = photos[i], [photos[i]], True
        else:
            image, images, paired = (photos[0] if photos else None), photos, False
        out.append({
            "layout_id": layout_id,
            "level": level,
            "link": link,
            "image": image,
            "images": images,
            "paired": paired,
            "position": i + 1,
            "of": len(layouts),
            "tweet_id": tweet_id,
            "tweet_url": tweet.get("url") or f"https://x.com/{handle}/status/{tweet_id}",
            "author_name": author.get("name") or handle,
            "author_handle": handle,
            "text": (tweet.get("text") or "")[:280],
            "tags": tags_from_text(tweet.get("text")),
            "likes": tweet.get("likeCount") or 0,
            "created_at": _created_at_iso(tweet.get("createdAt")),
        })
    return out
