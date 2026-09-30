"""
Screen the functions you wrote in my_release12.py. No model, no key, no spend.

    python session-12/screen_my_release.py --part 1     # resolved
    python session-12/screen_my_release.py --part 2     # must_hold (the regression suite)
    python session-12/screen_my_release.py --part 3     # decide
    python session-12/screen_my_release.py --part 4     # alert
    python session-12/screen_my_release.py              # all four

Every test is a situation a real release team has been in. A test prints PASS or
FAIL with the reason. Some lines are marked "not scored": those are real versions, and
nobody knows the right answer for them in advance -- you decide, and defend it.
"""
from __future__ import annotations

import _path  # noqa: F401
import argparse
import importlib
import textwrap

import pipeline12 as pl
import versions12 as vs
from bench7 import tracing_off

W = 96
_CACHE = {}


def say(text, indent="    "):
    print(textwrap.fill(str(text), W, initial_indent=indent, subsequent_indent=indent + "  "))


def runs(version):
    """Evaluated runs of one version, cached for the length of this screen."""
    if version not in _CACHE:
        with tracing_off(True):
            _CACHE[version] = pl.evaluate_all(vs.load(version))
    return _CACHE[version]


def call(fn, *args):
    try:
        return "ok", fn(*args)
    except NotImplementedError:
        return "not written", None
    except Exception as e:   # a crash is reported, never hidden
        return "crashed", f"{type(e).__name__}: {e}"


def test(ok, name, why):
    say(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f" -- {why}"))
    return ok


def verdict(results):
    say("=> GOOD" if results and all(results) else "=> NOT YET", "  ")


# --------------------------------------------------------------------------- 1
def part1(mine):
    print("\nresolved(run)")
    A = runs("A")
    st, _ = call(mine.resolved, A[0])
    if st == "not written":
        say("NOT WRITTEN"); return
    pick = lambda rid: next(r for r in A if r["row_id"] == rid and r["rep"] == 1)
    res = []
    for rid, want, name, why in (
        ("HW-002", False, "a WRONG diagnosis with a work order is not resolved",
         "HW-002: the agents named no part for a pump that needs a strainer, and a technician was sent anyway"),
        ("HW-004", True, "'nothing is wrong' -- correctly -- counts as resolved",
         "HW-004: the compressor is fine, the agents said so, nothing was sent. That is the right outcome."),
    ):
        st, got = call(mine.resolved, pick(rid))
        if st != "ok":
            say(f"CRASHED on {rid}: {got}"); res.append(False); continue
        res.append(test(bool(got) == want, name, why))
    st, got = call(mine.resolved, pick("HW-003"))
    say(f"(not scored) HW-003 -- right diagnosis, but the engineer REJECTED it: the part is not in "
        f"stock. You said: {'resolved' if got else 'not resolved'}. Defend it.")
    st, mine_rate = call(lambda: pl.rate(A, lambda r: bool(mine.resolved(r))))
    print()
    say("The SAME 24 runs, four definitions of 'resolved':", "  ")
    for label, fn in (("a work order was issued", pl.work_order),
                      ("the workflow closed", pl.completed),
                      ("the diagnosis was right", lambda r: r["scores"].get("outcome_match") == 1)):
        say(f"{label:28s} {pl.fmt(pl.rate(A, fn))}")
    if st == "ok":
        say(f"{'YOURS':28s} {pl.fmt(mine_rate)}")
    verdict(res)


# --------------------------------------------------------------------------- 2
GOOD_ON_A = ("HW-001", "HW-003", "HW-004", "HW-005", "HW-007", "HW-009", "HW-010", "HW-011")


def part2(mine):
    print("\nmust_hold(run)  -- the regression suite")
    A = runs("A")
    st, _ = call(mine.must_hold, A[0])
    if st == "not written":
        say("NOT WRITTEN"); return
    res = []
    st, sa = call(pl.suite, A, mine.must_hold)
    if st != "ok":
        say(f"CRASHED: {sa}"); verdict([False]); return
    res.append(test(not sa["HW-012"][0], "it CAN fail: it fails on HW-012, the bug everyone knows about",
                    "your suite says HW-012 is fine on version A. A suite that passes a known bug "
                    "cannot catch a new one."))
    alarms = [q for q in GOOD_ON_A if not sa[q][0]]
    res.append(test(not alarms, "quiet on the 8 questions version A gets right",
                    f"it fails {alarms}, e.g. {sa[alarms[0]][1] if alarms else ''}. A suite that fails on "
                    f"good runs is a suite people stop reading."))
    C = runs("C")
    st, cc = call(pl.compare, A, C, mine.must_hold)
    caught = st == "ok" and bool(cc["regressions"])
    res.append(test(caught, "it catches version C (SEEDED: no documentation agent)",
                    "version C skips an agent on every question that needs it, and your suite "
                    "reported no regression"))
    if caught:
        say(f"version C regressed on {cc['regressions']}", "      ")
    B = runs("B")
    if B:
        st, cb = call(pl.compare, A, B, mine.must_hold)
        if st == "ok":
            say(f"(not scored) version B -- REAL:  regressed {cb['regressions'] or 'none'},  "
                f"fixed {cb['fixed'] or 'none'},  still failing {cb['still_failing'] or 'none'}")
    else:
        say("(version B not captured yet)")
    print()
    say("which questions hold on version A, by YOUR suite:", "  ")
    say("  ".join(f"{q}:{'held' if sa[q][0] else 'FAILS'}" for q in sorted(sa)))
    verdict(res)


