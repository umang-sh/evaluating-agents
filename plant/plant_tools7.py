"""
Session 7 — the five plant tools. Deterministic, file-backed, zero API spend.

FOUR OF THESE ARE THE SESSION 10 TOOL SET, by name and by shape:
    equipment_kb          -- Equipment Knowledge Base
    maintenance_history   -- Maintenance History Database
    manual_search         -- Equipment Manual Search
    parts_inventory       -- Spare Parts Inventory
The fifth, `sensor_history`, is the condition-monitoring feed: it is what makes
a diagnosis possible at all, and it is deliberately separate so that Session 10
can test tool SELECTION between five candidates rather than four.

WHY DETERMINISTIC
-----------------
Every failure this session teaches is a COORDINATION failure. If the tools were
non-deterministic, a wrong answer could be the tool's fault, and the evaluator
could not tell the two apart. Pinning the tools makes the agents the only
moving part. Say this out loud: it is the same reason `reasoning_effort` is
pinned at the provider floor rather than varied (Session 3).

Gotcha #6 applies: every @tool needs a real docstring, not a # comment.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from plant7 import EQUIPMENT, HISTORY, MANUAL, PARTS, SENSORS

_NOT_FOUND = "not found: check the machine id against equipment_kb"


def _j(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=False, default=str)


@tool
def equipment_kb(machine_id: str) -> str:
    """Look up a machine in the Halvard Works equipment knowledge base.

    Returns the nameplate data, duty, criticality and — where relevant — the
    how many times a damaged part would thump per turn of the shaft
    (bearing_thumps_per_turn, gear_teeth_per_turn, impeller_vanes_per_turn,
    rotor_lobes_per_turn) plus the alarm limits. Compare those figures with
    measured_thumps_per_turn from sensor_history: if they match, that part is
    the damaged one.
    """
    eq = EQUIPMENT.get(machine_id.strip().upper())
    if not eq:
        return _j({"error": _NOT_FOUND, "known_machines": list(EQUIPMENT)})
    return _j({"machine_id": machine_id.strip().upper(), **eq})


@tool
def sensor_history(machine_id: str) -> str:
    """Return the last 14 days of condition-monitoring data for a machine.

    Includes vibration RMS trend, the dominant spectral peak as a multiple of
    shaft speed, temperatures, and any process values relevant to that machine
    type (suction head, DC-bus ripple, oil pressure). A value that is flat
    across the window is not a developing fault.
    """
    s = SENSORS.get(machine_id.strip().upper())
    if not s:
        return _j({"error": _NOT_FOUND, "known_machines": list(SENSORS)})
    return _j({"machine_id": machine_id.strip().upper(), **s})


@tool
def maintenance_history(machine_id: str) -> str:
    """Return past work orders for a machine, oldest first.

    Each entry has a date, work-order number, the action taken and who did it.
    Use it to tell a first-time failure from a repeat.
    """
    h = HISTORY.get(machine_id.strip().upper())
    if h is None:
        return _j({"error": _NOT_FOUND, "known_machines": list(HISTORY)})
    return _j({"machine_id": machine_id.strip().upper(), "work_orders": h})


@tool
def manual_search(query: str, machine_id: str = "") -> str:
    """Search the Halvard Works equipment manuals.

    Pass a query describing what you need (for example 'bearing replacement'
    or 'cavitation'). Optionally pass a machine_id to restrict the search to
    that machine's manual. Returns matching sections with their section id,
    title and full text. Quote the section id in any recommendation.
    """
    q = {w for w in query.lower().split() if len(w) > 3}
    mid = machine_id.strip().upper()
    hits = []
    for sec_id, sec in MANUAL.items():
        if mid and sec["machine"] != mid:
            continue
        hay = (sec["title"] + " " + sec["text"]).lower()
        score = sum(1 for w in q if w in hay)
        if score or (mid and not q):
            hits.append((score, sec_id, sec))
    if not hits:
        return _j({"query": query, "machine_id": mid or None, "sections": [],
                   "note": "no match; try fewer or broader words"})
    hits.sort(key=lambda t: (-t[0], t[1]))
    return _j({"query": query, "machine_id": mid or None,
               "sections": [{"section": sid, "title": s["title"],
                             "machine": s["machine"], "text": s["text"]}
                            for _, sid, s in hits[:3]]})


@tool
def parts_inventory(part_no: str) -> str:
    """Check the Halvard Works spare-parts store for a part number.

    Returns quantity on hand, bin location, lead time in days and unit cost in
    EUR. A lead time matters whenever the question is about timing.
    """
    p = PARTS.get(part_no.strip().upper())
    if not p:
        return _j({"error": "part not stocked", "known_parts": list(PARTS)})
    return _j({"part_no": part_no.strip().upper(), **p})


# The per-agent tool grants. Session 10 tests selection WITHIN these sets;
# Session 7 tests whether the right agent was asked in the first place.
TOOLS_DIAGNOSTICS = [equipment_kb, sensor_history, maintenance_history]
TOOLS_DOCUMENTATION = [manual_search, equipment_kb]
TOOLS_MAINTENANCE = [parts_inventory, maintenance_history]

# The single-agent arm gets the union: same capability, one decision maker.
ALL_TOOLS = [equipment_kb, sensor_history, maintenance_history,
             manual_search, parts_inventory]

TOOL_NAMES = [t.name for t in ALL_TOOLS]

if __name__ == "__main__":
    print("tools:", ", ".join(TOOL_NAMES))
    print(equipment_kb.invoke({"machine_id": "CONVEYOR"})[:220], "...")
    print(sensor_history.invoke({"machine_id": "CONVEYOR"})[:220], "...")
    print(manual_search.invoke({"query": "bearing replacement",
                                "machine_id": "CONVEYOR"})[:220], "...")
    print(parts_inventory.invoke({"part_no": "CAP-FILLER-KIT"}))
