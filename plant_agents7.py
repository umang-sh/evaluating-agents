"""
Session 7 — the Halvard Works maintenance assistant.

    Planner -> Diagnostics -> Documentation -> Maintenance Recommendation

and, as the control arm nobody in the syllabus asked for, the same capability
as ONE agent holding all five tools.

THE DESIGN DECISION, STATED SO IT CAN BE ARGUED WITH
----------------------------------------------------
LangChain's own current multi-agent guidance is: "Use single agent with
middleware for most handoffs use cases -- it's simpler." The `langgraph-
supervisor` package now carries a note recommending the supervisor pattern via
tools instead. So the framework's authors would not build this. We build it
anyway, because you cannot evaluate a coordination failure you never had --
and then we measure whether it was worth it. If the single agent wins on our
data, that is the session's best finding, not its embarrassment.

HOW DELEGATION HAPPENS HERE
---------------------------
The planner is an LLM that emits a PLAN: an ordered list of (agent, subtask).
A router dispatches the steps in order. This is "orchestrator-based" in the
syllabus's sense, and it has one property that matters for evaluation: the
delegation decision is a single readable object, not something you have to
infer from which spans happened to appear.

WHAT CROSSES A BOUNDARY
-----------------------
Each agent receives exactly one `context` string -- the previous agent's
report, or the planner's brief for the first step. That is the handoff, and it
is recorded in state as {from, to, payload}. `handoff_facts` in
delegation_rows7.py is asserted against that payload, i.e. against WHAT THE
RECEIVER HEARD, not against the final answer. An answer can be right while the
pipeline was broken; Session 1 taught that for outputs, and this is the same
lesson one level up.

STRUCTURED TAILS
----------------
Every agent ends its report with machine-readable lines:
    diagnostics    FAULT_CODE: BEARING-WEAR
    documentation  SECTION: MAN-CONVEYOR-4.2
    maintenance    PART: SKF-6208
                   ACTION: replace
This is what makes the outcome grader eight lines of string matching instead
of a judge (Session 1: the cheapest grader was the one with no model in it),
and it is what makes a handoff fact assertable.

TWO IMPLEMENTATIONS, ONE GRAPH
------------------------------
  impl="llm"   real agents, real model, costs money
  impl="stub"  deterministic agents that read plant7 ground truth directly
The stub exists so that the evaluators, the seeds and `preflight7 --offline`
can be verified with no API key, no network and no spend. Session 5's lesson:
the block that must never be cut has to work when the API is down.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Literal, TypedDict

from plant7 import (EQUIPMENT, FAULTS, MANUAL, PARTS, PLANT_NAME,
                    PLANT_ONE_LINER)
from plant_tools7 import (ALL_TOOLS, TOOLS_DIAGNOSTICS, TOOLS_DOCUMENTATION,
                          TOOLS_MAINTENANCE)

__version__ = "s7-2026-09-13a"

SPECIALISTS = ("diagnostics", "documentation", "maintenance")
AGENTS = ("planner",) + SPECIALISTS

# A four-agent pipeline with a router is a place where a loop can live. Cap it.
# Session 9 will make the cap itself a teaching point; here it is a seatbelt.
MAX_STEPS = 8


# ==========================================================================
# 1.  State
# ==========================================================================
class PlantState(TypedDict, total=False):
    request: str
    plan: list[dict]           # [{"agent": ..., "subtask": ...}]
    cursor: int
    steps: int
    agent_calls: list[str]     # ordered, one entry per agent INVOCATION
    handoffs: list[dict]       # [{"from": ..., "to": ..., "payload": ...}]
    reports: list[dict]        # [{"agent": ..., "text": ...}]
    tool_calls: list[dict]     # [{"agent": ..., "name": ..., "args": {...}}]
    context: str               # what the NEXT agent will receive
    answer: str


# ==========================================================================
# 2.  Prompts
# ==========================================================================
# The agents were given a machine roster and never told what the plant is for.
# That is fine for diagnostics -- a bearing defect is a bearing defect -- but it
# is fatal for the maintenance agent, which is the one asked "can it wait until
# the planned stop?". It cannot weigh a 21-day lead time against a consequence
# it has not been told. The criticality strings carry the consequence; this
# carries the shape of the line they sit on.
PLANT_CONTEXT = f"""{PLANT_NAME} is {PLANT_ONE_LINER}.

