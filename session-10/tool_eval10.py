"""
Session 10 -- four code evaluators for the tool layer. No model, no key, no spend.

SPINE: a tool that answers every mistake is a tool that hides every mistake.

WHY FOUR, AND WHY THIS SPLIT
-----------------------------
    tool_selection    WHICH tools were called          -- names only
    tool_arguments    WHAT they were called WITH       -- values
    tool_self_heal    how many calls came back EMPTY or as an error
    tool_result_used  did what came back reach the ANSWER

The split between the first two is the session. Session 7's `expected_calls` counts
invocations: `{"diagnostics": 2}` passes any run where diagnostics ran twice. It cannot
ask what each call was for, because a count has nowhere to put that. An ARGUMENT does.
HW-006 is the proof: diagnostics runs twice, both times looking up CONVEYOR, and the
BLOWER the engineer asked about is never looked up by any tool in the run.

`tool_self_heal` is the third one and it is the one nobody asks for. Not one tool in
this plant raises. Read the returns rather than the docstrings:

    equipment_kb("LINE4")      -> {"error": "not found: check the machine id against
                                    equipment_kb", "known_machines": [...]}
    parts_inventory("NONE")    -> {"error": "part not stocked", "known_parts": [...]}
    manual_search("imbalance") -> {"sections": [], "note": "no match; try fewer or
                                    broader words"}

All three are SUCCESSFUL string returns. Nothing raises, so there is no retry, no
failure recovery and no error-handling branch to observe -- and the model is handed the
list of things it should have asked for, so it asks again and gets it right. The mistake
costs one extra call and then vanishes from the outcome completely.

The same is true one level up. At our pin, langgraph-prebuilt 1.1.0,
`ToolNode._validate_tool_call` answers a tool name it does not recognise with

    ToolMessage("Error: {name} is not a valid tool, try one of [...]", status="error")

-- the identical shape. A hallucinated tool call is not prevented here. It is forgiven
here, and forgiven is harder to see than prevented.

WHAT THIS MEANS FOR AN EVALUATOR THAT READS THE FINAL ANSWER
-------------------------------------------------------------
It scores every one of those runs as clean, because by the time the answer is written
the mistake has been corrected. The only place it is still visible is a tool call you
have to count. That is the session, and `tool_self_heal` is the evaluator that counts.

SCORING CONVENTION, UNCHANGED FROM SESSION 7
---------------------------------------------
Every evaluator takes `(outputs, reference_outputs)` and returns
`{"key", "score", "comment"}` with 1 = pass, 0 = fail, None = not applicable, so these
drop into the same harness loop as `coord_eval7`'s five and `judge9`'s three with no
special case anywhere. `None` means the row asserts nothing here -- Session 7 learned to
distinguish that from a pass, after quoting 5/12 for an evaluator that applied to 7 rows.

COMMENTS ARE NEVER TRUNCATED
-----------------------------
Session 8's rule 5. `comment[:110]` throws away the evidence line, which is the only
part anyone can argue with, and arguing with it is the hands-on.
"""

from __future__ import annotations

import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first

from plant7 import EQUIPMENT, HISTORY, MANUAL, PARTS, SENSORS
from stub_tools10 import GRANTS, TOOL_NAMES

__version__ = "s10-2026-09-22a"


def _res(key: str, score, comment: str) -> dict:
    return {"key": key, "score": score, "comment": comment}


def _calls(outputs: dict) -> list[dict]:
    return list(outputs.get("tool_calls") or [])


def _fmt(c: dict) -> str:
    args = ", ".join(f"{k}={v!r}" for k, v in (c.get("args") or {}).items())
    return f"{c.get('name')}({args})"


# ---------------------------------------------------------------------------
# What a call comes back with, computed from the plant tables rather than by calling
# the tool.
#
# WHY NOT JUST CALL THE TOOL: `plant_tools7.py` imports langchain_core at module level,
# and the point of this file is that it runs with no dependencies, no key and no
# network. `preflight10` check [2] invokes the real tools where they ARE importable and
# asserts these predicates agree with them, so this stays a shortcut and never becomes
# a second source of truth.
# ---------------------------------------------------------------------------
_TABLE = {"equipment_kb": EQUIPMENT, "sensor_history": SENSORS,
          "maintenance_history": HISTORY}


