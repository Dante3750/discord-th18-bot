import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import scraper
from th18bot import discord, store, twitter
from th18bot.parse import bases_from_tweet, layout_from_link

TH18 = "https://link.clashofclans.com/en?action=OpenLayout&id=TH18%3AHV%3AAAAAPQAAAAJ1aaBB%2Bcc"
TH18_DE = "https://link.clashofclans.com/de?action=OpenLayout&id=TH18%3AHV%3AAAAAPQAAAAJ1aaBB%2Bcc"
TH17 = "https://link.clashofclans.com/en?action=OpenLayout&id=TH17%3AWB%3AAAAAXYZ"


def tweet(i, text="", urls=(), photo="https://pbs.twimg.com/media/default.jpg", retweet=False, photos=None):
    t = {
        "id": str(i), "text": text, "createdAt": "Tue Oct 20 07:00:30 +0000 2026", "likeCount": 3,
        "author": {"userName": f"user{i}", "name": f"User {i}"},
        "entities": {"urls": [{"expanded_url": u} for u in urls]},
    }
    photos = photos if photos is not None else ([photo] if photo else [])
    if photos:
        t["extendedEntities"] = {"media": [{"type": "photo", "media_url_https": u} for u in photos]}
    if retweet:
        t["retweeted_tweet"] = {"id": "1"}
    return t


# --- parsing -----------------------------------------------------------------

def test_level_comes_from_link():
    assert layout_from_link(TH18) == ("TH18:HV:AAAAPQAAAAJ1aaBB+cc", "TH18")
    assert layout_from_link(TH17)[1] == "TH17"
    assert layout_from_link("https://link.clashofclans.com/en?action=OpenPlayerProfile&tag=%23ABC") is None


def test_trailing_punctuation_stripped():
    assert layout_from_link(TH18 + ").")[0].endswith("+cc")


def test_only_wanted_levels_and_language_variants_dedupe():
    t = tweet(5, text=f"th18 war base {TH18} also {TH17}", urls=[TH18_DE], photo="https://pbs.twimg.com/media/x.jpg")
    bases = bases_from_tweet(t, {"TH18"})
    assert len(bases) == 1
    b = bases[0]
    assert b["level"] == "TH18" and b["image"].endswith("x.jpg")
    assert b["tweet_url"] == "https://x.com/user5/status/5"
    assert b["created_at"].startswith("2026-10-20T07:00:30")


def test_link_only_in_expanded_url_is_found():
    assert len(bases_from_tweet(tweet(6, text="new base https://t.co/abc", urls=[TH18]), {"TH18"})) == 1


def test_retweets_ignored():
    assert bases_from_tweet(tweet(7, text=TH18, retweet=True), {"TH18"}) == []


# --- twitter paging stops at already-processed tweets (saves credits) ----------

class FakeResp:
    def __init__(self, code, body):
        self.status_code, self._body, self.text = code, body, json.dumps(body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, **kw):
        self.calls.append(kw["params"])
        return self.responses.pop(0)

    def post(self, url, **kw):
        self.calls.append(kw["json"])
        return self.responses.pop(0)


def test_search_stops_at_last_seen_id():
    page1 = {"tweets": [tweet(30), tweet(29)], "has_next_page": True, "next_cursor": "c1"}
    page2 = {"tweets": [tweet(28), tweet(20), tweet(19)], "has_next_page": True, "next_cursor": "c2"}
    s = FakeSession([FakeResp(200, page1), FakeResp(200, page2)])
    got = twitter.search_new_tweets("k", "q", stop_at_id=20, session=s, delay=0)
    assert [t["id"] for t in got] == ["30", "29", "28"]
    assert len(s.calls) == 2 and s.calls[1]["cursor"] == "c1"


def test_search_raises_when_out_of_credits():
    s = FakeSession([FakeResp(402, {"msg": "insufficient credits"})])
    try:
        twitter.search_new_tweets("k", "q", session=s, delay=0)
        assert False, "should raise"
    except twitter.TwitterAPIError as e:
        assert "402" in str(e)


