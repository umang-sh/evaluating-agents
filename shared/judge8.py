"""
Session 8 — LLM-as-a-Judge evaluators for Halvard Works.

WHAT IS NEW HERE, AND WHAT IS NOT
---------------------------------
NOT new: the class has had a judge since Session 4. `evalkit.make_groundedness_judge`
ships, it was taught, and its own docstring says rubrics, position bias, verbosity bias
and self-preference are Session 8's job. Do not open this session by introducing the
idea of a judge. Open it by asking who checked the one we already have.

New: four judges, a ternary rubric, and -- the point of the whole session -- a
measurement of whether any of them can tell two things apart by more than they
disagree with themselves.

WHERE THESE FIRE, AND WHY IT IS NOT WHERE YOU EXPECT
----------------------------------------------------
Session 7 measured pipeline vs single at outcome_match -4% [-52, +43]. That interval
is enormous. A judge aimed at it cannot resolve it -- no judge can resolve a
difference wider than the plus-or-minus of the thing it is judging, and pretending
otherwise is this session's own spine used against it.

So the judges are NOT aimed at the tie. They are aimed at the NULLS.

    coord_eval7.delegation_accuracy(single arm)  -> None   "not applicable"
    coord_eval7.handoff_integrity(single arm)    -> None
    coord_eval7.agent_no_redundancy(single arm)  -> None
    coord_eval7.no_delegation_loop(single arm)   -> None

Four columns of nothing. A coordination evaluator MUST skip one agent -- scoring a
bicycle on an emissions test is not a finding. But that leaves the single arm
unjudged on everything except a keyword match on its tail.

These four judges score one agent and four agents ON THE SAME SCALE, because they ask
about the reasoning in the report, not about the org chart that produced it. That is
the capability code in this course does not have.

THE RUBRIC IS TERNARY, NOT 1-5
-------------------------------
    SOUND                  -> 1
    UNSOUND                -> 0
    INSUFFICIENT-EVIDENCE  -> None      (skipped, exactly like coord_eval7's _NA)

Session 6 established that a number without a spread is not a measurement. A 1-5 mean
over three repetitions is noise wearing a decimal point, and nothing in this course can
defend it. A ternary verdict, by contrast, drops straight into `paired.py`, into
Session 5's rule-of-three bound, and into the `None`-means-skip convention every
evaluator here already uses.

INSUFFICIENT-EVIDENCE is load-bearing and is not a cop-out. It is the honest answer
when the report does not contain enough to judge, and a judge that never returns it is
a judge that is guessing. Its rate is reported on the slide next to the other two.

EVERY VERDICT MUST NAME ITS EVIDENCE
------------------------------------
Line 1 is the verdict word. Line 2 names the single fact the verdict rests on. A
verdict with no evidence line is parsed as INSUFFICIENT-EVIDENCE and counted -- not
silently dropped. The hands-on attacks exactly this join: a report that supplies a
plausible-looking evidence line the judge will repeat back.

WHAT THE JUDGE IS AND IS NOT GIVEN
-----------------------------------
Given: the report text, and the plant's PUBLIC reference data for the machine (the
equipment record, the manual index, the parts list). That is what a reviewing engineer
would have on their desk.

NOT given: `plant7.FAULTS[code]`, which contains the correct derivation and the correct
manual section. Hand a judge the answer key and you have not built a judge, you have
built a lookup with a latency problem -- and it will score 100% on the seeded set for
a reason that teaches nothing.
"""

from __future__ import annotations


import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first
import re

import plant7

__version__ = "s8-2026-09-17a"   # parser fix: a labelled verdict is a verdict (harness bug #11)

# ---------------------------------------------------------------------------
# The ternary scale. One place, so the deck, the notebook and the pre-flight
# cannot disagree about what a word is worth.
# ---------------------------------------------------------------------------
VERDICTS: dict[str, int | None] = {
    "SOUND": 1,
    "UNSOUND": 0,
    "INSUFFICIENT-EVIDENCE": None,
}
VERDICT_WORDS = tuple(VERDICTS)

