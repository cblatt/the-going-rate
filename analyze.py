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


def quantiles(prices_sorted):
    q = lambda p: prices_sorted[min(int(len(prices_sorted) * p), len(prices_sorted) - 1)]
    return {"n": len(prices_sorted), "p10": q(.10), "p25": q(.25),
            "median": q(.50), "p75": q(.75), "p90": q(.90)}


def main():
    db = sqlite3.connect("data/reverb.db")
    snapshot_date = datetime.now(timezone.utc)
    rows = db.execute("""
        SELECT listing_id, make, model, year, title, condition, product_type,
               published_at, url, photo_url, price_usd_cents
        FROM listings JOIN observations USING (listing_id)
        WHERE price_usd_cents BETWEEN ? AND ?""", PRICE_SANE).fetchall()

    # ---- sort every listing into its bin
    guitars = []
    for (lid, make, model, year, title, cond, pt, published, url, photo, cents) in rows:
        family = match_family(make, model, title, pt)
        group = CONDITION_GROUP.get(cond)
        if not family or not group or PARTS_TITLE.search(title or ""):
            continue
        guitars.append({
            "id": lid, "family": family, "cond": group,
            "era": None if REISSUE.search(title or "") else decade(year),
            "title": title, "price": cents / 100, "url": url, "photo": photo,
            "days_listed": (snapshot_date - datetime.fromisoformat(published)).days
                           if published else None,
        })
    print(f"{len(guitars):,} guitars sorted into bins")

    # ---- collect prices at three levels of specificity
    prices = {}
    for g in guitars:
        for key in [(g["family"], g["era"], g["cond"]),
                    (g["family"], None, g["cond"]),
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
    top_deals = deals[:200]

    # ---- price-range tables for the lookup page
    market = {}
    for (family, era, cond), plist in prices.items():
        if len(plist) < MIN_COMPS:
            continue
        market.setdefault(family, []).append(
            {"era": era, "cond": cond, **quantiles(plist)})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "market.json").write_text(json.dumps(market))
    (OUT_DIR / "deals.json").write_text(json.dumps(top_deals))
    print(f"{len(market)} families with price tables -> site/data/market.json")
    print(f"{len(deals):,} below-typical listings; top 200 -> site/data/deals.json")

    print("\ntonight's five biggest discounts:")
    for g in top_deals[:5]:
        print(f"  ${g['price']:>7,.0f} (typical ${g['median']:>7,.0f}, "
              f"{g['discount']:.0%} below, {g['comps']} comps) {g['bin']}")
        print(f"           {g['title'][:78]}")


if __name__ == "__main__":
    main()