In scope is one bottling line, Line 3, which runs in series:
  infeed (convey in and rinse) -> filling (fill and cap) -> labelling (air-knife
  dry, label, pack).
Those are positions on Line 3, not separate lines. Rinse water and plant air are
plant-wide utilities serving all of it. Nothing downstream of the filler runs
when the filler stops."""

ROSTER = "\n".join(
    f"  {mid}  {eq['name']} ({eq['type']}), {eq['line']}, {eq['criticality']}"
    for mid, eq in EQUIPMENT.items()
)

PLANNER_PROMPT = f"""You are the planner for the {PLANT_NAME} maintenance assistant.

{PLANT_CONTEXT}

You do not answer maintenance questions yourself. You decide which specialist
agents should handle the request, in what order, and what each one is being
asked to do.

The machines at this plant:
{ROSTER}

The specialists available to you:
  diagnostics    reads sensor data, the equipment knowledge base and past work
                 orders, and identifies the fault. Use it when the request asks
                 what is wrong, or whether anything is wrong.
  documentation  searches the equipment manuals and returns the relevant
                 section. Use it when a procedure, a limit or a specification
                 is needed.
  maintenance    checks the spare-parts store and recommends an action. Use it
                 when the request asks what to do, whether parts are available,
                 or how long something will take.

RULES
  1. Call only the specialists the request actually needs. Calling one that is
     not needed costs money and can produce a recommendation nobody asked for.
  1a. But do not skip documentation when the answer depends on it. If the
     request asks what to DO about a fault, or whether something is within
     limits, or how long a job takes, the manual is what settles it -- call
     documentation BEFORE maintenance. A repair recommended without the
     procedure behind it is a guess with a work order attached.
  2. Each specialist appears at most once, UNLESS the request covers more than
     one machine, in which case diagnostics may appear once per machine.
  3. If the request names a machine that does not match the knowledge base,
     trust the knowledge base and say so in the subtask.
  4. Resolve the machine id yourself and put it in every subtask. A specialist
     cannot see the original request.

Reply with JSON only, no prose, in exactly this shape:
{{"machine_ids": ["..."], "steps": [{{"agent": "diagnostics", "subtask": "..."}}]}}"""

DIAGNOSTICS_PROMPT = f"""You are the diagnostics specialist at a fictional plant.

{PLANT_CONTEXT}

Identify the fault. Method: read the equipment knowledge base for the machine's
expected "thumps per turn" figures and alarm limits, read the sensor history,
and compare the two. If the measured thumps per turn matches the figure for a
damaged part, that part is damaged. A channel that is flat across the window is
not a developing fault. Check past
work orders to tell a repeat failure from a first occurrence.

Be willing to conclude that nothing is wrong. If every channel is within limits
and not trending, the fault code is NO-FAULT.

Fault codes you may use, exactly as written:
  BEARING-WEAR     a worn bearing
  CAVITATION       a pump starved of suction, boiling its own liquid
  CAPACITOR-WEAR   a drive whose power smoothing has aged
  IMBALANCE        a rotor slightly out of balance, steady and harmless
  NO-FAULT         nothing wrong

Write at most six sentences, stating the evidence you compared. Then end with
exactly these two lines:
MACHINE: <machine id>
FAULT_CODE: <code>"""

DOCUMENTATION_PROMPT = f"""You are the documentation specialist at a fictional plant.

{PLANT_CONTEXT}

Find the manual section that the situation described to you calls for, and
quote what matters from it. If you are told a fault code, look up the procedure
or criterion for that fault. If you are asked for a specification, return the
specification.

Do not diagnose, and do not recommend work. Report what the manual says.

Write at most six sentences. Then end with exactly this line:
SECTION: <section id, or NONE>"""

MAINTENANCE_PROMPT = f"""You are the maintenance recommendation specialist at a
fictional plant.

{PLANT_CONTEXT}

Decide what should be done, using what you were told and the spare-parts store.
If a part is needed, check it: quantity on hand, lead time and cost all change
the recommendation, and a question about timing cannot be answered without the
lead time.

Recommending work that the evidence does not support is a failure, not
caution. If what you were told says the machine is within limits or that no
intervention is required, the action is `monitor` or `none`, and you say so.