def returns_nothing(name: str, args: dict) -> str | None:
    """The self-healing return this call gets back, described, or None if it lands.

    Returns a human-readable reason, because the reason is what goes on the slide.
    """
    args = args or {}
    if name in _TABLE:
        mid = str(args.get("machine_id", "")).strip().upper()
        if mid not in _TABLE[name]:
            return (f"machine id {mid!r} is not in the knowledge base; the tool answers "
                    f"with an 'error' string AND the list of real machine ids, so the "
                    f"agent can simply ask again")
        return None

    if name == "parts_inventory":
        part = str(args.get("part_no", "")).strip().upper()
        if part not in PARTS:
            return (f"part {part!r} is not stocked; the tool answers with an 'error' "
                    f"string AND the list of stocked part numbers")
        return None

    if name == "manual_search":
        query = str(args.get("query", ""))
        mid = str(args.get("machine_id", "")).strip().upper()
        words = {w for w in query.lower().split() if len(w) > 3}
        for sec in MANUAL.values():
            if mid and sec["machine"] != mid:
                continue
            hay = (sec["title"] + " " + sec["text"]).lower()
            if any(w in hay for w in words) or (mid and not words):
                return None
        return (f"no manual section matches {query!r}"
                + (f" for {mid}" if mid else "")
                + "; the tool answers with an empty section list and the note "
                  "'no match; try fewer or broader words'")

    return f"{name!r} is not one of the five plant tools"


# ---------------------------------------------------------------------------
# 1. tool_selection -- WHICH tools were called.
# ---------------------------------------------------------------------------
def tool_selection(outputs: dict, reference_outputs: dict) -> dict:
    key = "tool_selection"
    row = reference_outputs or {}
    must, forbid = row.get("must_call") or {}, row.get("forbidden") or {}
    if not must and not forbid:
        return _res(key, None, "row asserts nothing about tool selection")

    calls = _calls(outputs)
    if not calls:
        return _res(key, 0, "no tool calls at all; the row requires "
                            + " and ".join(f"{a}:{sorted(t)}" for a, t in must.items()))

    by_agent: dict[str, set[str]] = {}
    for c in calls:
        by_agent.setdefault(c.get("agent", "?"), set()).add(c.get("name", "?"))

    problems: list[str] = []

    # An agent reaching a tool it was never granted. This is the hallucinated-tool
    # shape, and at our pin it does not raise -- it comes back as a ToolMessage with
    # status="error" naming the tools the agent does hold.
    for agent, names in by_agent.items():
        ungranted = sorted(names - GRANTS.get(agent, TOOL_NAMES))
        if ungranted:
            problems.append(f"{agent} called {ungranted}, which it does not hold")

    for agent, tools in must.items():
        missing = sorted(set(tools) - by_agent.get(agent, set()))
        if missing:
            problems.append(f"{agent} never called {missing}")

    for agent, tools in forbid.items():
        present = sorted(set(tools) & by_agent.get(agent, set()))
        if present:
            problems.append(f"{agent} called {present}, which this request rules out")

    if row.get("match_mode") == "exact":
        for agent, names in by_agent.items():
            extra = sorted(names - set(must.get(agent, ())))
            if extra:
                problems.append(f"{agent} also called {extra} (match_mode is 'exact')")

    if problems:
        return _res(key, 0, "; ".join(problems))
    return _res(key, 1, f"{len(calls)} call(s); every required tool was called and "
                        f"nothing ruled out was")


# ---------------------------------------------------------------------------
# 2. tool_arguments -- WHAT they were called with.
# ---------------------------------------------------------------------------
def tool_arguments(outputs: dict, reference_outputs: dict) -> dict:
    key = "tool_arguments"
    row = reference_outputs or {}
    cover = row.get("must_cover") or {}
    calls = _calls(outputs)
    if not calls:
        return _res(key, None, "no tool calls to inspect")

    problems: list[str] = []

    # (a) Shape. Every tool has one required argument and it must be a non-empty string.
    REQUIRED = {"equipment_kb": "machine_id", "sensor_history": "machine_id",
                "maintenance_history": "machine_id", "manual_search": "query",
                "parts_inventory": "part_no"}
    for c in calls:
        want = REQUIRED.get(c.get("name", ""))
        if want is None:
            continue
        got = (c.get("args") or {}).get(want)
        if not isinstance(got, str) or not got.strip():
            problems.append(f"{_fmt(c)} is missing its {want}")

    # (b) Coverage. THE NEW QUESTION. Did the arguments, taken together, mention
    #     everything the request named? A count of calls cannot ask this.
    seen: dict[str, set[str]] = {}
    for c in calls:
        for k, v in (c.get("args") or {}).items():
            if isinstance(v, str):
                seen.setdefault(k, set()).add(v.strip().upper())
    for arg, wanted in cover.items():
        missing = [w for w in wanted if w.upper() not in seen.get(arg, set())]
        if missing:
            got = sorted(seen.get(arg, set())) or ["nothing"]
            problems.append(
                f"no tool call ever passed {arg}={missing} -- the request names it, "
                f"and across {len(calls)} call(s) the only {arg} value(s) used were "
                f"{got}")

    if problems:
        return _res(key, 0, "; ".join(problems))
    if not cover:
        return _res(key, 1, f"{len(calls)} call(s), every argument well formed; "
                            f"the row asserts no coverage")
    return _res(key, 1, f"{len(calls)} call(s); every argument well formed and every "
                        f"value the request names was actually passed to a tool")


