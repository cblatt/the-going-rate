"""Independent LLM audit of the deal feed.

The keyword rules that sort guitars into bins are fast and transparent,
but sellers' titles can fool them — and a mis-binned guitar shows up as
a fake bargain. This script has an LLM referee re-read the top bargains
(title vs. assigned bin) and flag the ones that don't belong. The
verdicts land in audit_verdicts.json; analyze.py drops flagged listings
from the deal feed on its next run.

The referee runs through Claude Code's headless mode (`claude -p`), so
it uses the existing Claude subscription — no API key, no extra cost.

Usage:
    python3 analyze.py                     # writes data/audit_candidates.json
    python3 audit.py --limit 1000         # audit the top 1,000 bargains
    python3 analyze.py                     # rebuild the site minus flagged deals

Verdicts are cached per listing: an interrupted run resumes where it
stopped, and re-runs only audit listings it hasn't seen.
"""

import argparse
import concurrent.futures
import glob
import json
import shutil
import subprocess
from pathlib import Path

CANDIDATES = Path("data/audit_candidates.json")
VERDICTS = Path("audit_verdicts.json")


def claude_bin():
    """The claude CLI: from PATH, or bundled inside the VS Code extension."""
    found = shutil.which("claude")
    if found:
        return found
    bundled = sorted(glob.glob(str(
        Path.home() / ".vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude")))
    if bundled:
        return bundled[-1]
    raise SystemExit("claude CLI not found — install Claude Code or add it to PATH")

PROMPT = """You are auditing a guitar-listing classification system for a price-comparison site.
Each numbered line below is a live Reverb listing: its TITLE and the GROUP the system placed it in (model family, sometimes with a factory tier, era, and condition).
Flag a listing (ok=false) only if the title clearly does not belong in its group:
- different model or brand than the group says (incl. licensed copies like Orville/Tokai/Burny in a Gibson group)
- budget factory line placed in a premium group or vice versa (e.g. Squier in a Fender group, Epiphone in a Gibson group, MIM/import in an American/Custom Shop group)
- a reissue/tribute placed in a real vintage-era group
- not an ordinary playable guitar: parts, bodies, necks, projects, heavily damaged, miniatures
If the title is consistent with the group, or too vague to judge, answer ok=true.
Respond with ONLY a JSON array, one object per listing, same order:
[{"id": 123, "ok": true}, {"id": 456, "ok": false, "why": "Squier, group says Fender"}]

LISTINGS:
"""


def audit_batch(batch, model):
    lines = "\n".join(f'{d["id"]}: "{d["title"]}"  GROUP: {d["bin"]}' for d in batch)
    cmd = [claude_bin(), "-p", PROMPT + lines]
    if model:
        cmd += ["--model", model]
    for attempt in (1, 2):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            text = r.stdout
            arr = json.loads(text[text.find("["): text.rfind("]") + 1])
            return {str(v["id"]): {"ok": bool(v["ok"]), "why": v.get("why", "")}
                    for v in arr if "id" in v}
        except Exception as e:
            if attempt == 2:
                print(f"  batch failed twice, skipping ({e})")
                return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--model", default=None, help="claude CLI model override, e.g. sonnet")
    args = ap.parse_args()

    candidates = json.loads(CANDIDATES.read_text())[: args.limit]
    verdicts = json.loads(VERDICTS.read_text()) if VERDICTS.exists() else {}
    todo = [c for c in candidates if str(c["id"]) not in verdicts]
    print(f"{len(candidates)} candidates, {len(verdicts)} already audited, {len(todo)} to go")

    batches = [todo[i: i + args.batch] for i in range(0, len(todo), args.batch)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(audit_batch, b, args.model) for b in batches]
        done = 0
        for f in concurrent.futures.as_completed(futures):
            verdicts.update(f.result())
            VERDICTS.write_text(json.dumps(verdicts, indent=0))
            done += 1
            print(f"  batch {done}/{len(batches)} done ({len(verdicts)} verdicts total)", flush=True)

    flagged = {k: v for k, v in verdicts.items() if not v["ok"]}
    print(f"\naudited {len(verdicts):,} listings — referee flagged {len(flagged)}")
    for k, v in list(flagged.items())[:15]:
        print(f"  {k}: {v['why']}")
    if len(flagged) > 15:
        print(f"  … and {len(flagged) - 15} more (see {VERDICTS})")
    print("\nnow run: python3 analyze.py   (rebuilds the site minus flagged deals)")


if __name__ == "__main__":
    main()