Write at most six sentences. Then end with exactly these two lines:
PART: <part number, or NONE>
ACTION: <one of: replace | restore suction | replace at next planned stop | monitor | none>"""

SINGLE_PROMPT = f"""You are the {PLANT_NAME} maintenance assistant. You handle
the whole request yourself, using the tools available.

{PLANT_CONTEXT}

The machines at this plant:
{ROSTER}

Method: identify the fault by comparing the equipment knowledge base's
expected thumps-per-turn figures and alarm limits against the sensor history;
consult the manual when a procedure, limit or specification is needed; check
the spare-parts store when a part, a cost or a lead time matters. Use only the
tools the request actually needs.

Be willing to conclude that nothing is wrong, and do not recommend work the
evidence does not support. Write NONE for any line that does not apply, and
`none` for ACTION when no work is warranted. A line you filled in because the
format asked for it is a recommendation nobody asked for.

(The pipeline can decline to answer a line by simply not running the agent that
would have written it. This paragraph is what gives the single agent the same
option -- without it the comparison measures the prompt, not the architecture.)

Fault codes, exactly as written: BEARING-WEAR (a worn bearing), CAVITATION (a
pump starved of suction), CAPACITOR-WEAR (a drive whose power smoothing has
aged), IMBALANCE (a rotor slightly out of balance, steady and harmless),
NO-FAULT (nothing wrong).