JUDGE_KEYS = ("diagnosis_soundness", "doc_relevance",
              "recommendation_safety", "workflow_coherence")


def _res(key: str, score, comment: str) -> dict:
    """coord_eval7's result shape, unchanged, so these plug into bench7."""
    return {"key": key, "score": score, "comment": comment}


# ---------------------------------------------------------------------------
# Reading a multi-agent answer back apart.
#
# run_pipeline joins the specialist reports as "[diagnostics]\n...\n[documentation]..."
# The single arm produces one unlabelled blob. Both are handled, and the single
# arm's blob is offered to every judge -- that is the whole point of decision #1.
# ---------------------------------------------------------------------------
_HEAD = re.compile(r"^\[(\w+)\]\s*$", re.MULTILINE)


def split_reports(answer: str) -> dict[str, str]:
    """agent -> its report text. A single-agent answer comes back as {'single': ...}."""
    answer = answer or ""
    heads = list(_HEAD.finditer(answer))
    if not heads:
        return {"single": answer.strip()} if answer.strip() else {}
    out: dict[str, str] = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(answer)
        out[m.group(1)] = answer[m.end():end].strip()
    return out


def report_for(outputs: dict, agent: str) -> str:
    """The text this judge should read.

    Falls back to the single-agent blob, because a one-agent answer contains the
    diagnosis, the citation and the recommendation all in one paragraph -- which is
    exactly why a code evaluator cannot score it and a judge can.
    """
    reports = split_reports(outputs.get("answer", ""))
    if agent in reports:
        return reports[agent]
    return reports.get("single", "")


# ---------------------------------------------------------------------------
# The reference material the judge is allowed to see.
# ---------------------------------------------------------------------------
def machine_card(machine: str) -> str:
    """The public equipment record, rendered for a prompt. No fault answers in it."""
    eq = plant7.EQUIPMENT.get(machine)
    if not eq:
        return "(no equipment record for this machine)"
    lines = [f"MACHINE {machine} — {eq['name']} ({eq['type']})",
             f"  line/area: {eq.get('line', '?')}",
             f"  criticality: {eq.get('criticality', '?')}",
             f"  duty: {eq.get('duty', '?')}"]
    for k, v in eq.items():
        if k in ("name", "type", "line", "criticality", "duty", "installed"):
            continue
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def manual_index(machine: str) -> str:
    """Section ids AND their titles.

    The titles are not decoration. Session 7's hands-on listed six section ids with
    no titles, students could not tell MAN-CONVEYOR-4.2 from MAN-CONVEYOR-5.0, and
    most pairs guessed. A judge asked to rule on relevance with untitled ids would be
    guessing for the same reason -- and it would be OUR fault, not the judge's.
    """
    rows = []
    for sec, body in plant7.MANUAL.items():
        if isinstance(body, dict):
            if machine and body.get("machine") not in (machine, None):
                continue
            title = body.get("title", "")
        else:
            title = str(body)[:70]
        rows.append(f"  {sec} — {title}")
    return "\n".join(rows) or "  (no manual sections for this machine)"


def parts_index() -> str:
    return "\n".join(
        f"  {p} — {d['desc']}; on hand {d['on_hand']}, lead time {d['lead_time_days']} d"
        for p, d in plant7.PARTS.items())


# ---------------------------------------------------------------------------
# The rubrics.
#
# Each one names WHERE TO LOOK and WHAT WOULD COUNT AS UNSOUND, in the same shape
# coord_eval7 uses for code evaluators. A rubric that does not say what failing looks
# like is a vibe, and Session 4's rule -- an evaluator is a hypothesis about a
# failure -- applies to prose evaluators too.
# ---------------------------------------------------------------------------
_PREAMBLE = """You are reviewing one section of a maintenance report from an industrial
assistant at {plant}, {oneliner}.

Reply with exactly two lines and nothing else. Do not label them.

The first line is one word, and nothing else on that line:
SOUND, UNSOUND, or INSUFFICIENT-EVIDENCE.
The second line is the single fact your verdict rests on, quoted from the report
or the reference.

Correct reply:
    UNSOUND
    "suction head of 3.6 m, below the NPSHr of 4.2 m" is a pump metric, not a gearbox one.

SOUND                  the report's own stated evidence supports what it concludes.
UNSOUND                the stated evidence does not support the conclusion, contradicts
                       the reference data, or the conclusion does not follow.
INSUFFICIENT-EVIDENCE  the report does not contain enough to rule either way. Use this
                       rather than guessing. It is a real answer, not a failure.

Judge only what is asked below. Length is not quality: a long report and a short one
are judged the same way, on whether the evidence carries the conclusion.
"""

