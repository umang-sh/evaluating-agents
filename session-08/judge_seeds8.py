"""
Session 8 — seeded reports whose correct verdict is known by construction.

WHY SEEDING, AND WHAT IT DOES NOT BUY
-------------------------------------
Session 7 calibrated its code evaluators by breaking the pipeline on purpose, four
ways, where the right answer was known. The equivalent for a judge is a report that is
wrong on purpose -- so "did the judge get it right" has an answer that does not depend
on anybody's opinion.

Say the limitation out loud, because it is real: I wrote both the flaw AND the rubric.
A judge that catches my flaws may be catching my vocabulary. Seeding measures
SENSITIVITY. It cannot measure whether the judge is right about a report nobody
tampered with.

That is why two of the six arms are not broken at all:

    healthy   the untouched report. Every judge must say SOUND.
    padded    the same report plus 400 words of correct, irrelevant boilerplate.
              Every judge must STILL say SOUND.

Those two are the false-positive side of the matrix, and they are the half that
catches the failure this course has already made twice -- Session 2's classifier
tagging a clean control as broken, and Session 7's handoff evaluator passing 7/7 rows
vacuously and looking healthy. `padded` doubles as the verbosity-bias probe: if a
judge's verdict moves when only the word count moved, that is the bias, measured, on
our own plant, for the cost of one extra call.

MUTATORS FAIL LOUDLY
--------------------
Every mutator asserts that its anchor text was present and that the text actually
changed. A mutator that silently no-ops hands the separation check a HEALTHY report
labelled BROKEN, and the resulting number -- "the judge missed it" -- is a lie about
the judge. Session 7 caught ten harness bugs; every one was the measurer. This is the
same trap, pre-armed with an exception.

THE BASE REPORT
---------------
HW-001, pipeline arm, rep 1, from `runs7.json` phase `comparison`. A real, live,
four-agent report about a real seeded fault (BEARING-WEAR on the filler infeed
conveyor). No agent is re-run to build any of this: the whole seeded set costs zero.
"""

from __future__ import annotations

import copy
import json

import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first

__version__ = "s8-2026-09-17a"   # mutators rewritten after the first live run

# Where Session 7's saved runs live, now that the repo is organised by session.
# Session 8 calibrates against Session 7's measured output, so this is a real
# cross-session dependency and it is spelled out rather than assumed.
RUNS7 = str(_path.session(7) / "runs7.json")

BASE_ROW = "HW-001"
BASE_PHASE = "comparison"
BASE_ARM = "pipeline"
BASE_REP = 1


class MutationFailed(RuntimeError):
    """An anchor was missing, or the text did not change. Never caught silently."""


def load_base(path: str | None = None) -> dict:
    # Session 7's runs live in session-07/. Spelled out rather than assumed, because a
    # cross-session dependency should be visible in the code that has it.
    path = path or RUNS7
    with open(path, encoding="utf-8") as fh:
        recs = json.load(fh)["runs"]
    hit = [r for r in recs
           if r.get("phase") == BASE_PHASE and r.get("version") == BASE_ARM
           and r.get("row_id") == BASE_ROW and r.get("rep") == BASE_REP]
    if not hit:
        raise MutationFailed(
            f"no {BASE_ARM} {BASE_ROW} rep{BASE_REP} in phase {BASE_PHASE!r} of {path}. "
            "An unphased runs file is the Session 7 bug — do not pool phases to find one.")
    return copy.deepcopy(hit[0]["outputs"])


def _sub(text: str, old: str, new: str, what: str) -> str:
    if old not in text:
        raise MutationFailed(f"{what}: anchor not found — {old[:70]!r}")
    out = text.replace(old, new)
    if out == text:
        raise MutationFailed(f"{what}: replacement changed nothing")
    return out


# ---------------------------------------------------------------------------
# The six arms.
#
# Each returns the mutated `outputs`. Each declares, in EXPECT below, the verdict
# every judge SHOULD return -- 1 SOUND, 0 UNSOUND. Exactly one judge is targeted per
# broken arm; the other three are, in effect, three more false-positive tests.
# ---------------------------------------------------------------------------
# The live HW-001 report contains a real internal contradiction that nobody put
# there: diagnostics says bearing temperature "rose from 54->72 C (at the alarm
# limit)", and maintenance then says levels "weren't stated as currently exceeding
# ... the 72.0 C alarm threshold". Both sentences are in a report Session 7's code
# evaluators passed.
#
# The live judge FOUND IT, unprompted, and quoted both halves. My answer key called
# that a false alarm, which made `healthy` a control that is not clean and scored a
# true positive as a miss.
#
# So there are two arms now:
#   healthy          the report with that one sentence repaired -> a real control
#   real_contradiction  the report exactly as the agent produced it -> UNSOUND for
#                    workflow_coherence, and the only arm in this set whose flaw I
#                    did not write.
_REAL_CONTRADICTION = (
    "Given vibration and bearing temperature levels weren't stated as currently "
    "exceeding Zone D (7.1 mm/s) or the 72.0\u00b0C alarm threshold in what you told me, "
    "there's no evidence of imminent secondary-damage risk requiring emergency shutdown")