Answer in at most eight sentences, then end with exactly these lines:
MACHINE: <machine id>
FAULT_CODE: <code, or NONE>
SECTION: <section id, or NONE>
PART: <part number, or NONE>
ACTION: <one of: replace | restore suction | replace at next planned stop | monitor | none>"""

PROMPTS = {
    "diagnostics": DIAGNOSTICS_PROMPT,
    "documentation": DOCUMENTATION_PROMPT,
    "maintenance": MAINTENANCE_PROMPT,
}
TOOLSETS = {
    "diagnostics": TOOLS_DIAGNOSTICS,
    "documentation": TOOLS_DOCUMENTATION,
    "maintenance": TOOLS_MAINTENANCE,
}


# ==========================================================================
# 3.  Reading a structured tail
# ==========================================================================
TAIL_KEYS = ("MACHINE", "FAULT_CODE", "SECTION", "PART", "ACTION")


def read_tail(text: str) -> dict[str, str]:
    """Pull the structured tail lines out of an agent report.

    Deliberately forgiving about surrounding markdown and case, and
    deliberately unforgiving about the key names: an agent that invents its own
    field name has not followed the contract, and the grader should notice.
    """
    out: dict[str, str] = {}
    for key in TAIL_KEYS:
        m = re.findall(rf"^\W*{key}\s*:\s*(.+?)\s*$", text or "", re.M | re.I)
        if m:
            val = m[-1].strip().strip("`*_ ")
            out[key] = "" if val.upper() in ("NONE", "N/A", "-") else val
    return out


# ==========================================================================
# 4.  The stub implementation -- no model, no key, no spend
# ==========================================================================
def _fault_for(machine_id: str) -> dict:
    for code, f in FAULTS.items():
        if f["machine"] == machine_id:
            return {"code": code, **f}
    return {"code": "NO-FAULT", **FAULTS["NO-FAULT"]}


def _stub_planner(request: str) -> dict:
    """Route by what the request ASKS FOR, not by which machine it names."""
    r = request.lower()
    # ONE ordered, consuming pass. Longest phrase first, and each match removes
    # its span from the text before the next phrase is tried.
    #
    # There is no separate "does the id appear literally" pass any more, and
    # that is the point: once the machines are called CONVEYOR and FILLER, the
    # ids ARE ordinary words, so "the filler infeed conveyor" matched both and
    # the planner invented a second machine. The friendly names did not create
    # that bug, they made it visible -- the same collision existed as a phrase
    # collision before, and cost two rows the first time round.
    PHRASES = (
        # position on the line beats the machine it feeds
        ("filler infeed", "CONVEYOR"), ("infeed conveyor", "CONVEYOR"),
        ("infeed", "CONVEYOR"), ("conveyor", "CONVEYOR"), ("gearbox", "CONVEYOR"),
        ("bearing", "CONVEYOR"),
        # the air KNIFE is not the air COMPRESSOR
        ("air-knife", "BLOWER"), ("air knife", "BLOWER"), ("blower", "BLOWER"),
        ("fan", "BLOWER"),
        ("plant air", "AIR-COMP"), ("air-comp", "AIR-COMP"), ("compressor", "AIR-COMP"),
        ("rinse-pump", "RINSE-PUMP"), ("rinse pump", "RINSE-PUMP"),
        ("rinse", "RINSE-PUMP"), ("strainer", "RINSE-PUMP"), ("pump", "RINSE-PUMP"),
        ("capper", "FILLER"), ("filler", "FILLER"), ("capacitor", "FILLER"),
        ("dc-bus", "FILLER"), ("inverter", "FILLER"), ("drive", "FILLER"),
    )
    ids: list[str] = []
    rest = r
    for phrase, mid in PHRASES:
        if phrase in rest:
            rest = rest.replace(phrase, " ")
            if mid not in ids:
                ids.append(mid)
    if not ids:
        for mid, eq in EQUIPMENT.items():        # a position, e.g. "infeed"
            tail = eq["line"].lower().split("·")[-1].strip()
            if tail and tail in r and mid not in ids:
                ids.append(mid)
    if not ids:
        for mid, eq in EQUIPMENT.items():        # a bare line name covers all 3
            if eq["line"].lower().split("·")[0].strip() in r and mid not in ids:
                ids.append(mid)

    # Rule 3: the knowledge base wins over the words in the request. There is
    # no Line 4 at this plant, and no gearbox trips on overcurrent -- the only
    # drive is the filler and capper inverter.
    if "line 4" in r and "FILLER" not in ids:
        ids = ["FILLER"]
    ids = ids or ["CONVEYOR"]

    wants_spec = any(w in r for w in ("criterion", "criteria", "spec", "limit",
                                      "within limits", "threshold"))
    wants_parts = any(w in r for w in ("stock", "shelf", "cost", "parts", "part",
                                       "lead time", "on hand"))
    wants_diag = any(w in r for w in ("wrong", "vibrat", "noise", "trip", "hot",
                                      "worry", "failure", "fault", "same",
                                      "attention", "sort it out", "88 c",
                                      "discharge"))
    wants_action = any(w in r for w in ("what do we do", "fix", "re-balance",
                                        "rebalance", "act", "do about",
                                        "need to act", "sort it out",
                                        "attention first", "wait until"))
    just_spec = "do not need a diagnosis" in r or "just the spec" in r
    steps: list[dict] = []
    if just_spec:
        steps = [{"agent": "documentation", "subtask": f"specification for {ids[0]}"}]
    elif wants_parts and not wants_diag:
        steps = [{"agent": "maintenance", "subtask": f"stock check for {ids[0]}"}]
    else:
        for mid in ids:
            steps.append({"agent": "diagnostics", "subtask": f"diagnose {mid}"})
        if wants_spec or wants_action:
            steps.append({"agent": "documentation",
                          "subtask": f"procedure or criterion for {ids[0]}"})
        if wants_action and not wants_spec:
            steps.append({"agent": "maintenance",
                          "subtask": f"recommendation for {ids[0]}"})
    return {"machine_ids": ids, "steps": steps}


def _stub_specialist(agent: str, subtask: str, context: str) -> str:
    mid = next((m for m in EQUIPMENT if m in (subtask + " " + context)), "CONVEYOR")
    f = _fault_for(mid)
    if agent == "diagnostics":
        return (f"Compared the sensor history for {mid} against its knowledge-base "
                f"limits. {f['derivation']}.\n"
                f"MACHINE: {mid}\nFAULT_CODE: {f['code']}")
    if agent == "documentation":
        sec = f.get("manual") or next((s for s, v in MANUAL.items()
                                       if v["machine"] == mid), None)
        body = MANUAL.get(sec, {}).get("text", "")[:200] if sec else ""
        return (f"Manual section for {mid}: {body}\n"
                f"SECTION: {sec or 'NONE'}")
    part = f.get("part")
    stock = PARTS.get(part or "", {})
    action = {"BEARING-WEAR": "replace", "CAVITATION": "restore suction",
              "CAPACITOR-WEAR": "replace at next planned stop", "IMBALANCE": "monitor",
              "NO-FAULT": "none"}.get(f["code"], "none")
    # A stock question asks what is on the shelf, not what to do about it.
    if "stock check" in subtask.lower():
        action = "none"
    return (f"Checked the store for {part or 'no part'}"
            + (f": {stock.get('on_hand')} on hand, {stock.get('lead_time_days')} day "
               f"lead time." if stock else ".")
            + f"\nPART: {part or 'NONE'}\nACTION: {action}")


# ==========================================================================
# 5.  The LLM implementation
# ==========================================================================
_AGENT_CACHE: dict[str, Any] = {}


def _llm_agent(name: str):
    if name not in _AGENT_CACHE:
        from langchain.agents import create_agent
        import evalkit
        _AGENT_CACHE[name] = create_agent(
            model=evalkit.get_chat(),
            tools=TOOLSETS[name],
            system_prompt=PROMPTS[name],
        )
    return _AGENT_CACHE[name]


def _tagged(name: str) -> dict:
    """Gotcha, new in Session 7: tag the span, do not infer the agent from the
    span NAME. Every specialist here is a `create_agent` graph, so they all
    produce spans with the same default names. An evaluator that matches on
    names will silently attribute one agent's tool calls to another -- the
    same class of bug as #17, one level up."""
    return {"metadata": {"agent_name": name, "session": 7},
            "run_name": f"agent:{name}",
            "tags": [f"agent:{name}"]}


