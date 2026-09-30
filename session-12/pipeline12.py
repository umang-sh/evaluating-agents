"""
Session 12 -- THE EVALUATION PIPELINE. One file, four stages. Read it; you do not edit it.

    runs on disk ──> 1. EVALUATE ──> 2. SCORECARD ──> 3. COMPARE ──> 4. DECIDE
                     every check      every metric     version A vs     SHIP / HOLD /
                     on every run     with a spread    a candidate      REJECT

1. EVALUATE   each saved run goes through every check this course has built:
                coordination checks  (plant/coord_eval7.py)   did the right agents run, in order?
                outcome check        (plant/coord_eval7.py)   right fault, part and action?
                tool checks          (session-10/tool_eval10.py)  right tools, right arguments?
                tool judges          (session-10/judge10.py)  a model's opinion -- REPLAYED from
                                                              session-12/judge12.json, never re-asked
                the approval workflow (session-11/workflow11.py) replayed, with a finish check
              No model is called. Replaying a saved run is free and gives everyone the same answer.

2. SCORECARD  turns 24 evaluated runs into numbers, and every number carries its spread:
              a rate is "k of n" with a 95% interval; a cost is a mean with a 95% interval.
              A number without a spread is not a measurement.

3. COMPARE    lines up two versions QUESTION BY QUESTION (the same 12 questions, averaged
              over repeats) and asks, per metric: better, worse, or no detectable
              difference? Then runs the regression suite (you write it) on both.

4. DECIDE     you write this too, in my_release12.py.
"""
from __future__ import annotations

import _path  # noqa: F401  -- must be first
import math
import statistics
import sys

sys.path.insert(0, str(_path.session(10)))
sys.path.insert(0, str(_path.session(11)))

import coord_eval7
import tool_eval10
import tool_rows10
import workflow11 as wf
from intervals import wilson
from paired import t975

__version__ = "s12-2026-09-29a"


# ==========================================================================
# 1. EVALUATE
# ==========================================================================
def finish_status(plant_final: dict) -> str:
    """The workflow's finish check: a run that did not do every planned step is STALLED
    and never reaches an engineer."""
    return "COMPLETE" if plant_final.get("cursor") == plant_final.get("plan_len") else "STALLED"


def evaluate(run: dict) -> dict:
    """One run in, the same run out with `scores` and `workflow` added.

    scores[name] = 1 (pass), 0 (fail) or None (this question asserts nothing about it)
    workflow     = the approval workflow's final state: status_log, approval, work_order
    """
    out, row = run["outputs"], run["row"]
    scores = {k: v["score"] for k, v in coord_eval7.run_all(out, row).items()}
    tool_out = {**out, "question": run["question"]}
    scores.update({k: v["score"] for k, v in
                   tool_eval10.run_all(tool_out, tool_rows10.BY_ID[run["row_id"]]).items()})
    for k, v in (run.get("judges") or {}).items():
        scores["judge_" + k] = v["score"]
    w = wf.run_workflow(run["row_id"], plant_out=out, policy=finish_status)
    return {**run, "scores": scores,
            "workflow": {"status": w["status"], "status_log": w["status_log"],
                         "approval": w.get("approval"), "work_order": w.get("work_order")}}


def evaluate_all(runs: list[dict]) -> list[dict]:
    return [evaluate(r) for r in runs]


# ==========================================================================
# 2. SCORECARD
# ==========================================================================
def asked_for_approval(r):   return "AWAITING_APPROVAL" in r["workflow"]["status_log"]
def approved(r):             return "APPROVED" in r["workflow"]["status_log"]
def completed(r):            return r["workflow"]["status"] == "CLOSED"
def work_order(r):           return bool(r["workflow"]["work_order"])


def rate(runs, passed, applies=lambda r: True) -> dict:
    """k of n, with a 95% Wilson interval. `applies` picks the runs that count at all."""
    pool = [r for r in runs if applies(r)]
    k = sum(1 for r in pool if passed(r))
    lo, hi = wilson(k, len(pool))
    return {"kind": "rate", "k": k, "n": len(pool), "value": k / len(pool) if pool else None,
            "lo": lo, "hi": hi}


def score_rate(runs, name) -> dict:
    return rate(runs, lambda r: r["scores"].get(name) == 1,
                lambda r: r["scores"].get(name) is not None)


