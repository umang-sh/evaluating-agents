"""
Session 9 — reference-free trajectory judges.

THE ONE IDEA
------------
Session 7 built five code evaluators for trajectories. They work. They are cheap, they
are deterministic, and on the seeded matrix they catch everything they were pointed at.

They also all take a second argument:

    coord_eval7.delegation_accuracy(outputs, reference_outputs)
                                             ^^^^^^^^^^^^^^^^^
                                             the delegation row: expected_agents,
                                             expected_calls, handoff_facts

Somebody wrote that row. Twelve of them, by hand, for twelve questions. In production
there are not twelve questions, there are twelve thousand, and nobody wrote any rows.

So the question this session asks is not "code or judge". It is: **how much of what the
code does survives taking the answer key away?**

    code   trajectory + the row   ->  verdict
    judge  trajectory             ->  verdict

These three judges are the second line. They receive the question, the agent roster and
the trajectory. They never receive the row. Each one is aimed at exactly one code
evaluator, so the deck can put them side by side:

    code (has the key)                    judge (no key)          arm it must stop
    --------------------------------------------------------------------------------
    delegation_accuracy                   delegation_fit          wrong_delegation
    handoff_integrity                     handoff_sufficiency     lost_handoff
    agent_no_redundancy + no_delegation_loop  path_efficiency     redundant_call,
                                                                  delegation_loop

WHAT THEY ARE NOT SHOWN, AND WHY EACH OMISSION IS DELIBERATE
-------------------------------------------------------------
NOT the delegation row. That is the measurement; see above.

NOT the final report. A trajectory judge shown the finished answer is Session 8's judge
with a new label. It would score well on `wrong_delegation` by noticing the answer is
thin, which tells you nothing about whether it can read a path. The rendering in
`traj9.render()` has no report in it, for every caller, so this cannot drift.

NOT `plant7.FAULTS`. Session 8's rule, unchanged: hand a judge the answer key and you
have built a lookup with a latency problem.

THE ARM THIS IS EXPECTED TO FAIL, WRITTEN DOWN BEFORE THE RUN
--------------------------------------------------------------
`lost_handoff` strips the `MACHINE:`/`FAULT_CODE:` tail off the diagnostics ->
documentation payload and changes nothing else. `agent_calls` stays byte-identical to
healthy, and so does the final answer, on all twelve rows.

So `handoff_sufficiency` has to notice an ABSENCE -- a fact that is not there, with no
list of facts that should have been. Session 8 measured that exact weakness and it is in
`Session8_LiveResults.md`: the `hide_the_risk` attack fooled `recommendation_safety`
first try by DELETING the sentence stating the alarm limit. Nothing was added, nothing
was contradicted, and the certified judge waved it through.

**Prediction, recorded here before the live run: `handoff_sufficiency` will be the
DECORATION judge of this session.** `preflight9.py` check [6] tests it. If it clears,
suspect the measurer before celebrating -- the most likely explanation for a surprising
pass is that the arm leaked somewhere it should not have.

RUBRIC SCALE, AND WHY IT IS SESSION 8'S
----------------------------------------
Ternary, identical to `judge8.VERDICTS`: SOUND / UNSOUND / INSUFFICIENT-EVIDENCE ->
1 / 0 / None. Same words, same parser, same `agree8` machinery, same `None`-means-skip
convention as `coord_eval7`. Nothing here re-implements anything in `judge8.py`; the
parser in particular survived three providers and harness bug #11 and is imported, not
copied.
"""

from __future__ import annotations

import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first

import re
from collections import Counter

import judge8
import traj9

__version__ = "s9-2026-09-20a"

# Session 8's scale and parser, imported rather than restated. If these ever need to
# differ, that is a decision with a reason, not a copy-paste.
VERDICTS = judge8.VERDICTS
parse_verdict = judge8.parse_verdict
_res = judge8._res

JUDGE_KEYS = ("delegation_fit", "handoff_sufficiency", "path_efficiency")