# --- discord -------------------------------------------------------------------

def test_discord_batches_of_ten_and_embed_shape():
    bases = [bases_from_tweet(tweet(i, text=TH18.replace("cc", f"c{i}"), photo="https://p/i.jpg"), {"TH18"})[0]
             for i in range(23)]
    assert [len(g) for g in discord.chunks(bases)] == [10, 10, 3]
    e = discord.build_embed(bases[0])
    assert e["url"] == bases[0]["link"] and e["image"]["url"] == "https://p/i.jpg" and "timestamp" in e


def test_discord_retries_on_429():
    s = FakeSession([FakeResp(429, {"retry_after": 0}), FakeResp(204, {})])
    discord.send_message("https://hook", [{"title": "x"}], session=s)
    assert len(s.calls) == 2


# --- end to end: no reposts across runs ---------------------------------------

def test_full_run_never_reposts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWITTER_API_KEY", "k")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://hook")
    sent = []
    monkeypatch.setattr(discord, "send_message", lambda hook, embeds: sent.append(embeds))

    run1 = [tweet(11, text=TH18), tweet(10, text=TH17)]
    monkeypatch.setattr(scraper, "search_new_tweets", lambda *a, **k: run1)
    assert scraper.main() == 0
    assert len(sent) == 1 and len(sent[0]) == 1

    state = store.load_state()
    assert state["last_tweet_id"] == 11 and len(state["seen"]) == 1
    assert json.load(open("data/bases.json"))[0]["tweet_id"] == "11"

    # Same base reposted by someone else in a newer tweet (different language link): must be skipped.
    monkeypatch.setattr(scraper, "search_new_tweets", lambda *a, **k: [tweet(12, text=TH18_DE)])
    assert scraper.main() == 0
    assert len(sent) == 1
    assert store.load_state()["last_tweet_id"] == 12


def test_default_query_shape():
    q = scraper.default_query(["TH18"])
    assert "url:link.clashofclans.com" in q and "filter:images" in q and "-filter:retweets" in q and "th18" in q and "since:" in q


# --- images required + multi-base tweets ---------------------------------------

def link(n, level="TH18"):
    return f"https://link.clashofclans.com/en?action=OpenLayout&id={level}%3AHV%3ABASE{n}"


def test_tweet_without_picture_skipped_by_default():
    t = tweet(40, text=link(1), photo=None)
    assert bases_from_tweet(t, {"TH18"}) == []
    assert len(bases_from_tweet(t, {"TH18"}, require_image=False)) == 1


def test_four_links_four_pictures_paired_in_order():
    pics = [f"https://p/{n}.jpg" for n in range(1, 5)]
    t = tweet(41, urls=[link(n) for n in range(1, 5)], photos=pics)
    bases = bases_from_tweet(t, {"TH18"})
    assert [b["image"] for b in bases] == pics
    assert all(b["paired"] for b in bases)
    assert [(b["position"], b["of"]) for b in bases] == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_mixed_levels_keep_pairing_position():
    # TH17 base is first, so the TH18 base must still get the SECOND picture
    t = tweet(42, urls=[link(1, "TH17"), link(2)], photos=["https://p/a.jpg", "https://p/b.jpg"])
    (b,) = bases_from_tweet(t, {"TH18"})
    assert b["image"] == "https://p/b.jpg" and b["paired"]


def test_five_links_four_pictures_not_guessed():
    pics = [f"https://p/{n}.jpg" for n in range(4)]
    t = tweet(43, urls=[link(n) for n in range(5)], photos=pics)
    bases = bases_from_tweet(t, {"TH18"})
    assert len(bases) == 5
    assert all(not b["paired"] and b["images"] == pics for b in bases)
    assert "different base" in discord.build_embed(bases[0])["description"]
