"""
Session 10 -- two reference-free judges for the tool layer.

WHAT THIS SESSION IS ACTUALLY ASKING
-------------------------------------
Session 9 asked whether a judge with no answer key could recover a code evaluator's
verdict about a PATH. Three of its four judge/arm pairs came back DECORATION, and the
one that worked was the one you could get by counting.

Session 10 goes one level down and the arithmetic is worse, not better. Tool names are
strings and arguments are structured, so almost everything here is a set operation:

    "did documentation call manual_search?"        set membership
    "were the arguments well formed?"              a schema check
    "did the result reach the answer?"             a substring search

Measured on the five arms, 22 Sep, the four code evaluators separate cleanly on every
arm they are pointed at -- +67% to +92%, every interval clear of the wobble bound. Code
wins. That is not a disappointment, it is the starting position, and any judge that
"wins" on one of those arms has demonstrated only that it can do a set operation slowly
and at a price.

So the question is narrow and it is the only one worth a model:

    Two of the five arms are CountABLE. Two are READABLE.
    Code catches the readable ones ONLY because a human wrote the row.
    Can a judge catch them with no row?

    countable   bad_machine_id     an id that is not in the knowledge base
                hallucinated_tool  a name that is not in the granted list
    readable    wrong_machine      the request says conveyor; the tool looked up
                                   the air compressor. Every argument is valid.
                dropped_lookup     the request asks whether it can wait until the
                                   weekend, and nobody checked the lead time.

THE TWO JUDGES
---------------
    tool_fit            Was each tool call the right one for what was asked?
                        Aimed at: wrong_machine, hallucinated_tool
    search_sufficiency  Did the agent stop looking before it had what it needed?
                        Aimed at: dropped_lookup

THE PREDICTION, WRITTEN DOWN BEFORE THE RUN
--------------------------------------------
Recorded here so the deck can quote it verbatim rather than paraphrasing it after the
fact, which is the direction Session 9's rule 11 says to be suspicious of.

    1. On `hallucinated_tool` and `bad_machine_id`, `tool_fit` MAY separate, and it
       will not matter. Code separates on both at +92% and +67%. A judge that agrees
       with a set operation has added nothing but latency, and the slide will say
       DECORATION even if the number is good. A positive that costs money to reproduce
       a free result is not a positive.

    2. On `wrong_machine`, `tool_fit` SHOULD separate, and this is the session's real
       test. The failure is legible from the request alone -- the engineer names a
       machine, the tool call names a different one -- and no row is needed to see it.
       `tool_arguments` catches it 10/12, but only because somebody hand-wrote
       `must_cover` for twelve rows.

    3. On `dropped_lookup`, `search_sufficiency` SHOULD separate, and it is the harder
       of the two: nothing in the trajectory is WRONG, there is simply one less of it.
       The judge has to decide from the English of the request that something is
       missing. This is the same shape as Session 9's `handoff_sufficiency`, which
       failed 0/4 -- so if this one also fails, that is a REPLICATION and a real
       finding about absence-detection, not a fourth shrug.

    4. `tool_result_used` is excluded from every seeded arm in both directions.
       The seeds inject into a SAVED trajectory whose answer is frozen, so data from an
       injected call can never appear in an answer written before the injection. On the
       first run of the gate that evaluator scored 10/12 on `wrong_machine` and it was
       measuring the injection, not the agent. Suspect the measurer first; this is what
       that looks like when it is caught in time.

WHAT THE JUDGES ARE NOT SHOWN, AND WHY EACH OMISSION IS DELIBERATE
-------------------------------------------------------------------
NOT the row from `tool_rows10.py`. That is the measurement.

NOT the final answer. A tool judge shown the finished answer is Session 8's judge with a
new label: it would score well on `dropped_lookup` by noticing the answer is thin, which
says nothing about whether it can read a tool trace. `render()` never includes it.

NOT `plant7.EQUIPMENT`, `FAULTS` or `PARTS`. Session 8's rule: hand a judge the answer
key and you have built a lookup with a latency problem. The judge is told WHICH TOOLS
EACH AGENT HOLDS, because a reviewing engineer would know that from the system design --
but never which machines exist, because that is exactly what `bad_machine_id` tests.

RUBRIC SCALE
-------------
Ternary, identical to `judge8.VERDICTS` and `judge9`: SOUND / UNSOUND /
INSUFFICIENT-EVIDENCE -> 1 / 0 / None. Same words, same parser, same `agree8` machinery,
same None-means-skip convention as every code evaluator in this course. The parser is
imported, never copied -- it survived three providers and Session 8's harness bug 11.
"""

