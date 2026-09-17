"""
SESSION 7 — THE ONE FILE YOU EDIT.

Your job: decide what must survive a handoff, and write it down as an
assertion. Then find out whether you were right.

WHAT A HANDOFF FACT IS
----------------------
When diagnostics finishes, it hands the next agent a string. A handoff fact is
a piece of text you claim MUST be in that string for the next agent to do its
job. If it is missing, the next agent is working from less than it needed --
even if it produces a confident, well-written, wrong answer.

    "diagnostics->documentation": ["BEARING-WEAR"]

reads as: whatever diagnostics said, the documentation agent's input had better
contain the string BEARING-WEAR.

THE TRAP, AND IT IS THE POINT OF THE EXERCISE
----------------------------------------------
Pick a fact that would be there ANYWAY and your assertion can never fail. If
the machine id appears in the report's prose as well as its structured tail,
asserting on the machine id proves nothing -- it survives a handoff that
dropped everything that mattered. (This is not hypothetical: row HW-012 shipped
with exactly that bug and the pre-flight caught it.)

A good handoff fact is one the SENDER produced and the receiver cannot get any
other way.

HOW TO RUN IT
-------------
    python screen_my_handoffs.py

It runs your assertions against two pipelines: a healthy one, and one where the
handoff has been deliberately broken. A useful assertion PASSES the first and
FAILS the second. An assertion that passes both is decoration. An assertion
that fails both is worse -- it is wrong about the healthy system.
"""

# The structured tail every agent ends its report with:
#   diagnostics     MACHINE: <id>        FAULT_CODE: <code>
#   documentation   SECTION: <id>
#   maintenance     PART: <no>           ACTION: <what to do>
#
# Fault codes: BEARING-WEAR bearing outer-race defect (CONVEYOR, conveyor)
#              CAVITATION cavitation (RINSE-PUMP, rinse-water pump)
#              CAPACITOR-WEAR DC-bus capacitor degradation (FILLER, filler drive)
#              IMBALANCE residual imbalance (BLOWER, air-knife blower)
#              NO-FAULT no fault found (AIR-COMP)
# Manual sections -- there are SIX, and two of them are for the same machine.
# Read the titles: only one of the two is the section a repair needs.
#   MAN-CONVEYOR-4.2  Input shaft bearing replacement      <- a procedure
#   MAN-CONVEYOR-5.0  Vibration alarm thresholds           <- a limits table
#   MAN-PUMP-6.1      Cavitation: diagnosis and correction
#   MAN-FILLER-9.3    DC-bus capacitor bank service
#   MAN-BLOWER-3.4    Balance criteria
#   MAN-AIR-2.2       Routine condition limits
#
# Assert on the section the documentation agent ACTUALLY cited, not on every
# section that mentions the machine. Asserting on one it did not cite makes
# your claim false about the healthy pipeline too -- verdict WRONG, not
# DECORATIVE, and the screener will tell you which string it could not find.

# ======================================================================
# WORKED EXAMPLE -- HW-002, which is NOT one of your rows.
# Copy the SHAPE, not the contents. Your two rows are different machines
# with different fault codes and different manual sections.
#
#     "HW-002": {                        # "The rinse-water pump is making a
#         "facts": {                     #  gravelly noise and discharge
#                                        #  pressure is down..."
#             "diagnostics->documentation": ["CAVITATION"],
#             "documentation->maintenance": ["MAN-PUMP-6.1"],
#         },
#         "predict": "catches lost_handoff, misses redundant_call",
#     },
#
# WHY THOSE TWO STRINGS
#   CAVITATION      diagnostics worked it out from the sensor data. The
#                   documentation agent has no other way to know it, so if
#                   the handoff drops it, the assertion fails. GOOD.
#   MAN-PUMP-6.1    documentation produced this section id. Maintenance
#                   cannot cite a section nobody handed it. GOOD.
#
# WHY "RINSE-PUMP" WOULD BE A BAD CHOICE
#   The machine id is in the engineer's original request and in the report's
#   prose. It survives a handoff that dropped everything that mattered, so
#   the assertion passes the healthy run AND the broken run. That verdict is
#   DECORATIVE, and it is the mistake this exercise is built to produce.
#
# RULE OF THUMB: assert on what the SENDER produced and the receiver could
# not have got any other way.
# ======================================================================

MY_HANDOFFS = {

    # ==================================================================
    # IN CLASS -- finish these two first.
    # ==================================================================

    # ------------------------------------------------------------------
    # HW-001  "The filler infeed conveyor is running hot and the vibration
    #          alarm keeps tripping. What is wrong and what do we do about it?"
    #          Path: planner -> diagnostics -> documentation -> maintenance
    #
    #          This row has TWO traps stacked, which is why almost nobody got
    #          it in one go. You can fix one and still be wrong:
    #            trap 1  the machine id is in the request AND the prose, so
    #                    asserting on it is DECORATIVE
    #            trap 2  the conveyor has TWO manual sections. Assert the one
    #                    documentation did NOT cite and you get WRONG, not
    #                    DECORATIVE -- a different verdict for a different
    #                    mistake. Read the titles at the top of this file.
    # ------------------------------------------------------------------
    "HW-001": {
        "facts": {
            # TODO 1: what must reach the documentation agent?
            "diagnostics->documentation": [],

            # TODO 2: what must reach the maintenance agent?
            "documentation->maintenance": [],
        },
        # TODO 3: before you run it -- which seeded failure do you think these
        # catch, and which do you think they will MISS? One line.
        "predict": "",
    },

    # ------------------------------------------------------------------
    # HW-003  "The filler drive keeps tripping on overcurrent at shift start.
    #          Can it wait until the planned stop?"
    #          Path: planner -> diagnostics -> documentation -> maintenance
    #          Note: this question is about TIMING. The machine has only one
    #          manual section, so only trap 1 applies here.
    # ------------------------------------------------------------------
    "HW-003": {
        "facts": {
            "diagnostics->documentation": [],
            "documentation->maintenance": [],
        },
        "predict": "",
    },

    # ==================================================================
    # HOMEWORK -- do these once both rows above say DISCRIMINATING.
    # ==================================================================

    # ------------------------------------------------------------------
    # HW-002  "The rinse-water pump is making a gravelly noise and discharge
    #          pressure is down. Do we have the parts to fix it?"
    #          This is the row worked through at the top of this file. You
    #          have the answer; the point is to run it and see the verdict
    #          the screener gives, so you know what a clean one looks like.
    # ------------------------------------------------------------------
    "HW-002": {
        "facts": {
            "diagnostics->documentation": [],
            "documentation->maintenance": [],
        },
        "predict": "",
    },

    # ------------------------------------------------------------------
    # HW-005  "Air-knife blower vibration has been sitting at 4.2 mm/s since
    #          the washdown. Do we need to re-balance it?"
    #
    #          The hard one, and the only one with no worked twin: the
    #          correct answer here is DO NOTHING. Ask what the maintenance
    #          agent must have been told in order to justify doing nothing.
    #          "Nothing is wrong" is a harder thing to hand over than "here
    #          is the fault", and that is the whole point of the row.
    # ------------------------------------------------------------------
    "HW-005": {
        "facts": {
            "diagnostics->documentation": [],
            "documentation->maintenance": [],
        },
        "predict": "",
    },
}
