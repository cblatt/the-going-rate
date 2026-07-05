"""Snapshot collector for used guitar listings on Reverb.

Pulls every live *used* listing in the guitar categories (electric,
acoustic, bass) from Reverb's public API into SQLite. Each run is a
snapshot; diffs between snapshots are how we later infer sales and
price drops, so run it every day or two.

The API silently caps any query at 20,000 reachable listings (400
pages x 50 per page — verified empirically; page 401+ returns empty).
We recursively split each category into price bands until every band
fits inside that window.

Usage:
    python3 collect.py            # full snapshot (~30 min, polite pacing)
    python3 collect.py --test     # one small price band, ~1 min sanity check
"""

import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://api.reverb.com/api/listings"
HEADERS = {"Accept-Version": "3.0", "Accept": "application/hal+json",
           "User-Agent": "guitar-market-research/0.1"}
PRODUCT_TYPES = ["electric-guitars", "acoustic-guitars", "bass-guitars"]

PER_PAGE = 50
WINDOW = 20_000        # hard API cap on reachable results per query
SAFE_BAND = 15_000     # split bands bigger than this (margin for drift)
SLEEP = 0.25           # politeness delay between requests
DB_PATH = "data/reverb.db"


def get_json(params):
    """One API request with retry/backoff on 429s and server errors."""
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except Exception as e:
            wait = 2 ** attempt
            print(f"    retry in {wait}s ({e})")
            time.sleep(wait)
    raise RuntimeError(f"gave up on {url}")


def count(product_type, lo, hi):
    """How many used listings does this price band contain?"""
    params = {"product_type": product_type, "condition": "used",
              "price_min": lo, "per_page": 1}
    if hi is not None:
        params["price_max"] = hi
    time.sleep(SLEEP)
    return get_json(params)["total"]


def price_bands(product_type, lo, hi):
    """Recursively bisect [lo, hi] until each band is under SAFE_BAND.

    Bands share their boundary dollar (e.g. [0,750], [750,1500]) so a
    listing priced at exactly $750.xx can't fall between bands; the
    resulting duplicates are dropped by INSERT OR IGNORE downstream.
    """
    n = count(product_type, lo, hi)
    if n <= SAFE_BAND:
        return [(lo, hi, n)]
    if hi is None:
        # open-ended top band is too big: split at $50k, recurse below
        return price_bands(product_type, lo, 50_000) + price_bands(product_type, 50_000, None)
    mid = (lo + hi) // 2
    if mid == lo:  # can't split a single dollar further; take it anyway
        return [(lo, hi, n)]
    return price_bands(product_type, lo, mid) + price_bands(product_type, mid, hi)


def fetch_band(product_type, lo, hi):
    """Yield every listing in one price band, walking pages until empty."""
    page = 1
    while page <= 400:
        params = {"product_type": product_type, "condition": "used",
                  "price_min": lo, "per_page": PER_PAGE, "page": page}
        if hi is not None:
            params["price_max"] = hi
        time.sleep(SLEEP)
        batch = get_json(params).get("listings", [])
        if not batch:
            return
        yield from batch
        page += 1


def trim(listing, product_type):
    """Keep only the fields the analysis needs."""
    cat = listing.get("categories") or [{}]
    return {
        "listing_id": listing["id"],
        "make": listing.get("make"),
        "model": listing.get("model"),
        "year": listing.get("year"),
        "finish": listing.get("finish"),
        "title": listing.get("title"),
        "description": listing.get("description"),
        "condition": (listing.get("condition") or {}).get("slug"),
        "category": cat[0].get("full_name"),
        "product_type": product_type,
        "auction": 1 if listing.get("auction") else 0,
        "listing_currency": listing.get("listing_currency"),
        "published_at": listing.get("published_at"),
        "url": ((listing.get("_links") or {}).get("web") or {}).get("href"),
        "price_usd_cents": (listing.get("price") or {}).get("amount_cents"),
        "state": (listing.get("state") or {}).get("slug"),
    }


def main():
    test_mode = "--test" in sys.argv
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT, finished_at TEXT, mode TEXT, n_listings INTEGER);
        CREATE TABLE IF NOT EXISTS listings (
            listing_id INTEGER PRIMARY KEY,
            make TEXT, model TEXT, year TEXT, finish TEXT, title TEXT,
            description TEXT, condition TEXT, category TEXT, product_type TEXT,
            auction INTEGER, listing_currency TEXT, published_at TEXT, url TEXT,
            first_seen TEXT, last_seen TEXT);
        CREATE TABLE IF NOT EXISTS observations (
            snapshot_id INTEGER, listing_id INTEGER,
            price_usd_cents INTEGER, state TEXT,
            PRIMARY KEY (snapshot_id, listing_id));
    """)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = db.execute("INSERT INTO snapshots (started_at, mode) VALUES (?, ?)",
                     (now, "test" if test_mode else "full"))
    snapshot_id = cur.lastrowid
    total_seen = 0

    if test_mode:
        work = [("electric-guitars", 7_000, 7_100, count("electric-guitars", 7_000, 7_100))]
    else:
        work = []
        for pt in PRODUCT_TYPES:
            bands = price_bands(pt, 0, None)
            print(f"{pt}: {sum(b[2] for b in bands):,} listings in {len(bands)} price bands")
            work += [(pt, lo, hi, n) for lo, hi, n in bands]

    for pt, lo, hi, n in work:
        hi_label = f"${hi:,}" if hi is not None else "up"
        print(f"  {pt} ${lo:,}-{hi_label} (~{n:,} listings)...", flush=True)
        for listing in fetch_band(pt, lo, hi):
            row = trim(listing, pt)
            seen = datetime.now(timezone.utc).isoformat(timespec="seconds")
            db.execute("""
                INSERT INTO listings (listing_id, make, model, year, finish, title,
                    description, condition, category, product_type, auction,
                    listing_currency, published_at, url, first_seen, last_seen)
                VALUES (:listing_id, :make, :model, :year, :finish, :title,
                    :description, :condition, :category, :product_type, :auction,
                    :listing_currency, :published_at, :url, :seen, :seen)
                ON CONFLICT(listing_id) DO UPDATE SET last_seen = :seen
            """, {**row, "seen": seen})
            db.execute("""
                INSERT OR IGNORE INTO observations
                    (snapshot_id, listing_id, price_usd_cents, state)
                VALUES (?, ?, ?, ?)
            """, (snapshot_id, row["listing_id"], row["price_usd_cents"], row["state"]))
            total_seen += 1
        db.commit()

    done = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db.execute("UPDATE snapshots SET finished_at = ?, n_listings = ? WHERE snapshot_id = ?",
               (done, total_seen, snapshot_id))
    db.commit()
    n_obs = db.execute("SELECT COUNT(*) FROM observations WHERE snapshot_id = ?",
                       (snapshot_id,)).fetchone()[0]
    print(f"snapshot {snapshot_id} done: {n_obs:,} unique listings "
          f"({total_seen:,} fetched incl. band-boundary dupes)")


if __name__ == "__main__":
    main()
