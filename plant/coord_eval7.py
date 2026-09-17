"""
Session 7 — coordination evaluators.

Session 4 said: an evaluator is a hypothesis about a failure. It says WHERE TO
LOOK and WHAT WOULD COUNT AS FAILING. These four say where to look when the
thing that went wrong is not inside any agent.

    delegation_accuracy   WHERE: the sequence of agent invocations
                          FAILS:  a forbidden agent ran, an expected agent did
                                  not, or the order was wrong
    handoff_integrity     WHERE: the payload the RECEIVER was handed
                          FAILS:  a fact the sender established is absent from
                                  what the next agent received
    agent_no_redundancy   WHERE: how many times each agent ran
                          FAILS:  more invocations than the plan needed
    no_delegation_loop    WHERE: the shape of the sequence
                          FAILS:  a cycle repeats three or more times

    outcome_match         the ordinary outcome grader, kept here so the
                          discrimination report can show that it PASSES three
                          of the four seeds -- which is the point.

TWO SHAPES, SAME QUESTION (Session 4's convention)
--------------------------------------------------
  OFFLINE  evaluator(outputs, reference_outputs) where outputs is what
           run_pipeline() returned and reference_outputs is a delegation row.
           No LangSmith round trip. This is what students iterate on.
  ONLINE   evaluator(run) walks the trace. No reference outputs exist, so only
           the row-free checks (loop, redundancy-against-plan) survive.

READ THE METADATA, NOT THE SPAN NAME
------------------------------------
Every specialist is a `create_agent` graph, so every one of them emits spans
with the same default names. `plant_agents7._tagged()` stamps
metadata.agent_name on each invocation; `agents_from_run` reads that. Matching
on names instead would attribute one agent's tool calls to another and never
raise -- the same shape as conventions gotcha #17.

Redundancy is counted against `expected_calls`, NOT against "more than one".
HW-006 covers two machines and correctly runs diagnostics twice. A redundancy
check that cannot tell those apart fires on a healthy run, which Session 2
established is the classic evaluator bug.
"""

from __future__ import annotations

from collections import Counter

__version__ = "s7-2026-09-13a"

SPECIALISTS = ("diagnostics", "documentation", "maintenance")
# Doing nothing has more than one spelling. An agent that says "monitor" and an
# agent that says "none" have made the same decision.
NO_ACTION = ("none", "monitor", "no action", "")

LOOP_REPEATS = 3          # a cycle seen this many times is a loop
LOOP_MAX_CYCLE = 3        # longest cycle we look for


def _res(key: str, score, comment: str) -> dict:
    return {"key": key, "score": score, "comment": comment}


# The single-agent arm has no coordination. Scoring it against a four-agent
# plan does not make it lose -- it makes the number meaningless: one agent
# "fails" delegation_accuracy for the same reason a bicycle fails an MOT
# emissions test. A coordination evaluator must SKIP it (score None), not fail
# it, or the comparison silently rewards the pipeline for the shape of the
# measurement rather than for anything it did.
_NA = "not applicable — one agent, so there is no coordination to get wrong"


def _single(outputs: dict) -> bool:
    return outputs.get("arm") == "single" or outputs.get("agent_calls") == ["single"]


# ==========================================================================
# OFFLINE
# ==========================================================================
def delegation_accuracy(outputs: dict, reference_outputs: dict) -> dict:
    """Did the right agents run, and in the right order?"""
    if _single(outputs):
        return _res("delegation_accuracy", None, _NA)
    got = list(outputs.get("agent_calls", []))
    want = list(reference_outputs.get("expected_agents", []))
    forbidden = set(reference_outputs.get("forbidden_agents", []))
    order = reference_outputs.get("expected_order", "strict")

    problems = []
    fired = sorted(set(got) & forbidden)
    if fired:
        problems.append(f"forbidden agent ran: {', '.join(fired)}")
    missing = sorted(set(want) - set(got))
    if missing:
        problems.append(f"expected agent never ran: {', '.join(missing)}")

    if not problems:
        if order == "strict" and got != want:
            problems.append(f"order {' -> '.join(got)} != {' -> '.join(want)}")
        elif order == "partial" and Counter(got) != Counter(want):
            problems.append("agent multiset differs from expected")

    if problems:
        return _res("delegation_accuracy", 0, "; ".join(problems))
    return _res("delegation_accuracy", 1, " -> ".join(got))


def handoff_integrity(outputs: dict, reference_outputs: dict) -> dict:
    """Did each fact survive the boundary it had to cross?

    Asserted against the payload the RECEIVER was handed. A run can pass the
    outcome grader and fail here; that is the whole reason this exists.
    """
    if _single(outputs):
        return _res("handoff_integrity", None, _NA)
    edges = reference_outputs.get("handoff_facts") or {}
    if not edges:
        return _res("handoff_integrity", 1, "no handoff facts asserted for this row")
    handoffs = outputs.get("handoffs", [])
    problems = []
    checked = 0
    for edge, facts in edges.items():
        snd, rcv = edge.split("->", 1)
        payloads = [h["payload"] for h in handoffs
                    if h.get("from") == snd and h.get("to") == rcv]
        if not payloads:
            problems.append(f"{edge}: handoff never happened")
            continue
        blob = "\n".join(payloads)
        for fact in facts:
            checked += 1
            if fact not in blob:
                problems.append(f"{edge}: '{fact}' absent from what {rcv} received")
    if problems:
        return _res("handoff_integrity", 0, "; ".join(problems))
    return _res("handoff_integrity", 1, f"{checked} fact(s) survived {len(edges)} handoff(s)")