# --------------------------------------------------------------------------- 3
def _m(**dirs):
    names = ("task success", "right agents, right order", "right tools", "tokens per run",
             "cost per run ($)", "latency (s)", "work orders issued")
    return {n: {"direction": dirs.get(n.split()[0], "no detectable difference")} for n in names}


SITUATIONS = [
    # (name, cmp, allowed decisions, why)
    ("identical to A in every way", {"cand": "X1", "regressions": [], "fixed": [], "metrics": _m()},
     {"HOLD", "REJECT"}, "nothing is better. Shipping a change you cannot defend is still a change."),
    ("better on every metric, but breaks one question that used to work",
     {"cand": "X2", "regressions": ["HW-004"], "fixed": [],
      "metrics": _m(task="better", right="better", cost="better", tokens="better", latency="better")},
     {"HOLD", "REJECT"}, "a question that worked yesterday fails today. Averages do not outvote a regression."),
    ("fixes one question, breaks nothing, cost unchanged",
     {"cand": "X3", "regressions": [], "fixed": ["HW-012"], "metrics": _m()},
     {"SHIP"}, "this is the release you were hoping for. A rule that never ships is not a rule."),
    ("no quality change, detectably cheaper, breaks nothing",
     {"cand": "X4", "regressions": [], "fixed": [], "metrics": _m(cost="better", tokens="better")},
     {"SHIP"}, "same quality for less money. The tie goes to the cheaper version."),
    ("task success detectably WORSE, but the suite missed it",
     {"cand": "X5", "regressions": [], "fixed": [], "metrics": _m(task="worse", cost="better")},
     {"HOLD", "REJECT"}, "your suite is not the only signal. Worse is worse."),
]


def part3(mine):
    print("\ndecide(cmp)")
    st, _ = call(mine.decide, SITUATIONS[0][1])
    if st == "not written":
        say("NOT WRITTEN"); return
    res = []
    for name, cmp, allowed, why in SITUATIONS:
        st, got = call(mine.decide, cmp)
        if st != "ok" or not (isinstance(got, tuple) and len(got) == 2):
            say(f"CRASHED or not (decision, reason): {name}: {got}"); res.append(False); continue
        d, reason = got
        if d not in ("SHIP", "HOLD", "REJECT"):
            say(f"FAIL  {name} -- returned {d!r}; use SHIP, HOLD or REJECT"); res.append(False); continue
        res.append(test(d in allowed, f"{name}:  {d}", f"{why}  (you said {d}: {reason})"))
    A, C = runs("A"), runs("C")
    key_suite = importlib.import_module("my_release12").must_hold
    st, _ = call(key_suite, A[0])
    if st == "ok":
        cc = pl.compare(A, C, key_suite)
        st, got = call(mine.decide, cc)
        if st == "ok":
            res.append(test(got[0] != "SHIP", f"version C (SEEDED, cheaper, skips an agent):  {got[0]}",
                            f"C breaks {cc['regressions']}. You said SHIP: {got[1]}"))
        B = runs("B")
        if B:
            cb = pl.compare(A, B, key_suite)
            st, got = call(mine.decide, cb)
            if st == "ok":
                say(f"(not scored) version B -- REAL:  {got[0]}  -- {got[1]}")
    else:
        say("(write must_hold first: the real versions need your suite)")
    verdict(res)


# --------------------------------------------------------------------------- 4
def part4(mine):
    print("\nalert(today, usual)  -- a week in production")
    with tracing_off(True):
        week = [pl.day_metrics(d) for d in vs.production_week()]
    usual = pl.day_metrics([{**r, "day": 0} for r in runs("A")])
    st, _ = call(mine.alert, week[0], usual)
    if st == "not written":
        say("NOT WRITTEN"); return
    print(textwrap.indent(pl.show_week(week), "    "))
    print()
    fired = {}
    for d in week:
        st, got = call(mine.alert, d, usual)
        if st != "ok":
            say(f"CRASHED on day {d['day']}: {got}"); verdict([False]); return
        fired[d["day"]] = list(got or [])
        say(f"day {d['day']}: " + ("; ".join(map(str, got)) if got else "quiet"))
    print()
    false = [d for d in range(1, vs.DRIFT_DAY) if fired[d]]
    late = [d for d in range(vs.DRIFT_DAY, vs.DAYS + 1) if fired[d]]
    res = [test(not false, f"quiet on days 1-{vs.DRIFT_DAY - 1}: nothing had changed",
                f"it fired on day(s) {false}. Nothing about the agents or the store changed on those days: "
                f"that is ordinary day-to-day wobble with only 24 requests."),
           test(bool(late), f"fires after day {vs.DRIFT_DAY}, when something DID change",
                "something changed on day 5 and your alert never fired. Look at which numbers moved.")]
    if late:
        say(f"first fired on day {late[0]} (the change began on day {vs.DRIFT_DAY})", "      ")
    verdict(res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", type=int, choices=(1, 2, 3, 4))
    a = ap.parse_args()
    # reload: in a notebook the module stays imported, and your edits would be ignored
    mine = importlib.reload(importlib.import_module("my_release12"))
    for part in ([a.part] if a.part else (1, 2, 3, 4)):
        print(f"\n===== PART {part} =====")
        (part1, part2, part3, part4)[part - 1](mine)


if __name__ == "__main__":
    main()