def mean_ci(values) -> dict:
    """Mean with a 95% t interval. Missing values are left out, and COUNTED."""
    xs = [v for v in values if v is not None]
    if len(xs) < 2:
        return {"kind": "mean", "value": xs[0] if xs else None, "lo": None, "hi": None,
                "n": len(xs), "missing": len(values) - len(xs)}
    m, sd = statistics.fmean(xs), statistics.stdev(xs)
    half = t975(len(xs) - 1) * sd / math.sqrt(len(xs))
    return {"kind": "mean", "value": m, "lo": m - half, "hi": m + half, "n": len(xs),
            "missing": len(values) - len(xs)}


def percentile(values, p) -> dict:
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return {"kind": "pctl", "value": None, "n": 0, "missing": len(values)}
    i = min(len(xs) - 1, max(0, math.ceil(p / 100 * len(xs)) - 1))
    return {"kind": "pctl", "value": xs[i], "n": len(xs), "missing": len(values) - len(xs),
            "lo": xs[0], "hi": xs[-1]}


# Which metrics measure the AGENTS, and which measure something else we built.
# The engineer is a rule: approve if the part is on the shelf. So anything that counts
# approvals is measuring the stock list as much as the agents.
MEASURES = {
    "task success": "agents", "right agents, right order": "agents",
    "right tools": "agents", "judge: tool fit": "a model's opinion of the agents",
    "finished the plan": "agents", "latency p50 (s)": "agents + API", "latency p90 (s)": "agents + API",
    "tokens per run": "agents", "cost per run ($)": "agents + price list",
    "workflow completion": "agents + finish check", "approval rate": "the stock list (engineer is a rule)",
    "engineer acceptance": "the stock list (same rule)", "work orders issued": "agents + stock list",
}
ENGINEERING = ("task success", "right agents, right order", "right tools", "judge: tool fit",
               "finished the plan", "latency p50 (s)", "latency p90 (s)", "tokens per run",
               "cost per run ($)")
BUSINESS = ("workflow completion", "approval rate", "engineer acceptance", "work orders issued")


def scorecard(runs: list[dict], resolved=None) -> dict:
    """Every metric for one version's evaluated runs. `resolved` is YOUR definition of a
    resolved maintenance request (my_release12.resolved); None leaves it out."""
    lat = [r["metrics"]["latency_s"] for r in runs]
    sc = {
        "task success": score_rate(runs, "outcome_match"),
        "right agents, right order": score_rate(runs, "delegation_accuracy"),
        "right tools": score_rate(runs, "tool_selection"),
        "judge: tool fit": score_rate(runs, "judge_tool_fit"),
        "finished the plan": rate(runs, lambda r: finish_status(wf.final(r["outputs"])) == "COMPLETE"),
        "latency p50 (s)": percentile(lat, 50),
        "latency p90 (s)": percentile(lat, 90),
        "tokens per run": mean_ci([r["metrics"]["tokens_billed"] for r in runs]),
        "cost per run ($)": mean_ci([r["metrics"]["cost_usd"] for r in runs]),
        "workflow completion": rate(runs, completed),
        "approval rate": rate(runs, approved, asked_for_approval),
        "engineer acceptance": rate(runs, approved, asked_for_approval),
        "work orders issued": rate(runs, work_order),
    }
    if resolved is not None:
        sc["resolution rate (yours)"] = rate(runs, lambda r: bool(resolved(r)))
    return sc


def fmt(m: dict, money: bool = False) -> str:
    """One metric as text, always with its spread."""
    if m.get("value") is None:
        return "not measured" + (f" ({m.get('missing')} runs missing)" if m.get("missing") else "")
    if m["kind"] == "rate":
        return f"{m['k']:>2} of {m['n']:<2} = {m['value']:4.0%}   (95%: {m['lo']:.0%} to {m['hi']:.0%})"
    f = (lambda x: f"{x:.4f}") if money else (lambda x: f"{x:,.1f}" if x < 100 else f"{x:,.0f}")
    miss = f"   [{m['missing']} missing]" if m.get("missing") else ""
    if m["kind"] == "pctl":
        return f"{f(m['value']):>8}          (range {f(m['lo'])} to {f(m['hi'])}){miss}"
    if m.get("lo") is None:
        return f"{f(m['value']):>8}          (too few runs for a spread){miss}"
    return f"{f(m['value']):>8}          (95%: {f(m['lo'])} to {f(m['hi'])}){miss}"