from __future__ import annotations

import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first

import judge8
import seeds10
import stub_tools10

__version__ = "s10-2026-09-22a"

VERDICTS = judge8.VERDICTS
parse_verdict = judge8.parse_verdict
_res = judge8._res

JUDGE_KEYS = ("tool_fit", "search_sufficiency")

# Which arm each judge is supposed to stop. Read by the separation arithmetic as the
# answer key.
#
# THE OVERLAP CAVEAT, SAID OUT LOUD RATHER THAN HIDDEN, AS IN SESSION 9:
# these arms are not orthogonal either. `dropped_lookup` removes the last call, which on
# a four-call row is the parts lookup -- so a `tool_fit` UNSOUND there ("the parts tool
# was never used") is arguably correct rather than a false alarm. The key below names
# ONE judge per arm because a key has to. A judge firing on an overlapping arm is
# counted against it while possibly being right. Do not quietly re-score it afterwards.
TARGETS: dict[str, tuple[str, ...]] = {
    "tool_fit": ("wrong_machine", "hallucinated_tool"),
    "search_sufficiency": ("dropped_lookup",),
}

# Arms where a judge separating proves nothing, because code already separates for free.
# Kept as data so the deck cannot disagree with the code.
COUNTABLE_ARMS = ("bad_machine_id", "hallucinated_tool")
READABLE_ARMS = ("wrong_machine", "dropped_lookup")

EXPECT: dict[str, dict[str, int]] = {
    arm: {k: (0 if arm in TARGETS[k] else 1) for k in JUDGE_KEYS}
    for arm in seeds10.ARMS
}


def roster() -> str:
    """Who holds which tools. The judge gets this; a reviewing engineer would have it."""
    lines = []
    for agent in ("diagnostics", "documentation", "maintenance"):
        tools = ", ".join(sorted(stub_tools10.GRANTS[agent]))
        lines.append(f"  {agent:<14} may call: {tools}")
    return "\n".join(lines)


def render(question: str, calls: list[dict]) -> str:
    """The trajectory a judge is shown: the request and the tool calls. Nothing else.

    Arguments in full, never truncated -- Session 8's rule 5. Here the argument IS the
    evidence, so a truncated render would remove the thing being judged.
    """
    return (f"THE ENGINEER ASKED\n  {question}\n\n"
            f"THE TOOL CALLS THAT WERE MADE, IN ORDER\n"
            f"{stub_tools10.render(calls)}")


_PREAMBLE = """You are reviewing how a team of maintenance agents at a bottling plant went
about answering one engineer's request. You are reviewing WHICH TOOLS THEY CALLED AND
WITH WHAT -- you are not being shown the answer they produced.

Reply with exactly two lines and nothing else. Do not label them.

The first line is one word, and nothing else on that line:
SOUND, UNSOUND, or INSUFFICIENT-EVIDENCE.
The second line is the single fact your verdict rests on, quoted from the tool calls.

Correct reply:
    UNSOUND
    call 1 looks up machine_id='AIR-COMP' but the engineer asked about the conveyor.

SOUND                  the tool calls are a reasonable way to have answered this request.
UNSOUND                the specific fault described in the question below is present.
INSUFFICIENT-EVIDENCE  the tool calls do not contain enough to rule either way. Use this
                       rather than guessing. It is a real answer, not a failure.

You have no test plan and no list of what should have been called. Judge from the
request, the roster and the calls themselves. A short list of calls is not therefore
wrong: some requests need one lookup. A long list is not therefore thorough.

WHICH AGENT MAY CALL WHICH TOOL
{roster}

WHAT EACH TOOL DOES
  equipment_kb         nameplate data, duty, criticality and alarm limits for one machine
  sensor_history       the last 14 days of condition-monitoring data for one machine
  maintenance_history  past work orders for one machine, oldest first
  manual_search        searches the equipment manuals; takes a query and optionally a machine
  parts_inventory      quantity on hand, bin, lead time and cost for one part number
"""

