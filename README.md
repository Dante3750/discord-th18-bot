# TH18 Base Finder

Finds fresh **Town Hall 18** base layouts posted on X/Twitter and drops them in your Discord channel, with the picture, author, tags and a one-tap **Copy base** link. Every base is fingerprinted so you can later **find a base from a screenshot**. Runs free on GitHub Actions.

## What it does

- **Collect (every 6 h):** tweets that mention TH18, contain a `link.clashofclans.com` layout link **and** a picture. Retweets excluded.
- **Verify:** the Town Hall level is read from the layout link itself (`id=TH18:...`), so mislabeled bases are dropped.
- **Multi-base tweets:** 4 links + 4 pictures, link N gets picture N. If a tweet has more links than pictures (X allows max 4), the bot doesn't guess; it keeps all pictures and says so.
- **Never repost:** a layout is posted once, even if reposted with another language link.
- **Tags:** `war`, `cwl`, `legend`, `anti-3-star`, `anti-2-star`, `farming`, `trophy`, `hybrid` from the tweet text.
- **Reused-picture flag:** if a "new" base uses a picture we already have under a different layout, the post says so.
- **Screenshot search:**
  - *Same picture* (resized/recompressed/cropped a bit): perceptual hash, near-certain match.
  - *Different screenshot of the same base*: AI similarity with Meta's DINOv2-small model (free, CPU).
  - Nothing close: "No matching base found".

## Buttons (Actions tab -> pick a workflow -> Run workflow)

| Workflow | Use |
|---|---|
| **TH18 CoC Scraper** | Runs by itself every 6 h. Run by hand any time; tick *Dry run* to preview. |
| **Find base from screenshot** | Paste an image URL (in Discord: open image -> Copy link). Answer is posted to Discord. |
| **Add base manually** | Paste a base link (+ picture URL, note). Posted to Discord and made searchable. |

Works from the GitHub mobile app too. A real Discord bot with `/find` and `/add` commands is the next step.

## Data (all in `data/`, committed by the bot)

| File | What |
|---|---|
| `state.json` | memory: last tweet checked + every layout already posted |
| `bases.json` | newest 300 bases, newest first, for an app/website |
| `catalog.jsonl` | **every** base ever, one per line, with picture fingerprints, used for screenshot search |

Public read URL for apps: `https://raw.githubusercontent.com/Dante3750/discord-th18-bot/main/data/bases.json`

## Setup

1. twitterapi.io API key; Discord channel webhook URL.
2. Repo **Settings -> Secrets and variables -> Actions**: add `TWITTER_API_KEY`, `DISCORD_WEBHOOK_URL`.
3. Actions -> **TH18 CoC Scraper** -> Run workflow (tick *Dry run* the first time).

## Cost

twitterapi.io: 15 credits per tweet returned (min 15 per call). Free signup credit (up to 100,000) expires after 31 days. Expect well under 40,000 credits/month, about **$0.40/month** after that. GitHub Actions, the AI model and storage are free.

## Options (env vars)

| Var | Default | Meaning |
|---|---|---|
| `TH_LEVELS` | `TH18` | e.g. `TH18,TH17` |
| `SEARCH_QUERY` | built-in | full custom search query |
| `MAX_PAGES` | `5` | cap on API calls per run |
| `REQUIRE_IMAGE` | `1` | `0` = also keep tweets without a picture |
| `VISION` | `1` | `0` = skip AI model (hashes still saved) |
| `DRY_RUN` | `0` | `1` = search and print only |

## Local

```bash
pip install -r requirements.txt pytest
pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements-vision.txt
python -m pytest -q            # unit tests (offline)
python tests/smoke_model.py    # real model check (downloads ~90 MB once)
python find.py screenshot.jpg
```

## Roadmap: step C (best accuracy)

Detect each building on the screenshot, map it to its grid tile, and compare layouts tile by tile, which is how BaseDrop/ClashFox-style finders work. No public model covers TH18 yet, so we train our own on the pictures this bot collects (labelled once, then retrained as new buildings appear).
