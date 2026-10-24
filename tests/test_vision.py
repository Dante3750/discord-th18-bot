import json

import numpy as np
from PIL import ImageEnhance

import add
import find
import scraper
from conftest import TinyEmbedder, fake_base_image, jpeg_bytes
from th18bot import catalog, discord, pipeline, store, verify, vision

LINK = "https://link.clashofclans.com/en?action=OpenLayout&id=TH18%3AHV%3A{}"


def base(n, image):
    return add.make_base(LINK.format(f"B{n}"), [image], note="anti 3 star war base", by="tester")


def test_phash_survives_resize_and_recompress_but_not_other_bases():
    a = fake_base_image("a")
    repost = vision.open_image(jpeg_bytes(a.resize((640, 360)), quality=55))
    assert vision.hamming(vision.phash(a), vision.phash(repost)) <= catalog.SAME_PICTURE_BITS
    assert vision.hamming(vision.phash(a), vision.phash(fake_base_image("b"))) > 20


def test_vector_roundtrip_and_letterbox_shape():
    v = vision.normalize(np.arange(10, dtype=np.float32))
    assert np.allclose(vision.decode_vec(vision.encode_vec(v)), v, atol=1e-3)
    assert vision.letterbox(fake_base_image("x", size=(1920, 886))).shape == (3, 224, 224)


def test_find_same_picture_similar_and_not_found(tmp_path):
    emb = TinyEmbedder()
    known = [base(n, f"https://img/{n}.jpg") for n in range(3)]
    catalog.append(pipeline.fingerprint_all(known, emb).values())

    # 1. exact repost (smaller + recompressed) -> same picture
    jpeg = tmp_path / "repost.jpg"
    jpeg.write_bytes(jpeg_bytes(fake_base_image("https://img/1.jpg").resize((480, 270)), quality=60))
    r = find.find(str(jpeg), emb)
    assert r["same_picture"][0]["link"] == LINK.format("B1")

    # 2. unknown base -> nothing
    r = find.find("https://img/never-seen.jpg", emb)
    assert r["same_picture"] == [] and r["same_base"] == []
    assert discord.build_find_embed(None, r)["title"] == "No matching base found"


class AllLookAlike:
    """Worst case for the AI shortlist (what CI showed with the real model): every base scores ~1."""
    model_id = "all-alike"

    def __call__(self, img):
        return vision.normalize(np.ones(8, dtype=np.float32))


def reshoot(img):
    """Same base, new screenshot: panned, zoomed in, darker."""
    w, h = img.size
    return ImageEnhance.Brightness(img.crop((60, 40, w - 140, h - 60)).resize((1280, 720))).enhance(0.75)


def test_layout_check_picks_the_right_base_even_when_ai_thinks_all_look_alike(tmp_path):
    emb = AllLookAlike()
    known = [base(n, f"https://img/{n}.jpg") for n in range(6)]
    catalog.append(pipeline.fingerprint_all(known, emb).values())

    shot = tmp_path / "my_screenshot.jpg"
    shot.write_bytes(jpeg_bytes(reshoot(fake_base_image("https://img/4.jpg")), quality=70))
    r = find.find(str(shot), emb)
    assert r["same_picture"] == []                         # not the same picture...
    assert [m["link"] for m in r["same_base"]] == [LINK.format("B4")]  # ...but the same base, and only that one
    assert r["same_base"][0]["points"] >= verify.SAME_BASE_INLIERS
    assert all(m["points"] < verify.SAME_BASE_INLIERS for m in r["maybe"])
    assert "Same base" in discord.build_find_embed(None, r)["description"]

    # a base we don't have: shortlisted by the AI, but nothing lines up -> not found
    stranger = tmp_path / "other.jpg"
    stranger.write_bytes(jpeg_bytes(reshoot(fake_base_image("https://img/unknown.jpg"))))
    r = find.find(str(stranger), emb)
    assert r["same_base"] == [] and len(r["maybe"]) == 3
    e = discord.build_find_embed(None, r)
    assert e["title"] == "No matching base found" and "not confirmed" in e["description"]


def test_verify_scores():
    a = fake_base_image("v-a")
    assert verify.inliers(a, reshoot(a)) >= verify.SAME_BASE_INLIERS
    assert verify.inliers(a, fake_base_image("v-b")) < verify.SAME_BASE_INLIERS


def test_reused_picture_is_flagged(monkeypatch):
    sent = []
    monkeypatch.setattr(discord, "send_message", lambda hook, embeds: sent.append(embeds))
    first = base(1, "https://img/shared.jpg")
    pipeline.publish([first], "hook", store.load_state(), pipeline.fingerprint_all([first], None))
    # someone posts a DIFFERENT layout link with the SAME picture
    second = base(2, "https://img/shared.jpg")
    pipeline.publish([second], "hook", store.load_state(), pipeline.fingerprint_all([second], None))
    assert second["repeat_of"] == first["link"]
    assert "Same picture as an earlier base" in sent[1][0]["description"]


def test_manual_add_flow(monkeypatch):
    sent = []
    monkeypatch.setattr(discord, "send_message", lambda hook, embeds: sent.append(embeds))
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://hook")
    args = [LINK.format("MINE"), "--image", "https://img/mine.jpg", "--note", "legend push base", "--by", "Dante"]
    assert add.main(args) == 0
    assert add.main(args) == 0  # second time: already known, no repost
    assert len(sent) == 1
    e = sent[0][0]
    assert "Added by Dante" in e["description"] and "`legend`" in e["description"]
    line = json.loads(open(catalog.CATALOG_FILE).read().splitlines()[0])
    assert line["prints"] and line["tags"] == ["legend", "trophy"]
    assert add.main(["https://example.com/not-a-base"]) == 1


def test_scraper_writes_catalog_with_prints(monkeypatch):
    from test_bot import TH18, tweet
    monkeypatch.setenv("TWITTER_API_KEY", "k")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://hook")
    monkeypatch.setattr(discord, "send_message", lambda hook, embeds: None)
    monkeypatch.setattr(scraper, "search_new_tweets", lambda *a, **k: [tweet(50, text="th18 cwl base " + TH18)])
    assert scraper.main() == 0
    (rec,) = catalog.load()
    assert rec["prints"][0]["phash"] and rec["tags"] == ["war", "cwl"]
