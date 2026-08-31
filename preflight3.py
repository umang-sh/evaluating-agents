#!/usr/bin/env python3
"""
preflight3.py — run this the night before Session 3.

Session 2 shipped preflight.py because you cannot set `temperature`, so an agent
that is *meant* to misbehave may simply behave. One of five seeds was retired on
the strength of it. Same pattern, different failure mode: Session 3's risk is not
that a staged bug fails to reproduce, it is that the three architectures produce
numbers too close to tell apart — in which case the benchmark is a damp squib and
the last thirty minutes of the session have nothing to stand on.

Usage:
    python preflight3.py                      # full GO/NO-GO, default provider
    python preflight3.py --provider google    # verify a student provider
    python preflight3.py --all-providers      # every provider with a key present
    python preflight3.py --reclassify         # re-score saved results, no API cost
    python preflight3.py --save runs.json     # save results for the outage fallback

Exit code 0 = GO. Non-zero = NO-GO, and the table says which check failed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append((name, ok, detail))
    print(f"  [{'GO ' if ok else 'NO-GO'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def banner(text: str) -> None:
    print(f"\n{'=' * 72}\n{text}\n{'=' * 72}")


# ---------------------------------------------------------------------------
# 1. Environment
# ---------------------------------------------------------------------------

def check_env(provider: str) -> bool:
    banner(f"1. Environment — provider: {provider}")

    key_var = {"anthropic": "ANTHROPIC_API_KEY",
               "openai": "OPENAI_API_KEY",
               "google": "GOOGLE_API_KEY"}[provider]
    ok = check(f"{key_var} present", bool(os.environ.get(key_var)))
    ok &= check("TAVILY_API_KEY present", bool(os.environ.get("TAVILY_API_KEY")))
    ok &= check("LANGSMITH_API_KEY present", bool(os.environ.get("LANGSMITH_API_KEY")))
    if not ok:
        return False

    os.environ["COURSE_PROVIDER"] = provider
    import arch_bench

    try:
        resolved = arch_bench.env_setup()
        # Gotcha #5: silent failure mode — traces land in `default` with NO error.
        check("LangSmith project resolves (not 'default')",
              resolved == arch_bench.PROJECT, resolved)
    except RuntimeError as exc:
        return check("LangSmith project resolves (not 'default')", False, str(exc))

    import importlib.metadata as md
    pins = {"langchain": "1.3.16", "langchain-core": "1.6.1", "langgraph": "1.2.11",
            "langsmith": "0.11.1", "langchain-tavily": "0.2.18"}
    if provider == "google":
        # Verified against the pin set 30 Aug 2026 — and the reason langchain-core
        # is 1.6.1 rather than 1.6.0 (this package requires >=1.6.1).
        pins["langchain-google-genai"] = "4.3.7"
    for pkg, want in pins.items():
        try:
            got = md.version(pkg)
        except md.PackageNotFoundError:
            check(f"{pkg} installed", False, "not installed")
            ok = False
            continue
        check(f"{pkg} == {want}", got == want, f"found {got}")
        if got != want:
            ok = False

    # langchain-core >= 1.5.2 is what makes reasoning_effort a STANDARD param.
    try:
        core = tuple(int(x) for x in md.version("langchain-core").split(".")[:3])
        check("langchain-core >= 1.5.2 (reasoning_effort is standard)",
              core >= (1, 5, 2), md.version("langchain-core"))
    except Exception:
        pass
    return ok


# ---------------------------------------------------------------------------
# 2. reasoning_effort — accepted on a REAL request, not just at construction
# ---------------------------------------------------------------------------

def check_effort(provider: str) -> bool:
    banner("2. reasoning_effort pinned at the floor")
    import arch_bench

    chat, constructed = arch_bench.make_chat(provider, arch_bench.EFFORT_FLOOR)
    if not check(f"constructor accepts reasoning_effort={arch_bench.EFFORT_FLOOR!r}",
                 constructed):
        return check("effort pinned identically across architectures", False,
                     "falls back to provider default — comparison caveat REQUIRED on slide")
    try:
        msg = chat.invoke("Reply with the single word: ok")
        _ = msg.text                      # gotcha #2: .text, never .content
        return check("live request accepted with effort pinned", True)
    except Exception as exc:
        return check("live request accepted with effort pinned", False, str(exc)[:120])


# ---------------------------------------------------------------------------
# 3. Cost populates. If this is NO-GO the cost hands-on collapses.
# ---------------------------------------------------------------------------

def check_cost(provider: str) -> bool:
    banner("3. LangSmith cost population")
    import arch_bench
    from langchain_core.tracers.context import collect_runs
    from langchain_core.tracers.langchain import wait_for_all_tracers
    from langsmith import Client

    chat, _ = arch_bench.make_chat(provider)
    with collect_runs() as cb:
        chat.invoke("Reply with the single word: ok")
    wait_for_all_tracers()
    client = Client()
    client.flush()

    if not cb.traced_runs:
        return check("traced run collected", False)

    # A freshly-flushed run is NOT immediately readable: LangSmith has to ingest
    # and index it first, and read_run raises 404 until it has. Retry on the
    # exception as well as on the empty value.
    # A bare chat.invoke is ONE span and has no children — min_spans=1, or the
    # readiness test (written for agent runs) never settles and reports a false
    # NO-GO. traced_runs[0] is safe here for the same reason: one call, one run.
    run, note = arch_bench.read_run_when_ready(client, cb.traced_runs[0].id,
                                               min_spans=1)

    if run is None:
        return check("run readable back from LangSmith", False, note)
    check("run readable back from LangSmith", True,
          "(ingestion lag tolerated)")

    if run.total_cost:
        return check(f"total_cost populated for {arch_bench.MODEL_IDS[provider]}",
                     True, f"${float(run.total_cost):.6f}")
    check(f"total_cost populated for {arch_bench.MODEL_IDS[provider]}", False, note)
    return False


# ---------------------------------------------------------------------------
# 4. Span-walk regression test.  The Session 2 meta-lesson: always test a
#    classifier against a known-good run.
# ---------------------------------------------------------------------------

def check_span_walk(provider: str) -> bool:
    banner("4. Tool-span counting (gotcha #8 regression test)")
    import arch_bench
    from probes import EASY

    probe = EASY[0]
    res = arch_bench.run_one("react", probe, provider=provider)

    ok = check("no partial-trace warning on the run",
               not res.notes.startswith("PARTIAL TRACE"), res.notes[:100])
    ok &= check("react run produced at least one tool span", res.tool_calls >= 1,
                f"{res.tool_calls} outermost tool spans — 0 here means the walk "
                f"never reached the tool node; check the trace in the UI")
    ok &= check("outermost count is not an even doubling of a plausible naive count",
                res.tool_calls < 8,
                "if this is ~2x what the trace shows in the UI, the walk is "
                "counting nested @tool spans — every number in the table is wrong")
    ok &= check("run URL obtained from the SDK, not hand-built (gotcha #7)",
                bool(res.run_url), res.run_url[:60])
    return ok


# ---------------------------------------------------------------------------
# 5. The one that saves the session: is the spread legible, and is it stable?
# ---------------------------------------------------------------------------

def check_spread(provider: str, save: str | None) -> bool:
    banner("5. Architecture spread and ordering stability (TWO runs)")
    import arch_bench
    from probes import CLASS_SET

    frames = []
    for i in (1, 2):
        print(f"\n  --- run {i} of 2 ---")
        frames.append(arch_bench.run_bench(CLASS_SET, provider=provider))

    if save:
        payload = [f.to_dict(orient="records") for f in frames]
        with open(save, "w") as fh:
            json.dump(payload, fh, indent=2, default=str)
        print(f"\n  saved -> {save}  (API-outage fallback, and --reclassify input)")

    emit_deck_numbers(frames[0])
    return _score_frames(frames)


def emit_deck_numbers(df, path: str = "deck_numbers.json") -> None:
    """Write the figures slides 12 and 13 plot.

    Drop this file next to make_deck.js and rebuild: the deck stops saying
    ILLUSTRATIVE and starts showing what you actually measured. Nothing in the
    deck depends on a student having submitted anything — this is the only
    source of data in it, and it is yours.
    """
    def mean(arch, metric, diff=None):
        sel = df[df.arch == arch]
        if diff is not None:
            sel = sel[sel.difficulty == diff]
        v = sel[metric].mean()
        return None if v != v else float(v)          # NaN -> None

    payload = {
        "provider": str(df.provider.iloc[0]) if "provider" in df else "unknown",
        "probes": int(df.question.nunique()),
        "easy_tools": {a: mean(a, "tool_calls", "easy") for a in
                       ("react", "toolcall", "workflow")},
        "tokens_easy": {a: mean(a, "tokens_billed", "easy") for a in
                        ("react", "workflow")},
        "tokens_hard": {a: mean(a, "tokens_billed", "hard") for a in
                        ("react", "workflow")},
        "cost": {a: mean(a, "cost_usd") for a in ("react", "toolcall", "workflow")},
        "latency": {a: mean(a, "latency_s") for a in ("react", "toolcall", "workflow")},
        # Success by difficulty decides WHICH STORY slide 13 tells. If the
        # workflow cannot answer dependent multi-hop questions, the finding is
        # "it failed them", not "it was cheaper on them" — and the slide must
        # say whichever is true.
        "success_easy": {a: mean(a, "success", "easy") for a in
                         ("react", "toolcall", "workflow")},
        "success_hard": {a: mean(a, "success", "hard") for a in
                         ("react", "toolcall", "workflow")},
    }
    if any(v is None for d in ("easy_tools", "tokens_easy", "tokens_hard")
           for v in payload[d].values()):
        print("\n  WARNING: some slide figures are empty — the deck will keep the "
              "illustrative values for those. Check your probe difficulty split.")
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"  saved -> {path}  (copy next to make_deck.js and rerun `node make_deck.js`)")


def _score_frames(frames) -> bool:
    import arch_bench

    ok = True
    # react and toolcall are the SAME architecture, so their relative order is
    # meaningless and swapping is evidence FOR the session's claim, not against
    # it. What must be stable is model-decides vs code-decides.
    def side(f, metric):
        m = f.groupby("arch")[metric].mean()
        model_side = min(v for a, v in m.items() if a in ("react", "toolcall"))
        return "model-decides" if model_side < m.get("workflow", float("inf")) \
               else "code-decides"

    for metric in ("cost_usd", "latency_s", "tokens_billed"):
        orders = [arch_bench.ordering(f, metric) for f in frames]
        sides = [side(f, metric) for f in frames]
        stable = sides[0] == sides[-1]
        ok &= check(f"model-vs-code ordering stable on {metric}", stable,
                    f"{sides[0]} cheaper" + ("" if stable else
                    f", then {sides[-1]} — FLIPPED; the comparison is noise"))
        check(f"  (full order on {metric}, FYI)", True, " < ".join(orders[0]) +
              ("" if orders[0] == orders[-1] else
               f"   vs   {' < '.join(orders[-1])}  — react/toolcall swapping here "
               f"is EXPECTED and is a talking point, not a failure"))

    df = frames[0]
    for metric, floor in (("cost_usd", 1.5), ("latency_s", 1.3), ("tokens_billed", 1.5)):
        s = df.groupby("arch")[metric].mean()
        if s.isna().any() or s.min() == 0:
            ok &= check(f"{metric} spread legible", False, "missing or zero values")
            continue
        ratio = float(s.max() / s.min())
        ok &= check(f"{metric} spread >= {floor}x", ratio >= floor, f"{ratio:.2f}x")

    # The staged bottleneck: the workflow must actually over-search on easy probes.
    easy = df[df.difficulty == "easy"]
    if len(easy):
        wf = easy[easy.arch == "workflow"].tool_calls.mean()
        rc = easy[easy.arch == "react"].tool_calls.mean()
        ok &= check("workflow bottleneck reproduces on easy probes",
                    wf > rc, f"workflow {wf:.1f} tools vs react {rc:.1f}")

    # A row with no tokens at all means no root run was resolved for that
    # architecture — not "a cheap run". Seen live: the hand-rolled toolcall loop
    # had no parent span, so every sub-call was its own root.
    dead = df[df.tokens_billed == 0]
    ok &= check("every row resolved a trace root (tokens > 0)", len(dead) == 0,
                "" if len(dead) == 0 else
                f"{len(dead)} row(s) with 0 tokens: "
                f"{sorted(set(dead.arch))} — check that architecture declares a "
                f"parent span")

    # And the counterpoint that makes the recommendation exercise non-trivial.
    hard = df[df.difficulty == "hard"]
    if len(hard):
        wf = hard[hard.arch == "workflow"].tokens_billed.mean()
        rc = hard[hard.arch == "react"].tokens_billed.mean()
        check("counterpoint present: workflow cheaper on hard probes",
              wf < rc, f"workflow {wf:.0f} tok vs react {rc:.0f} tok "
                       "(NOT fatal — but without it, 'no architecture wins "
                       "everywhere' has no evidence and the domain exercise "
                       "becomes a lecture)")

    # Task success must not be uniformly zero or uniformly one.
    succ = df.groupby("arch").success.mean()
    ok &= check("task success is discriminating (not all-pass / all-fail)",
                0 < succ.mean() < 1 or succ.nunique() > 1,
                ", ".join(f"{k}={v:.2f}" for k, v in succ.items()))
    return ok


def reclassify(path: str) -> bool:
    banner(f"5. Re-scoring saved results from {path} (no API cost)")
    import pandas as pd
    with open(path) as fh:
        payload = json.load(fh)
    return _score_frames([pd.DataFrame(rows) for rows in payload])


# ---------------------------------------------------------------------------

def main() -> int:
    # Load .env the same way check_env.py does. Without this, keys set in .env
    # are invisible here and every check_env() row reports a missing key while
    # check_env.py says GO — a confusing five minutes at 11pm.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=os.environ.get("COURSE_PROVIDER", "anthropic"),
                    choices=["anthropic", "openai", "google"])
    ap.add_argument("--all-providers", action="store_true")
    ap.add_argument("--reclassify", metavar="PATH")
    ap.add_argument("--save", metavar="PATH", default="session3_preflight_runs.json")
    args = ap.parse_args()

    if args.reclassify:
        ok = reclassify(args.reclassify)
        return _verdict(ok)

    providers = ["anthropic", "openai", "google"] if args.all_providers else [args.provider]
    overall = True
    for prov in providers:
        key = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
               "google": "GOOGLE_API_KEY"}[prov]
        if args.all_providers and not os.environ.get(key):
            print(f"\n(skipping {prov}: no {key})")
            continue
        import arch_bench as _ab
        _ab._COST_UNAVAILABLE = False    # each provider gets its own verdict
        ok = check_env(prov)
        if not ok:
            overall = False
            continue
        for name, fn in (("reasoning_effort", lambda: check_effort(prov)),
                         ("cost", lambda: check_cost(prov)),
                         ("span walk", lambda: check_span_walk(prov)),
                         ("spread", lambda: check_spread(
                             prov, args.save if prov == providers[0] else None))):
            try:
                ok &= fn()
            except Exception as exc:
                # A traceback at 11pm is a worse diagnostic than a named NO-GO row.
                ok &= check(f"{name} check completed ({prov})", False,
                            f"{type(exc).__name__}: {str(exc)[:110]}")
        overall &= ok
    return _verdict(overall)


def _verdict(ok: bool) -> int:
    banner("VERDICT")
    width = max(len(n) for n, _, _ in CHECKS) if CHECKS else 20
    for name, passed, detail in CHECKS:
        print(f"  {'GO   ' if passed else 'NO-GO'}  {name:<{width}}  {detail[:60]}")
    print(f"\n  ==> {'GO — Session 3 is safe to run' if ok else 'NO-GO — fix the rows above'}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
