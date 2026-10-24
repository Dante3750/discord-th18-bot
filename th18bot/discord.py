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
        f"[View tweet]({base['tweet_url']}) · ❤️ {base['likes']}",
    ]
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