def _llm_planner(request: str) -> dict:
    import evalkit
    msg = evalkit.get_chat().invoke(
        [{"role": "system", "content": PLANNER_PROMPT},
         {"role": "user", "content": request}],
        config=_tagged("planner"),
    )
    raw = getattr(msg, "text", None) or str(msg.content)   # gotcha #2
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {"machine_ids": [], "steps": []}
    try:
        plan = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"machine_ids": [], "steps": []}
    steps = [s for s in plan.get("steps", []) if s.get("agent") in SPECIALISTS]
    return {"machine_ids": plan.get("machine_ids", []), "steps": steps}


def _llm_specialist(agent: str, subtask: str, context: str) -> tuple[str, list[dict]]:
    result = _llm_agent(agent).invoke(
        {"messages": [{"role": "user",
                       "content": f"TASK: {subtask}\n\nWHAT YOU WERE TOLD:\n{context}"}]},
        config=_tagged(agent),
    )
    import evalkit
    text = evalkit.final_text(result)
    calls = [{"agent": agent, **c} for c in evalkit.tool_calls_from_messages(
        evalkit.as_messages(result))]
    return text, calls


# ==========================================================================
# 6.  The graph
# ==========================================================================
def build_pipeline(impl: Literal["llm", "stub"] = "llm",
                   seed: Callable[[str, PlantState], PlantState] | None = None):
    """The four-agent pipeline, compiled.

    `seed` is a coordination-failure injector (see seeds7.py). It is called
    after the planner and after each specialist, and may rewrite state. That is
    how a wrong delegation, a dropped handoff, a redundant call or a loop are
    produced WITHOUT touching any agent's prompt -- so the failure is a
    property of the coordination, which is what this session evaluates.
    """
    from langgraph.graph import END, START, StateGraph

    def _seed(stage: str, state: PlantState) -> PlantState:
        return seed(stage, state) if seed else state

    def planner_node(state: PlantState) -> PlantState:
        plan = (_stub_planner if impl == "stub" else _llm_planner)(state["request"])
        brief = "\n".join(f"machine: {m}" for m in plan.get("machine_ids", []))
        out: PlantState = {
            "plan": plan.get("steps", []),
            "cursor": 0,
            "steps": 1,
            "agent_calls": ["planner"],
            "handoffs": [],
            "reports": [],
            "tool_calls": [],
            "context": brief or "no machine resolved",
        }
        return _seed("planner", {**state, **out})

    def dispatch_node(state: PlantState) -> PlantState:
        i = state.get("cursor", 0)
        plan = state.get("plan") or []
        step = plan[i]
        agent, subtask = step["agent"], step.get("subtask", "")
        sender = state["agent_calls"][-1] if state.get("agent_calls") else "planner"
        payload = state.get("context", "")

        if impl == "stub":
            text, calls = _stub_specialist(agent, subtask, payload), []
        else:
            text, calls = _llm_specialist(agent, subtask, payload)

        out: PlantState = {
            "cursor": i + 1,
            "steps": state.get("steps", 0) + 1,
            "agent_calls": state.get("agent_calls", []) + [agent],
            "handoffs": state.get("handoffs", []) + [
                {"from": sender, "to": agent, "payload": payload}],
            "reports": state.get("reports", []) + [{"agent": agent, "text": text}],
            "tool_calls": state.get("tool_calls", []) + calls,
            "context": text,
        }
        return _seed(agent, {**state, **out})

    def finish_node(state: PlantState) -> PlantState:
        # Deterministic synthesis. A synthesiser LLM here would be a fifth
        # agent and a fifth confound; the reports already carry the tails.
        body = "\n\n".join(f"[{r['agent']}]\n{r['text']}" for r in state.get("reports", []))
        return {**state, "answer": body or "no specialist produced a report"}

    def route(state: PlantState) -> str:
        if state.get("steps", 0) >= MAX_STEPS:
            return "finish"
        return "dispatch" if state.get("cursor", 0) < len(state.get("plan") or []) else "finish"

    g = StateGraph(PlantState)
    g.add_node("planner", planner_node)
    g.add_node("dispatch", dispatch_node)
    g.add_node("finish", finish_node)
    g.add_edge(START, "planner")
    g.add_conditional_edges("planner", route, {"dispatch": "dispatch", "finish": "finish"})
    g.add_conditional_edges("dispatch", route, {"dispatch": "dispatch", "finish": "finish"})
    g.add_edge("finish", END)
    return g.compile()


