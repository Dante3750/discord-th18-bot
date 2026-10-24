# TH18 Base Finder

Finds fresh **Town Hall 18** base layouts posted on X/Twitter and drops them in your Discord channel — image, author and a one-tap **Copy base** link. Runs free on GitHub Actions every 6 hours.

## How it works

1. Searches twitterapi.io for tweets that mention TH18 **and** contain a `link.clashofclans.com` link (retweets excluded).
2. Reads the Town Hall level straight from the layout link (`id=TH18:...`), so mislabeled bases are dropped.
3. Skips any layout ever posted before (even if someone reposts it with a different language link).
4. Posts up to 10 bases per Discord message.
5. Commits `data/state.json` (memory) and `data/bases.json` (latest 300 bases, ready for an app/website) back to the repo.

Only tweets newer than the last run are fetched, so each run usually costs a single API call.

## Setup (5 minutes)

1. **twitterapi.io key** — sign up at twitterapi.io, copy your API key.
2. **Discord webhook** — Channel → Edit Channel → Integrations → Webhooks → New Webhook → Copy URL.
3. In this repo: **Settings → Secrets and variables → Actions → New repository secret**
   - `TWITTER_API_KEY`
   - `DISCORD_WEBHOOK_URL`
4. **Actions tab → TH18 CoC Scraper → Run workflow.** Tick *Dry run* the first time to see what it finds without posting.

## Cost

twitterapi.io charges 15 credits per tweet returned (minimum 15 per call). The free signup credit (up to 100,000 credits) expires after 31 days. With this narrow query and every-6-hours schedule, expect well under 40,000 credits a month — after the free credit runs out that is roughly **$0.40/month**. If the key runs out of credits the run fails and GitHub emails you.

## Options (env vars in the workflow)

| Var | Default | Meaning |
|---|---|---|
| `TH_LEVELS` | `TH18` | e.g. `TH18,TH17` |
| `SEARCH_QUERY` | built-in | full custom search query |
| `MAX_PAGES` | `5` | hard cap on API calls per run |
| `DRY_RUN` | `0` | `1` = search and print only |

## Local run

```bash
pip install -r requirements.txt pytest
python -m pytest -q
TWITTER_API_KEY=... DRY_RUN=1 python scraper.py
```