_REPAIRED = (
    "Bearing temperature is at the 72.0\u00b0C alarm threshold and vibration is below "
    "Zone D (7.1 mm/s), so there is no evidence of imminent secondary-damage risk "
    "requiring emergency shutdown")


def healthy(o: dict) -> dict:
    """The base report with its one REAL inconsistency repaired.

    A control arm has to be clean or it is not a control. Session 2's classifier
    tagged a clean run as broken and that was the bug; here the run was not clean
    and the answer key was the bug. Same lesson, other direction.
    """
    o = copy.deepcopy(o)
    o["answer"] = _sub(o["answer"], _REAL_CONTRADICTION, _REPAIRED, "healthy/repair")
    return o


def real_contradiction(o: dict) -> dict:
    """The report EXACTLY as the four agents produced it, untouched.

    Its flaw is not mine. This is the one arm in the set that is immune to the
    objection that a judge catching my flaws may be catching my vocabulary.
    """
    return copy.deepcopy(o)


def wrong_evidence(o: dict) -> dict:
    """Right fault code, and NO evidence that supports it.

    WHY THIS HAD TO BE REWRITTEN. The first version swapped one sentence and left
    three more sentences of genuinely correct bearing evidence standing -- the RMS
    trend, the alarm-limit temperature, the oil particle counts. The judge read
    those, said SOUND, and quoted them. It was right: most of the stated evidence
    DID support the fault. My answer key assumed one bad sentence poisons a report,
    which is not what the rubric asks, and scored a correct verdict as a miss.

    Now every bearing-specific line is replaced with pump evidence. The conclusion
    is BEARING-WEAR and nothing in the report supports it.
    """
    o = copy.deepcopy(o)
    a = _sub(o["answer"],
             "matches the input bearing's BPFO (3.19x) almost exactly, with 1x "
             "sidebands confirming a discrete race defect rather than broadband wear",
             "coincides with a suction head of 3.6 m, which is below the NPSHr of "
             "4.2 m, and the spectrum is broadband with no discrete peak",
             "wrong_evidence/derivation")
    a = _sub(a,
             "Vibration RMS climbed from 2.1\u21926.8 mm/s and bearing temperature rose "
             "from 54\u219272\u00b0C (at the alarm limit) over 14 days, with an accelerating "
             "trend in the last 4 days \u2014 consistent with a developing localized "
             "defect, not a flat/no-fault condition.",
             "Discharge pressure has fallen over 14 days while suction conditions "
             "have not recovered.",
             "wrong_evidence/trend")
    a = _sub(a,
             "Oil particle counts also increased (16/14/11 \u2192 19/17/14), corroborating "
             "metal wear debris from the bearing.",
             "The noise reported is a gravelly rattle consistent with vapour bubble "
             "collapse.",
             "wrong_evidence/oil")
    a = _sub(a, "a recurrence of an outer-race defect on the same bearing",
             "a recurrence of the same condition", "wrong_evidence/recurrence")
    o["answer"] = a
    return o


def unsafe_action(o: dict) -> dict:
    """A machine the report itself places at its alarm limit, and the advice is to watch it."""
    o = copy.deepcopy(o)
    a = _sub(o["answer"],
             "warrants scheduled replacement rather than continued monitoring alone",
             "warrants continued monitoring rather than scheduled replacement",
             "unsafe_action/stance")
    a = _sub(a,
             "Recommend performing the MAN-CONVEYOR-4.2 procedure (~4.5 hrs, two techs, "
             "drive isolated) at the next planned stop, and flag the repeat failure for "
             "root-cause investigation (alignment/lubrication) to prevent recurrence.",
             "Bearing temperature is at the alarm limit of 72.0 °C and vibration is "
             "trending up, but no secondary damage has occurred yet. Recommend leaving "
             "the gearbox in service and re-reading vibration at the next routine round "
             "in four weeks. No work order is required at this time.",
             "unsafe_action/recommendation")
    a = _sub(a, "ACTION: replace at next planned stop", "ACTION: monitor",
             "unsafe_action/tail")
    o["answer"] = a
    o["tail"] = dict(o["tail"], ACTION="monitor")
    return o


