"""
Session 11 -- the maintenance WORKFLOW: the four agents, then an engineer's approval,
then a work order.

WHAT THIS ADDS TO THE PLANT
---------------------------
The four agents (Planner -> Diagnostics -> Documentation -> Maintenance) end with a
recommendation. A plant does not act on a recommendation. An engineer approves it, and
only then does a WORK ORDER exist -- the piece of paper that sends a technician to a
machine with a part in their hand.

So this file wraps the four agents in a second, small graph:

    REQUESTED -> (agents run) -> DIAGNOSED / DOCUMENTED / RECOMMENDED
              -> AWAITING_APPROVAL -> APPROVED  -> WORK_ORDER_ISSUED -> CLOSED
                                   -> REJECTED  -> CLOSED
    and, if a workflow is judged not to have finished:  -> STALLED

`status` is WHERE the workflow is now. `status_log` is every status it has been in, in
order. Checking that log against a table of allowed moves is how an invalid transition
is caught (see `LEGAL` in my_state11.py).

TWO WAYS TO KEEP STATE, IN ONE ROOM
-----------------------------------
The plant's graph rebuilds every list by hand (`state.get(k, []) + [x]`) and returns the
whole state from every node. This graph uses LangGraph's own mechanism, a REDUCER:
`status_log: Annotated[list, operator.add]`. A node returns only the NEW statuses, and
LangGraph appends them. A channel without a reducer (`status`) is overwritten by the last
node that writes it. Both styles work. Only one is LangGraph's.

THE ENGINEER IS SIMULATED -- SAY SO
-----------------------------------
A real approval is a person. Pausing a graph to wait for one needs a checkpointer and
`interrupt()` (demo cell `interrupt-demo`). Here the engineer is one deterministic rule:
approve if the recommended part is on the shelf, reject if it is not. That keeps every
run reproducible, free and identical on every student's laptop.

WHAT IS DELIBERATELY WRONG IN THE DEFAULT
-----------------------------------------
`finish_blindly` treats every run of the agents as finished. The plant's step cap
(MAX_STEPS) stops a looping run and writes an answer anyway, so a run that never
finished its plan can still reach an engineer and still get a work order. That is the
bug the `redesign` exercise fixes. It is left in on purpose.
"""
from __future__ import annotations

import _path  # noqa: F401  -- must be first
import operator
import re
from typing import Annotated, Callable, TypedDict

from plant7 import EQUIPMENT, PARTS
from plant_agents7 import MAX_STEPS, read_tail, run_pipeline
from delegation_rows7 import BY_ID

__version__ = "s11-2026-09-28a"

STATUSES = ("REQUESTED", "DIAGNOSED", "DOCUMENTED", "RECOMMENDED", "AWAITING_APPROVAL",
            "APPROVED", "REJECTED", "WORK_ORDER_ISSUED", "STALLED", "CLOSED")

AGENT_STATUS = {"diagnostics": "DIAGNOSED", "documentation": "DOCUMENTED",
                "maintenance": "RECOMMENDED"}

NO_WORK = ("", "none", "monitor")   # actions that need no technician

MACHINES = tuple(EQUIPMENT)


class WorkState(TypedDict, total=False):
    row_id: str
    request: str
    plant: dict                                   # the four agents' result
    status: str                                   # no reducer: last writer wins
    status_log: Annotated[list, operator.add]     # reducer: every write is appended
    approval: dict | None
    work_order: dict | None


# ==========================================================================
# Helpers students use. None of these is a check -- they only read state.
# ==========================================================================
def snapshots(run: dict) -> list[dict]:
    """The agents' state after every node, in order (planner, each agent, finish)."""
    return run["plant"].get("state_history", [])


def final(run_or_plant: dict) -> dict:
    """The agents' LAST recorded state (cursor, steps, plan_len, ...)."""
    plant = run_or_plant.get("plant", run_or_plant)
    hist = plant.get("state_history") or []
    return hist[-1] if hist else {}


def agent_steps(run: dict) -> list[dict]:
    """One entry per agent step: which agent, what it was asked, what it produced."""
    plan = run["plant"].get("plan") or []
    out = []
    for i, h in enumerate(s for s in snapshots(run) if s["node"] == "dispatch"):
        out.append({"agent": h["agent"],
                    "subtask": plan[i]["subtask"] if i < len(plan) else "",
                    "report": h["context"],
                    "tool_calls": h.get("new_tool_calls", [])})
    return out