# Which arm(s) each judge is supposed to stop, and what every judge should return on
# every arm. `agree8.separation()` reads this as the answer key.
#
# THE OVERLAP CAVEAT, WHICH GOES ON THE SLIDE RATHER THAN BEING HIDDEN:
# the seeds are not orthogonal, and Session 7 ruled on this already. `wrong_delegation`
# hands "diagnose CONVEYOR" to the documentation agent, so the payload that agent
# produces is also poorer -- a `handoff_sufficiency` UNSOUND there is arguably right.
# `delegation_loop` visits agents that had nothing left to add, which is both a loop and
# an inefficiency. The key below calls ONE flaw per arm because a key has to; reality
# overlaps, and a judge that fires on an overlapping arm is counted as a false alarm
# while possibly being correct. Say it out loud; do not quietly re-score it.
TARGETS: dict[str, tuple[str, ...]] = {
    "delegation_fit": ("wrong_delegation",),
    "handoff_sufficiency": ("lost_handoff",),
    "path_efficiency": ("redundant_call", "delegation_loop"),
}

EXPECT: dict[str, dict[str, int]] = {
    arm: {k: (0 if arm in TARGETS[k] else 1) for k in JUDGE_KEYS}
    for arm in traj9.ARMS
}


# ---------------------------------------------------------------------------
# The rubrics.
# ---------------------------------------------------------------------------
_PREAMBLE = """You are reviewing how a team of maintenance agents at {plant}, {oneliner},
went about answering one engineer's request. You are reviewing THE PATH THEY TOOK, not
the answer they produced -- you are not being shown the answer.

Reply with exactly two lines and nothing else. Do not label them.

The first line is one word, and nothing else on that line:
SOUND, UNSOUND, or INSUFFICIENT-EVIDENCE.
The second line is the single fact your verdict rests on, quoted from the trajectory.

Correct reply:
    UNSOUND
    step 2 hands "diagnose CONVEYOR" to documentation, whose job is manual lookup.

SOUND                  the path is a reasonable way to have answered this request.
UNSOUND               the specific fault named in the question below is present.
INSUFFICIENT-EVIDENCE  the trajectory does not contain enough to rule either way. Use
                       this rather than guessing. It is a real answer, not a failure.

You have no test plan and no list of what the path should have been. Judge from the
request, the roster and the trajectory itself. A path that is short is not therefore
wrong: some requests need one specialist. A path that is long is not therefore thorough.

THE AGENTS AND WHAT EACH IS FOR
{roster}
"""

RUBRICS: dict[str, dict] = {
    "delegation_fit": {
        "asks": "Was each subtask given to an agent that could actually do it?",
        "body": """QUESTION
Was each subtask handed to an agent whose job covers it?

UNSOUND if: a subtask is assigned to an agent whose role does not cover that kind of
work -- for example a diagnosis handed to the documentation agent, or a manual lookup
handed to the diagnostics agent; or an agent the request plainly needed was never given
anything to do.

Not UNSOUND if: an agent was reasonably left out because the request did not need it.
Deciding that a request needs only one specialist is the planner doing its job.

TRAJECTORY
{trajectory}
""",
    },
    "handoff_sufficiency": {
        "asks": "Did each agent receive what it needed from the one before it?",
        "body": """QUESTION
Did each agent receive, in the payload handed to it, what it needed to do its subtask?

Look at what each handoff actually carries, and ask whether the receiving agent could
have done the job it was assigned with only that in hand.

UNSOUND if: a payload omits a conclusion the sending agent had clearly reached and the
receiver needed -- for example the receiver is asked to find the procedure for a fault,
but the payload it was handed never names the fault or the machine; or a handoff the
plan required never happened at all.

Pay attention to what is MISSING from a payload, not only to what is wrong in it. The
handoffs in this trajectory are shown in full and are not truncated.

Not UNSOUND if: a payload is merely terse, while still carrying what the receiver needed.

TRAJECTORY
{trajectory}
""",
    },
    "path_efficiency": {
        "asks": "Did the path contain invocations that added nothing?",
        "body": """QUESTION
Did any agent run when it had nothing new to contribute?

UNSOUND if: an agent was invoked twice for THE SAME subtask; or the path cycles between
agents, revisiting them with nothing new each time.

NOT UNSOUND if an agent runs more than once for DIFFERENT subtasks. A request that names
two machines needs two diagnoses, and an agent that runs twice for two different jobs has
done exactly the right amount of work. Read the subtasks in the decomposition before
calling a repeat wasteful -- the number of invocations alone does not tell you.

TRAJECTORY
{trajectory}
""",
    },
}