RUBRICS: dict[str, dict] = {
    "diagnosis_soundness": {
        "agent": "diagnostics",
        "asks": "Does the evidence the report states actually support the fault it names?",
        "body": """QUESTION
Does the evidence stated in this diagnosis actually support the fault it names?

UNSOUND if: the cited mechanism belongs to a different kind of machine or fault; a
number quoted does not match the equipment record; the conclusion names one fault while
the evidence describes another; or the evidence is generic and could support any fault.

REFERENCE — equipment record (this is all you get; there is no answer key)
{machine_card}

REPORT
{report}
""",
    },
    "doc_relevance": {
        "agent": "documentation",
        "asks": "Is the cited section the one that answers THIS fault?",
        "body": """QUESTION
Is the manual section this report cites the one that answers the fault under
investigation — not merely a section that belongs to the same machine?

UNSOUND if: the section cited covers a different subject from the fault described (for
example a limits/threshold table cited where a repair procedure is needed, or the
reverse); or the report cites nothing while claiming manual support.

REFERENCE — manual index (ids with titles)
{manual_index}

FAULT UNDER INVESTIGATION, as the pipeline recorded it: {fault_code}

REPORT
{report}
""",
    },
    "recommendation_safety": {
        "agent": "maintenance",
        "asks": "Is the recommended action proportionate to the risk and the stock?",
        "body": """QUESTION
Is the action this report recommends proportionate to the condition described?

UNSOUND if: it recommends continuing to run or merely monitoring a machine whose
described condition is at or past an alarm limit and trending; or it recommends
replacing or stripping a machine whose described condition is stable and within limits;
or it promises a repair using a part the stock list shows is unavailable, without
saying so.

Doing nothing is a legitimate recommendation when the evidence supports it. Judge
whether the action fits the evidence, not whether it is cautious.

REFERENCE — equipment record
{machine_card}

REFERENCE — parts
{parts_index}

REPORT
{report}
""",
    },
    "workflow_coherence": {
        "agent": "__all__",
        "asks": "Do the sections contradict each other?",
        "body": """QUESTION
Do these report sections contradict one another?

UNSOUND if: two sections name different faults, different machines, or different parts
for the same request; or the final recommendation acts on something no earlier section
established.

A section that adds detail the others did not mention is NOT a contradiction.
A one-section report cannot contradict itself: answer INSUFFICIENT-EVIDENCE only if
there is genuinely nothing to compare, and SOUND if the single section is internally
consistent.

REPORT — all sections, in the order they were produced
{report}
""",
    },
}


def build_prompt(key: str, outputs: dict, machine: str) -> str:
    spec = RUBRICS[key]
    agent = spec["agent"]
    if agent == "__all__":
        reports = split_reports(outputs.get("answer", ""))
        report = "\n\n".join(f"[{a}]\n{t}" for a, t in reports.items()) or "(empty)"
    else:
        report = report_for(outputs, agent) or "(this agent produced no report)"
    tail = outputs.get("tail") or {}
    return (_PREAMBLE.format(plant=plant7.PLANT_NAME, oneliner=plant7.PLANT_ONE_LINER)
            + "\n" + spec["body"].format(
                machine_card=machine_card(machine),
                manual_index=manual_index(machine),
                parts_index=parts_index(),
                fault_code=tail.get("FAULT_CODE") or "(none recorded)",
                report=report))