RUBRICS: dict[str, dict] = {
    "tool_fit": {
        "asks": "Was each call the right tool, on the right thing?",
        "body": """QUESTION
Was each tool call the right tool to use, pointed at the right thing?

UNSOUND if: a call is aimed at a machine or a part the engineer did not ask about and
did not mention; or a call uses a tool that is not in the roster above at all; or a tool
is used for a job it does not do -- for example searching the manuals to find out what a
sensor is currently reading.

Not UNSOUND if: a tool is called more than once, or a tool you would not personally have
chosen was called as well as the ones you would. Extra work is not the same as wrong work.
Judge what each call is POINTED AT, not how many there are.

{trajectory}
""",
    },
    "search_sufficiency": {
        "asks": "Did they stop looking before they had what they needed?",
        "body": """QUESTION
Do these tool calls gather everything this particular request needs answered?

Read the request closely and ask what a competent engineer would have to look up before
they could answer it. Then check whether each of those lookups actually happened.

UNSOUND if: the request asks something that one of the available tools answers directly,
and that tool was never called -- for example the engineer asks whether a repair can wait
until the weekend, which is a question about lead time, and nothing ever checks the parts
store; or asks whether this is the same failure as last time, and nothing ever checks the
past work orders.

Not UNSOUND if: the calls are few but cover what was asked. A request that needs one
lookup should get one lookup.

Pay attention to what is MISSING, not only to what is present.

{trajectory}
""",
    },
}


def build_prompt(key: str, question: str, calls: list[dict]) -> str:
    """The exact text a judge is sent. One place, so the notebook can print it.

    A student who cannot read the prompt cannot argue with the verdict, and arguing with
    the verdict is the hands-on.
    """
    spec = RUBRICS[key]
    return (_PREAMBLE.format(roster=roster())
            + "\n" + spec["body"].format(trajectory=render(question, calls)))


def make_judge(key: str, chat=None):
    """An evaluator with `tool_eval10`'s signature, backed by a model.

    It takes `reference_outputs` and IGNORES it, on purpose: that is what lets a judge
    drop into the same harness loop as a code evaluator so the two can be run over the
    same runs and compared with no special case. The parameter is named `_unused_row` so
    nobody later "fixes" it by passing it into the prompt, which would silently end the
    experiment.
    """
    if key not in RUBRICS:
        raise KeyError(f"unknown judge {key!r}; have {sorted(RUBRICS)}")

    def judge(outputs: dict, _unused_row: dict | None = None) -> dict:
        import evalkit
        c = chat or evalkit.get_chat()
        prompt = build_prompt(key, outputs.get("question", ""),
                              outputs.get("tool_calls") or [])
        msg = c.invoke(prompt)
        word, evidence = parse_verdict(msg.text)   # gotcha 2: .text, never .content
        return _res(key, VERDICTS[word], f"{word} — {evidence}")

    judge.__name__ = key
    judge.judge_key = key
    judge.is_stub = False
    return judge