def machines_named(text: str) -> list[str]:
    """Machine ids that appear in a piece of text, e.g. a subtask."""
    return [m for m in MACHINES if m in (text or "")]


def machine_worked_on(step: dict) -> str | None:
    """Which machine an agent step actually worked on.

    Live runs: the machine_id its tool calls were pointed at.
    Stub runs (no tool calls): the machine its report says it looked at.
    None when the step gives no evidence either way (e.g. a stock check).
    """
    ids = [c["args"]["machine_id"] for c in step.get("tool_calls", [])
           if c.get("args", {}).get("machine_id") in MACHINES]
    if ids:
        return ids[-1]
    m = re.search(r"(?:history for|section for) ([A-Z-]+)", step.get("report", ""))
    return m.group(1) if m else None


# ==========================================================================
# Finish policies -- "did the agents finish?"
# ==========================================================================
def finish_blindly(plant_final: dict) -> str:
    """THE DEFAULT, AND IT IS WRONG. Every run counts as finished."""
    return "COMPLETE"


# ==========================================================================
# The graph
# ==========================================================================
Route = Callable[[str, dict, str], str]


def build_workflow(impl: str = "stub", plant_seed=None, route_seed: Route | None = None,
                   policy: Callable[[dict], str] = finish_blindly, plant_out: dict | None = None):
    """Compile the workflow.

    plant_seed  a seeds7-style injector passed through to the four agents
    route_seed  (stage, state, default_next) -> next : a router with a bug in it
    policy      finish policy: plant final state -> "COMPLETE" | "STALLED"
    plant_out   a saved run of the agents to REPLAY instead of running them (free)
    """
    from langgraph.graph import END, START, StateGraph

    def _route(stage, state, default):
        return route_seed(stage, state, default) if route_seed else default

    def agents(state: WorkState) -> dict:
        out = plant_out if plant_out is not None else run_pipeline(
            state["request"], impl=impl, seed=plant_seed)
        new = [AGENT_STATUS[h["agent"]] for h in out.get("state_history", [])
               if h["node"] == "dispatch" and h["agent"] in AGENT_STATUS]
        return {"plant": out, "status": new[-1] if new else "REQUESTED", "status_log": new}

    def after_agents(state: WorkState) -> str:
        if policy(final(state["plant"])) == "STALLED":
            return _route("agents", state, "stall")
        tail = state["plant"].get("tail", {})
        needs_work = (state["status"] == "RECOMMENDED"
                      and tail.get("ACTION", "").lower() not in NO_WORK)
        return _route("agents", state, "request_approval" if needs_work else "close")

    def stall(state: WorkState) -> dict:
        return {"status": "STALLED", "status_log": ["STALLED"]}

    def request_approval(state: WorkState) -> dict:
        return {"status": "AWAITING_APPROVAL", "status_log": ["AWAITING_APPROVAL"]}

    def engineer(state: WorkState) -> dict:
        part = state["plant"].get("tail", {}).get("PART", "")
        stock = PARTS.get(part, {}).get("on_hand", 0) if part else 1
        ok = stock > 0
        decision = "APPROVED" if ok else "REJECTED"
        reason = (f"{part or 'no part needed'}: {stock} on hand" if part
                  else "no part needed")
        return {"status": decision, "status_log": [decision],
                "approval": {"by": "engineer (simulated)", "decision": decision,
                             "reason": reason}}

    def after_engineer(state: WorkState) -> str:
        return _route("engineer", state,
                      "work_order" if state["status"] == "APPROVED" else "close")

    def work_order(state: WorkState) -> dict:
        tail = state["plant"].get("tail", {})
        wo = {"id": f"WO-{state['row_id']}", "machine": tail.get("MACHINE", "?"),
              "fault": tail.get("FAULT_CODE", "?"), "part": tail.get("PART", ""),
              "action": tail.get("ACTION", "")}
        return {"status": "WORK_ORDER_ISSUED", "status_log": ["WORK_ORDER_ISSUED"],
                "work_order": wo}

    def close(state: WorkState) -> dict:
        return {"status": "CLOSED", "status_log": ["CLOSED"]}

    g = StateGraph(WorkState)
    for name, fn in [("agents", agents), ("stall", stall), ("request_approval", request_approval),
                     ("engineer", engineer), ("work_order", work_order), ("close", close)]:
        g.add_node(name, fn)
    g.add_edge(START, "agents")
    g.add_conditional_edges("agents", after_agents,
                            {"stall": "stall", "request_approval": "request_approval",
                             "close": "close", "work_order": "work_order"})
    g.add_edge("request_approval", "engineer")
    g.add_conditional_edges("engineer", after_engineer,
                            {"work_order": "work_order", "close": "close"})
    g.add_edge("work_order", "close")
    g.add_edge("stall", END)
    g.add_edge("close", END)
    return g.compile()


