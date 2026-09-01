#!/usr/bin/env python3
"""
preflight4.py — verify Session 4 is TEACHABLE, not merely that it runs.

    python preflight4.py --offline      # logic only. No API keys, no cost.
    python preflight4.py --save         # live. Writes fixtures + deck numbers.
    python preflight4.py --all-providers

THE RULE THIS FILE EXISTS TO ENFORCE
-------------------------------------
Session 2's preflight asked: did the broken agent misbehave?
Session 3's asked:           is the difference large enough to see?
Session 4's asks:            CAN EACH EVALUATOR FAIL?

An evaluator that returns the same verdict on every run has not measured
anything. It cannot distinguish a good run from a bad one, so its number
carries no information however much you like it. Session 3 shipped exactly
such a metric -- task_success = 1.00 across three architectures whose costs
differed 2x -- and only a live run caught it.

So the central artifact here is a DISCRIMINATION MATRIX: every evaluator
against every seed. An evaluator with an all-pass or all-fail row is retired
before class, the same way Session 2 retired seed E.

A check that can only say "it executed" does not ship. Every check below
asserts something that could plausibly come out false.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict

# Gotcha #5: the project must be set before anything reads langsmith.
# Load .env BEFORE importing evalkit -- gotcha #5, the LangSmith project is
# read at import time and cached. A .env that loads late loads for nothing.
try:
    from dotenv import load_dotenv, find_dotenv
    _ENV = find_dotenv(usecwd=True)
    if _ENV:
        load_dotenv(_ENV, override=False)
except ImportError:
    _ENV = ""

import evalkit
from evalkit import (MODEL_IDS, PROJECT, discrimination_report,
                     env_setup, make_chat, make_groundedness_judge,
                     print_discrimination, run_offline_evaluators)

import eval_dataset
import seeds

__version__ = "s4-2026-09-01a"

DECK_NUMBERS = "deck_numbers4.json"

# Two probes is what Session 3 used, and four NO-GOs traced back to exactly
# that. Here the sample is per SEED, and each seed's defect is structural
# rather than statistical, so 2 probes x 2 runs is defensible -- but the
# reproduce-across-runs check below is what makes it so. If a seed passes on
# run 1 and fails on run 2, it is retired, not averaged.
PROBES = [
    "What is the latest released version of the `langgraph` package on PyPI?",
    "Which company maintains the LangGraph library, and in which year was that "
    "company founded?",
]

REPORT: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "", gate: bool = True) -> bool:
    """gate=False records a measurement without letting it fail the run.

    Used sparingly and only where the thing measured is genuinely
    informative rather than a pass/fail requirement -- the judge's
    self-consistency, for instance, which is a Session 8 finding, not a
    Session 4 blocker. An ungated check that quietly becomes the norm is how
    a preflight stops meaning anything, so every one of them carries a
    comment saying why.
    """
    if gate:
        REPORT.append((name, ok, detail))
    tag = "GO" if ok else ("NO-GO" if gate else "note")
    print(f"  [{tag}] {name}" + (f"  -- {detail}" if detail else ""))
    return ok


# ==========================================================================
# 1.  The pin set.  Gotcha #15: adding one provider can make the ENTIRE
#     install fail and pip installs nothing. Resolving is not importing.
# ==========================================================================

REQUIRED = {
    "langchain": "1.3.16", "langchain_core": "1.6.1", "langchain_anthropic": "1.6.1",
    "langgraph": "1.2.11", "langsmith": "0.11.1", "langchain_tavily": "0.2.18",
}


def check_pins(strict: bool = False) -> bool:
    import importlib
    import importlib.metadata as md

    ok = True
    for mod, want in REQUIRED.items():
        dist = mod.replace("_", "-")
        try:
            importlib.import_module(mod)
            got = md.version(dist)
        except Exception as exc:
            ok = check(f"import {mod}", False, repr(exc)) and ok
            continue
        same = got == want
        ok = check(f"{dist} == {want}", same or not strict,
                   f"found {got}" + ("" if same else "  <-- DRIFT")) and ok

    # Importing the module is not importing the SYMBOLS the course uses.
    # A resolution that quietly installed a different minor version is silent.
    try:
        from langchain.agents import create_agent            # noqa: F401
        from langchain_core.tools import tool                # noqa: F401
        from langgraph.graph import StateGraph               # noqa: F401
        from langsmith import Client                         # noqa: F401
        from langsmith.utils import LangSmithNotFoundError   # noqa: F401
        ok = check("every symbol the course uses imports", True) and ok
    except Exception as exc:
        ok = check("every symbol the course uses imports", False, repr(exc)) and ok
    return ok


# ==========================================================================
# 2.  reasoning_effort ON THE WIRE.  Gotcha #12: constructing is not proving.
#     A provider can accept the kwarg and drop it before the request.
# ==========================================================================

def check_effort_on_wire(provider: str = "anthropic") -> bool:
    chat, pinned = make_chat(provider)  # type: ignore[arg-type]
    if not pinned:
        return check(f"reasoning_effort pinned ({provider})", False,
                     "constructor rejected it - falling back, caveat the slide")
    try:
        msg = chat.invoke("Reply with the single word: ok")
        return check(f"reasoning_effort accepted on the wire ({provider})", True,
                     f"model replied {msg.text.strip()[:20]!r}")
    except Exception as exc:
        return check(f"reasoning_effort accepted on the wire ({provider})", False,
                     repr(exc)[:180])


# ==========================================================================
# 3.  Ground truth re-verification.  A stale keyword marks a CORRECT answer
#     wrong, which is worse than no check -- it looks like a finding.
# ==========================================================================

def check_ground_truth() -> bool:
    agent = seeds.build_healthy()
    ok = True
    for row in eval_dataset.EXAMPLES:
        if not row["metadata"].get("verify_url"):
            continue
        q = row["inputs"]["question"]
        want = row["outputs"]["must_contain"]
        try:
            out = agent.invoke({"messages": [q]})
            answer = evalkit.final_text(out).lower()
        except Exception as exc:
            ok = check(f"ground truth: {q[:44]}...", False, repr(exc)[:120]) and ok
            continue
        hit = all(k.lower() in answer for k in want)
        ok = check(f"ground truth: {q[:44]}...", hit,
                   f"must_contain={want}" +
                   ("" if hit else f"  <-- STALE? check {row['metadata']['verify_url']}")) and ok
    return ok


# ==========================================================================
# 4.  THE DISCRIMINATION MATRIX.  This is the file's reason to exist.
# ==========================================================================

SYNTHETIC = {
    # Used by --offline to exercise the matrix logic with no API cost. These
    # are the SHAPES each seed should produce, not saved real runs. They test
    # the harness; they do not verify the seeds. Only a live run does that.
    "healthy": {
        "answer": "The latest langgraph release is 1.2.11 according to PyPI.",
        "tool_calls": [{"name": "web_search", "args": {"query": "langgraph pypi version"}}],
        "evidence": ["[{\"title\": \"langgraph 1.2.11\", \"url\": \"pypi.org\"}]"],
    },
    "wrong_tool": {
        "answer": "The latest langgraph release is 1.2.11.",
        "tool_calls": [{"name": "package_registry", "args": {"package_name": "langgraph"}}],
        "evidence": ['{"package": "langgraph", "version": "1.2.11", '
                     '"source": "internal registry snapshot"}'],
    },
    "redundant": {
        "answer": "The latest langgraph release is 1.2.11 according to PyPI.",
        "tool_calls": [
            {"name": "web_search", "args": {"query": "langgraph pypi version"}},
            {"name": "web_search", "args": {"query": "langgraph pypi version"}},
        ],
        "evidence": ["[{\"title\": \"langgraph 1.2.11\"}]",
                     "[{\"title\": \"langgraph 1.2.11\"}]"],
    },
    # UPDATED 1 Sep from a live run. The original synthetic answer here was a
    # confident "1.2.11" -- the staged hallucination the session was designed
    # around. The real agent refused instead. The fixture now matches what was
    # measured, not what was assumed, because a synthetic that disagrees with
    # reality is a harness that lies to you in advance.
    "empty_search": {
        "answer": ("I could not find any results for this. I do not want to "
                   "state a version number I have not verified."),
        "tool_calls": [{"name": "web_search", "args": {"query": "langgraph pypi version"}}],
        "evidence": ["[]"],
    },
}

# The reference the matrix grades against. Deliberately the row that every
# seed is capable of answering, so the ONLY thing separating them is how.
MATRIX_REF = {
    "must_contain": ["1.2"],
    "expected_tools": ["web_search"],
    "forbidden_tools": ["calculator", "package_registry"],
    "max_tool_calls": 1,
}
MATRIX_INPUTS = {"question": PROBES[0]}


def evaluate_seed(outputs: dict, judge=None) -> list[dict]:
    evs = list(evalkit.OFFLINE_EVALUATORS)
    if judge is not None:
        evs.append(judge)
    return run_offline_evaluators(MATRIX_INPUTS, outputs, MATRIX_REF, evs)


def matrix(runs: dict[str, list[dict]], judge=None):
    """runs: {seed_name: [outputs_dict, ...]}.  Returns (grid, all_rows)."""
    grid: dict[str, dict[str, list]] = defaultdict(dict)
    all_rows: list[dict] = []
    for seed, outs in runs.items():
        per_key: dict[str, list] = defaultdict(list)
        for o in outs:
            for r in evaluate_seed(o, judge):
                per_key[r["key"]].append(r["score"])
                all_rows.append(r)
        grid[seed] = dict(per_key)
    return grid, all_rows


def print_matrix(grid) -> None:
    keys = sorted({k for row in grid.values() for k in row})
    w = max((len(k) for k in keys), default=10) + 2
    print(f"\n{'seed':<14}" + "".join(f"{k:<{w}}" for k in keys))
    print("-" * (14 + w * len(keys)))
    for seed, row in grid.items():
        cells = []
        for k in keys:
            v = row.get(k, [])
            if not v:
                cells.append("-")
            elif all(x is None for x in v):
                cells.append("skip")
            elif all(x for x in v if x is not None):
                cells.append("PASS")
            elif not any(x for x in v if x is not None):
                cells.append("fail")
            else:
                cells.append("FLAKY")
        print(f"{seed:<14}" + "".join(f"{c:<{w}}" for c in cells))
    print()


def assert_matrix(grid, judge_on: bool) -> bool:
    """Four assertions. Each can come out false, which is the whole point."""
    ok = True

    # (a) healthy passes everything. Session 2's classifier tagged its own
    #     clean control as broken THREE ways. Test the control first.
    healthy = grid.get("healthy", {})
    bad = [k for k, v in healthy.items()
           if any(x is False for x in v)]
    ok = check("control: healthy passes every evaluator", not bad,
               f"failed {bad}" if bad else "") and ok

    # (b) each broken seed trips the evaluator it exists to trip.
    for seed, expected in seeds.EXPECTED.items():
        if seed == "healthy" or seed in getattr(seeds, "RETIRED", set()):
            continue
        row = grid.get(seed, {})
        for key in expected:
            if key == "groundedness" and not judge_on:
                check(f"{seed} fails {key}", True, "judge off - not checked")
                continue
            vals = [x for x in row.get(key, []) if x is not None]
            tripped = bool(vals) and not any(vals)
            ok = check(f"{seed} fails {key}", tripped,
                       "" if tripped else f"got {vals} - seed does not reproduce, RETIRE IT") and ok

    # (c) THE PUNCHLINE. Every broken seed must still pass outcome_keyword.
    #     If it does not, the seed makes the cheap grader look better than it
    #     is, and the session's argument evaporates.
    for seed in seeds.EXPECTED:
        if seed == "healthy" or seed in getattr(seeds, "RETIRED", set()):
            continue
        # A seed whose EXPECTED failure IS outcome_keyword cannot also be
        # required to pass it.
        if "outcome_keyword" in seeds.EXPECTED[seed]:
            continue
        vals = [x for x in grid.get(seed, {}).get("outcome_keyword", []) if x is not None]
        waved = bool(vals) and all(vals)
        ok = check(f"outcome_keyword still PASSES {seed}", waved,
                   "" if waved else f"got {vals} - wrong seed for this session") and ok

    # (d) no evaluator is all-pass or all-fail across the whole matrix.
    flat = [{"key": k, "score": x}
            for row in grid.values() for k, v in row.items() for x in v]
    report = discrimination_report(flat)
    print_discrimination(report)

    blind = evalkit.BLIND_BY_DESIGN
    offenders = [k for k, d in report.items()
                 if not d.discriminates and k not in blind]
    ok = check("every evaluator discriminates (except the blind-by-design)",
               not offenders,
               f"retire: {offenders}" if offenders else
               f"blind by design, as expected: {sorted(blind & set(report))}") and ok

    # And the exemption is itself checked. outcome_keyword must be blind here
    # -- if it started discriminating, a seed stopped producing a plausible
    # answer and the session's argument quietly changed underneath us.
    for k in sorted(blind & set(report)):
        d = report[k]
        # Informational, not a gate. Measured 1 Sep: outcome_keyword DOES
        # discriminate, because empty_search fails it. The design assumed it
        # would be blind to all four seeds. It is blind to `redundant` -- a
        # perfect-looking answer reached by wasteful path -- and that single
        # row is enough to carry the session's argument.
        check(f"{k} blind across seeds", not d.discriminates, gate=False, detail=
              "blind, as designed" if not d.discriminates else
              f"discriminates {d.passed}p/{d.failed}f - see the `redundant` row, "
              "which is the one that carries the argument")

    # (e) nothing FLAKY: a verdict that changes between runs is not a verdict.
    not_a_gate = getattr(seeds, "NOT_A_GATE", set())
    flaky = [f"{s}.{k}" for s, row in grid.items() for k, v in row.items()
             if len({x for x in v if x is not None}) > 1 and k not in not_a_gate]
    soft = [f"{s}.{k}" for s, row in grid.items() for k, v in row.items()
            if len({x for x in v if x is not None}) > 1 and k in not_a_gate]
    if soft:
        print(f"  [note] judge disagreed with itself on: {soft}")
        print("         Not a gate. This IS the Session 8 argument, measured.")
    ok = check("no verdict flips between runs", not flaky,
               f"flaky: {flaky}" if flaky else "") and ok
    return ok


# ==========================================================================
# 5.  Live experiment round trip.  "It executed" is not the check.
# ==========================================================================

def check_experiment(client, judge=None) -> bool:
    from langsmith import Client  # noqa: F401

    target = evalkit.make_target(seeds.build_healthy())
    evs = list(evalkit.OFFLINE_EVALUATORS) + ([judge] if judge else [])
    data = eval_dataset.EXAMPLES[:2]
    try:
        eval_dataset.push(client)
        rows = list(client.list_examples(dataset_name=evalkit.DATASET,
                                         metadata={"category": "browser_search"}))
        results = client.evaluate(
            target,
            data=rows or evalkit.DATASET,
            evaluators=evs,
            experiment_prefix="s4-preflight",
            max_concurrency=2,
            num_repetitions=1,
            metadata={"preflight": __version__, "provider": evalkit.PROVIDER},
        )
        got = list(results)
    except Exception as exc:
        return check("live evaluate() round trip", False, repr(exc)[:200])

    if not got:
        return check("live evaluate() round trip", False, "experiment returned no rows")

    def _key(r):
        # EvaluationResult is a pydantic model, not a dict. Handle both --
        # the SDK returns objects here and dicts elsewhere.
        return getattr(r, "key", None) or (r.get("key") if isinstance(r, dict) else None)

    keys = set()
    for row in got:
        er = row.get("evaluation_results") if isinstance(row, dict) else None
        for r in (er or {}).get("results", []) if isinstance(er, dict) else []:
            keys.add(_key(r))
    keys.discard(None)
    expected = {"outcome_keyword", "tool_correctness", "trajectory_no_waste"}
    missing = expected - keys
    return check("feedback keys readable back from the experiment", not missing,
                 f"got {sorted(keys)}" + (f" missing {sorted(missing)}" if missing else ""))


# ==========================================================================
# 6.  What the judge costs.  Nothing goes on a slide that was not measured.
# ==========================================================================

def measure_judge_cost(judge, sample: dict) -> dict:
    from langsmith import Client
    from datetime import datetime, timedelta, timezone

    t0 = time.time()
    since = datetime.now(timezone.utc) - timedelta(seconds=5)
    verdict = judge(MATRIX_INPUTS, sample)
    latency = round(time.time() - t0, 2)

    evalkit.flush_traces()
    client = Client()
    cost = None
    root_id = evalkit.find_trace_root(client, since=since)
    if root_id:
        run, _ = evalkit.read_run_when_ready(client, root_id, min_spans=1)
        if run is not None and run.total_cost:
            cost = float(run.total_cost)
    return {"latency_s": latency, "cost_usd": cost,
            "verdict": str(verdict.get("score"))}


# ==========================================================================

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="exercise the matrix logic with synthetic runs, no API")
    ap.add_argument("--save", action="store_true", help="write fixtures + deck numbers")
    ap.add_argument("--all-providers", action="store_true")
    ap.add_argument("--runs", type=int, default=2, help="runs per seed (live only)")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--strict-pins", action="store_true")
    args = ap.parse_args()

    print(f"preflight4 {__version__} | evalkit {evalkit.__version__} | "
          f"seeds {seeds.__version__} | dataset {eval_dataset.__version__}")
    print("=" * 74)

    if evalkit.__version__ != seeds.__version__ != eval_dataset.__version__:
        print("WARNING: module versions differ. A stale module cached in a running "
              "kernel reports the previous version's verdicts. Restart it.")

    # ---- offline: harness self-test -------------------------------------
    if args.offline:
        print("\nOFFLINE — exercising the matrix logic on synthetic runs.")
        print("This verifies the HARNESS. It does NOT verify the seeds; only a")
        print("live run does that, and Session 2 retired a seed on exactly this")
        print("distinction.\n")
        runs = {k: [v] for k, v in SYNTHETIC.items()}
        grid, _ = matrix(runs, judge=None)
        print_matrix(grid)
        ok = assert_matrix(grid, judge_on=False)
        print("\n" + "=" * 74)
        print("HARNESS", "OK" if ok else "BROKEN — fix before spending live credits")
        return 0 if ok else 1

    # ---- live ------------------------------------------------------------
    print("\n1. pin set")
    ok = check_pins(strict=args.strict_pins)

    print("\n2. environment")
    try:
        ok = check("LANGSMITH_PROJECT resolves", env_setup() == PROJECT, PROJECT) and ok
    except Exception as exc:
        ok = check("LANGSMITH_PROJECT resolves", False, repr(exc)[:160]) and ok
    missing = [v for v in ("ANTHROPIC_API_KEY", "LANGSMITH_API_KEY", "TAVILY_API_KEY")
               if not os.environ.get(v)]
    for v in ("ANTHROPIC_API_KEY", "LANGSMITH_API_KEY", "TAVILY_API_KEY"):
        check(f"{v} present", v not in missing)

    # HARD GATE. Not a NO-GO among others -- a stop.
    #
    # Everything below this line measures the agent. With no keys, every
    # measurement is the same authentication error wearing a different label,
    # and the run prints sixteen confident verdicts about material that never
    # executed. That is the failure mode this whole file exists to prevent,
    # and the first version of it committed the error itself.
    if missing:
        print("\n" + "=" * 74)
        print("STOPPED. No API keys loaded, so nothing below could have run.")
        print(f"missing: {', '.join(missing)}")
        if not _ENV:
            print("\nNo .env was found from this directory.")
            print("  cp .env.example .env      # then fill in the three keys")
            print("  pip install python-dotenv # preflight4 reads .env automatically")
        else:
            print(f"\nLoaded .env from {_ENV} but the keys above are not in it.")
        print("\nNothing was saved. Re-run once the keys are set.")
        return 1

    print("\n3. reasoning_effort on the wire")
    provs = list(MODEL_IDS) if args.all_providers else [evalkit.PROVIDER]
    for p in provs:
        if p != "anthropic" and not args.all_providers:
            continue
        check_effort_on_wire(p)   # informational: a fallback is not a NO-GO

    judge = None if args.no_judge else make_groundedness_judge()

    print("\n4. ground truth still current")
    ok = check_ground_truth() and ok

    print(f"\n5. discrimination matrix — {len(seeds.SEEDS)} seeds x "
          f"{args.runs} runs x {len(PROBES)} probes")
    runs: dict[str, list[dict]] = {}
    for name in seeds.SEEDS:
        outs = []
        for r in range(args.runs):
            for q in PROBES[:1]:      # matrix grades one reference row
                try:
                    outs.append(seeds.run_seed(name, q))
                except Exception as exc:
                    print(f"    {name} run {r} raised: {exc!r}")
        runs[name] = outs
        print(f"    {name:<14} {len(outs)} runs captured")

    empty = [n for n, o in runs.items() if not o]
    if empty:
        print("\n" + "=" * 74)
        print(f"STOPPED. No runs captured for: {', '.join(empty)}")
        print("The matrix has no data, so it has no verdicts. An earlier version")
        print("of this file printed 'seed does not reproduce, RETIRE IT' here --")
        print("a confident conclusion about material that never executed.")
        print("\nNothing was saved. Fix the errors above and re-run.")
        return 1

    grid, _ = matrix(runs, judge)
    print_matrix(grid)
    ok = assert_matrix(grid, judge_on=judge is not None) and ok

    print("\n6. live experiment round trip")
    from langsmith import Client
    client = Client()
    ok = check_experiment(client, judge) and ok

    deck: dict = {"version": __version__, "provider": evalkit.PROVIDER,
                  "effort_pinned": evalkit.EFFORT_PINNED,
                  "matrix": {s: {k: v for k, v in row.items()} for s, row in grid.items()}}

    if judge is not None and runs.get("empty_search"):
        print("\n7. what the judge costs")
        m = measure_judge_cost(judge, runs["empty_search"][0])
        deck["judge"] = m
        check("judge cost measured", m["cost_usd"] is not None,
              f"{m['latency_s']}s, " +
              (f"${m['cost_usd']:.4f}/example" if m["cost_usd"]
               else "no pricing row - add one in Settings -> Models BEFORE the run"))

    if args.save and any(not good for _, good, _ in REPORT):
        print("\nNOT saving fixtures or deck numbers -- there are NO-GOs above.")
        print("Session 3 propagated two unsupported claims into four artifacts")
        print("before a live run caught them. Fix the NO-GOs, then --save.")
    elif args.save:
        flat = [r for outs in runs.values() for r in outs]
        p = seeds.save_fixtures(flat)
        with open(DECK_NUMBERS, "w") as fh:
            json.dump(deck, fh, indent=2)
        print(f"\nwrote {p} and {DECK_NUMBERS}")
        print("Copy deck_numbers4.json next to make_deck.js before building the deck,")
        print("or the data slides ship with their ILLUSTRATIVE stamp still on.")

    print("\n" + "=" * 74)
    fails = [n for n, good, _ in REPORT if not good]
    print(f"{len(REPORT) - len(fails)}/{len(REPORT)} checks GO")
    if fails:
        print("\nNO-GO:")
        for f in fails:
            print(f"  - {f}")
        print("\nA NO-GO is information. Session 3's four NO-GOs corrected two")
        print("overclaims that had already propagated into four artifacts.")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
