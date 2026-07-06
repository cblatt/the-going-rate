"""Compute market price ranges and find underpriced guitars.

Reads the collected listings, sorts each one into its bin (via
families.py), then works out per-bin price ranges and scores every
guitar against its own bin. Writes two small JSON files the webpage
reads — nothing here runs at demo time.

A "bin" at its most specific is family + decade + condition group
(e.g. "Fender Stratocaster, 2010s, Excellent"). If a specific bin has
fewer than 30 guitars, the listing is compared against the next wider
group instead: same family + condition, then whole family. Every
comparison shown is against at least 30 real guitars.

Usage:  python3 analyze.py
"""

import csv
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from families import match_family

MIN_COMPS = 30
PRICE_SANE = (50_00, 100_000_00)   # cents; outside this = junk/typo listings
DEAL_MIN_PRICE = 100_00            # ignore "deals" under $100 (usually parts)
MAX_REAL_DISCOUNT = 0.70           # >70% below typical = mislabeled, not a deal
OUT_DIR = Path("site/data")

# Sellers miscategorize parts as whole guitars; a part's title gives it away.
PARTS_TITLE = re.compile(
    r"\b(pots?|potentiometer|pickups?|tailpiece|harness|knobs?|pickguard|"
    r"tuners?|saddles?|decal|body only|neck only|loaded body|case only|"
    r"empty case|truss rod|switch|bridge cover|neck plate|"
    r"partscaster|parts caster|partcaster|"
    r"mini|travel guitar|3/4)\b", re.I)

# A reissue's year field often holds the year it imitates, not the year
# it was built — never trust it for era binning.
REISSUE = re.compile(r"reissue|\bavri\b|\bri\b|tribute|\breplica\b", re.I)

# Damaged/modified guitars stay in the price tables (they're real market
# data) but the feed never *recommends* one: its low price is the damage
# speaking, not a bargain.
DEAL_RED_FLAGS = re.compile(
    r"refin|franken|repair|crack|as[- ]is|project|husk|luthier special|"
    r"broken|damage|needs work|non[- ]original finish", re.I)

CONDITION_GROUP = {
    "mint": "Excellent", "excellent": "Excellent",
    "very-good": "Good", "good": "Good",
    "fair": "Rough", "poor": "Rough", "non-functioning": "Rough",
}

# Listing currency stands in for seller region (the API has no seller country).
REGION = {"USD": "US", "EUR": "Europe", "GBP": "Europe", "JPY": "Japan"}


def decade(year_text):
    """'1974' -> '1970s'; anything unparseable -> None."""
    y = (year_text or "").strip()
    return y[:3] + "0s" if re.fullmatch(r"(19|20)\d{2}", y) else None


def pctile(prices_sorted, price):
    """Share of comps strictly cheaper than this price (0..1)."""
    lo, hi = 0, len(prices_sorted)
    while lo < hi:
        mid = (lo + hi) // 2
        if prices_sorted[mid] < price:
            lo = mid + 1
        else:
            hi = mid
    return lo / len(prices_sorted)


DEAL_FIELDS = ("photo", "url", "title", "bin", "comps", "days_listed",
               "price", "median", "discount")


def slim(g):
    """Only the fields a deal card renders — full dicts would bloat data.js."""
    return {k: g[k] for k in DEAL_FIELDS}


def quantiles(prices_sorted):
    q = lambda p: prices_sorted[min(int(len(prices_sorted) * p), len(prices_sorted) - 1)]
    return {"n": len(prices_sorted), "p10": q(.10), "p25": q(.25),
            "median": q(.50), "p75": q(.75), "p90": q(.90)}