# ---------------------------------------------------------------------------
# 3. tool_self_heal -- how many calls came back empty or as an error.
# ---------------------------------------------------------------------------
def tool_self_heal(outputs: dict, _reference_outputs: dict | None = None) -> dict:
    """1 when every call landed, 0 when any call came back empty or as an error.

    Deliberately NOT keyed off the row: this asks a question about the run, not about
    whether the run matched anyone's expectation. It is the only evaluator here that
    needs no key at all -- which is itself worth saying on the slide, because it means
    this one scales to the twelve thousand questions nobody wrote rows for.
    """
    key = "tool_self_heal"
    calls = _calls(outputs)
    if not calls:
        return _res(key, None, "no tool calls to inspect")

    misses = [(c, r) for c in calls if (r := returns_nothing(c.get("name", ""),
                                                             c.get("args") or {}))]
    if not misses:
        return _res(key, 1, f"all {len(calls)} call(s) returned real data")
    detail = "; ".join(f"{_fmt(c)} -> {r}" for c, r in misses)
    return _res(key, 0, f"{len(misses)} of {len(calls)} call(s) came back with nothing "
                        f"usable, and NONE of them raised: {detail}")


# ---------------------------------------------------------------------------
# 4. tool_result_used -- did what came back reach the answer.
# ---------------------------------------------------------------------------
# What to look for in the answer as evidence that a call's return was actually used.
# An honest approximation, and its limits go on the slide: a witness appearing proves
# the value reached the text, not that the agent reasoned from it; and a witness absent
# does not prove the call was wasted, only that nothing traceable survived.
def _witness(c: dict) -> str | None:
    name, args = c.get("name", ""), (c.get("args") or {})
    if name == "parts_inventory":
        return str(args.get("part_no", "")).strip().upper() or None
    if name == "manual_search":
        mid = str(args.get("machine_id", "")).strip().upper()
        words = {w for w in str(args.get("query", "")).lower().split() if len(w) > 3}
        for sec_id, sec in MANUAL.items():
            if mid and sec["machine"] != mid:
                continue
            hay = (sec["title"] + " " + sec["text"]).lower()
            if any(w in hay for w in words):
                return sec_id
        return None
    return str(args.get("machine_id", "")).strip().upper() or None


def tool_result_used(outputs: dict, _reference_outputs: dict | None = None) -> dict:
    key = "tool_result_used"
    calls = _calls(outputs)
    answer = (outputs.get("answer") or "").upper()
    if not calls:
        return _res(key, None, "no tool calls to inspect")
    if not answer:
        return _res(key, None, "no answer recorded")

    landed = [c for c in calls
              if not returns_nothing(c.get("name", ""), c.get("args") or {})]
    if not landed:
        return _res(key, None, "no call returned anything that could reach the answer")

    unused = [c for c in landed if (w := _witness(c)) and w not in answer]
    if unused:
        detail = "; ".join(f"{_fmt(c)} returned data the answer never mentions "
                           f"(looked for {_witness(c)!r})" for c in unused)
        return _res(key, 0, f"{len(unused)} of {len(landed)} landed call(s) left no "
                            f"trace in the answer: {detail}")
    return _res(key, 1, f"every one of {len(landed)} landed call(s) left something "
                        f"traceable in the answer")


OFFLINE = (tool_selection, tool_arguments, tool_self_heal, tool_result_used)
KEYS = tuple(f.__name__ for f in OFFLINE)


def run_all(outputs: dict, row: dict) -> dict[str, dict]:
    """Every code evaluator over one run. Zero model calls, by construction."""
    return {f.__name__: f(outputs, row) for f in OFFLINE}


LIVE_CALLS_PER_RUN = 0


if __name__ == "__main__":
    import argparse
    import json

    import stub_tools10 as st
    import tool_rows10

    ap = argparse.ArgumentParser(description="Run the four tool evaluators on one run.")
    ap.add_argument("--row", default="HW-006")
    ap.add_argument("--arm", default="healthy")
    ap.add_argument("--show", action="store_true", help="print the tool calls too")
    a = ap.parse_args()

    runs = json.loads((_path.session(7) / "runs7.json").read_text())["runs"]
    rec = next((r for r in runs if r.get("phase") == "matrix"
                and r.get("seed") == a.arm and r.get("row_id") == a.row), None)
    if rec is None:
        raise SystemExit(f"no matrix record for {a.row}/{a.arm}")

    out = st.with_tools(rec["outputs"])
    print(f"tool_eval10 {__version__}   {a.row} / {a.arm}   "
          f"({LIVE_CALLS_PER_RUN} model calls)\n")
    print(f"question: {rec['question']}\n")
    if a.show:
        print(st.render(out["tool_calls"]), "\n")
    for k, v in run_all(out, tool_rows10.BY_ID[a.row]).items():
        mark = {1: ".", 0: "X", None: "-"}[v["score"]]
        print(f"  {mark} {k:18s} {str(v['score']):>5s}  {v['comment']}")