def wrong_section(o: dict) -> dict:
    """The limits TABLE cited as the basis for a replacement. The procedure is gone.

    WHY THIS HAD TO BE REWRITTEN. The first version renamed MAN-CONVEYOR-4.2 to
    MAN-CONVEYOR-5.0 throughout -- including in the sentence that quotes the
    procedure text. So the report said "MAN-CONVEYOR-5.0 specifies: isolate and
    lock out the drive, drain oil, extract the SKF-6208..." The LABEL was wrong and
    the CONTENT was still the correct repair procedure, so the judge read the
    content, said SOUND, and quoted it. Correct verdict, broken mutator: I changed
    a name and called it a wrong citation.

    Now the procedure sentence is removed outright. What is left cites only the
    vibration alarm threshold table as the documentary basis for a bearing
    replacement, which is genuinely the wrong section for the job.
    """
    o = copy.deepcopy(o)
    a = _sub(o["answer"],
             "For inspection/repair, **MAN-CONVEYOR-4.2** specifies: isolate and lock "
             "out the drive, drain oil, remove the input cover (8x M10), extract the "
             "SKF-6208 with a blind-hole puller (\"do not strike the race\"), heat the "
             "replacement bearing to 110 \u00b0C max, refill with ISO VG 320 oil, and torque "
             "cover bolts to 47 Nm, estimated at 4.5 hours with two technicians and the "
             "drive isolated.",
             "**MAN-CONVEYOR-5.0** is the applicable section for this work.",
             "wrong_section/procedure")
    a = _sub(a, "SECTION: MAN-CONVEYOR-5.0, MAN-CONVEYOR-4.2",
             "SECTION: MAN-CONVEYOR-5.0", "wrong_section/tail")
    a = a.replace("Recommend performing the MAN-CONVEYOR-4.2 procedure",
                  "Recommend performing the MAN-CONVEYOR-5.0 procedure")
    o["answer"] = a
    o["tail"] = dict(o["tail"], SECTION="MAN-CONVEYOR-5.0")
    return o


def contradiction(o: dict) -> dict:
    """Two sections, two different machines' faults, and the RECOMMENDATION acts on
    the wrong one.

    WHY THIS HAD TO BE REWRITTEN. The first version appended a sentence beginning
    "Separately, DC-bus ripple on this drive..." -- and "separately" is exactly the
    word that tells a reader it is an aside. The judge treated it as additional
    detail, which is what the rubric explicitly says is NOT a contradiction, and
    said SOUND on all three reps. A contradiction nobody has to act on is a footnote.

    Now the maintenance section orders the capacitor kit for the filler drive while
    diagnostics has diagnosed a conveyor bearing, and the tail says so.
    """
    o = copy.deepcopy(o)
    a = _sub(o["answer"],
             "Two SKF-6208 units are in stock (bin A-14, 5-day lead time if more are "
             "needed), so parts are not a constraint.",
             "The DC-bus ripple on this drive is at 5.8%, above the 3.0% limit and "
             "trending, so the capacitor bank is the item that needs replacing. "
             "CAP-FILLER-KIT is not in stock (bin D-21, 21-day lead time).",
             "contradiction/parts")
    a = _sub(a, "PART: SKF-6208", "PART: CAP-FILLER-KIT", "contradiction/tail")
    o["answer"] = a
    o["tail"] = dict(o["tail"], PART="CAP-FILLER-KIT")
    return o


_FILLER = (
    "Halvard Works operates one bottling line, Line 3, running eighteen hours a day, "
    "five days a week, with empty bottles conveyed in and rinsed, then filled and "
    "capped, then blown dry by an air knife before labelling and packing into cases. "
    "Nothing downstream of the filler runs when the filler stops. All vibration "
    "measurements referenced in this report are RMS velocity in millimetres per second, "
    "taken at the bearing housing in the radial direction, consistent with ISO 10816-3 "
    "for rigidly mounted machines in this power class. Temperatures are taken at the "
    "bearing housing surface and are not corrected for ambient. Oil cleanliness is "
    "reported to ISO 4406 in the three-number form. All work described here assumes the "
    "drive has been isolated and locked out in accordance with site procedure, that the "
    "permit to work has been raised and countersigned, and that the area has been "
    "cordoned. Spare part availability is quoted from the plant stores system as at the "
    "time of writing and should be reconfirmed before the work is scheduled, as stock "
    "is drawn down by other lines. Lead times quoted are supplier working days and "
    "exclude goods-inward inspection. Where a maintenance history is cited, it is taken "
    "from the plant record and covers the period for which that record exists; work "
    "carried out before the record began is not represented. Nothing in this report "
    "should be read as overriding the equipment manufacturer's own documentation where "
    "the two differ."
)


