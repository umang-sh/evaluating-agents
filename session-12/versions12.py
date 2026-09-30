"""
Session 12 -- where every version's runs come from. Read it if you want; you do not edit it.

    version  what it is                                                     how it was made
    -------  -------------------------------------------------------------  -------------------------
    A        the maintenance assistant as it is today                       24 REAL runs, 25 Sep
    B        A with one change: the planner's rule about "within limits"     24 REAL runs (capture12)
             questions (see version_b12.py)
    C        A with the documentation agent removed from every run           SEEDED: made from A's
                                                                            saved runs, not re-run

Every run is loaded from a file on disk. Nothing here calls a model, so every laptop gets
the same numbers, for free.

"SEEDED" means broken on purpose, by code we wrote. C is built by deleting the
documentation agent's step from each of A's saved runs, and subtracting that agent's
measured tokens and cost. Its later agents are NOT re-run, so their answers are A's
answers. A real re-run could come out better or worse. C exists to test the regression
suite, not to be a real candidate.
"""
from __future__ import annotations

import _path  # noqa: F401  -- must be first
import json
import random
import sys

sys.path.insert(0, str(_path.session(10)))   # tool_eval10 lives in session-10/

from delegation_rows7 import BY_ID
from plant_agents7 import read_tail

__version__ = "s12-2026-09-29a"

HERE = _path.ROOT / "session-12"
RUNS_A = _path.session(11) / "runs11.json"
TOKENS_A = HERE / "tokens11.json"
RUNS_B = HERE / "runs12.json"
RUNS_B_STUB = HERE / "runs12_STUB.json"
AGENT_COSTS = HERE / "agent_costs12.json"
JUDGES = HERE / "judge12.json"

NAMES = {"A": "version A (today)", "B": "version B (planner fix)",
         "C": "version C (SEEDED: no documentation agent)"}


def _read(path):
    return json.loads(path.read_text()) if path.exists() else None


def _agent_costs():
    d = _read(AGENT_COSTS) or {"runs": []}
    return {(r["version"], r["row_id"], r["rep"]): r["agents"] for r in d["runs"]}


def _judges():
    d = _read(JUDGES) or {"runs": []}
    return {(r["version"], r["row_id"], r["rep"]): r["verdicts"] for r in d["runs"]}


def _raw(version: str):
    """[(record, metrics)] for one version, from disk."""
    if version == "A":
        d = _read(RUNS_A)
        tok = {(t["row_id"], t["rep"]): t for t in (_read(TOKENS_A) or {"runs": []})["runs"]}
        out = []
        for r in d["runs"]:
            if r.get("phase") != "state_capture":
                continue
            m = dict(r["outputs"]["metrics"])
            t = tok.get((r["row_id"], r["rep"]))
            if t:   # recovered from LangSmith after the capture (session-12/backfill_tokens12.py)
                m.update({k: t[k] for k in ("tokens_billed", "cost_usd")})
            out.append((r, m))
        return out, d["generated"]
    if version == "B":
        d = _read(RUNS_B)
        if d is None:
            return None, None
        return [(r, dict(r["outputs"]["metrics"])) for r in d["runs"]
                if r.get("phase") == "version_b_prompt"], d["generated"]
    if version == "B_STUB":
        d = _read(RUNS_B_STUB)
        return [(r, dict(r["outputs"]["metrics"])) for r in d["runs"]], d["generated"]
    raise KeyError(version)