# ---------------------------------------------------------------------------
# Parsing. Strict on purpose.
# ---------------------------------------------------------------------------
# Formatting a model may add of its own accord. The prompt asks for two bare lines;
# these strip what a model puts there anyway.
#
# WHAT THIS COST, so nobody loosens it further without reading this:
# the first version of the prompt said "LINE 1: one word ..." and the first version of
# this parser required line one to START with a verdict word. The model replied
# "LINE 1: UNSOUND" -- doing exactly as told -- and all 192 live verdicts were scored
# INSUFFICIENT-EVIDENCE. The gate then reported four DECORATION judges and a NO-GO. The
# judge had been right every time; the harness threw the answer away. Harness bug #11.
#
# WHY IT IS THIS TOLERANT, which is the second lesson:
# students run three providers (COURSE_PROVIDER = anthropic | openai | google) and they
# do not format alike. One wraps the reply in a markdown fence, one bolds the verdict,
# one numbers the lines, one puts the verdict and the evidence on a single line. Every
# one of those would have scored 100% INSUFFICIENT-EVIDENCE for that student and nobody
# else -- the same silent failure as #11, but only visible to the people least able to
# diagnose it. A parser tuned on one provider is a parser that works for one provider.
#
# It is still strict about SUBSTANCE: prose with no verdict word, a number instead of a
# word, and a verdict with no evidence are all INSUFFICIENT-EVIDENCE, counted, never
# retried. Tolerant of format, strict about content.
_FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*$")
_LABEL = re.compile(
    r"^\s*(?:[*_#>\-\u2022]+\s*)*"                       # **bold**, ## head, - bullet, >
    r"(?:(?:line\s*)?(?:1|2|one|two)|verdict|answer|assessment|evidence|because|"
    r"reason(?:ing)?|justification)?"
    r"\s*[:.\)\-\u2014]*\s*", re.I)
_TRAIL = re.compile(r"[*_`\s]+$")
# A verdict and its evidence on ONE line: "SOUND - the BPFO multiple matches."
_ONELINE = re.compile(
    r"^(SOUND|UNSOUND|INSUFFICIENT[\s\-_]?EVIDENCE)\s*[\u2014\-:,.]\s*(.+)$", re.I)


def _clean(line: str) -> str:
    # _LABEL eats "**Evidence:" but leaves the closing "**", so strip stray emphasis
    # from both ends afterwards.
    out = _TRAIL.sub("", _LABEL.sub("", line, count=1))
    return out.strip(" *_`\u2014-").strip()


def _word_of(line: str) -> str | None:
    """The verdict word a line resolves to, or None. Standalone token only."""
    head = line.upper().strip(" .:*-_`\"'\u2014")
    head = head.replace("INSUFFICIENT EVIDENCE", "INSUFFICIENT-EVIDENCE")
    head = head.replace("INSUFFICIENT_EVIDENCE", "INSUFFICIENT-EVIDENCE")
    for w in VERDICT_WORDS:
        if head == w or head.startswith(w + " ") or head.startswith(w + "\u2014"):
            return w
    return next((w for w in VERDICT_WORDS if head.startswith(w)), None)


def parse_verdict(text: str) -> tuple[str, str]:
    """(verdict_word, evidence_line).

    Tolerant of formatting, strict about substance. A reply that does not resolve to one
    of the three words, or that supplies no evidence, is INSUFFICIENT-EVIDENCE -- counted,
    never dropped, never retried, because a judge that cannot answer the question is a
    measurement about the judge.
    """
    raw_lines = [ln for ln in (text or "").splitlines()]
    lines = [ln.strip() for ln in raw_lines
             if ln.strip() and not _FENCE.match(ln)]
    if not lines:
        return "INSUFFICIENT-EVIDENCE", "judge returned nothing"

    # The verdict is on one of the first three non-empty lines. More than that and the
    # model ignored the instruction, which is a finding rather than something to hunt for.
    word = None
    idx = 0
    for i, ln in enumerate(lines[:3]):
        cleaned = _clean(ln)
        w = _word_of(cleaned) or _word_of(ln)
        if w:
            word, idx, chosen = w, i, cleaned or ln
            break
    if word is None:
        return "INSUFFICIENT-EVIDENCE", f"unparseable first line: {lines[0][:120]!r}"

    # Same line? "SOUND - the BPFO multiple matches the record."
    m = _ONELINE.match(chosen)
    evidence = _clean(m.group(2)) if m else ""
    if not evidence:
        for ln in lines[idx + 1:]:
            cand = _clean(ln)
            if cand and not _word_of(cand):
                evidence = cand
                break
    if not evidence:
        return "INSUFFICIENT-EVIDENCE", f"verdict {word} with no evidence line"
    note = "" if lines[idx] == chosen and idx == 0 else " [reformatted]"
    return word, (evidence[:300] + note)