def build_prompt(key: str, outputs: dict) -> str:
    """The exact text a judge is sent. One place, so the notebook can print it.

    A student who cannot read the prompt cannot argue with the verdict, and arguing with
    the verdict is the hands-on.
    """
    import plant7
    spec = RUBRICS[key]
    return (_PREAMBLE.format(plant=plant7.PLANT_NAME, oneliner=plant7.PLANT_ONE_LINER,
                             roster=traj9.roster())
            + "\n" + spec["body"].format(trajectory=traj9.render(outputs)))


# ---------------------------------------------------------------------------
# The live judge.
# ---------------------------------------------------------------------------
def make_judge(key: str, chat=None):
    """An evaluator with coord_eval7's signature, backed by a model.

    The signature takes `reference_outputs` and IGNORES IT. That is not an oversight and
    it is not dead code: it is what lets a judge drop into the same harness loop as a
    code evaluator, so the two can be run over the same trajectories and compared without
    a special case anywhere. The name of the parameter is `_unused_row` so that nobody
    later "fixes" it by passing it into the prompt, which would silently end the
    experiment.
    """
    if key not in RUBRICS:
        raise KeyError(f"unknown judge {key!r}; have {sorted(RUBRICS)}")

    def judge(outputs: dict, _unused_row: dict | None = None) -> dict:
        import evalkit
        c = chat or evalkit.get_chat()
        msg = c.invoke(build_prompt(key, outputs))
        word, evidence = parse_verdict(msg.text)   # gotcha #2: .text, never .content
        return _res(key, VERDICTS[word], f"{word} — {evidence}")

    judge.__name__ = key
    judge.judge_key = key
    judge.is_stub = False
    return judge


# ---------------------------------------------------------------------------
# The stub judge. Free, deterministic, and NOT a finding about judges.
#
# Same contract as judge8's stub: it exists so the offline half of the pre-flight can
# check the plumbing -- do the arms differ, do verdicts parse, do records carry a phase,
# does the gate arithmetic refuse a zero-width interval -- with no key and no spend.
#
# It is stamped is_stub=True and `traj_bench9.save()` records how many stub verdicts a
# file contains, so no number from here can reach a slide unlabelled.
#
# SAY IT OUT LOUD WHEREVER IT RUNS: this is string matching. Fooling it is not fooling
# a model, and passing it is not passing a model.
# ---------------------------------------------------------------------------
# Which specialist a subtask belongs to, by the verb the planner used. This is the
# stub's whole "understanding" of the roster.
_OWNER = (
    ("diagnose", "diagnostics"),
    ("procedure", "documentation"),
    ("criterion", "documentation"),
    ("manual", "documentation"),
    ("recommendation", "maintenance"),
    ("recommend", "maintenance"),
)
_TAIL = re.compile(r"^(MACHINE|FAULT_CODE|SECTION|PART|ACTION)\s*:", re.MULTILINE)


def _owner_of(subtask: str) -> str | None:
    low = (subtask or "").lower()
    return next((a for word, a in _OWNER if word in low), None)