def build_single(impl: Literal["llm", "stub"] = "llm"):
    """The control arm: one agent, all five tools, same capability.

    It has no delegation to get wrong. That is the point, and it is a slide:
    every coordination evaluator in this session scores it vacuously, because
    there is no coordination. What is left to compare is the answer and the
    bill.
    """
    if impl == "stub":
        return None
    from langchain.agents import create_agent
    import evalkit
    return create_agent(model=evalkit.get_chat(), tools=ALL_TOOLS,
                        system_prompt=SINGLE_PROMPT)


# ==========================================================================
# 7.  Targets -- one call shape for both arms
# ==========================================================================
def run_pipeline(request: str, impl: str = "llm", seed=None) -> dict:
    graph = build_pipeline(impl=impl, seed=seed)
    state = graph.invoke({"request": request}, config={"metadata": {"arm": "pipeline"}})
    tails: dict[str, str] = {}
    for r in state.get("reports", []):
        tails.update(read_tail(r["text"]))
    return {
        "arm": "pipeline",
        "answer": state.get("answer", ""),
        "agent_calls": state.get("agent_calls", []),
        "handoffs": state.get("handoffs", []),
        "reports": state.get("reports", []),
        "tool_calls": state.get("tool_calls", []),
        "plan": state.get("plan", []),
        "tail": tails,
    }


def run_single(request: str, impl: str = "llm") -> dict:
    if impl == "stub":
        plan = _stub_planner(request)
        mid = (plan["machine_ids"] or ["CONVEYOR"])[0]
        text = "\n\n".join(_stub_specialist(a, f"handle {mid}", f"machine: {mid}")
                           for a in SPECIALISTS)
        return {"arm": "single", "answer": text, "agent_calls": ["single"],
                "handoffs": [], "reports": [{"agent": "single", "text": text}],
                "tool_calls": [], "plan": [], "tail": read_tail(text)}
    import evalkit
    agent = build_single("llm")
    result = agent.invoke({"messages": [{"role": "user", "content": request}]},
                          config={"metadata": {"arm": "single", "agent_name": "single",
                                               "session": 7},
                                  "run_name": "agent:single"})
    text = evalkit.final_text(result)
    calls = [{"agent": "single", **c} for c in evalkit.tool_calls_from_messages(
        evalkit.as_messages(result))]
    return {"arm": "single", "answer": text, "agent_calls": ["single"],
            "handoffs": [], "reports": [{"agent": "single", "text": text}],
            "tool_calls": calls, "plan": [], "tail": read_tail(text)}


if __name__ == "__main__":
    from delegation_rows7 import ROWS
    print(f"{PLANT_NAME} pipeline, impl=stub, {len(ROWS)} rows\n")
    for row in ROWS:
        out = run_pipeline(row["request"], impl="stub")
        got = " -> ".join(out["agent_calls"])
        want = " -> ".join(row["expected_agents"])
        mark = "ok " if got == want else "DIFF"
        print(f"{mark} {row['id']}  got:  {got}")
        if mark == "DIFF":
            print(f"      want: {want}")