# ---------------------------------------------------------------------------
# Which machine is this run about?
#
# The tail first (it is what the pipeline actually concluded), the row second.
# Not the other way round: reading the row would hand the judge a fact the run
# did not establish, and a judge scored against facts its subject never saw is
# measuring the row, not the report.
# ---------------------------------------------------------------------------
def machine_of(outputs: dict, reference_outputs: dict | None = None) -> str:
    tail = outputs.get("tail") or {}
    m = (tail.get("MACHINE") or "").strip()
    if m in plant7.EQUIPMENT:
        return m
    ref = (reference_outputs or {}).get("machine_id")
    if isinstance(ref, (list, tuple)):
        ref = ref[0] if ref else None
    return ref if ref in plant7.EQUIPMENT else ""


# ---------------------------------------------------------------------------
# The live judge.
# ---------------------------------------------------------------------------
def make_judge(key: str, chat=None):
    """Return an evaluator with coord_eval7's signature, backed by a model.

    Uses evalkit.get_chat(), so it follows the course CHAT alias and works on all
    three providers without adding a package to a pin set forty students installed
    as homework (conventions gotcha #15).
    """
    if key not in RUBRICS:
        raise KeyError(f"unknown judge {key!r}; have {sorted(RUBRICS)}")

    def judge(outputs: dict, reference_outputs: dict | None = None) -> dict:
        import evalkit
        c = chat or evalkit.get_chat()
        machine = machine_of(outputs, reference_outputs)
        prompt = build_prompt(key, outputs, machine)
        msg = c.invoke(prompt)
        word, evidence = parse_verdict(msg.text)   # gotcha #2: .text, never .content
        return _res(key, VERDICTS[word], f"{word} — {evidence}")

    judge.__name__ = key
    judge.judge_key = key
    judge.is_stub = False
    return judge


# ---------------------------------------------------------------------------
# The stub judge. For the offline pre-flight and for CI -- NOT for the room.
#
# It is keyword matching. It exists so that six of the eight pre-flight checks can
# verify the HARNESS -- do the mutators mutate, do verdicts parse, do records carry
# a phase, do the intervals refuse to report zero width -- with no key, no network
# and no spend, exactly as Session 7 did.
#
# SAY THIS OUT LOUD WHEREVER IT IS USED: fooling a keyword matcher is not fooling a
# model. Any number produced by this stub is a test of our plumbing and is never a
# finding about judges. It is stamped is_stub=True so nothing can quietly put it on
# a slide.
# ---------------------------------------------------------------------------
# A mechanism phrase that belongs to exactly one machine. Seeing one of these on
# the wrong machine is the fingerprint the `wrong_evidence` mutator leaves.
_MECHANISM = {
    "bpfo": "CONVEYOR",
    "npshr": "RINSE-PUMP",
    "suction head": "RINSE-PUMP",
    "bus ripple": "FILLER",
    "balance grade": "BLOWER",
}
_NO_ACTION = ("none", "monitor", "no action", "")
_WORK_ACTION = ("replace", "restore", "service", "strip", "overhaul")
_REFERENCE_SECTION = ("threshold", "criteria", "limits")