def agent_no_redundancy(outputs: dict, reference_outputs: dict) -> dict:
    """More invocations of an agent than the row's plan calls for."""
    if _single(outputs):
        return _res("agent_no_redundancy", None, _NA)
    want = dict(reference_outputs.get("expected_calls") or {})
    got = Counter(outputs.get("agent_calls", []))
    over = {a: (got[a], want.get(a, 0)) for a in got
            if got[a] > want.get(a, 0) and a != "planner"}
    if over:
        detail = ", ".join(f"{a} ran {g}x, plan needed {w}x" for a, (g, w) in sorted(over.items()))
        return _res("agent_no_redundancy", 0, detail)
    return _res("agent_no_redundancy", 1,
                ", ".join(f"{a}x{n}" for a, n in sorted(got.items())))


def _has_cycle(seq: list[str]) -> tuple[bool, str]:
    for size in range(1, LOOP_MAX_CYCLE + 1):
        if len(seq) < size * LOOP_REPEATS:
            continue
        seen: Counter = Counter()
        for i in range(len(seq) - size + 1):
            seen[tuple(seq[i:i + size])] += 1
        for gram, n in seen.items():
            if n >= LOOP_REPEATS:
                return True, f"{' -> '.join(gram)} repeats {n}x"
    return False, ""


def no_delegation_loop(outputs: dict, reference_outputs: dict | None = None) -> dict:
    """A cycle of one to three agents repeating three or more times.

    Row-free on purpose: a loop is a loop whatever the request was, so this
    evaluator also works online, where there is no reference output at all.
    """
    if _single(outputs):
        return _res("no_delegation_loop", None, _NA)
    seq = [a for a in outputs.get("agent_calls", []) if a in SPECIALISTS]
    looped, why = _has_cycle(seq)
    if looped:
        return _res("no_delegation_loop", 0, why)
    return _res("no_delegation_loop", 1, f"{len(seq)} specialist call(s), no cycle")


def outcome_match(outputs: dict, reference_outputs: dict) -> dict:
    """The ordinary outcome grader. Kept so the discrimination report can show
    how much of a coordination failure it cannot see."""
    tail = outputs.get("tail") or {}
    exp = reference_outputs.get("expected_outcome") or {}
    problems = []
    for field, key in (("fault_code", "FAULT_CODE"), ("part", "PART"), ("action", "ACTION")):
        want = exp.get(field)
        got = (tail.get(key) or "").strip()
        if want is None:
            if got:
                problems.append(f"{field}: expected none, got {got!r}")
        elif field == "action" and want.lower() in NO_ACTION:
            # "none", "monitor" and "the agent that would have said it never
            # ran" are ONE outcome: do nothing. The first version of this check
            # accepted only "none" and rejected "monitor", so an agent that
            # correctly declined to recommend work scored zero -- 11 live runs
            # failed on exactly that. An evaluator that punishes the right
            # answer is worse than no evaluator.
            if got and got.lower() not in NO_ACTION:
                problems.append(f"{field}: expected no action, got {got!r}")
        elif want.lower() in ("none", ""):
            if got and got.lower() != "none":
                problems.append(f"{field}: expected none, got {got!r}")
        elif want.lower() not in got.lower():
            problems.append(f"{field}: expected {want!r}, got {got!r}")
    if problems:
        return _res("outcome_match", 0, "; ".join(problems))
    return _res("outcome_match", 1, "fault code, part and action all match")


OFFLINE = (delegation_accuracy, handoff_integrity, agent_no_redundancy,
           no_delegation_loop, outcome_match)
COORDINATION_ONLY = (delegation_accuracy, handoff_integrity,
                     agent_no_redundancy, no_delegation_loop)


def run_all(outputs: dict, row: dict) -> dict[str, dict]:
    return {fn.__name__: fn(outputs, row) for fn in OFFLINE}


# ==========================================================================
# ONLINE — walk a LangSmith trace
# ==========================================================================
def _meta(run) -> dict:
    extra = getattr(run, "extra", None) or {}
    return (extra.get("metadata") or {}) if isinstance(extra, dict) else {}


def agents_from_run(run, _inside: bool = False, acc: list | None = None) -> list[str]:
    """Ordered agent invocations, read from metadata.agent_name.

    Outermost only: a specialist's own internal spans inherit the tag, and
    counting them would turn one invocation into five. This is conventions
    gotcha #8 applied to agents instead of tools.
    """
    acc = [] if acc is None else acc
    name = _meta(run).get("agent_name")
    tagged = bool(name)
    if tagged and not _inside:
        acc.append(name)
    for child in (getattr(run, "child_runs", None) or []):
        agents_from_run(child, _inside or tagged, acc)
    return acc


def online_no_loop(run) -> dict:
    return no_delegation_loop({"agent_calls": agents_from_run(run)})


def online_agent_census(run) -> dict:
    """Not pass/fail — a census. Online you have no plan to compare against,
    so the honest output is a count, not a verdict. Say that out loud: half of
    what an offline evaluator can assert simply does not exist in production."""
    c = Counter(agents_from_run(run))
    return _res("agent_census", 1, ", ".join(f"{a}x{n}" for a, n in sorted(c.items())) or "none tagged")


if __name__ == "__main__":
    from delegation_rows7 import ROWS
    from plant_agents7 import run_pipeline
    import seeds7

    print(f"{'row':8s} {'seed':18s} " + " ".join(f"{f.__name__[:12]:>13s}" for f in OFFLINE))
    for row in ROWS[:3]:
        for seed in ("healthy",) + seeds7.BROKEN:
            out = run_pipeline(row["request"], impl="stub", seed=seeds7.get(seed))
            res = run_all(out, row)
            cells = " ".join(f"{('PASS' if res[f.__name__]['score'] else 'FAIL'):>13s}"
                             for f in OFFLINE)
            print(f"{row['id']:8s} {seed:18s} {cells}")
        print()