# ---------------------------------------------------------------------------
# The stub judge. Free, deterministic, and NOT a finding about judges.
#
# Same contract as judge8's and judge9's: it exists so the offline half of the
# pre-flight can check the plumbing -- do the arms differ, do verdicts parse, does the
# gate arithmetic refuse a zero-width interval -- with no key and no spend.
#
# SAY IT OUT LOUD WHEREVER IT RUNS: this is string matching. Fooling it is not fooling a
# model, and passing it is not passing a model.
# ---------------------------------------------------------------------------
def make_stub_judge(key: str):
    def judge(outputs: dict, _unused_row: dict | None = None) -> dict:
        calls = outputs.get("tool_calls") or []
        question = (outputs.get("question") or "").lower()

        if key == "tool_fit":
            for n, c in enumerate(calls, 1):
                if c.get("name") not in stub_tools10.TOOL_NAMES:
                    return _res(key, 0, f"UNSOUND — stub: call {n} uses "
                                        f"{c.get('name')!r}, which is not a tool")
                grant = stub_tools10.GRANTS.get(c.get("agent", ""), frozenset())
                if c.get("name") not in grant:
                    return _res(key, 0, f"UNSOUND — stub: call {n} lets "
                                        f"{c.get('agent')} use {c.get('name')}")
            return _res(key, 1, f"SOUND — stub: {len(calls)} call(s), every one a "
                                f"granted tool")

        # search_sufficiency. The stub's whole "understanding" of a request is three
        # phrase lists, one per tool that answers a specific kind of question.
        WANTS = (
            (("wait until", "lead time", "on the shelf", "in stock", "what does it cost",
              "order"), "parts_inventory"),
            (("same failure", "last september", "again", "last time", "before"),
             "maintenance_history"),
            (("criterion", "criteria", "within limits", "limit", "spec", "threshold"),
             "manual_search"),
        )
        called = {c.get("name") for c in calls}
        for phrases, tool in WANTS:
            if any(p in question for p in phrases) and tool not in called:
                hit = next(p for p in phrases if p in question)
                return _res(key, 0, f"UNSOUND — stub: the request says {hit!r}, which "
                                    f"{tool} answers, and {tool} was never called")
        return _res(key, 1, f"SOUND — stub: {len(calls)} call(s) cover what was asked")

    judge.__name__ = key
    judge.judge_key = key
    judge.is_stub = True
    return judge


def judges(stub: bool = False) -> tuple:
    make = make_stub_judge if stub else make_judge
    return tuple(make(k) for k in JUDGE_KEYS)


def run_all(outputs: dict, stub: bool = False) -> dict[str, dict]:
    """Every judge over one run.

    COST, DERIVED RATHER THAN TYPED: exactly len(JUDGE_KEYS) model calls when
    stub=False. Session 8's correction 8 and Session 9's rule 2 are both this: four
    files once claimed a cost that was a fifth of the truth because somebody typed it.
    """
    return {j.judge_key: j(outputs, None) for j in judges(stub=stub)}


LIVE_CALLS_PER_RUN = len(JUDGE_KEYS)


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Run the tool judges on one run.")
    ap.add_argument("--row", default="HW-003")
    ap.add_argument("--arm", default="healthy", choices=seeds10.ARMS)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--show", action="store_true",
                    help="print what the judges are shown, and exit")
    ap.add_argument("--prompt", metavar="JUDGE",
                    help="print the exact prompt this judge is sent, and exit")
    a = ap.parse_args()

    runs = json.loads((_path.session(7) / "runs7.json").read_text())["runs"]
    rec = next(r for r in runs if r.get("phase") == "matrix"
               and r.get("seed") == "healthy" and r.get("row_id") == a.row)
    calls = seeds10.apply(a.arm, stub_tools10.reconstruct(rec["outputs"]), {})
    out = {"question": rec["question"], "tool_calls": calls}

    if a.show:
        print(render(out["question"], calls)); raise SystemExit(0)
    if a.prompt:
        print(build_prompt(a.prompt, out["question"], calls)); raise SystemExit(0)

    stub = not a.live
    print(f"judge10 {__version__}  {a.row}/{a.arm}  "
          f"({'STUB — plumbing only' if stub else 'LIVE'}; "
          f"{0 if stub else LIVE_CALLS_PER_RUN} model call(s))\n")
    for k, v in run_all(out, stub=stub).items():
        exp = EXPECT[a.arm][k]
        mark = "." if v["score"] == exp else "X"
        print(f"  {mark} {k:20s} {str(v['score']):>5s} (key says {exp})  {v['comment']}")
