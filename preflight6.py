#!/usr/bin/env python3
"""
preflight6.py — run this the night before Session 6. It also MAKES the runs.

WHAT EACH PRE-FLIGHT HAS ACTUALLY ASSERTED
------------------------------------------
    preflight.py   (S2)  did the broken agent misbehave?
    preflight3.py  (S3)  is the difference legible, and is the ordering stable?
    preflight4.py  (S4)  can every evaluator both pass and fail something?
    preflight5.py  (S5)  can every row be failed -- and did we run it enough?
    preflight6.py  (S6)  is the regression DETECTABLE at the sample size the
                         room gets -- and is the thing measuring it honest?

Session 6's punchline is a confidence interval that excludes zero for one
candidate (redundant) and is REPORTED, whatever it says, for the other
(concise). If redundant vs healthy lands inside the noise at 12 rows, nothing
is wrong with the code and the session still has no punchline. You want to
know that tonight.

GATES WERE FIXED BEFORE ANY RUN (10 Sep 2026). Session 5 re-scoped two gates
after they failed; that precedent is accepted on one condition: a gate changed
after a NO-GO is logged in Session6_State.md WITH the output from before the
change. `concise` is deliberately NOT gated on its sign -- gating on the answer
you want is how a pre-flight turns into decoration.

THREE HARD STOPS INHERITED FROM preflight4, KEPT
  1. Missing API keys stop the run BEFORE any verdict prints.
  2. Zero captured runs is a hard stop.
  3. --save refuses to write runs6.json / deck_numbers6.json on any NO-GO.
     runs6_UNVERIFIED.json is always written, so a failed night can still be
     diagnosed with --reanalyse. Nothing reads the UNVERIFIED file but you.

Usage:
    python preflight6.py --offline               # stats + replay self-tests. No keys.
    python preflight6.py                         # full run: 3 x 12 x 5 = 180 runs
    python preflight6.py --save                  # + runs6.json, deck_numbers6.json
    python preflight6.py --reanalyse runs6_UNVERIFIED.json   # zero-cost re-check
    python preflight6.py --reps 3                # cheaper; min detectable ~29%

Budget at --reps 5: 180 agent runs, roughly 360 Tavily searches [estimate --
redundant doubles its searches], one key. Wall clock ~20 min at concurrency 4.

Exit 0 = GO.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import sys
import time

CHECKS: list[tuple[str, bool, str, bool]] = []
NUMBERS: dict = {}

S5_SIGMA, S5_MEAN = 2444, 6174          # Session 3, react hard probe, 4 runs


def check(name: str, ok: bool, detail: str = "", gate: bool = True) -> bool:
    CHECKS.append((name, ok, detail, gate))
    tag = "GO " if ok else ("NO-GO" if gate else "note ")
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))
    return ok if gate else True


def note(name: str, detail: str) -> None:
    check(name, False, detail, gate=False)


def banner(text: str) -> None:
    print(f"\n{'=' * 78}\n{text}\n{'=' * 78}")


def hard_stop(msg: str) -> int:
    banner("HARD STOP")
    print(f"  {msg}\n\n  Nothing was verified. No verdict is printed, because a\n"
          "  verdict computed from zero data is worse than no verdict at all.\n")
    return 2


KEY_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY"}


# ==========================================================================
# 1.  OFFLINE: test the measurer before it measures anything.
# ==========================================================================

def _fake_runs(deltas: dict[str, float], rows: int = 12, reps: int = 5,
               cv: float = 0.4, seed: int = 0) -> list[dict]:
    """Synthetic runs with a KNOWN true difference. Rows differ in difficulty
    (that is what pairing is for) and every run carries cv run-to-run noise."""
    rnd = random.Random(seed)
    out = []
    for i in range(rows):
        base = rnd.choice([3000, 6000, 12000])      # easy / hard / report rows
        for v, delta in deltas.items():
            for _ in range(reps):
                x = max(base * (1 + delta) * (1 + rnd.gauss(0, cv)), 1)
                out.append({"version": v, "question": f"q{i}",
                            "outputs": {"metrics": {"tokens_billed": x}},
                            "scores": {}})
    return out


def check_stats_selftest() -> bool:
    banner("1. The measurer — does paired.py report what is actually there?")
    import paired as P

    # (a) A 2x difference, 200 synthetic experiments. The estimate must be
    #     unbiased ON AVERAGE and detected nearly every time. Deliberately not
    #     one seed: seed 0 alone reads +69% for a true +100% (a 1.9-sd draw),
    #     which is the session's lesson turning up inside its own test.
    ests = [P.paired(_fake_runs({"a": 0.0, "b": 1.0}, seed=s), "a", "b", "tokens_billed")
            for s in range(200)]
    avg = statistics.fmean(e.pct for e in ests)
    hit = sum(e.direction == "HIGHER" for e in ests) / len(ests)
    ok = check("known +100%: unbiased on average and detected", 95 < avg < 105 and hit > 0.95,
               f"mean estimate {avg:+.0f}%, detected {hit:.0%}; seed 0 alone "
               f"said {ests[0].pct:+.0f}%")
    r = _fake_runs({"a": 0.0, "b": 1.0})
    p = ests[0]

    # (b) Pairing is by question, not position. Shuffle and nothing may change.
    r2 = list(r)
    random.Random(1).shuffle(r2)
    p2 = P.paired(r2, "a", "b", "tokens_billed")
    ok &= check("row order does not change the result (paired by question)",
                abs(p.diff - p2.diff) < 1e-6 and abs(p.lo - p2.lo) < 1e-6)

    # (c) Coverage. 400 synthetic experiments with a true difference of +15%;
    #     a 95% interval should contain +15% about 95% of the time. This is
    #     the check that would have caught a wrong t value or a wrong sd.
    hits = 0
    trials = 400
    for s in range(trials):
        rr = _fake_runs({"a": 0.0, "b": 0.15}, seed=100 + s)
        q = P.paired(rr, "a", "b", "tokens_billed")
        # true row-level diff is 0.15 * each row's base; compare in % of base
        hits += q.pct_lo <= 15 <= q.pct_hi
    cov = hits / trials
    ok &= check("95% interval covers the true difference ~95% of the time",
                0.91 <= cov <= 0.99, f"{cov:.1%} of {trials}")

    # (d) The arithmetic the room will be told: min detectable at 12 rows.
    table = {}
    for reps in (1, 3, 5):
        sd_d = math.sqrt(2) * 0.4 / math.sqrt(reps)
        # t(0.975, 11) + t(0.80, 11): 95% confidence, 80% power, 12 rows
        table[reps] = round(100 * (P.t975(11) + 0.876) * sd_d / math.sqrt(12))
    NUMBERS["min_detectable_pct_12rows"] = table
    check("min detectable difference at 12 rows (CV 0.4, assumed)", True,
          ", ".join(f"{k} reps -> ~{v}%" for k, v in table.items()))
    return ok


def check_verdict_fix() -> bool:
    banner("2. evalkit.Discrimination.verdict — the Session 4 bug, fixed 10 Sep")
    from evalkit import Discrimination as D
    cases = {"ALL-PASS": D("k", n=3, passed=3), "ALL-FAIL": D("k", n=2, failed=2),
             "ALL-SKIP": D("k", n=2, skipped=2), "DISCRIMINATES": D("k", n=2, passed=1, failed=1)}
    ok = True
    for want, d in cases.items():
        got = d.verdict
        ok &= check(f"{want} evaluator reports {want}", bool(got) and got.startswith(want),
                    repr(got)[:50])
    return ok


def check_replay_selftest() -> bool:
    banner("3. Replay target — students get exactly the runs you made")
    import seeds6
    runs = [{"version": "healthy", "question": "q", "outputs": {"answer": f"a{i}"}}
            for i in range(3)]
    t = seeds6.make_replay_target(runs, "healthy")
    got = [t({"question": "q"})["answer"] for _ in range(3)]
    ok = check("replays every saved rep, in order", got == ["a0", "a1", "a2"], str(got))
    try:
        t({"question": "q"})
        ok &= check("a 4th call for 3 saved reps raises", False, "it did not")
    except RuntimeError:
        ok &= check("a 4th call for 3 saved reps raises", True)
    try:
        t({"question": "not in the file"})
        ok &= check("an unknown question raises (wrong dataset)", False, "it did not")
    except KeyError:
        ok &= check("an unknown question raises (wrong dataset)", True)
    return ok


def check_pool_local() -> bool:
    banner("4. The regression set, locally")
    import instructor_pool
    rows = instructor_pool.rows_for_pool()
    ok = check("instructor pool is the 12 rows v1 was pushed from", len(rows) == 12,
               f"{len(rows)} rows")
    inj = [r for r in rows if r.get("metadata", {}).get("category") == "adversarial"]
    if inj:
        note("adversarial row(s) in the regression set",
             f"{len(inj)} — no version under test has the injected tool, so these "
             "rows cannot show an injection; they still measure cost and searches.")
    qs = [r["inputs"]["question"] for r in rows]
    NUMBERS["distinct_questions"] = len(set(qs))
    if len(set(qs)) != len(qs):
        note("duplicate question text in the pool",
             f"{len(qs)} rows, {len(set(qs))} distinct questions. Identical inputs are "
             "one question to the agent, so paired n is the DISTINCT count. Say "
             "'12 rows, 11 questions' on the slide.")
    return ok


# ==========================================================================
# 2.  LIVE: make the runs.
# ==========================================================================

def check_env(provider: str) -> bool:
    banner(f"5. Environment — provider: {provider}")
    ok = check(f"{KEY_VARS[provider]} present", bool(os.environ.get(KEY_VARS[provider])))
    ok &= check("TAVILY_API_KEY present", bool(os.environ.get("TAVILY_API_KEY")))
    ok &= check("LANGSMITH_API_KEY present", bool(os.environ.get("LANGSMITH_API_KEY")))
    if not ok:
        return False
    os.environ["COURSE_PROVIDER"] = provider
    import evalkit
    import seeds6
    try:
        resolved = evalkit.env_setup(seeds6.PROJECT)            # gotcha #5
        ok &= check("LangSmith project resolves (not 'default')",
                    resolved == seeds6.PROJECT, resolved)
    except RuntimeError as exc:
        return check("LangSmith project resolves", False, str(exc))
    import importlib.metadata as md
    for pkg, want in {"langchain-core": "1.6.1", "langgraph": "1.2.11",
                      "langsmith": "0.11.1"}.items():
        try:
            got = md.version(pkg)
        except md.PackageNotFoundError:
            got = "not installed"
        ok &= check(f"{pkg} == {want}", got == want, f"found {got}")
    return ok


def _examples(client):
    import seeds6
    return list(client.list_examples(dataset_name=seeds6.POOL, as_of=seeds6.POOL_TAG))


def check_dataset(client) -> bool:
    banner("6. The regression set in LangSmith, pinned at the tag")
    import seeds6
    if not client.has_dataset(dataset_name=seeds6.POOL):
        return check(f"dataset {seeds6.POOL!r} exists", False,
                     "run: python push_pool.py instructor_pool.py --tag v1")
    ex = _examples(client)
    ok = check(f"list_examples(as_of={seeds6.POOL_TAG!r}) returns rows", bool(ex),
               f"{len(ex)} examples")
    if ex and len(ex) != 12:
        note("row count at the tag", f"{len(ex)}, expected 12 — the deck's arithmetic "
             "assumes 12; deck_numbers6.json records the real n")
    NUMBERS["rows"] = len(ex)
    return ok


def run_versions(client, reps: int, concurrency: int) -> tuple[list[dict], dict]:
    """One experiment per version, same examples, same tag. Returns flat runs."""
    import seeds6
    examples = _examples(client)
    runs, experiments = [], {}
    for v in [seeds6.INCUMBENT] + seeds6.CANDIDATES:
        print(f"\n  running {v}: {len(examples)} rows x {reps} reps ...")
        t0 = time.time()
        res = client.evaluate(
            seeds6.make_measured_target(v), data=examples,
            evaluators=seeds6.QUALITY_EVALUATORS + seeds6.METRIC_EVALUATORS,
            num_repetitions=reps, max_concurrency=concurrency,
            experiment_prefix=f"s6-{v}",
            metadata={"version": v, "seeds6": seeds6.__version__,
                      "dataset_tag": seeds6.POOL_TAG, "prompt": seeds6.PROMPTS[v][-80:]})
        experiments[v] = res.experiment_name
        seen: dict[str, int] = {}
        for row in res:
            run, ex = row["run"], row["example"]
            scores = {}
            for er in (row.get("evaluation_results") or {}).get("results", []):
                key = getattr(er, "key", None) or er.get("key")
                sc = getattr(er, "score", None) if not isinstance(er, dict) else er.get("score")
                scores[key] = sc
            q = ex.inputs["question"]
            seen[q] = seen.get(q, 0) + 1
            runs.append({"version": v, "question": q, "example_id": str(ex.id),
                         "rep": seen[q], "run_id": str(run.id),
                         "error": getattr(run, "error", None),
                         "outputs": run.outputs if not getattr(run, "error", None) else None,
                         "scores": scores})
        print(f"  {v}: {sum(seen.values())} runs in {time.time() - t0:.0f}s "
              f"-> {res.experiment_name}")
    return runs, experiments


# ==========================================================================
# 3.  The gates. Also run by --reanalyse on a saved file, at zero cost.
# ==========================================================================

def check_capture(runs: list[dict], reps: int) -> bool:
    banner("7. Capture — did every run arrive, and did we measure its tokens?")
    import seeds6
    ok = True
    for v in [seeds6.INCUMBENT] + seeds6.CANDIDATES:
        mine = [r for r in runs if r["version"] == v]
        good = [r for r in mine if r.get("outputs")]
        per_row: dict[str, int] = {}
        for r in good:
            per_row[r["question"]] = per_row.get(r["question"], 0) + 1
        thin = [q for q, n in per_row.items() if n < max(reps - 1, 2)]
        ok &= check(f"{v}: every row has >= {max(reps - 1, 2)} good runs",
                    bool(per_row) and not thin,
                    f"{len(good)}/{len(mine)} good; thin rows: {len(thin)}")
        zero = [r for r in good if not r["outputs"]["metrics"].get("tokens_billed")]
        ok &= check(f"{v}: tokens_billed > 0 on every run (the measurer works)",
                    not zero, f"{len(zero)} runs read 0 tokens")
    return ok


def check_measurer_vs_langsmith(client, runs: list[dict]) -> bool:
    """Our local token count against LangSmith's, on ONE run. Compares TOTAL
    tokens (input incl. cached + output), because that is what LangSmith's
    total_tokens is. A local measurer is still a measurer."""
    banner("8. Cross-check one run against LangSmith")
    import evalkit
    r = next((x for x in runs if x.get("outputs") and x["version"] == "healthy"), None)
    if r is None:
        return check("a healthy run to cross-check", False, "none captured")
    evalkit.flush_traces()
    run, why = evalkit.read_run_when_ready(client, r["run_id"])
    if run is None or not getattr(run, "total_tokens", None):
        note("LangSmith total_tokens readable", why or "total_tokens empty")
        return True
    m = r["outputs"]["metrics"]
    local = m["in_uncached"] + m["cached_read"] + m["out"]
    gap = abs(local - run.total_tokens) / max(run.total_tokens, 1)
    return check("local token count matches LangSmith within 5%", gap <= 0.05,
                 f"local {local} vs LangSmith {run.total_tokens} ({gap:.1%})")


def check_sigma(runs: list[dict]) -> bool:
    banner("9. Sigma, measured properly this time")
    import paired as P
    sigma, df, mean = P.within_row_sigma(runs, "healthy", "tokens_billed")
    cv = sigma / mean if mean else float("nan")
    NUMBERS["sigma"] = {"sigma": round(sigma), "df": df, "mean": round(mean),
                        "cv": round(cv, 3), "s5_sigma": S5_SIGMA, "s5_mean": S5_MEAN,
                        "s5_df": 3}
    ok = check("healthy run-to-run sigma has df >= 30", df >= 30,
               f"sigma {sigma:.0f} on mean {mean:.0f} (CV {cv:.2f}), df {df}  "
               f"[Session 5: 2,444 on 6,174, CV 0.40, df 3]")
    note("sigma is from a DIFFERENT cell than Session 5's",
         "12 mixed rows vs one react hard probe — say so if the two go on one slide")
    # Added 10 Sep AFTER the first live GO. Notes only; no gate changed.
    # The pooled sigma above assumes every row is equally noisy. It is not.
    shares = P.variance_share(runs, "healthy", "tokens_billed")
    if shares:
        q, share, sd, m = shares[0]
        s2, df2, m2 = P.within_row_sigma(P.without(runs, q), "healthy", "tokens_billed")
        NUMBERS["sigma"]["concentration"] = {
            "top_row": q, "top_share": round(share, 3), "top_sd": round(sd),
            "top_mean": round(m), "rest_sigma": round(s2), "rest_mean": round(m2),
            "rest_cv": round(s2 / m2, 3) if m2 else None}
        note("where the noise lives",
             f"{share:.0%} of run-to-run variance is ONE row ({q[:40]}...: sd {sd:.0f} "
             f"on {m:.0f}). The rest: CV {s2 / m2:.2f}. Do NOT put the pooled CV on a "
             "slide as a property of the agent.")
    return ok


def check_regression(runs: list[dict]) -> bool:
    banner("10. The punchline: is redundant's regression detectable at this n?")
    import paired as P
    ok = True
    out = {}
    for m in ("n_searches", "tokens_billed"):
        p = P.paired(runs, "healthy", "redundant", m)
        print("    " + p.line())
        ok &= check(f"redundant vs healthy: {m} CI excludes zero (REGRESSION)",
                    p.verdict == "REGRESSION", f"{p.pct:+.0f}% [{p.pct_lo:+.0f}, {p.pct_hi:+.0f}]")
        out[m] = _pack(p)
    s = P.paired(runs, "healthy", "redundant", "outcome_keyword")
    print("    " + s.line())
    ok &= check("redundant vs healthy: no detectable task-success difference",
                s.direction == "NO DETECTABLE DIFFERENCE",
                f"{s.diff:+.2f} [{s.lo:+.2f}, {s.hi:+.2f}]")
    out["outcome_keyword"] = _pack(s)
    lat = P.paired(runs, "healthy", "redundant", "latency_s")
    out["latency_s"] = _pack(lat)
    note("latency (not gated; measured under concurrency)", lat.line()[20:])
    dec, why = P.recommend(s, P.paired(runs, "healthy", "redundant", "tokens_billed"))
    out["decision"] = [dec, why]
    check("tie rule decision for redundant", True, f"{dec} — {why}")
    _extras(runs, "redundant", out)
    NUMBERS["redundant"] = out
    return ok


def check_concise(runs: list[dict]) -> bool:
    banner("11. concise vs healthy — REPORTED, not gated on its sign")
    import paired as P
    out = {}
    for m in ("outcome_keyword", "tokens_billed", "answer_chars", "latency_s"):
        p = P.paired(runs, "healthy", "concise", m)
        print("    " + p.line())
        out[m] = _pack(p)
    s = P.paired(runs, "healthy", "concise", "outcome_keyword")
    c = P.paired(runs, "healthy", "concise", "tokens_billed")
    ok = check("concise: intervals computable (>= 10 paired rows)",
               s.n_rows >= 10 and c.n_rows >= 10, f"{c.n_rows} rows")
    dec, why = P.recommend(s, c)
    out["decision"] = [dec, why]
    beat = ("TIE — teach 'the tie goes to the cheaper agent'"
            if s.direction == "NO DETECTABLE DIFFERENCE" else
            f"success {s.verdict} — teach it as a detected change, not a tie")
    note("which beat to teach for concise", beat)
    check("tie rule decision for concise", True, f"{dec} — {why}")
    _extras(runs, "concise", out)
    NUMBERS["concise"] = out
    return ok


def _extras(runs: list[dict], cand: str, out: dict) -> None:
    """Added 10 Sep after the first live GO. Notes only; no gate changed."""
    import paired as P
    pcts = P.row_pcts(runs, "healthy", cand, "tokens_billed")
    med = statistics.median(pcts.values())
    worst = max(pcts, key=lambda q: abs(pcts[q]))
    rest = P.paired(P.without(runs, worst), "healthy", cand, "tokens_billed")
    out["tokens_row_pcts"] = {q[:60]: round(v, 1) for q, v in pcts.items()}
    out["tokens_median_row_pct"] = round(med, 1)
    out["tokens_without_biggest_row"] = _pack(rest)
    note(f"{cand}: tokens, row by row",
         f"median row {med:+.0f}%; biggest row {pcts[worst]:+.0f}% ({worst[:30]}...); "
         f"without it: {rest.pct:+.0f}% [{rest.pct_lo:+.0f}, {rest.pct_hi:+.0f}] {rest.verdict}")
    ok_vals = [value for r in runs if r["version"] in ("healthy", cand)
               for value in [(r.get("scores") or {}).get("outcome_keyword")]]
    if ok_vals and all(bool(v) for v in ok_vals):
        note(f"{cand}: outcome_keyword is ALL-PASS",
             "task success cannot fail on this set, so 'success tied' is not evidence "
             "the answers are equally good. Session 4's lesson, live.")


def check_comparative_api(client, experiments: dict) -> bool:
    """Verified from source 10 Sep, NOT yet live: evaluate_comparative groups
    ALL runs per example across both experiments, so with repetitions the
    comparator gets 2 x reps runs, A's first -- while the docs say 'two-item
    list'. Measure it instead of believing either."""
    banner("12. The comparative-experiment API — how many runs does a comparator get?")
    from langsmith.evaluation import evaluate_comparative
    seen: list[int] = []

    def count_runs(runs, example):
        seen.append(len(runs))
        return {"key": "s6_probe_runs_seen", "scores": {r.id: 0 for r in runs}}

    try:
        evaluate_comparative((experiments["healthy"], experiments["redundant"]),
                             evaluators=[count_runs], client=client,
                             experiment_prefix="s6-preflight-probe")
    except Exception as exc:
        return check("evaluate_comparative ran", False,
                     f"{type(exc).__name__}: {str(exc)[:100]}")
    counts = sorted(set(seen))
    NUMBERS["comparative_runs_per_example"] = counts
    return check("comparator run-count per example recorded", bool(seen),
                 f"{counts} (docs: [2]; a runs[0]-vs-runs[1] comparator is only "
                 "correct if this says [2])")