def run_workflow(row_id: str, impl: str = "stub", plant_seed=None, route_seed=None,
                 policy=finish_blindly, plant_out: dict | None = None,
                 label: str = "") -> dict:
    """Run one request through the whole workflow and return its final state."""
    from bench7 import tracing_off
    row = BY_ID[row_id]
    app = build_workflow(impl, plant_seed, route_seed, policy, plant_out)
    # A stub run or a replay is not a real run, so it is not logged as one: with
    # LANGSMITH_TRACING=true in .env every one of these would otherwise be sent to your
    # LangSmith project as a trace -- and on a machine that cannot reach LangSmith, each
    # invoke waits on the network. Same rule as bench7.tracing_off.
    with tracing_off(impl == "stub" or plant_out is not None):
        out = app.invoke({"row_id": row_id, "request": row["request"], "status": "REQUESTED",
                          "status_log": ["REQUESTED"], "approval": None, "work_order": None})
    out["label"] = label or row_id
    return out


def show(run: dict, width: int = 88) -> str:
    """What the plant manager sees: the request, the answer's tail, the work order."""
    import textwrap
    wo = run.get("work_order")
    tail = run["plant"].get("tail", {})
    lines = [f"== {run.get('label', run['row_id'])} ==",
             textwrap.fill("request: " + run["request"], width, subsequent_indent="         "),
             f"answer : {len(run['plant'].get('answer', ''))} characters, "
             f"{len(agent_steps(run))} agent steps",
             "tail   : " + ", ".join(f"{k}={v}" for k, v in tail.items()),
             f"approval: {run['approval']['decision'] + ' (' + run['approval']['reason'] + ')' if run.get('approval') else '-'}",
             f"WORK ORDER: {wo['id'] + ' -> ' + wo['machine'] + ', ' + (wo['part'] or 'no part') + ', ' + wo['action'] if wo else 'none'}"]
    return "\n".join(lines)


def show_state(run: dict, width: int = 88, full: bool = False) -> str:
    """The agents' state after every node -- what the next step was handed.

    full=False  one line per step, context shortened (fits four runs on a screen)
    full=True   one block per step, the WHOLE context, wrapped -- nothing cut off
    """
    import textwrap
    if full:
        out = []
        for i, h in enumerate(snapshots(run)):
            out.append(f"--- step {i}: {h['agent']}   cursor={h['cursor']}  steps={h['steps']}  "
                       f"plan={h['plan_len']} ---")
            out.append("context after this step (what the NEXT agent receives):")
            for para in (h.get("context") or "(empty)").splitlines():
                out.append(textwrap.fill(para, width, initial_indent="    ",
                                         subsequent_indent="    ") if para.strip() else "")
            out.append("")
        out.append(f"status_log: {' -> '.join(run['status_log'])}")
        return "\n".join(out)
    rows = [f"{'#':>2} {'node':9s} {'agent':14s} {'cursor':>6} {'steps':>5} {'plan':>4}  context (what the NEXT agent receives)"]
    for i, h in enumerate(snapshots(run)):
        ctx = " ".join((h.get("context") or "").split())
        ctx = textwrap.shorten(ctx, width - 48, placeholder=" ...")
        rows.append(f"{i:>2} {h['node']:9s} {h['agent']:14s} {h['cursor']!s:>6} "
                    f"{h['steps']!s:>5} {h['plan_len']:>4}  {ctx}")
    rows.append(f"status_log: {' -> '.join(run['status_log'])}")
    return "\n".join(rows)


if __name__ == "__main__":
    for rid in BY_ID:
        r = run_workflow(rid)
        print(f"{rid}: {' -> '.join(r['status_log'])}")