def show_scorecard(sc: dict, title: str = "") -> str:
    lines = [f"== {title} ==" if title else ""]
    for group, names in (("ENGINEERING", ENGINEERING), ("BUSINESS", BUSINESS + tuple(
            k for k in sc if k.startswith("resolution")))):
        lines.append(f"\n{group:28s} {'value':44s} measures")
        for k in names:
            if k in sc:
                lines.append(f"  {k:26s} {fmt(sc[k], money='$' in k):44s} {MEASURES.get(k, 'your definition')}")
    return "\n".join(lines)


def cost_by_agent(runs: list[dict]) -> str:
    """Where the money goes: each agent's share of the measured cost."""
    tot, calls = {}, {}
    for r in runs:
        for a, v in (r.get("agent_costs") or {}).items():
            tot[a] = tot.get(a, 0) + v["cost_usd"]
            calls[a] = calls.get(a, 0) + v["calls"]
    if not tot:
        return "per-agent cost not measured yet (session-12/agent_costs12.json missing)"
    s = sum(tot.values())
    lines = [f"{'agent':14s} {'calls':>5}  {'cost':>8}  share"]
    for a in sorted(tot, key=lambda a: -tot[a]):
        lines.append(f"{a:14s} {calls[a]:>5}  ${tot[a]:7.3f}  {tot[a] / s:4.0%}  " + "#" * round(40 * tot[a] / s))
    lines.append(f"{'total':14s} {'':>5}  ${s:7.3f}   over {len(runs)} runs")
    return "\n".join(lines)


# ==========================================================================
# 3. COMPARE
# ==========================================================================
# metric -> (how to read it from one run, which way is better)
PAIRED = {
    "task success":              (lambda r: r["scores"].get("outcome_match"), "higher"),
    "right agents, right order": (lambda r: r["scores"].get("delegation_accuracy"), "higher"),
    "right tools":               (lambda r: r["scores"].get("tool_selection"), "higher"),
    "tokens per run":            (lambda r: r["metrics"]["tokens_billed"], "lower"),
    "cost per run ($)":          (lambda r: r["metrics"]["cost_usd"], "lower"),
    "latency (s)":               (lambda r: r["metrics"]["latency_s"], "lower"),
    "work orders issued":        (lambda r: float(work_order(r)), None),
}


def _row_means(runs, get):
    by = {}
    for r in runs:
        v = get(r)
        if v is not None:
            by.setdefault(r["row_id"], []).append(float(v))
    return {k: statistics.fmean(v) for k, v in by.items()}


def paired_diff(base, cand, get, better) -> dict:
    """Question by question: average the repeats, subtract, then a 95% t interval on the
    12 differences. Pairing by question removes 'this question is just expensive'."""
    b, c = _row_means(base, get), _row_means(cand, get)
    rows = sorted(set(b) & set(c))
    d = [c[q] - b[q] for q in rows]
    res = {"n_rows": len(rows), "base": statistics.fmean(b[q] for q in rows) if rows else None,
           "cand": statistics.fmean(c[q] for q in rows) if rows else None}
    if len(rows) < 2:
        return {**res, "diff": None, "lo": None, "hi": None, "direction": "not measured"}
    m, sd = statistics.fmean(d), statistics.stdev(d)
    half = t975(len(d) - 1) * sd / math.sqrt(len(d)) if sd > 0 else 0.0
    lo, hi = m - half, m + half
    if lo > 0 or hi < 0:
        up = lo > 0
        direction = "changed" if better is None else ("better" if up == (better == "higher") else "worse")
    else:
        direction = "no detectable difference"
    return {**res, "diff": m, "lo": lo, "hi": hi, "direction": direction}


def suite(runs: list[dict], must_hold) -> dict:
    """The regression suite: for each of the 12 questions, does must_hold pass on EVERY
    repeat? -> {row_id: (held, evidence of the first failure)}"""
    out = {}
    for r in runs:
        ok, ev = must_hold(r)
        held, first = out.get(r["row_id"], (True, ""))
        out[r["row_id"]] = (held and bool(ok), first or ("" if ok else f"rep {r['rep']}: {ev}"))
    return out


