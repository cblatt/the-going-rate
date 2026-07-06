# The Going Rate

**Is that guitar priced fairly?** I made an AI read every used guitar listed on
Reverb — all 166,007 of them — and built the price guide the market never had.

**Live site:** `LIVE_URL_HERE`
**No internet / no setup:** open [`docs/index.html`](docs/index.html) in any
browser — the whole product runs offline, data baked in.

## How it works

1. **[`collect.py`](collect.py)** pulls every used-guitar listing from Reverb's
   public API into SQLite (finding along the way that any query silently caps at
   20,000 results — so it bisects the market into price bands).
2. **[`families.py`](families.py)** + **[`analyze.py`](analyze.py)** sort 56,498
   listings into 99 comparable groups using ~100 hand-written keyword rules, then
   price every guitar against its own kind — group comparables, take percentiles,
   no black box. "Cheaper than 82% of comparable Strats" is the whole model.
3. **[`audit.py`](audit.py)** is the honesty layer: an independent LLM re-reads
   the top 1,000 bargains and flags the ones whose titles don't match their group
   ("American Standard with Custom Shop *pickups*", filed under Custom Shop).
   It flagged 113; they're gone from the feed. Every verdict is in
   [`audit_verdicts.json`](audit_verdicts.json).

## Built with AI, decided by a human

Every line of code came out of Claude Code sessions — and the same tool, run
headless, powers the audit referee. But the AI decided nothing: the sorting
rules, the tier taxonomy, what counts as a deal, and what got cut are human
judgment calls. The rules measured **88.7% accurate** against the independent
audit, on the adversarial slice where errors concentrate.

## Honest limitations

Asking prices, not sale prices (Reverb doesn't publish those) — validated the
one way the data allows: listings this site calls overpriced measurably sit
unsold longer. One market snapshot, not a time series. The boutique long tail
isn't priced, because four comparables isn't an honest comparison.

## Reproduce it

```
python3 collect.py     # ~10 min: pull the live market into data/reverb.db
python3 analyze.py     # seconds: sort, price, and bake the site
python3 audit.py       # optional: LLM referee over the top bargains, via claude -p
```

No dependencies. Python stdlib all the way down.
