"""
Session 11 -- the broken workflows, and the four work orders the room votes on.

Every failure here is either SEEDED (injected on purpose, so it reproduces every time
and the agents are provably not at fault) or it is the STUB's own behaviour. None of
them was seen in the 24 live runs. Every slide that shows one says which.

    name                what is broken                               kind
    ------------------  -------------------------------------------  --------------------
    stall               two agents hand work back and forth until     seeded (agents)
                        the step cap stops them; the run still ends
                        with an answer
    hijack              an agent asked about BLOWER works on          STUB behaviour, no seed
                        CONVEYOR, because the previous report said    (the live agent: 0/24)
                        CONVEYOR
    counter_drift       the step counter is bumped twice on one       seeded (agents)
                        step, as a double-counted retry would
    skip_approval       the router jumps from the recommendation      seeded (workflow router)
                        straight to a work order
    order_after_reject  the engineer rejects, the router issues the   seeded (workflow router)
                        work order anyway
"""
from __future__ import annotations

import _path  # noqa: F401
import seeds7


def counter_drift(stage: str, state: dict) -> dict:
    """After documentation runs, `steps` goes up by one extra. Nothing else changes --
    the answer, the reports and the work order are all identical to a clean run."""
    if stage != "documentation":
        return state
    return {**state, "steps": state.get("steps", 0) + 1}


def skip_approval(stage: str, state: dict, default: str) -> str:
    return "work_order" if (stage == "agents" and default == "request_approval") else default


def order_after_reject(stage: str, state: dict, default: str) -> str:
    if stage == "engineer" and state.get("status") == "REJECTED":
        return "work_order"
    return default


# name -> how to produce it. `row` is the request it is shown on.
BROKEN = {
    "stall":              {"row": "HW-001", "plant_seed": seeds7.delegation_loop, "route_seed": None,
                           "kind": "seeded", "check": "check_finished"},
    "hijack":             {"row": "HW-006", "plant_seed": None, "route_seed": None,
                           "kind": "stub behaviour", "check": "check_machine"},
    "counter_drift":      {"row": "HW-005", "plant_seed": counter_drift, "route_seed": None,
                           "kind": "seeded", "check": "check_counters"},
    "skip_approval":      {"row": "HW-003", "plant_seed": None, "route_seed": skip_approval,
                           "kind": "seeded", "check": "check_transitions"},
    "order_after_reject": {"row": "HW-002", "plant_seed": None, "route_seed": order_after_reject,
                           "kind": "seeded", "check": "check_transitions"},
}

# The four work orders, in the order the room sees them. Three are broken.
VOTE = [
    ("Work order 1", "stall"),
    ("Work order 2", "hijack"),
    ("Work order 3", None),            # clean: HW-007
    ("Work order 4", "skip_approval"),
]
CLEAN_VOTE_ROW = "HW-007"

# Stub rows that are CLEAN. HW-006 is not: under the stub it is the hijack.
CLEAN_STUB_ROWS = ("HW-001", "HW-002", "HW-003", "HW-004", "HW-005", "HW-007",
                   "HW-008", "HW-009", "HW-010", "HW-011", "HW-012")


def run_broken(name: str, policy=None, label: str = ""):
    import workflow11 as wf
    b = BROKEN[name]
    kw = {"policy": policy} if policy else {}
    return wf.run_workflow(b["row"], plant_seed=b["plant_seed"], route_seed=b["route_seed"],
                           label=label or name, **kw)


def run_vote(policy=None):
    import workflow11 as wf
    kw = {"policy": policy} if policy else {}
    return [run_broken(n, policy, label) if n else wf.run_workflow(CLEAN_VOTE_ROW, label=label, **kw)
            for label, n in VOTE]


def live_runs(policy=None):
    """The 24 live runs of the agents, replayed through the approval workflow. Free:
    the agents are not re-run, their saved state is."""
    import json
    import workflow11 as wf
    d = json.loads((_path.ROOT / "session-11" / "runs11.json").read_text())
    kw = {"policy": policy} if policy else {}
    return [wf.run_workflow(r["row_id"], plant_out=r["outputs"],
                            label=f"live {r['row_id']} rep{r['rep']}", **kw)
            for r in d["runs"] if r.get("phase") == "state_capture"]


if __name__ == "__main__":
    import workflow11 as wf
    for run in run_vote():
        print(wf.show(run), "\n")
