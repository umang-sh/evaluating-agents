#!/usr/bin/env python3
"""
Session 5 — push the class benchmark pool to LangSmith, and version it.

    python push_pool.py --dry                 # screen only, no network, no key
    python push_pool.py --tag v1              # screen, push, tag
    python push_pool.py --show v1             # read the dataset back AT that tag

SCREEN-BEFORE-PUSH IS THE POINT, NOT A CONVENIENCE
--------------------------------------------------
Forty students times two rows is eighty rows in fifteen minutes -- a real
artifact, and exactly the corpus Session 6's regression testing needs. It is
also eighty rows nobody has falsified, which is the Session 4 sin one level up:
a regression baseline made of rows that nothing can fail will produce an
all-pass table forever, and an all-pass table is not a passing grade, it is an
absence of information.

So a row enters the pool only if the screener says it makes a bet. Rows that do
not are reported by name, not silently dropped -- a rejected row is the most
useful thing in the block and its author should see why.

VERSIONING, verified 7 Sep 2026 against the shipped langsmith wheel and
reference.langchain.com. Two things every tutorial gets wrong:

  * `update_dataset_tag` REQUIRES `as_of`, and it must be an EXACT version
    timestamp -- take it from `read_dataset_version(...).as_of`, never
    `datetime.now()`.
  * `list_examples(as_of=...)` accepts a TAG STRING as well as a timestamp,
    which is what makes a tag worth having.

And one that will cost you an hour: `list_examples` SILENTLY IGNORES unknown
keyword arguments. Misspell `splits` and you get the whole dataset back with no
error, no warning, and a number you will believe.
"""

from __future__ import annotations

import argparse
import sys

import row_screen

DATASET = "s5-class-benchmark-pool"


def _screen(rows: list[dict]) -> tuple[list[dict], list]:
    screens = row_screen.screen_all(rows)
    row_screen.print_screen(screens, verbose=False)
    keep = [r for r, s in zip(rows, screens) if s.ships]
    rejected = [s for s in screens if not s.ships]
    if rejected:
        print(f"\n  {len(rejected)} row(s) NOT admitted to the pool:")
        for s in rejected:
            reason = (f"healthy fails {s.healthy_failures}" if s.verdict == "BROKEN"
                      else (s.warnings[0] if s.warnings else "no shape fails it"))
            print(f"    - [{s.verdict}] {s.question[:52]:<52} {reason}")
    print(f"\n  admitted {len(keep)} / {len(rows)}")
    return keep, rejected


def collect(paths: list[str]) -> list[dict]:
    """Load rows from one or more student files. Instructor-owned fallback: if
    no submissions exist, the pool is the instructor's own rows and the block
    still runs. The opener never stands on a submission."""
    import importlib.util
    import os

    rows: list[dict] = []
    for p in paths:
        if not os.path.exists(p):
            print(f"  (no such file: {p})")
            continue
        spec = importlib.util.spec_from_file_location(f"_pool_{len(rows)}", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)          # type: ignore[union-attr]
        got = mod.rows_for_pool() if hasattr(mod, "rows_for_pool") else mod.MY_ROWS
        got = [r for r in got if "TODO" not in str(r["inputs"]["question"])]
        print(f"  {p}: {len(got)} row(s)")
        rows.extend(got)
    return rows


def push(rows: list[dict], tag: str | None) -> int:
    from langsmith import Client

    client = Client()
    if client.has_dataset(dataset_name=DATASET):
        ds = client.read_dataset(dataset_name=DATASET)
    else:
        ds = client.create_dataset(
            dataset_name=DATASET,
            description="Session 5 class benchmark pool. Every row screened: its own "
                        "expectations catch at least one measured failure shape.")

    # `split` is a FIRST-CLASS field on the example dict -- not metadata. The
    # course filters by metadata elsewhere because that path was verified
    # first; both work, and splits are what LangSmith's own UI understands.
    payload = []
    for r in rows:
        e = {"inputs": r["inputs"], "outputs": r["outputs"],
             "metadata": r.get("metadata", {})}
        e["split"] = "adversarial" if e["metadata"].get("category") == "adversarial" \
            else "core"
        payload.append(e)

    res = client.create_examples(dataset_id=ds.id, examples=payload)
    n = res.get("count", len(payload)) if isinstance(res, dict) else len(payload)
    print(f"\n  uploaded {n} examples to {DATASET!r}")

    if tag:
        versions = list(client.list_dataset_versions(dataset_name=DATASET, limit=1))
        if not versions:
            print("  no versions returned -- cannot tag")
            return 1
        latest = client.read_dataset_version(dataset_name=DATASET,
                                             as_of=versions[0].as_of)
        client.update_dataset_tag(dataset_name=DATASET, as_of=latest.as_of, tag=tag)
        print(f"  tagged {latest.as_of} as {tag!r}")
        print("\n  Session 6 pins this tag. Everything pushed after it is invisible to\n"
              "  a regression run reading `as_of={tag!r}` -- which is the whole reason\n"
              "  a benchmark gets a version number.".replace("{tag!r}", repr(tag)))
    return 0


def show(tag: str) -> int:
    from langsmith import Client

    client = Client()
    at_tag = list(client.list_examples(dataset_name=DATASET, as_of=tag))
    now = list(client.list_examples(dataset_name=DATASET))
    print(f"  at tag {tag!r}: {len(at_tag)} examples")
    print(f"  latest      : {len(now)} examples")
    if len(now) != len(at_tag):
        print(f"  -> {len(now) - len(at_tag)} row(s) added since the tag. A regression "
              "run pinned to the tag will not see them, and that is correct.")
    try:
        adv = list(client.list_examples(dataset_name=DATASET, splits=["adversarial"]))
        print(f"  adversarial split: {len(adv)} examples")
    except Exception as exc:
        print(f"  (splits read failed: {type(exc).__name__}: {str(exc)[:70]})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", default=["benchmark_rows.py"],
                    help="student row files (default: benchmark_rows.py)")
    ap.add_argument("--dry", action="store_true", help="screen only. No network.")
    ap.add_argument("--tag", help="tag the resulting version, e.g. v1")
    ap.add_argument("--show", metavar="TAG", help="read the dataset back at a tag")
    args = ap.parse_args()

    if args.show:
        return show(args.show)

    rows = collect(args.files or ["benchmark_rows.py"])
    if not rows:
        print("\n  No rows found. The instructor pool is the fallback -- point this at\n"
              "  eval_dataset.py's EXAMPLES and the block runs with zero submissions.")
        return 1

    keep, _ = _screen(rows)
    if not keep:
        print("\n  Nothing admitted. Nothing pushed. That is the correct outcome.")
        return 1
    if args.dry:
        print("\n  --dry: nothing was pushed.")
        return 0
    return push(keep, args.tag)


if __name__ == "__main__":
    sys.exit(main())
