"""Search index of every base ever collected: data/catalog.jsonl (append-only, never trimmed).

One JSON line per base: the base record + "prints": a fingerprint for each of its pictures.
Append-only text keeps git history small (git stores the new lines as a tiny delta).
"""

import json
import os

import numpy as np

from th18bot import vision

CATALOG_FILE = os.path.join("data", "catalog.jsonl")
SAME_PICTURE_BITS = 10   # phash distance <= this -> same picture (resized/recompressed/cropped a bit)
SIMILAR_SCORE = 0.80     # embedding cosine >= this -> probably the same layout (tune with real data)


def load(path=CATALOG_FILE) -> list:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append(records, path=CATALOG_FILE):
    if not records:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")


def fingerprint_base(base: dict, embedder=None, fetch=None) -> dict:
    """Return base + prints for each of its images. A failed download just leaves it unprinted."""
    fetch = fetch or vision.download
    prints = []
    for url in base.get("images") or ([base["image"]] if base.get("image") else []):
        try:
            img = vision.open_image(fetch(url))
            prints.append({"img": url, **vision.fingerprint(img, embedder)})
        except Exception as e:  # never let one bad image stop the run
            print(f"  could not fingerprint {url}: {e}")
    return {**base, "prints": prints}


class Index:
    def __init__(self, records):
        self.records = records
        self.hash_rows = []   # (phash, record index)
        emb_rows, self.emb_owner = [], []
        for i, rec in enumerate(records):
            for p in rec.get("prints") or []:
                self.hash_rows.append((p["phash"], i))
                if p.get("emb"):
                    emb_rows.append(vision.decode_vec(p["emb"]))
                    self.emb_owner.append(i)
        self.emb = np.stack(emb_rows) if emb_rows else np.zeros((0, 1), dtype=np.float32)

    def search(self, img_print: dict, top_k=5, exclude_layout=None) -> dict:
        """{"same_picture": [...], "similar": [...]} best first, one entry per layout."""
        same = {}
        for h, i in self.hash_rows:
            d = vision.hamming(img_print["phash"], h)
            lay = self.records[i]["layout_id"]
            if d <= SAME_PICTURE_BITS and lay != exclude_layout and (lay not in same or d < same[lay][0]):
                same[lay] = (d, i)
        same_list = [{"distance": d, **self._public(i)} for d, i in sorted(same.values())][:top_k]

        similar = []
        if img_print.get("emb") and len(self.emb_owner):
            q = vision.decode_vec(img_print["emb"])
            if q.shape[0] == self.emb.shape[1]:
                scores = self.emb @ q
                best = {}
                for row in np.argsort(-scores):
                    i = self.emb_owner[row]
                    lay = self.records[i]["layout_id"]
                    if scores[row] < SIMILAR_SCORE or len(best) >= top_k:
                        break
                    if lay != exclude_layout and lay not in best and lay not in same:
                        best[lay] = {"score": round(float(scores[row]), 3), **self._public(i)}
                similar = list(best.values())
        return {"same_picture": same_list, "similar": similar}

    def _public(self, i):
        r = self.records[i]
        return {k: r.get(k) for k in ("layout_id", "level", "link", "image", "tweet_url", "author_handle", "tags")}
