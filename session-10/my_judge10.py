"""
HOMEWORK. The one file you edit.

WHAT HAPPENED IN CLASS
-----------------------
We ran two judges against twenty runs. One of them, `search_sufficiency`, called
FOUR OUT OF FOUR clean runs unsound. Most of the time for the same reason: the run
never called `maintenance_history`, so past work orders were never checked.

It is not a stupid objection. "You diagnosed a recurring fault and never looked at
the history" is a fair thing for an engineer to say. It is just a STRICTER standard
than our answer key uses -- and a check that calls three-quarters of everything
broken cannot tell good runs from bad ones, because it says everything is bad.

YOUR JOB
--------
Make it stop crying wolf, WITHOUT making it useless.

    1. Rewrite the rubric below so it stops firing on clean runs.
    2. Re-run it. Count how many clean runs it still fires on.
    3. Count whether it still catches the arm it is supposed to catch.

The trap is in step 3, and you should expect to fall into it once. The easiest way
to stop a check false-alarming is to make it lenient -- and a lenient check catches
nothing. Both numbers go on the form. We are going to plot the class.

HOW TO RUN IT
-------------
    python session-10/screen_my_judge.py --offline    # free, no key, plumbing only
    python session-10/screen_my_judge.py --show       # print the exact prompt
    python session-10/screen_my_judge.py --live       # 20 model calls on YOUR key

`--live` prints the cost before it spends anything and asks you to confirm.
Twenty calls. Run it twice at most; you do not need more than that.

WHAT YOU MAY AND MAY NOT CHANGE
--------------------------------
You may rewrite RUBRIC completely. Add rules, remove rules, change the examples.

You may NOT show the judge the answer key. No list of which tools each question
needs, no `must_call`, no naming HW-003 or any other row. The whole point of this
judge is that it works without one -- hand it the key and you have built a slow,
expensive lookup table.

`screen_my_judge.py` refuses to run if it finds a row id or a `must_call` in your
rubric, and tells you which line. That is not a trick question; it is the rule.
"""

from __future__ import annotations

import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first

# ===========================================================================
# THIS IS WHAT THE JUDGE WAS SENT IN CLASS, VERBATIM.
#
# It is the version that fired on 4 of 4 clean runs. Read it before you change
# anything, and find the sentence that made it so strict.
# ===========================================================================
RUBRIC_AS_TAUGHT = """QUESTION
Do these tool calls gather everything this particular request needs answered?

Read the request closely and ask what a competent engineer would have to look up
before they could answer it. Then check whether each of those lookups actually
happened.

UNSOUND if: the request asks something that one of the available tools answers
directly, and that tool was never called -- for example the engineer asks whether a
repair can wait until the weekend, which is a question about lead time, and nothing
ever checks the parts store; or asks whether this is the same failure as last time,
and nothing ever checks the past work orders.

Not UNSOUND if: the calls are few but cover what was asked. A request that needs one
lookup should get one lookup.

Pay attention to what is MISSING, not only to what is present.
"""


# ===========================================================================
# YOUR VERSION. Edit this.
#
# It starts as an exact copy, so if you run the screener right now you will
# reproduce the class result: 4 false alarms out of 4. That is your baseline.
# ===========================================================================
RUBRIC = """QUESTION
Do these tool calls gather everything this particular request needs answered?

Read the request closely and ask what a competent engineer would have to look up
before they could answer it. Then check whether each of those lookups actually
happened.

UNSOUND if: the request asks something that one of the available tools answers
directly, and that tool was never called -- for example the engineer asks whether a
repair can wait until the weekend, which is a question about lead time, and nothing
ever checks the parts store; or asks whether this is the same failure as last time,
and nothing ever checks the past work orders.

Not UNSOUND if: the calls are few but cover what was asked. A request that needs one
lookup should get one lookup.

Pay attention to what is MISSING, not only to what is present.
"""


# ===========================================================================
# ONE SENTENCE, in your own words: what standard was the original applying that
# our answer key does not? Write it before you start editing -- it is the whole
# diagnosis, and the form asks for it.
# ===========================================================================
WHAT_IT_WAS_DOING = ""


if __name__ == "__main__":
    changed = RUBRIC.strip() != RUBRIC_AS_TAUGHT.strip()
    print("my_judge10")
    print(f"  rubric edited yet? {'yes' if changed else 'NO -- still the class version'}")
    print(f"  diagnosis written? {'yes' if WHAT_IT_WAS_DOING.strip() else 'not yet'}")
    print()
    print("  next:  python session-10/screen_my_judge.py --offline")