def compare(base: list[dict], cand: list[dict], must_hold=None) -> dict:
    """Everything decide() gets. `base` and `cand` are evaluated runs."""
    cmp = {"base": base[0]["version"] if base else "?", "cand": cand[0]["version"] if cand else "?",
           "n_questions": len({r["row_id"] for r in cand}),
           "seeded": any(r.get("seeded") for r in cand),
           "metrics": {k: paired_diff(base, cand, g, b) for k, (g, b) in PAIRED.items()}}
    if must_hold is not None:
        sb, sc = suite(base, must_hold), suite(cand, must_hold)
        cmp["regressions"] = sorted(q for q in sc if sb.get(q, (False,))[0] and not sc[q][0])
        cmp["fixed"] = sorted(q for q in sc if not sb.get(q, (True,))[0] and sc[q][0])
        cmp["still_failing"] = sorted(q for q in sc if not sb.get(q, (True,))[0] and not sc[q][0])
        cmp["evidence"] = {q: sc[q][1] for q in cmp["regressions"] + cmp["still_failing"]}
    return cmp


def show_compare(cmp: dict) -> str:
    lines = [f"== {cmp['base']} -> {cmp['cand']}   ({cmp['n_questions']} questions, paired)"
             + ("   SEEDED CANDIDATE" if cmp.get("seeded") else "") + " =="]
    lines.append(f"  {'metric':26s} {'base':>9} {'cand':>9} {'diff':>9}   95% interval          verdict")
    for k, m in cmp["metrics"].items():
        if m["diff"] is None:
            lines.append(f"  {k:26s} {'':>9} {'':>9} {'':>9}   {'':21s} {m['direction']}")
            continue
        f = (lambda x: f"{x:+.4f}") if "$" in k else (lambda x: f"{x:+,.2f}" if abs(x) < 100 else f"{x:+,.0f}")
        g = (lambda x: f"{x:.4f}") if "$" in k else (lambda x: f"{x:,.2f}" if abs(x) < 100 else f"{x:,.0f}")
        lines.append(f"  {k:26s} {g(m['base']):>9} {g(m['cand']):>9} {f(m['diff']):>9}   "
                     f"{f(m['lo']) + ' to ' + f(m['hi']):21s} {m['direction'].upper()}")
    if "regressions" in cmp:
        lines.append(f"\n  regression suite:  REGRESSED {cmp['regressions'] or 'none'}   "
                     f"FIXED {cmp['fixed'] or 'none'}   STILL FAILING {cmp['still_failing'] or 'none'}")
        for q, ev in cmp["evidence"].items():
            lines.append(f"      {q}: {ev}")
    return "\n".join(lines)


# ==========================================================================
# 4. MONITOR -- one day of production traffic as numbers
# ==========================================================================
def day_metrics(day_runs: list[dict]) -> dict:
    """The numbers a production dashboard shows for one day."""
    sc = scorecard(day_runs)
    lat = percentile([r["metrics"]["latency_s"] for r in day_runs], 90)
    return {"day": day_runs[0].get("day"), "requests": len(day_runs),
            "task_success": (sc["task success"]["k"], sc["task success"]["n"]),
            "approval": (sc["approval rate"]["k"], sc["approval rate"]["n"]),
            "work_orders": sc["work orders issued"]["k"],
            "completion": (sc["workflow completion"]["k"], sc["workflow completion"]["n"]),
            "cost_usd": round(sum(r["metrics"]["cost_usd"] or 0 for r in day_runs), 3),
            "p90_latency_s": lat["value"]}


def show_week(days: list[dict]) -> str:
    """The production dashboard, one line per day."""
    def pct(kn):
        k, n = kn
        return f"{k:>2}/{n:<2} {k / n:4.0%} " + ("#" * round(10 * k / n)).ljust(10) if n else "  -"
    lines = [f"{'day':>3}  {'task success':22s} {'approval rate':22s} {'work orders':>11} {'cost $':>7} {'p90 s':>6}"]
    for d in days:
        lines.append(f"{d['day']:>3}  {pct(d['task_success']):22s} {pct(d['approval']):22s} "
                     f"{d['work_orders']:>11} {d['cost_usd']:>7.2f} {d['p90_latency_s']:>6.1f}")
    return "\n".join(lines)