def make_stub_judge(key: str):
    """Deterministic, free, and deliberately shallow."""
    def judge(outputs: dict, reference_outputs: dict | None = None) -> dict:
        spec = RUBRICS[key]
        agent = spec["agent"]
        text = (outputs.get("answer", "") if agent == "__all__"
                else report_for(outputs, agent))
        if not text.strip():
            return _res(key, None, "INSUFFICIENT-EVIDENCE — stub: no report text")
        low = text.lower()
        tail = outputs.get("tail") or {}
        machine = machine_of(outputs, reference_outputs)
        action = (tail.get("ACTION") or "").strip().lower()
        section = (tail.get("SECTION") or "").strip().upper()

        if key == "diagnosis_soundness":
            for phrase, owner in _MECHANISM.items():
                if phrase in low and machine and owner != machine:
                    return _res(key, 0, f"UNSOUND — stub: {phrase!r} belongs to {owner}, "
                                        f"not {machine}")
            return _res(key, 1, "SOUND — stub: no foreign mechanism phrase")

        if key == "doc_relevance":
            # A tail may cite several sections ("MAN-CONVEYOR-5.0, MAN-CONVEYOR-4.2").
            # Citing a limits table ALONGSIDE the procedure is good practice, so the
            # stub fires only when EVERY section cited is a reference table while a
            # work action is recommended. An earlier version read the whole comma-
            # joined string as one id, found nothing in MANUAL, and passed everything.
            cited = [c.strip().upper() for c in section.split(",") if c.strip()]
            titles = {c: (plant7.MANUAL.get(c) or {}).get("title", "") for c in cited}
            known = {c: t for c, t in titles.items() if t}
            wants_work = any(w in action for w in _WORK_ACTION)
            if known and wants_work and all(
                    any(w in t.lower() for w in _REFERENCE_SECTION) for t in known.values()):
                shown = "; ".join(f"{c} = {t!r}" for c, t in known.items())
                return _res(key, 0, f"UNSOUND — stub: only reference tables cited ({shown}) "
                                    f"but the action is {action!r}")
            return _res(key, 1, f"SOUND — stub: cited {', '.join(cited) or '(none)'}")

        if key == "recommendation_safety":
            at_limit = ("at the alarm limit" in low or "at its alarm" in low
                        or "exceeds the" in low)
            if action in _NO_ACTION and at_limit:
                return _res(key, 0, "UNSOUND — stub: no action recommended on a machine "
                                    "the report itself puts at an alarm limit")
            return _res(key, 1, f"SOUND — stub: action {action or '(none)'} not contradicted")

        # The real, un-constructed contradiction in the live HW-001 report: one
        # section puts the bearing AT the alarm limit, another says levels were
        # never stated as exceeding it.
        if ("at the alarm limit" in low
                and "weren't stated as currently exceeding" in low):
            return _res(key, 0, "UNSOUND — stub: one section puts the bearing at the "
                                "alarm limit, another says it was never stated as "
                                "exceeding it")
        parts = {p for p in plant7.PARTS if p.lower() in low}
        if len(parts) > 1:
            return _res(key, 0, "UNSOUND — stub: sections name "
                                f"{len(parts)} different parts ({', '.join(sorted(parts))})")
        return _res(key, 1, f"SOUND — stub: {len(parts)} part named across sections")

    judge.__name__ = key
    judge.judge_key = key
    judge.is_stub = True
    return judge


def judges(stub: bool = False) -> tuple:
    """All four, in the order they go on the slide: three specialists, then the
    workflow-level one that only exists because there is more than one report."""
    make = make_stub_judge if stub else make_judge
    return tuple(make(k) for k in JUDGE_KEYS)


def run_all(outputs: dict, row: dict | None = None, stub: bool = False) -> dict[str, dict]:
    return {j.judge_key: j(outputs, row) for j in judges(stub=stub)}


if __name__ == "__main__":
    import json
    import sys

    with open(_path.session(7) / "runs7.json", encoding="utf-8") as fh:
        recs = json.load(fh)["runs"]
    sample = next(r for r in recs
                  if r.get("phase") == "comparison" and r["version"] == "pipeline"
                  and r["row_id"] == "HW-001")
    use_stub = "--live" not in sys.argv
    print(f"judge8 {__version__}  ({'STUB — plumbing only' if use_stub else 'LIVE'})\n")
    for k, v in run_all(sample["outputs"], stub=use_stub).items():
        print(f"  {k:24s} {str(v['score']):>5s}  {v['comment'][:90]}")
