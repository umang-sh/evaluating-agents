"""
Session 10 -- five tool-level failures, injected deterministically.

WHY NEW SEEDS ARE NEEDED AT ALL
--------------------------------
`plant/seeds7.py` has six injectors and every one of them works on the PLAN or on a
HANDOFF PAYLOAD -- `wrong_delegation` reassigns a step, `lost_handoff` strips a tail,
`delegation_loop` rewrites what comes next. Not one of them touches a tool call, because
in Session 7 there was nothing at the tool level to touch: `impl="stub"` returns an empty
tool-call list, and the seeds were built against the stub.

So Sessions 7, 8 and 9 have no arm in which a tool goes wrong. These five are that arm.

THE SHAPE, COPIED FROM seeds7 ON PURPOSE
-----------------------------------------
A seed is a pure function `(calls, row) -> calls`. It never touches the answer, never
touches the plan, and never touches the agents, so a fired tool evaluator is measuring
the tool layer and nothing else. Session 7's sentence, one level down: the agents are
byte-identical across all arms.

THE FIVE, AND WHAT EACH ONE IS FOR
-----------------------------------
    healthy           the control -- nothing injected
    bad_machine_id    a machine id that does not exist
    hallucinated_tool a tool name the agent was never granted
    wrong_machine     a DIFFERENT REAL machine looked up instead of the right one
    dropped_lookup    the agent stops one call short

The order above is the order they go on the slide, and it is deliberate: it runs from
the failure that is loudest to the failure that is silent.

    bad_machine_id     the tool answers with an error string and the list of real ids
    hallucinated_tool  ToolNode answers with an error ToolMessage and the list of
                       granted tools
    wrong_machine      THE TOOL ANSWERS PERFECTLY. With the wrong machine's data.
    dropped_lookup     nothing is called, so nothing can answer at all

`wrong_machine` is the one to spend time on. Nothing errors, nothing comes back empty,
every argument is well formed and every required tool was called. `tool_self_heal` sees
a clean run. `tool_selection` sees a clean run. The ONLY code evaluator that catches it
is `tool_arguments`, and it catches it solely because somebody wrote `must_cover` down
by hand. Take the row away and code has nothing left. That is the head-to-head this
session is built to run.

WHY NOT AN INVALID-PARAMETER SEED, WHICH THE SYLLABUS ASKS FOR
---------------------------------------------------------------
`bad_machine_id` IS that seed. The syllabus lists "invalid parameters" and "unavailable
tools" as separate failure modes, and at this pin they are the same failure mode wearing
two hats: both come back as a successful string return carrying the list of valid
options, neither raises, and the agent recovers from either in one extra call. Saying so
is more honest than staging two slides that show the same mechanism twice.
"""

from __future__ import annotations

import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first

from typing import Callable

from plant7 import EQUIPMENT

__version__ = "s10-2026-09-22a"

SeedFn = Callable[[list[dict], dict], list[dict]]

# A tool name that is not one of the five and is not granted to anyone. Chosen to look
# plausible, because a hallucinated tool name that looks absurd teaches nothing: the
# interesting case is the one a reviewer would skim past.
FAKE_TOOL = "vibration_api"

# The machine substituted by `wrong_machine`. A REAL machine, deliberately -- swapping in
# a fake id would just be `bad_machine_id` again, and the whole point is that this one
# comes back with perfectly good data.
SUBSTITUTE = "AIR-COMP"
_ALT = "CONVEYOR"          # used when the row's own machine IS the substitute


def _first_with_machine(calls: list[dict]) -> int | None:
    return next((i for i, c in enumerate(calls)
                 if (c.get("args") or {}).get("machine_id")), None)


def healthy(calls: list[dict], row: dict) -> list[dict]:
    """The control. Returns the calls unchanged, and exists so the arm loop has no
    special case for it -- a control that is handled by an `if` is a control that can
    drift."""
    return [dict(c) for c in calls]


def bad_machine_id(calls: list[dict], row: dict) -> list[dict]:
    """Point the first machine lookup at an asset id that does not exist.

    The tool does not raise. It returns
        {"error": "not found: check the machine id against equipment_kb",
         "known_machines": ["CONVEYOR", "RINSE-PUMP", "FILLER", "BLOWER", "AIR-COMP"]}
    -- an error AND the answer to the error, in one successful string return.
    """
    out = [dict(c) for c in calls]
    i = _first_with_machine(out)
    if i is None:
        return out
    out[i] = {**out[i], "args": {**out[i]["args"], "machine_id": "LINE4-GEARBOX"}}
    return out


