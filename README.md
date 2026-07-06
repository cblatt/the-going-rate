# The Going Rate

**Live site: <https://cblatt.github.io/the-going-rate/>**

Reverb has 166,007 used guitars listed right now. The Going Rate reads all of them, prices every guitar against its own kind, and tells you whether an asking price is fair: the price guide the used-guitar market never had.

**Repo & commit history:** <https://github.com/cblatt/the-going-rate>

The full story — what the AI did, what a human decided, and the independent
audit of the results — is on the site, under **"How it was built."**

## Files

| File | What it does |
|---|---|
| [`collect.py`](collect.py) | Pulls every used-guitar listing from Reverb's public API into SQLite |
| [`families.py`](families.py) | ~100 hand-written rules that sort listings into comparable groups |
| [`analyze.py`](analyze.py) | Prices every guitar against its own group; bakes the site's data |
| [`audit.py`](audit.py) | Independent LLM referee over the top bargains (via headless Claude Code) |
| [`audit_verdicts.json`](audit_verdicts.json) | The referee's verdicts — 1,000 audited, 113 flagged |
| [`docs/`](docs/) | The site: plain HTML/JS, no frameworks, no build step |

No dependencies — Python stdlib all the way down.