def main():
    db = sqlite3.connect("data/reverb.db")
    snapshot_date = datetime.now(timezone.utc)
    rows = db.execute("""
        SELECT listing_id, make, model, year, title, condition, product_type,
               published_at, url, photo_url, price_usd_cents, listing_currency
        FROM listings JOIN observations USING (listing_id)
        WHERE price_usd_cents BETWEEN ? AND ?""", PRICE_SANE).fetchall()

    # ---- sort every listing into its bin
    guitars = []
    for (lid, make, model, year, title, cond, pt, published, url, photo, cents, curr) in rows:
        family = match_family(make, model, title, pt)
        group = CONDITION_GROUP.get(cond)
        if not family or not group or PARTS_TITLE.search(title or ""):
            continue
        guitars.append({
            "id": lid, "family": family, "cond": group,
            "era": None if REISSUE.search(title or "") else decade(year),
            "title": title, "price": cents / 100, "url": url, "photo": photo,
            "currency": curr,
            "days_listed": (snapshot_date - datetime.fromisoformat(published)).days
                           if published else None,
        })
    print(f"{len(guitars):,} guitars sorted into bins")

    # ---- collect prices at three levels of specificity
    prices = {}
    for g in guitars:
        for key in [(g["family"], g["era"], g["cond"]),
                    (g["family"], None, g["cond"]),
                    (g["family"], g["era"], None),
                    (g["family"], None, None)]:
            prices.setdefault(key, []).append(g["price"])
    for v in prices.values():
        v.sort()

    # ---- score every guitar against its most specific big-enough bin
    deals = []
    for g in guitars:
        for key in [(g["family"], g["era"], g["cond"]),
                    (g["family"], None, g["cond"]),
                    (g["family"], None, None)]:
            comps = prices[key]
            if len(comps) >= MIN_COMPS:
                med = comps[len(comps) // 2]
                p25 = comps[len(comps) // 4]
                g["bin"] = " · ".join(str(k) for k in key if k)
                g["comps"] = len(comps)
                g["median"] = med
                g["pct"] = round(pctile(comps, g["price"]), 3)
                g["discount"] = round(1 - g["price"] / med, 3)
                # cheap even vs the cheap quartile = a real deal, not a
                # budget model hiding in a mixed bin
                g["vs_p25"] = round(1 - g["price"] / p25, 3)
                break
        else:
            continue
        if (g["cond"] in ("Excellent", "Good") and g["price"] >= DEAL_MIN_PRICE / 100
                and g["vs_p25"] >= 0.10 and g["discount"] <= MAX_REAL_DISCOUNT
                and not DEAL_RED_FLAGS.search(g["title"] or "")):
            deals.append(g)

    deals.sort(key=lambda g: -g["vs_p25"])

    # ---- independent LLM audit of the deal feed (see audit.py)
    # Candidates out: the top bargains, for the referee to inspect.
    # Verdicts in: anything the referee flagged is dropped from the feed.
    (Path("data") / "audit_candidates.json").write_text(json.dumps(
        [{"id": g["id"], "title": (g["title"] or "")[:140], "bin": g["bin"]}
         for g in deals[:1200]]))
    verdicts_path = Path("audit_verdicts.json")
    audit = {"audited": 0, "flagged": 0}
    if verdicts_path.exists():
        verdicts = json.loads(verdicts_path.read_text())
        flagged = {int(k) for k, v in verdicts.items() if not v["ok"]}
        audit = {"audited": len(verdicts), "flagged": len(flagged)}
        deals = [g for g in deals if g["id"] not in flagged]
        print(f"audit: {audit['audited']:,} deals reviewed by referee, "
              f"{audit['flagged']} flagged & removed from the feed")

    top_deals = deals[:200]

    # ---- price-range tables for the lookup page
    market = {}
    for (family, era, cond), plist in prices.items():
        if len(plist) < MIN_COMPS:
            continue
        market.setdefault(family, []).append(
            {"era": era, "cond": cond, **quantiles(plist)})

    # ---- per-family dashboard data
    by_family = {}
    for g in guitars:
        by_family.setdefault(g["family"], []).append(g)

    deal_pool_by_family = {}
    for d in deals:  # already sorted best-first
        deal_pool_by_family.setdefault(d["family"], []).append(d)

    all_days = sorted(g["days_listed"] for g in guitars if g["days_listed"] is not None)
    market_days_median = all_days[len(all_days) // 2]

    fam_sizes = sorted(by_family, key=lambda f: -len(by_family[f]))
    families = {}
    for fam, gs in by_family.items():
        ps = sorted(g["price"] for g in gs)
        if len(ps) < MIN_COMPS:
            continue
        q = quantiles(ps)
        # histogram of asking prices, clipped to p5..p95 so tails don't flatten it
        lo, hi = ps[int(len(ps) * .05)], ps[max(0, int(len(ps) * .95) - 1)]
        counts = [0] * 24
        span = (hi - lo) or 1
        for p in ps:
            if lo <= p <= hi:
                counts[min(23, int((p - lo) / span * 24))] += 1
        days = sorted(g["days_listed"] for g in gs if g["days_listed"] is not None)
        eras, conds = {}, {}
        for g in gs:
            if g["era"]:
                eras.setdefault(g["era"], []).append(g["price"])
            conds.setdefault(g["cond"], []).append(g["price"])
        fam_deals = deal_pool_by_family.get(fam, [])
        # non-US vs US ask gap for this family; needs a deep pool on both sides
        pools = {}
        for g in gs:
            r = REGION.get(g["currency"])
            if r:
                pools.setdefault(r, []).append(g["price"])
        us = sorted(pools.get("US", []))
        fam_regions = []
        if len(us) >= 50:
            us_med = us[len(us) // 2]
            for reg in ("Europe", "Japan"):
                p = sorted(pools.get(reg, []))
                if len(p) >= 50:
                    med = p[len(p) // 2]
                    fam_regions.append({"region": reg, "n": len(p), "abroad": med,
                                        "us": us_med, "gap": round(med / us_med - 1, 3)})
        # representative photo: an Excellent-condition listing priced
        # nearest the group median — the most "typical" example we have
        cands = [g for g in gs if g["photo"]]
        pool = [g for g in cands if g["cond"] == "Excellent"] or cands
        rep = min(pool, key=lambda g: abs(g["price"] - q["median"])) if pool else None
        families[fam] = {
            "photo": rep["photo"] if rep else None,
            "example_url": rep["url"] if rep else None,
            "example_title": rep["title"] if rep else None,
            **q,
            "rank": fam_sizes.index(fam) + 1,
            "hist": {"lo": lo, "hi": hi, "counts": counts},
            "by_era": [{"era": e, "n": len(v), "median": sorted(v)[len(v) // 2]}
                       for e, v in sorted(eras.items()) if len(v) >= MIN_COMPS],
            "by_cond": [{"cond": c, "n": len(v), "median": sorted(v)[len(v) // 2]}
                        for c in ("Excellent", "Good", "Rough")
                        if (v := conds.get(c)) and len(v) >= MIN_COMPS],
            "days_median": days[len(days) // 2] if days else None,
            "pct_over_year": round(sum(1 for d in days if d > 365) / len(days), 3) if days else None,
            "deal_count": len(fam_deals),
            "deals": [slim(d) for d in fam_deals[:25]],
            "regions": fam_regions,
        }

    # ---- cross-category insights: what to actually buy
    # vintage effect: 1970s price as a multiple of 2010s, same family
    vintage = []
    for fam, f in families.items():
        eras = {e["era"]: e["median"] for e in f["by_era"]}
        if "1970s" in eras and "2010s" in eras:
            vintage.append({"family": fam, "multiple": round(eras["1970s"] / eras["2010s"], 2),
                            "old": eras["1970s"], "new": eras["2010s"]})
    vintage.sort(key=lambda r: -r["multiple"])

    # condition discount: Good vs Excellent, same family
    condition = []
    for fam, f in families.items():
        cm = {c["cond"]: c["median"] for c in f["by_cond"]}
        if "Excellent" in cm and "Good" in cm and cm["Excellent"] > 0:
            condition.append({"family": fam, "save": round(1 - cm["Good"] / cm["Excellent"], 3),
                              "exc": cm["Excellent"], "good": cm["Good"]})
    condition.sort(key=lambda r: -r["save"])

    # liquidity: fastest and slowest movers (bigger families only, for stability)
    liq = [{"family": fam, "days": f["days_median"], "n": f["n"]}
           for fam, f in families.items() if f["days_median"] is not None and f["n"] >= 100]
    liq.sort(key=lambda r: r["days"])
    liquidity = {"fast": liq[:8], "slow": liq[-8:][::-1]}

    # deal density: where underpriced listings cluster right now
    density = [{"family": fam, "share": round(f["deal_count"] / f["n"], 3),
                "deal_count": f["deal_count"], "n": f["n"]}
               for fam, f in families.items() if f["n"] >= 100]
    density.sort(key=lambda r: -r["share"])

    scored = [g for g in guitars if "pct" in g]

    # does the market punish overpricing? price position vs time-on-market
    overpricing = []
    for label, lo_p, hi_p in [("cheapest 10%", 0, .10), ("10–25%", .10, .25),
                              ("25–50%", .25, .50), ("50–75%", .50, .75),
                              ("75–90%", .75, .90), ("priciest 10%", .90, 1.01)]:
        ds = sorted(g["days_listed"] for g in scored
                    if lo_p <= g["pct"] < hi_p and g["days_listed"] is not None)
        if ds:
            overpricing.append({"label": label, "days": ds[len(ds) // 2], "n": len(ds)})

    # what seller words tell you: title vocabulary vs price position
    WORDS = [
        ("“rare”", r"\brare\b"), ("“vintage”", r"vintage"), ("“mint”", r"\bmint\b"),
        ("“custom”", r"\bcustom\b"), ("“relic”", r"relic"),
        ("“original case”", r"ohsc|original (hard ?shell )?case"),
        ("“upgraded/modded”", r"upgrad|\bmodded\b|\bmods\b"),
        ("“player grade”", r"player('?s)? grade|player condition"),
        ("“OBO / make offer”", r"\bobo\b|make (me )?an offer|or best offer"),
    ]
    words = []
    for label, pat in WORDS:
        rx = re.compile(pat, re.I)
        sel = [g for g in scored if rx.search(g["title"] or "")]
        if len(sel) >= 200:
            pcts = sorted(g["pct"] for g in sel)
            ds = sorted(g["days_listed"] for g in sel if g["days_listed"] is not None)
            words.append({"word": label, "n": len(sel),
                          "pct": round(pcts[len(pcts) // 2], 3),
                          "days": ds[len(ds) // 2] if ds else None})
    words.sort(key=lambda w: -w["pct"])

    # the market itself: total asking value + units-vs-dollars brand share
    total_value = sum(r[10] for r in rows) / 100
    all_prices = sorted(r[10] for r in rows)
    overall_median = all_prices[len(all_prices) // 2] / 100
    brand_units, brand_dollars = {}, {}
    for r in rows:
        b = (r[1] or "?").strip().lower()
        brand_units[b] = brand_units.get(b, 0) + 1
        brand_dollars[b] = brand_dollars.get(b, 0) + r[10] / 100
    top_brands = sorted(brand_dollars, key=lambda b: -brand_dollars[b])[:6]
    brands = [{"brand": b.title(), "units": round(brand_units[b] / len(rows), 3),
               "dollars": round(brand_dollars[b] / total_value, 3)} for b in top_brands]

    # geographic arbitrage: the per-family gaps, biggest market-wide extremes
    regions = [{"family": fam, **r} for fam, f in families.items() for r in f["regions"]]
    regions.sort(key=lambda r: r["gap"])
    regions = regions[:12]

    insights = {
        "overpricing": overpricing,
        "words": words,
        "market": {"total_value": total_value, "median": overall_median,
                   "listings": len(rows), "brands": brands},
        "regions": regions,
        "vintage": vintage[:10],
        "vintage_flat": vintage[-3:][::-1] if len(vintage) > 12 else [],
        "condition": condition[:10],
        "condition_flat": condition[-3:][::-1] if len(condition) > 12 else [],
        "liquidity": liquidity,
        "density": density[:10],
    }

    meta = {
        "guitars": len(guitars),
        "groups": sum(len(v) for v in market.values()),
        "families": len(families),
        "market_days_median": market_days_median,
        "audit": audit,
        "generated": snapshot_date.strftime("%B %-d, %Y"),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "market.json").write_text(json.dumps(market))
    (OUT_DIR / "deals.json").write_text(json.dumps([slim(g) for g in top_deals]))
    # full per-family deal pools, lazy-loaded on the first "show all" click
    (OUT_DIR / "famdeals.js").write_text(
        "window.FAM_DEALS=" + json.dumps(
            {fam: [slim(d) for d in deal_pool_by_family.get(fam, [])]
             for fam in families}) + ";")
    # data.js lets the page work from a plain double-click (no server, no fetch)
    (OUT_DIR / "data.js").write_text(
        f"window.FAMILIES={json.dumps(families)};"
        f"window.DEALS={json.dumps([slim(g) for g in top_deals])};"
        f"window.INSIGHTS={json.dumps(insights)};"
        f"window.META={json.dumps(meta)};")

    # ---- the raw-data tab: every scored listing, lazily loaded + CSV
    scored = sorted((g for g in guitars if "bin" in g),
                    key=lambda g: (g["family"], g["pct"]))
    cols = ["id", "family", "title", "price", "cond", "era", "days_listed", "pct", "discount"]
    rows_out = [[g["id"], g["family"], (g["title"] or "")[:80], round(g["price"]),
                 g["cond"], g["era"], g["days_listed"], g["pct"], g["discount"]]
                for g in scored]
    (OUT_DIR / "listings.js").write_text(
        f"window.LISTING_COLS={json.dumps(cols)};"
        f"window.LISTINGS={json.dumps(rows_out, separators=(',', ':'))};")
    with (OUT_DIR / "listings.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols + ["url"])
        for r in rows_out:
            w.writerow(r + [f"https://reverb.com/item/{r[0]}"])
    print(f"{len(rows_out):,} scored listings -> site/data/listings.js + listings.csv")
    print(f"{len(market)} families with price tables -> site/data/market.json")
    print(f"{len(deals):,} below-typical listings; top 200 -> site/data/deals.json")

    print("\ntonight's five biggest discounts:")
    for g in top_deals[:5]:
        print(f"  ${g['price']:>7,.0f} (typical ${g['median']:>7,.0f}, "
              f"{g['discount']:.0%} below, {g['comps']} comps) {g['bin']}")
        print(f"           {g['title'][:78]}")


if __name__ == "__main__":
    main()