def hallucinated_tool(calls: list[dict], row: dict) -> list[dict]:
    """Rename the first call to a tool nobody was granted.

    At langgraph-prebuilt 1.1.0 this does not raise either. `ToolNode._validate_tool_call`
    returns a ToolMessage with status="error" whose content is
        "Error: vibration_api is not a valid tool, try one of [...]"
    so the model is handed the list of tools it does hold and can simply call one.

    This is the syllabus's "hallucinated tool" line, and building it is the only way to
    have one: nothing in the live data happens to contain an unbound tool name.
    """
    out = [dict(c) for c in calls]
    if out:
        out[0] = {**out[0], "name": FAKE_TOOL}
    return out


def wrong_machine(calls: list[dict], row: dict) -> list[dict]:
    """Look up a different REAL machine. The quiet one.

    Every argument is well formed, the tool returns real data, nothing errors and nothing
    comes back empty. Only a hand-written `must_cover` catches it.
    """
    out = [dict(c) for c in calls]
    i = _first_with_machine(out)
    if i is None:
        return out
    current = str(out[i]["args"]["machine_id"]).strip().upper()
    other = _ALT if current == SUBSTITUTE else SUBSTITUTE
    assert other in EQUIPMENT, f"{other} must be a real machine for this seed to mean anything"

    # EVERY call that named the original machine is redirected, not just the first.
    #
    # The first version of this seed changed one call and it was the wrong experiment:
    # with the other calls still naming the right machine, `must_cover` was satisfied
    # and `tool_arguments` fired on only 2 rows of 12. That is CORRECT behaviour for a
    # row that asks "was this machine looked up at all" -- so the seed, not the
    # evaluator, was measuring the wrong thing. An agent that looks up the wrong asset
    # looks up the wrong asset throughout.
    for j, c in enumerate(out):
        if str((c.get("args") or {}).get("machine_id", "")).strip().upper() == current:
            out[j] = {**c, "args": {**c["args"], "machine_id": other}}
    return out


def dropped_lookup(calls: list[dict], row: dict) -> list[dict]:
    """Delete the LAST tool call. The agent stops one step short.

    Nothing about the remaining calls is wrong. There is simply one fewer of them, and
    whether that matters depends entirely on what the request asked for -- which is the
    question a reference-free judge has to answer and a count cannot.
    """
    return [dict(c) for c in calls[:-1]]


SEEDS: dict[str, dict] = {
    "healthy": {
        "fn": healthy,
        "designated": None,
        "one_line": "the control -- nothing injected",
    },
    "bad_machine_id": {
        "fn": bad_machine_id,
        "designated": "tool_self_heal",
        "one_line": "a machine id that does not exist; the tool hands back the real ones",
    },
    "hallucinated_tool": {
        "fn": hallucinated_tool,
        "designated": "tool_selection",
        "one_line": "a tool the agent was never granted; ToolNode hands back the granted list",
    },
    "wrong_machine": {
        "fn": wrong_machine,
        "designated": "tool_arguments",
        "one_line": "a different REAL machine looked up; the tool answers perfectly",
    },
    "dropped_lookup": {
        "fn": dropped_lookup,
        "designated": "tool_selection",
        "one_line": "the agent stops one call short",
    },
}

ARMS: tuple[str, ...] = tuple(SEEDS)
BROKEN: tuple[str, ...] = tuple(k for k in SEEDS if k != "healthy")


def get(name: str) -> SeedFn:
    if name not in SEEDS:
        raise KeyError(f"unknown seed {name!r}; known: {list(SEEDS)}")
    return SEEDS[name]["fn"]


def apply(name: str, calls: list[dict], row: dict) -> list[dict]:
    return get(name)(calls, row)


if __name__ == "__main__":
    import json

    import stub_tools10 as st

    runs = json.loads((_path.session(7) / "runs7.json").read_text())["runs"]
    rec = next(r for r in runs if r.get("phase") == "matrix"
               and r.get("seed") == "healthy" and r.get("row_id") == "HW-001")
    base = st.reconstruct(rec["outputs"])

    print(f"seeds10 {__version__}   HW-001, {len(base)} healthy call(s)\n")
    for name in ARMS:
        calls = apply(name, base, {})
        changed = [i for i in range(max(len(base), len(calls)))
                   if base[i:i + 1] != calls[i:i + 1]]
        print(f"{name:18} {SEEDS[name]['one_line']}")
        print(f"{'':18} {len(calls)} call(s); "
              f"{'identical to healthy' if not changed else f'differs at index {changed}'}")
        for i in changed:
            if i < len(calls):
                print(f"{'':18}   -> {st.render([calls[i]]).strip()}")
        print()