def _pack(p) -> dict:
    return {k: (None if isinstance(v, float) and math.isnan(v) else
                (round(v, 3) if isinstance(v, float) else v))
            for k, v in {"n": p.n_rows, "base": p.mean_base, "cand": p.mean_cand,
                         "diff": p.diff, "lo": p.lo, "hi": p.hi, "pct": p.pct,
                         "pct_lo": p.pct_lo, "pct_hi": p.pct_hi,
                         "verdict": p.verdict}.items()}


# ==========================================================================

def _guard(fn, name: str) -> bool:
    try:
        return fn()
    except Exception as exc:
        return check(f"{name} completed", False, f"{type(exc).__name__}: {str(exc)[:110]}")


def analyse(runs: list[dict], reps: int) -> bool:
    ok = True
    for name, fn in (("capture", lambda: check_capture(runs, reps)),
                     ("sigma", lambda: check_sigma(runs)),
                     ("regression", lambda: check_regression(runs)),
                     ("concise", lambda: check_concise(runs))):
        ok &= _guard(fn, name)
    return ok


def save_runs(path: str, runs: list[dict], experiments: dict, reps: int) -> None:
    import seeds6
    with open(path, "w") as fh:
        json.dump({"version": seeds6.__version__, "generated": time.strftime("%Y-%m-%d %H:%M"),
                   "dataset": seeds6.POOL, "tag": seeds6.POOL_TAG, "reps": reps,
                   "experiments": experiments, "runs": runs}, fh, indent=1, default=str)
    print(f"  saved -> {path}")


