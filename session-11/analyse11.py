"""
Session 11 -- state checks over the captured runs. INSTRUCTOR_ONLY.

Recomputes, from saved files only (no model, free):
  1. steps == cursor + 1 at every recorded state          (invariant)
  2. truncated: step cap hit with plan steps still undone (silent stall)
  3. machine drift: a specialist works on a machine other than the one its
     SUBTASK names (the row's machine_id when the subtask names none). Checked
     against the subtask, not the row: on a two-machine row, the CONVEYOR step
     doing BLOWER work is still "inside the row". Split into NAME (a machine's display name passed as the id --
     a tool-argument error) and HIJACK (a different machine id -- state pollution).
Stub runs have no tool calls, so for them (3) reads the machine the report
says it worked on ("history for X" / "section for X").

    python session-11/analyse11.py        # prints, writes state_checks11.json
"""
from __future__ import annotations

import _path  # noqa: F401
import json
import re

from delegation_rows7 import ROWS
from plant7 import EQUIPMENT
from intervals import rule_of_three

HERE = _path.ROOT / "session-11"
WANT = {r["id"]: set(r["machine_id"] if isinstance(r["machine_id"], list) else [r["machine_id"]])
        if r["machine_id"] else set() for r in ROWS}
NAMES = {v["name"].lower(): k for k, v in EQUIPMENT.items()}


def check(path):
    d = json.loads(path.read_text())
    runs = d["runs"]
    out = {"file": path.name, "phase": d.get("phase"), "impl": d.get("impl"),
           "n_runs": len(runs), "n_states": 0, "invariant_breaks": 0, "truncated": 0,
           "hijack": [], "name_as_id": [], "dispatches_checked": 0}
    for r in runs:
        o, row_want = r["outputs"], WANT[r["row_id"]]
        plan, di = o.get("plan") or [], 0
        out["truncated"] += bool(o["final_state"].get("truncated"))
        for h in o["state_history"]:
            out["n_states"] += 1
            out["invariant_breaks"] += h["steps"] != h["cursor"] + 1
            if h["node"] != "dispatch":
                continue
            sub = plan[di]["subtask"] if di < len(plan) else ""
            di += 1
            want = {m for m in EQUIPMENT if m in sub} or row_want
            if not want:
                continue
            if d.get("impl") == "stub":
                m = re.search(r"(?:history for|section for) ([A-Z-]+)", h["context"])
                used = [m.group(1)] if m else []
            else:
                used = [c["args"]["machine_id"] for c in h["new_tool_calls"]
                        if "machine_id" in c.get("args", {})]
            if not used:
                continue
            out["dispatches_checked"] += 1
            ev = f"{r['row_id']} rep{r['rep']} {h['agent']}: asked={sorted(want)} used={used}"
            if any(u not in EQUIPMENT and NAMES.get(u.lower()) in want for u in used):
                out["name_as_id"].append(ev)
            if any(u in EQUIPMENT and u not in want for u in used):
                out["hijack"].append(ev)
    n = out["n_runs"]
    runs_hijacked = len({e.split(":")[0] for e in out["hijack"]})
    out["runs_hijacked"] = runs_hijacked
    out["hijack_upper95_if_zero"] = rule_of_three(n) if runs_hijacked == 0 else None
    return out


if __name__ == "__main__":
    import textwrap
    res = [check(HERE / f) for f in ("runs11.json", "runs11_STUB.json") if (HERE / f).exists()]
    for o in res:
        print(f"\n{o['file']}  phase={o['phase']}  runs={o['n_runs']}  states={o['n_states']}")
        print(f"  steps==cursor+1 broken : {o['invariant_breaks']}")
        print(f"  truncated              : {o['truncated']}/{o['n_runs']}")
        print(f"  dispatches checked     : {o['dispatches_checked']}")
        print(f"  runs hijacked          : {o['runs_hijacked']}/{o['n_runs']}"
              + (f"  (95% upper bound {o['hijack_upper95_if_zero']})"
                 if o['hijack_upper95_if_zero'] is not None else ""))
        for e in o["hijack"]:
            print(textwrap.fill(e, 100, initial_indent="    HIJACK ", subsequent_indent="      "))
        for e in o["name_as_id"]:
            print(textwrap.fill(e, 100, initial_indent="    NAME   ", subsequent_indent="      "))
    (HERE / "state_checks11.json").write_text(json.dumps(res, indent=1))