def make_stub_judge(key: str):
    def judge(outputs: dict, _unused_row: dict | None = None) -> dict:
        plan = outputs.get("plan") or []
        calls = [a for a in (outputs.get("agent_calls") or []) if a != "planner"]
        handoffs = outputs.get("handoffs") or []

        if key == "delegation_fit":
            for i, step in enumerate(plan, 1):
                want = _owner_of(step.get("subtask", ""))
                got = step.get("agent")
                if want and got and want != got:
                    return _res(key, 0, f"UNSOUND — stub: step {i} gives "
                                        f"{step.get('subtask','')!r} to {got}, "
                                        f"which is {want}'s job")
            return _res(key, 1, f"SOUND — stub: {len(plan)} step(s), each with its owner")

        if key == "handoff_sufficiency":
            # lost_handoff's fingerprint: a payload that ends without its structured
            # tail, sent by an agent whose conclusion the next one needs.
            for h in handoffs:
                if h.get("from") == "planner":
                    continue
                if not _TAIL.search(h.get("payload") or ""):
                    return _res(key, 0, f"UNSOUND — stub: the {h.get('from')} -> "
                                        f"{h.get('to')} payload carries no structured "
                                        f"tail, so {h.get('to')} was told no machine "
                                        f"or fault code")
            return _res(key, 1, f"SOUND — stub: {len(handoffs)} handoff(s), each with a tail")

        # path_efficiency. The reference-free trick, and the one worth reading:
        # an agent may legitimately run once per DISTINCT subtask it was given. The plan
        # says how many distinct jobs each agent has. No delegation row needed -- the
        # planner wrote its own intent down.
        jobs: dict[str, set] = {}
        for step in plan:
            jobs.setdefault(step.get("agent"), set()).add((step.get("subtask") or "").strip())
        ran = Counter(calls)
        for agent, n in ran.items():
            allowed = max(1, len(jobs.get(agent, {""})))
            if n > allowed:
                return _res(key, 0, f"UNSOUND — stub: {agent} ran {n}x for "
                                    f"{allowed} distinct subtask(s)")
        import coord_eval7
        looped, how = coord_eval7._has_cycle(calls)
        if looped:
            return _res(key, 0, f"UNSOUND — stub: {how}")
        return _res(key, 1, f"SOUND — stub: {len(calls)} call(s), none repeated "
                            f"for the same subtask")

    judge.__name__ = key
    judge.judge_key = key
    judge.is_stub = True
    return judge


def judges(stub: bool = False) -> tuple:
    make = make_stub_judge if stub else make_judge
    return tuple(make(k) for k in JUDGE_KEYS)


def run_all(outputs: dict, stub: bool = False) -> dict[str, dict]:
    """Every judge over one trajectory.

    COST, DERIVED RATHER THAN CLAIMED: this makes exactly len(JUDGE_KEYS) model calls
    when stub=False. Session 8's correction 8 is the reason that sentence is computed
    from the tuple and not typed: four files claimed `screen_my_attack.py` cost one call
    when it cost eight, and the run sheet budgeted a fifth of the truth.
    """
    return {j.judge_key: j(outputs, None) for j in judges(stub=stub)}


LIVE_CALLS_PER_TRAJECTORY = len(JUDGE_KEYS)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Run the trajectory judges on one path.")
    ap.add_argument("--row", default="HW-001")
    ap.add_argument("--arm", default="healthy", choices=traj9.ARMS)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--show", action="store_true",
                    help="print the trajectory the judges are reading, and exit")
    ap.add_argument("--prompt", metavar="JUDGE",
                    help="print the exact prompt this judge is sent, and exit")
    a = ap.parse_args()

    t = traj9.trajectory(a.row, a.arm)
    if a.show:
        print(traj9.render(t)); raise SystemExit(0)
    if a.prompt:
        print(build_prompt(a.prompt, t)); raise SystemExit(0)

    stub = not a.live
    print(f"judge9 {__version__}  {a.row}/{a.arm}  "
          f"({'STUB — plumbing only' if stub else 'LIVE'}; "
          f"{0 if stub else LIVE_CALLS_PER_TRAJECTORY} model call(s))\n")
    for k, v in run_all(t, stub=stub).items():
        exp = EXPECT[a.arm][k]
        mark = "." if v["score"] == exp else "X"
        print(f"  {mark} {k:22s} {str(v['score']):>5s} (key says {exp})  {v['comment']}")