def padded(o: dict) -> dict:
    """The healthy report, four times longer, with nothing false added.

    Every verdict must be unchanged from `healthy`. If one moves, the judge is
    responding to length. That is the verbosity-bias measurement, and it costs one
    call per judge.
    """
    o = copy.deepcopy(o)
    out, changed = [], 0
    for block in o["answer"].split("\n\n"):
        out.append(block)
        if block.strip().startswith("[") or block.strip().endswith("."):
            if changed < 3 and len(block) > 200:
                out.append(_FILLER)
                changed += 1
    if changed == 0:
        raise MutationFailed("padded: found nowhere to pad")
    o["answer"] = "\n\n".join(out)
    if len(o["answer"]) <= len(_FILLER):
        raise MutationFailed("padded: answer did not grow")
    return o


ARMS = {
    "healthy": healthy,
    "real_contradiction": real_contradiction,
    "wrong_evidence": wrong_evidence,
    "unsafe_action": unsafe_action,
    "wrong_section": wrong_section,
    "contradiction": contradiction,
    "padded": padded,
}

# The answer key. 1 = the judge SHOULD say SOUND, 0 = SHOULD say UNSOUND.
# Read the columns, not the rows: every 1 in a broken arm's row is a
# false-positive test, and there are eighteen of them against six true positives.
EXPECT: dict[str, dict[str, int]] = {
    "healthy":        {"diagnosis_soundness": 1, "doc_relevance": 1,
                       "recommendation_safety": 1, "workflow_coherence": 1},
    # Not constructed. The agents produced this, and the judge found it.
    "real_contradiction": {"diagnosis_soundness": 1, "doc_relevance": 1,
                           "recommendation_safety": 1, "workflow_coherence": 0},
    "wrong_evidence": {"diagnosis_soundness": 0, "doc_relevance": 1,
                       "recommendation_safety": 1, "workflow_coherence": 1},
    "unsafe_action":  {"diagnosis_soundness": 1, "doc_relevance": 1,
                       "recommendation_safety": 0, "workflow_coherence": 1},
    "wrong_section":  {"diagnosis_soundness": 1, "doc_relevance": 0,
                       "recommendation_safety": 1, "workflow_coherence": 1},
    "contradiction":  {"diagnosis_soundness": 1, "doc_relevance": 1,
                       "recommendation_safety": 1, "workflow_coherence": 0},
    "padded":         {"diagnosis_soundness": 1, "doc_relevance": 1,
                       "recommendation_safety": 1, "workflow_coherence": 1},
}

BROKEN = ("wrong_evidence", "unsafe_action", "wrong_section", "contradiction",
          "real_contradiction")
CONTROLS = ("healthy", "padded")


def build(path: str | None = None) -> dict[str, dict]:
    """Every arm. Raises rather than returning a quietly unmutated report.

    THE BASE FOR A BROKEN ARM IS THE REPAIRED REPORT, NOT THE RAW ONE.
    The raw HW-001 report carries a real internal contradiction (see `healthy`).
    Building `unsafe_action` on top of it produced an arm with TWO flaws, so
    workflow_coherence fired on it and my answer key counted that as a false alarm.
    Each broken arm must carry exactly one flaw, or its own judge's separation is
    measured against noise from somebody else's.

    `real_contradiction` is the deliberate exception: it is the raw report.
    """
    raw = load_base(path)
    clean = healthy(raw)
    out = {}
    for name, fn in ARMS.items():
        if name == "healthy":
            out[name] = clean
        elif name == "real_contradiction":
            out[name] = fn(raw)
        else:
            out[name] = fn(clean)
    return out


if __name__ == "__main__":
    arms = build()
    base_len = len(arms["healthy"]["answer"])
    print(f"judge_seeds8 {__version__}   base = {BASE_ARM} {BASE_ROW} rep{BASE_REP}, "
          f"{base_len} chars\n")
    for name, o in arms.items():
        delta = len(o["answer"]) - base_len
        same = "SAME TEXT" if o["answer"] == arms["healthy"]["answer"] else ""
        if name != "healthy" and same:
            raise MutationFailed(f"{name} did not change the report")
        tgt = [k for k, v in EXPECT[name].items() if v == 0] or ["— (control)"]
        print(f"  {name:16s} {delta:+6d} chars   should fail: {', '.join(tgt)}")
