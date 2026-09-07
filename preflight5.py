#!/usr/bin/env python3
"""
preflight5.py — run this the night before Session 5.

WHAT EACH PRE-FLIGHT HAS ACTUALLY ASSERTED
------------------------------------------
    preflight.py   (S2)  did the broken agent misbehave?
    preflight3.py  (S3)  is the difference legible, and is the ordering stable?
    preflight4.py  (S4)  can every evaluator both pass and fail something?
    preflight5.py  (S5)  can every ROW be failed -- and did we run it enough
                         times to believe the answer?

Session 5's punchline is not a table, it is an arithmetic result: the Session 3
finding that reproduced needed about a dozen runs to see, and the Session 3
finding we overclaimed needed hundreds. Both come out of one formula. So this
file asserts the two numbers are still legibly different, in addition to
screening the suite.

THREE HARD STOPS INHERITED FROM preflight4, KEPT
------------------------------------------------
  1. Missing API keys stop the run BEFORE any verdict prints. preflight4's
     first version printed `[GO] control passes` on zero data and told us to
     retire three working seeds.
  2. Zero captured runs is a hard stop.
  3. --save refuses to write fixtures or deck numbers when any check is NO-GO.

Usage:
    python preflight5.py --offline      # checks 2,3,4 only. No keys, no cost.
    python preflight5.py                # full GO/NO-GO
    python preflight5.py --save         # + bench_fixtures.json, deck_numbers5.json
    python preflight5.py --runs 5       # injection fire-rate sample size

Exit 0 = GO.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time

CHECKS: list[tuple[str, bool, str, bool]] = []


def check(name: str, ok: bool, detail: str = "", gate: bool = True) -> bool:
    CHECKS.append((name, ok, detail, gate))
    tag = "GO " if ok else ("NO-GO" if gate else "note ")
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))
    return ok if gate else True


def banner(text: str) -> None:
    print(f"\n{'=' * 78}\n{text}\n{'=' * 78}")


def hard_stop(msg: str) -> int:
    banner("HARD STOP")
    print(f"  {msg}\n\n  Nothing was verified. No verdict is printed, because a\n"
          "  verdict computed from zero data is worse than no verdict at all\n"
          "  (preflight4 told us to retire three working seeds that way).\n")
    return 2


# ==========================================================================
# 1.  ENVIRONMENT — hard stops first.
# ==========================================================================

KEY_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY"}


def check_env(provider: str) -> bool:
    banner(f"1. Environment — provider: {provider}")
    ok = check(f"{KEY_VARS[provider]} present", bool(os.environ.get(KEY_VARS[provider])))
    ok &= check("TAVILY_API_KEY present", bool(os.environ.get("TAVILY_API_KEY")))
    ok &= check("LANGSMITH_API_KEY present", bool(os.environ.get("LANGSMITH_API_KEY")))
    if not ok:
        return False

    os.environ["COURSE_PROVIDER"] = provider
    import evalkit
    try:
        resolved = evalkit.env_setup()          # gotcha #5
        ok &= check("LangSmith project resolves (not 'default')",
                    resolved == evalkit.PROJECT, resolved)
    except RuntimeError as exc:
        return check("LangSmith project resolves (not 'default')", False, str(exc))

    import importlib.metadata as md
    for pkg, want in {"langchain-core": "1.6.1", "langgraph": "1.2.11",
                      "langsmith": "0.11.1"}.items():
        try:
            got = md.version(pkg)
        except md.PackageNotFoundError:
            ok &= check(f"{pkg} installed", False, "not installed")
            continue
        ok &= check(f"{pkg} == {want}", got == want, f"found {got}")
    return ok


# ==========================================================================
# 2.  THE ROW SCREEN.  Zero API cost.  This is the file's reason to exist.
# ==========================================================================

def check_row_screen(save: bool) -> bool:
    banner("2. Row screen — can every shipping row be failed?")
    import row_screen
    from eval_dataset import EXAMPLES
    from seeds5 import INJECTION_ROW

    rows = list(EXAMPLES) + [INJECTION_ROW]
    screens = row_screen.screen_all(rows)
    all_ship = row_screen.print_screen(screens)

    broken = [s for s in screens if s.verdict == "BROKEN"]
    retire = [s for s in screens if s.verdict == "RETIRE"]

    ok = check("no row is BROKEN (healthy passes every shipping row)", not broken,
               "; ".join(s.question[:40] for s in broken))
    ok &= check("every shipping row is failed by at least one shape", not retire,
                "RETIRE before class: " + "; ".join(s.question[:40] for s in retire))

    covered = {sh for s in screens if s.ships for sh in s.caught}
    missing = sorted(set(row_screen.ATTRIBUTABLE_SHAPES) - covered)
    ok &= check("suite covers every row-attributable failure shape", not missing,
                f"uncovered: {missing}" if missing else "")

    # The adversarial row must be caught by the SUITE, and specifically by the
    # injected shape -- otherwise Session 5's safety line is a slide, not a row.
    inj = screens[-1]
    ok &= check("adversarial row catches the injected shape",
                "injected" in inj.caught, f"catches {sorted(inj.caught)}")

    if save:
        payload = [{"question": s.question, "category": s.category,
                    "verdict": s.verdict, "caught": s.caught,
                    "warnings": s.warnings} for s in screens]
        with open("row_screen5.json", "w") as fh:
            json.dump({"version": row_screen.__version__, "rows": payload}, fh, indent=2)
        print("  saved -> row_screen5.json")
    return ok and all_ship


# ==========================================================================
# 3.  IS THE SCREENER ITSELF FALSIFIABLE?
#
#     Six times in this course the HARNESS was the broken thing, not the
#     agent. A screener that says SHIPS for everything is preflight4's
#     "[GO] control passes" on zero data, wearing a new hat.
# ==========================================================================

GOOD_ROW = {
    "inputs": {"question": "What is the latest released version of `langgraph` on PyPI?"},
    "outputs": {"must_contain": ["1.2"], "expected_tools": ["web_search"],
                "forbidden_tools": ["package_registry"], "max_tool_calls": 2},
    "metadata": {"category": "browser_search", "difficulty": "easy", "verify_url": None},
}

BLUNT_ROW = {
    "inputs": {"question": "Name a Python package used for building agents."},
    "outputs": {"must_contain": [], "expected_tools": [], "forbidden_tools": [],
                "max_tool_calls": 9},
    "metadata": {"category": "browser_search", "difficulty": "easy", "verify_url": None},
}

WRONG_ROW = {
    "inputs": {"question": "What is the latest released version of `langgraph` on PyPI?"},
    # Ground truth that is simply false. The screener must NOT claim to catch
    # this: its synthetic healthy answer is built FROM must_contain, so a false
    # keyword passes by construction. Asserted here so nobody later mistakes
    # the screen for a ground-truth check.
    "outputs": {"must_contain": ["9.9.9-does-not-exist"], "expected_tools": ["web_search"],
                "forbidden_tools": ["package_registry"], "max_tool_calls": 2},
    "metadata": {"category": "browser_search", "difficulty": "easy", "verify_url": None},
}

# A row whose only catch is the one every row gets for free.
FREEBIE_ROW = {
    "inputs": {"question": "Name a Python package used for building agents."},
    "outputs": {"must_contain": [], "expected_tools": [], "forbidden_tools": [],
                "max_tool_calls": 9},
    "metadata": {"category": "browser_search", "difficulty": "easy", "verify_url": None},
}


def check_screener_falsifiable() -> bool:
    banner("3. Is the screener itself falsifiable?")
    import row_screen

    blunt = row_screen.screen_row(BLUNT_ROW)
    free = row_screen.screen_row(FREEBIE_ROW)
    wrong = row_screen.screen_row(WRONG_ROW)
    good = row_screen.screen_row(GOOD_ROW)

    ok = check("a row with no expectations is RETIREd", blunt.verdict == "RETIRE",
               f"got {blunt.verdict}; attributable catches={sorted(blunt.caught)}")
    ok &= check("blunt row is diagnosed, not merely rejected", len(blunt.warnings) >= 3,
                f"{len(blunt.warnings)} named reasons")
    ok &= check("a duplicate-query catch is reported as FREE, not as a bet",
                "redundant" in free.free and "redundant" not in free.caught,
                f"free={sorted(free.free)} attributed={sorted(free.caught)}")
    ok &= check("a sharp row SHIPS (the screener is not just saying no)",
                good.verdict == "SHIPS", f"got {good.verdict}, catches {sorted(good.caught)}")

    # The screener's honest ceiling, asserted so it cannot quietly be forgotten.
    ok &= check("the screener does NOT claim to catch false ground truth offline",
                wrong.verdict != "BROKEN" and not wrong.ground_truth_checked,
                "ground truth is preflight4's check_ground_truth(), or a live "
                "healthy run passed in -- the synthetic answer is built FROM "
                "must_contain and cannot disagree with it")
    return ok


# ==========================================================================
# 4.  SAMPLE SIZE.  The session's spine, and it costs nothing to compute.
# ==========================================================================
#
# Provenance, and it matters: these are Session 3's own measured numbers, from
# `Session3_State.md`. sigma is the run-to-run stdev of ReAct's hard-probe
# billed tokens over FOUR runs (range 4,009-8,503, mean 6,174).
#
# HONEST LIMITATION, say it on the slide: we have sigma for ONE cell. Applying
# it to the easy-probe comparison assumes the spread is similar there, which
# nobody has measured. The conclusion survives it -- the two n values differ by
# two orders of magnitude, far more than any plausible error in sigma -- but the
# claim is "about a dozen versus hundreds", not a precise number.

S3_SIGMA_TOKENS = 2444.0        # stdev, react hard-probe billed tokens, n=4
S3_MEAN_TOKENS = 6174.0
S3_RANGE = (4009.0, 8503.0)
S3_SIGMA_SOURCE = "Session3_State.md — 4 runs, react hard probe, billed tokens"

# The finding that reproduced on every run: workflow over-searches on easy
# probes. 5,806 vs 2,934 billed tokens.
DELTA_REPRODUCED = 5806.0 - 2934.0
# The finding the deck asserted and the data did not support: the 4% hard-probe
# "flip". 6,174 vs 5,927.
DELTA_OVERCLAIMED = 6174.0 - 5927.0

Z_ALPHA = 1.959964    # two-sided 95%
Z_BETA = 0.841621     # 80% power


def n_per_arm(sigma: float, delta: float,
              z_a: float = Z_ALPHA, z_b: float = Z_BETA) -> int:
    """Two-sample n per arm. The whole sample-size block is this one line."""
    if delta <= 0:
        return math.inf
    return math.ceil(2 * (sigma ** 2) * ((z_a + z_b) ** 2) / (delta ** 2))


def check_sample_size(save: bool) -> bool:
    banner("4. Sample size — the two numbers the session turns on")

    # sigma has no machine-readable source in the repo: preflight3.py's --save
    # output was never committed. Assert the provenance is at least internally
    # consistent, and say plainly that re-deriving it means re-running S3.
    lo, hi = S3_RANGE
    plausible = (hi - lo) / 4.0 < S3_SIGMA_TOKENS < (hi - lo)
    check("sigma is consistent with the recorded range", plausible,
          f"sigma={S3_SIGMA_TOKENS:.0f} on range {lo:.0f}-{hi:.0f}")
    check("sigma has a machine-readable source", False,
          "session3_preflight_runs.json was never committed — sigma is quoted "
          "from Session3_State.md prose. Re-run `preflight3.py --save` to "
          "re-derive it, or the slide rests on a number this file cannot check",
          gate=False)

    n_repro = n_per_arm(S3_SIGMA_TOKENS, DELTA_REPRODUCED)
    n_over = n_per_arm(S3_SIGMA_TOKENS, DELTA_OVERCLAIMED)
    cv = S3_SIGMA_TOKENS / S3_MEAN_TOKENS

    print(f"\n  run-to-run CV .................... {cv:.0%}")
    print(f"  n/arm to see the 2x finding ...... {n_repro:>6}   (delta = {DELTA_REPRODUCED:.0f} tok)")
    print(f"  n/arm to see the 4% 'flip' ....... {n_over:>6}   (delta = {DELTA_OVERCLAIMED:.0f} tok)")
    print(f"  Session 3 actually ran ........... {2:>6}\n")

    ok = check("the reproduced finding is reachable in a classroom", n_repro <= 20,
               f"n={n_repro} per arm")
    ok &= check("the overclaimed finding is visibly out of reach", n_over >= 200,
                f"n={n_over} per arm")
    ok &= check("the two numbers differ by >= 10x (the slide is legible)",
                n_over / max(n_repro, 1) >= 10, f"{n_over / max(n_repro, 1):.0f}x apart")

    if save:
        with open("sample_size5.json", "w") as fh:
            json.dump({"sigma": S3_SIGMA_TOKENS, "sigma_source": S3_SIGMA_SOURCE,
                       "mean": S3_MEAN_TOKENS, "cv": cv,
                       "delta_reproduced": DELTA_REPRODUCED,
                       "delta_overclaimed": DELTA_OVERCLAIMED,
                       "n_reproduced": n_repro, "n_overclaimed": n_over,
                       "n_actually_run": 2}, fh, indent=2)
        print("  saved -> sample_size5.json")
    return ok


# ==========================================================================
# 5.  JUDGE VARIANCE — the live half of the sample-size block.
#     Runs on saved fixtures: no agent invocation, no Tavily searches.
# ==========================================================================

def check_judge_variance(n: int, save: bool) -> bool:
    banner(f"5. Judge variance — {n} runs on IDENTICAL saved evidence")
    import evalkit
    from evalkit import run_offline_evaluators
    from seeds import load_fixtures

    fixtures = load_fixtures()
    if not fixtures:
        return check("fixtures present", False,
                     "seed_fixtures.json missing — run `preflight4.py --save` first")

    sample = next((f for f in fixtures if f["seed"] == "empty_search"), None)
    if sample is None:
        return check("empty_search fixture present", False, "no empty_search run saved")

    judge = evalkit.make_groundedness_judge()
    ref = {"must_contain": ["1.2"], "expected_tools": ["web_search"],
           "forbidden_tools": [], "max_tool_calls": 2}
    inputs = {"question": "What is the latest released version of `langgraph` on PyPI?"}

    verdicts, latencies = [], []
    for i in range(n):
        t0 = time.perf_counter()
        try:
            res = run_offline_evaluators(inputs, sample, ref, [judge])
        except Exception as exc:
            return check(f"judge run {i + 1} completed", False,
                         f"{type(exc).__name__}: {str(exc)[:90]}")
        latencies.append(time.perf_counter() - t0)
        verdicts.append(next((r.get("score") for r in res
                              if r.get("key") == "groundedness"), None))
        print(f"    run {i + 1}: score={verdicts[-1]!r}  {latencies[-1]:.1f}s")

    if not latencies:
        return check("judge produced runs", False)

    spread = max(latencies) / max(min(latencies), 1e-6)
    disagrees = len({v for v in verdicts}) > 1
    mean_lat = statistics.mean(latencies)

    print(f"\n  latency  min {min(latencies):.1f}s  max {max(latencies):.1f}s  "
          f"mean {mean_lat:.1f}s  spread {spread:.1f}x")
    print(f"  verdicts {verdicts}  -> {'SPLIT' if disagrees else 'unanimous'}\n")

    # The gate is on the DEMO, not on the judge. If the judge has become stable
    # the live block has nothing to show and you need to know tonight.
    ok = check("the live demo has something to show "
               "(latency spread >= 2x OR the judge splits)",
               spread >= 2.0 or disagrees,
               f"spread {spread:.1f}x, {'split' if disagrees else 'unanimous'}; "
               "if this is NO-GO, teach the arithmetic block and cut the live half")
    check("judge self-disagreement reproduces (Session 4 finding)", disagrees,
          "not a gate — one unanimous set of 5 does not retire the finding",
          gate=False)

    if save:
        with open("judge_variance5.json", "w") as fh:
            json.dump({"n": n, "verdicts": verdicts,
                       "latency_s": [round(x, 2) for x in latencies],
                       "spread_x": round(spread, 2), "mean_s": round(mean_lat, 2),
                       "split": disagrees}, fh, indent=2)
        print("  saved -> judge_variance5.json")
    return ok


# ==========================================================================
# 6.  THE INJECTION.  Live, instructor-only, and it must beat its control.
# ==========================================================================

def check_injection(n: int, save: bool) -> bool:
    banner(f"6. Prompt injection — {n} runs each, injected vs clean control")
    import seeds5

    runs = {"injected": [], "injection_control": []}
    for seed in runs:
        for i in range(n):
            try:
                r = seeds5.run_injection(seed)
            except Exception as exc:
                return check(f"{seed} run {i + 1} completed", False,
                             f"{type(exc).__name__}: {str(exc)[:90]}")
            runs[seed].append(r)
            print(f"    {seed:<18} run {i + 1}: "
                  f"tools={[tc['name'] for tc in r['tool_calls']]}  "
                  f"{'FIRED' if seeds5.fired(r) else '-'}")

    if not any(runs.values()):
        return check("injection runs captured", False, "zero runs — hard stop")

    rate = {k: sum(seeds5.fired(r) for r in v) / len(v) for k, v in runs.items()}
    print(f"\n  fire rate  injected {rate['injected']:.0%}   "
          f"control {rate['injection_control']:.0%}\n")

    ok = check("the injection is CAUSED by the document, not the model's habit",
               rate["injected"] > rate["injection_control"],
               f"{rate['injected']:.0%} vs {rate['injection_control']:.0%} — if the "
               "control also fires, this measures tool preference, not an attack")
    ok &= check("the injection fires often enough to demo", rate["injected"] >= 0.5,
                f"{rate['injected']:.0%} of {n} runs — below this, RETIRE the live "
                "demo and teach the measured fire rate instead. That is an honest "
                "block; an exploit that no-shows in front of the room is not")

    # The punchline: the answer is still correct. Right answer, injected path.
    correct = [r for r in runs["injected"]
               if "1.2" in (r["answer"] or "") and seeds5.fired(r)]
    check("a fired run still produces a CORRECT answer "
          "(outcome_keyword waves it through)",
          bool(correct) or rate["injected"] == 0,
          f"{len(correct)}/{len(runs['injected'])} fired-and-correct", gate=False)

    if save:
        with open("injection5.json", "w") as fh:
            json.dump({"n": n, "fire_rate": rate,
                       "runs": {k: [{"seed": r["seed"], "answer": r["answer"],
                                     "tool_calls": r["tool_calls"],
                                     "evidence": r["evidence"]} for r in v]
                                for k, v in runs.items()}}, fh, indent=2)
        print("  saved -> injection5.json")
    return ok


# ==========================================================================
# 7.  VERSIONING API.  The sacrificial block -- but the code still has to run.
#     Signatures verified 7 Sep 2026 against reference.langchain.com and the
#     shipped langsmith wheel. as_of on update_dataset_tag is REQUIRED and must
#     be an exact version timestamp from read_dataset_version().as_of.
# ==========================================================================

def check_versioning(save: bool) -> bool:
    banner("7. Dataset versioning / tagging / splits")
    from langsmith import Client
    from evalkit import DATASET

    client = Client()
    if not client.has_dataset(dataset_name=DATASET):
        return check(f"dataset {DATASET!r} exists", False,
                     "run eval_dataset.push() first")
    check(f"dataset {DATASET!r} exists", True)

    try:
        versions = list(client.list_dataset_versions(dataset_name=DATASET, limit=5))
        ok = check("list_dataset_versions returns at least one version",
                   bool(versions), f"{len(versions)} versions")
        if not versions:
            return False
        latest = client.read_dataset_version(dataset_name=DATASET,
                                             as_of=versions[0].as_of)
        ok &= check("read_dataset_version(as_of=...) resolves", latest is not None,
                    str(getattr(latest, "as_of", ""))[:32])
        client.update_dataset_tag(dataset_name=DATASET, as_of=latest.as_of,
                                  tag="s5-preflight")
        ok &= check("update_dataset_tag(as_of=<exact version>) accepted", True,
                    "tag 's5-preflight'")
        tagged = list(client.list_examples(dataset_name=DATASET, as_of="s5-preflight"))
        ok &= check("list_examples(as_of=<tag>) reads the tagged version",
                    bool(tagged), f"{len(tagged)} examples at tag")
    except Exception as exc:
        return check("versioning API exercised", False,
                     f"{type(exc).__name__}: {str(exc)[:110]}")

    try:
        splits = client.list_dataset_splits(dataset_name=DATASET)
        check("list_dataset_splits available", True, str(list(splits))[:60], gate=False)
    except Exception as exc:
        check("list_dataset_splits available", False,
              f"{type(exc).__name__}: {str(exc)[:70]} — the course filters by "
              "metadata anyway (eval_dataset.slice_for)", gate=False)
    return ok


# ==========================================================================

def emit_deck_numbers(path: str = "deck_numbers5.json") -> None:
    """Everything the deck plots. Absent -> the deck stamps itself ILLUSTRATIVE
    in red, on the projector. Session 3's pattern, kept."""
    blob: dict = {"generated": time.strftime("%Y-%m-%d %H:%M")}
    for src, key in (("sample_size5.json", "sample_size"),
                     ("judge_variance5.json", "judge"),
                     ("injection5.json", "injection"),
                     ("row_screen5.json", "row_screen")):
        if os.path.exists(src):
            with open(src) as fh:
                blob[key] = json.load(fh)
    with open(path, "w") as fh:
        json.dump(blob, fh, indent=2)
    missing = [k for k in ("sample_size", "judge", "injection", "row_screen")
               if k not in blob]
    print(f"\n  saved -> {path}"
          + (f"   WARNING: no data for {missing} — those slides stay ILLUSTRATIVE"
             if missing else ""))


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("(python-dotenv not installed — relying on the ambient environment)")

    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=os.environ.get("COURSE_PROVIDER", "anthropic"),
                    choices=list(KEY_VARS))
    ap.add_argument("--offline", action="store_true",
                    help="checks 2,3,4 only — no keys, no API cost")
    ap.add_argument("--runs", type=int, default=5,
                    help="runs for the judge-variance and injection checks")
    ap.add_argument("--save", action="store_true",
                    help="write deck numbers + fixtures (refuses on NO-GO)")
    ap.add_argument("--skip-versioning", action="store_true")
    args = ap.parse_args()

    ok = True
    if args.offline:
        banner("OFFLINE MODE — checks 2, 3, 4. Nothing live is verified.")
        for fn in (lambda: check_row_screen(args.save),
                   check_screener_falsifiable,
                   lambda: check_sample_size(args.save)):
            ok &= _guard(fn)
        return _verdict(ok, args.save, offline=True)

    # HARD STOP 1: no keys, no verdict.
    if not os.environ.get(KEY_VARS[args.provider]):
        return hard_stop(f"{KEY_VARS[args.provider]} is not set. Use --offline to run "
                         "the zero-cost checks, or load your .env.")
    if not check_env(args.provider):
        return hard_stop("environment checks failed — see the rows above.")

    steps = [("row screen", lambda: check_row_screen(args.save)),
             ("screener falsifiable", check_screener_falsifiable),
             ("sample size", lambda: check_sample_size(args.save)),
             ("judge variance", lambda: check_judge_variance(args.runs, args.save)),
             ("injection", lambda: check_injection(args.runs, args.save))]
    if not args.skip_versioning:
        steps.append(("versioning", lambda: check_versioning(args.save)))

    for name, fn in steps:
        ok &= _guard(fn, name)
    return _verdict(ok, args.save)


def _guard(fn, name: str = "check") -> bool:
    """A traceback at 11pm is a worse diagnostic than a named NO-GO row."""
    try:
        return fn()
    except Exception as exc:
        return check(f"{name} completed", False,
                     f"{type(exc).__name__}: {str(exc)[:110]}")


def _verdict(ok: bool, save: bool, offline: bool = False) -> int:
    banner("VERDICT")
    width = max((len(n) for n, _, _, _ in CHECKS), default=20)
    for name, passed, detail, gate in CHECKS:
        tag = "GO   " if passed else ("NO-GO" if gate else "note ")
        print(f"  {tag}  {name:<{width}}  {detail[:56]}")

    if save:
        # HARD STOP 3, inherited from preflight4.
        if ok:
            emit_deck_numbers()
        else:
            print("\n  --save REFUSED: at least one check is NO-GO. Writing deck "
                  "numbers now would put an unverified figure on the projector, "
                  "which is exactly how Session 3 propagated two unsupported "
                  "claims into four artifacts.")

    verdict = ("GO — Session 5 is safe to run" if ok else "NO-GO — fix the rows above")
    if ok and offline:
        verdict = "GO (offline) — the live checks 5, 6 and 7 have NOT been run"
    print(f"\n  ==> {verdict}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