def verdict(ok: bool, save: bool, runs, experiments, reps, offline=False) -> int:
    banner("VERDICT")
    width = max((len(n) for n, _, _, _ in CHECKS), default=20)
    for name, passed, detail, gate in CHECKS:
        tag = "GO   " if passed else ("NO-GO" if gate else "note ")
        print(f"  {tag}  {name:<{width}}  {detail[:60]}")
    if save:
        if ok and not offline:
            save_runs("runs6.json", runs, experiments, reps)
            NUMBERS["generated"] = time.strftime("%Y-%m-%d %H:%M")
            with open("deck_numbers6.json", "w") as fh:
                json.dump(NUMBERS, fh, indent=2)
            print("  saved -> deck_numbers6.json")
        elif not ok:
            print("\n  --save REFUSED: at least one check is NO-GO. runs6.json is what the\n"
                  "  students replay; writing it now would hand the room an unverified\n"
                  "  regression. Diagnose with --reanalyse runs6_UNVERIFIED.json.")
    v = "GO — Session 6 is safe to run" if ok else "NO-GO — fix the rows above"
    if ok and offline:
        v = "GO (offline) — nothing live has been run; the punchline is UNVERIFIED"
    print(f"\n  ==> {v}\n")
    return 0 if ok else 1


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("(python-dotenv not installed — relying on the ambient environment)")

    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=os.environ.get("COURSE_PROVIDER", "anthropic"),
                    choices=list(KEY_VARS))
    ap.add_argument("--offline", action="store_true", help="self-tests only; no keys")
    ap.add_argument("--reanalyse", metavar="FILE", help="re-run the gates on saved runs")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    ok = True
    for name, fn in (("stats self-test", check_stats_selftest),
                     ("verdict fix", check_verdict_fix),
                     ("replay self-test", check_replay_selftest),
                     ("local pool", check_pool_local)):
        ok &= _guard(fn, name)

    if args.offline:
        return verdict(ok, args.save, [], {}, args.reps, offline=True)

    if args.reanalyse:
        with open(args.reanalyse) as fh:
            blob = json.load(fh)
        NUMBERS["rows"] = len({r.get("example_id") for r in blob["runs"]})
        runs = blob["runs"]
        if not runs:
            return hard_stop("the saved file has zero runs.")
        ok &= analyse(runs, blob.get("reps", args.reps))
        # Check 12 re-reads finished experiments: zero agent cost, but it needs
        # the LangSmith key. Without it deck_numbers6.json would silently lose
        # the comparator count (it did once, 10 Sep).
        if os.environ.get("LANGSMITH_API_KEY") and blob.get("experiments"):
            from langsmith import Client as _Client
            ok &= _guard(lambda: check_comparative_api(_Client(), blob["experiments"]),
                         "comparative API")
        else:
            note("comparative API not re-checked", "no LANGSMITH_API_KEY or no experiments "
                 "in the file — deck_numbers6.json will lack the comparator count")
        return verdict(ok, args.save, runs, blob.get("experiments", {}),
                       blob.get("reps", args.reps))

    # HARD STOP 1: no keys, no verdict.
    if not os.environ.get(KEY_VARS[args.provider]):
        return hard_stop(f"{KEY_VARS[args.provider]} is not set. Use --offline, "
                         "or load your .env.")
    if not check_env(args.provider):
        return hard_stop("environment checks failed — see the rows above.")

    from langsmith import Client
    client = Client()
    if not _guard(lambda: check_dataset(client), "dataset"):
        return verdict(False, args.save, [], {}, args.reps)

    runs, experiments = run_versions(client, args.reps, args.concurrency)
    save_runs("runs6_UNVERIFIED.json", runs, experiments, args.reps)
    if not any(r.get("outputs") for r in runs):          # HARD STOP 2
        return hard_stop("zero runs captured. Check the provider key and Tavily quota.")

    ok &= analyse(runs, args.reps)
    ok &= _guard(lambda: check_measurer_vs_langsmith(client, runs), "LangSmith cross-check")
    ok &= _guard(lambda: check_comparative_api(client, experiments), "comparative API")
    return verdict(ok, args.save, runs, experiments, args.reps)


if __name__ == "__main__":
    sys.exit(main())
