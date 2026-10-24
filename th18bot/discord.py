"""Post bases to a Discord channel through a webhook (10 embeds per message)."""

import time
import requests

MAX_EMBEDS_PER_MESSAGE = 10
LEVEL_COLORS = {"TH18": 0xE8B730}


class DiscordError(RuntimeError):
    pass


def build_embed(base: dict) -> dict:
    lines = [
        f"**[\U0001f4cb Copy this base]({base['link']})**",
        (f"[View tweet]({base['tweet_url']}) · ❤️ {base.get('likes', 0)}"
         if base.get("tweet_url") else f"Added by {base['author_name']}"),
    ]
    if base.get("tags"):
        lines.append(" ".join(f"`{t}`" for t in base["tags"]))
    if base.get("repeat_of"):
        lines.append(f"\U0001f501 Same picture as an earlier base: [open]({base['repeat_of']})")
    if base.get("of", 1) > 1:
        lines.append(f"Base {base['position']} of {base['of']} in this tweet")
    if base.get("paired") is False and len(base.get("images") or []) > 1:
        lines.append("⚠️ Tweet has more bases than pictures — image may be a different base")
    embed = {
        "title": f"{base['level']} base — @{base['author_handle']}",
        "url": base["link"],  # tapping the title on mobile opens the layout in-game
        "description": "\n".join(lines),
        "color": LEVEL_COLORS.get(base["level"], 0x2ECC71),
        "footer": {"text": base["author_name"]},
    }
    if base.get("image"):
        embed["image"] = {"url": base["image"]}
    if base.get("created_at"):
        embed["timestamp"] = base["created_at"]
    return embed


def build_find_embed(query_image_url, result) -> dict:
    """Discord reply for a screenshot lookup."""
    lines = []
    for m in result["same_picture"]:
        lines.append(f"✅ **Same picture** — [{m['level']} copy link]({m['link']}) · [tweet]({m['tweet_url']})")
    for m in result.get("same_base", []):
        lines.append(f"✅ **Same base** ({m['points']} points line up) — [{m['level']} copy link]({m['link']}) · [tweet]({m['tweet_url']})")
    found = bool(lines)
    if not found:
        for m in result.get("maybe", []):
            lines.append(f"\U0001f50e Looks similar, not confirmed — [{m['level']} copy link]({m['link']})")
    embed = {
        "title": "Base found" if found else "No matching base found",
        "description": "\n".join(lines) if lines else "This base isn't in the collection yet.",
        "color": 0x2ECC71 if found else 0x888888,
    }
    if query_image_url:
        embed["thumbnail"] = {"url": query_image_url}
    return embed


def chunks(items, size=MAX_EMBEDS_PER_MESSAGE):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def send_message(webhook_url, embeds, session=None, retries=4):
    session = session or requests.Session()
    for attempt in range(retries):
        r = session.post(webhook_url, json={"embeds": embeds}, timeout=30)
        if r.status_code in (200, 204):
            return
        if r.status_code == 429 and attempt < retries - 1:
            try:
                wait = float(r.json().get("retry_after", 2))
            except ValueError:
                wait = 2.0
            time.sleep(wait + 0.5)
            continue
        raise DiscordError(f"Discord {r.status_code}: {r.text[:300]}")