def _rebuild(outputs: dict, drop: str) -> dict:
    """A saved run with every step by agent `drop` removed. State history is rebuilt so
    the counters still obey steps == cursor + 1 -- nothing else about the run is broken."""
    plan = [p for p in outputs["plan"] if p["agent"] != drop]
    calls = [a for a in outputs["agent_calls"] if a != drop]
    # saved runs keep each agent's report as the context it left behind
    reports = [{"agent": h["agent"], "text": h["context"]} for h in outputs["state_history"]
               if h["node"] == "dispatch" and h["agent"] != drop]
    tools = [c for c in outputs["tool_calls"] if c.get("agent") != drop]
    brief = outputs["handoffs"][0]["payload"] if outputs.get("handoffs") else ""
    handoffs, hist, prev = [], [], brief
    hist.append({"node": "planner", "agent": "planner", "cursor": 0, "steps": 1,
                 "plan_len": len(plan), "n_agent_calls": 1, "new_tool_calls": [], "context": brief})
    for i, r in enumerate(reports):
        handoffs.append({"from": calls[i] if i < len(calls) else "planner", "to": r["agent"], "payload": prev})
        prev = r["text"]
        hist.append({"node": "dispatch", "agent": r["agent"], "cursor": i + 1, "steps": i + 2,
                     "plan_len": len(plan), "n_agent_calls": i + 2,
                     "new_tool_calls": [c for c in tools if c.get("agent") == r["agent"]],
                     "context": prev})
    hist.append({**hist[-1], "node": "finish", "new_tool_calls": []})
    tail = {}
    for r in reports:
        tail.update(read_tail(r["text"]))
    answer = "\n\n".join(f"[{r['agent']}]\n{r['text']}" for r in reports)
    return {**outputs, "plan": plan, "agent_calls": calls, "reports": reports,
            "tool_calls": tools, "handoffs": handoffs, "state_history": hist,
            "tail": tail, "answer": answer or "no specialist produced a report"}


def load(version: str) -> list[dict]:
    """Every run of one version, flattened for the pipeline:
        version, row_id, rep, question, row (the question's answer key),
        outputs (what the agents did), metrics (latency_s, tokens_billed, cost_usd),
        agent_costs (per agent, when measured), judges (saved verdicts, when measured)
    Returns [] when the version has not been captured yet."""
    costs, judged = _agent_costs(), _judges()
    src = "A" if version == "C" else version
    raw, generated = _raw(src)
    if raw is None:
        return []
    out = []
    for r, m in raw:
        key = ("A" if src == "A" else "B", r["row_id"], r["rep"])
        ac = costs.get(key)
        outputs = r["outputs"]
        judges = judged.get(key)
        if version == "C":
            doc = (ac or {}).get("documentation")
            if "documentation" in outputs["agent_calls"]:
                outputs = _rebuild(outputs, "documentation")
                judges = None           # the judges saw A's calls, not C's
                if doc:
                    m = {**m, "tokens_billed": None if m.get("tokens_billed") is None else m["tokens_billed"] - doc["tokens"],
                         "cost_usd": None if m.get("cost_usd") is None else round(m["cost_usd"] - doc["cost_usd"], 6)}
                else:
                    m = {**m, "tokens_billed": None, "cost_usd": None}
                m["latency_s"] = None   # not re-run: we do not know how long it would take
                ac = {k: v for k, v in (ac or {}).items() if k != "documentation"} or None
        out.append({"version": version, "row_id": r["row_id"], "rep": r["rep"],
                    "question": r["question"], "row": BY_ID[r["row_id"]], "outputs": outputs,
                    "metrics": {k: m.get(k) for k in ("latency_s", "tokens_billed", "cost_usd")},
                    "agent_costs": ac, "judges": judges, "captured": generated,
                    "seeded": version == "C"})
    return out


# ==========================================================================
# A production week -- for the monitoring hands-on
# ==========================================================================
DRIFT_DAY = 5          # from this day on, the store is out of SKF-6208 bearings
DRIFT_PART = "SKF-6208"
DAYS = 7
REQUESTS_PER_DAY = 24


def production_week(seed: int = 12) -> list[dict]:
    """Seven days of traffic. Each day, 24 requests are drawn at random from version A's
    24 real runs and pushed through the approval workflow.

    Nothing about the AGENTS changes all week. From day DRIFT_DAY on, the spare-parts
    store runs out of one bearing (SEEDED). Returns one list of workflow runs per day,
    each tagged with its day."""
    import pipeline12 as pl
    from plant7 import PARTS
    base = load("A")
    rng = random.Random(seed)
    days = []
    saved = PARTS[DRIFT_PART]["on_hand"]
    try:
        for day in range(1, DAYS + 1):
            PARTS[DRIFT_PART]["on_hand"] = 0 if day >= DRIFT_DAY else saved
            picks = [rng.choice(base) for _ in range(REQUESTS_PER_DAY)]
            days.append([{**pl.evaluate(dict(p)), "day": day} for p in picks])
    finally:
        PARTS[DRIFT_PART]["on_hand"] = saved
    return days
