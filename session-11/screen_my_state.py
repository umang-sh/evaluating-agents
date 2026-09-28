"""
Screen the checks you wrote in my_state11.py. No model, no key, no spend.

It asks one question of every check: DOES IT TELL A BROKEN RUN FROM A CLEAN ONE?

    broken runs   one specific thing damaged (see seeds11.py for the list)
    clean runs    11 stub runs with nothing damaged. A check that fires on one of these
                  is a FALSE ALARM.
    real runs     the 24 LIVE runs of the real agents, replayed through the approval
                  workflow. Nothing was injected into them -- but nobody promised they
                  are correct either. When your check fires on one, it is not scored:
                  it is listed, and you decide whether the agent or your check is wrong.

Verdicts, per check:
    CATCHES IT    fires on the broken run it is meant for
    MISSES IT     does not fire on that broken run
    FALSE ALARM   fires on a CLEAN run (listed, with your evidence line)
    NOT WRITTEN   still raises NotImplementedError

    python session-11/screen_my_state.py              # everything
    python session-11/screen_my_state.py --part 1     # just Part 1 (or 2, or 3)
    python session-11/screen_my_state.py --show 2     # print work order 2 and its state
    python session-11/screen_my_state.py --show stall # or any broken run by name
    python session-11/screen_my_state.py --show live:HW-012:1   # a real run (row, rep)
"""
from __future__ import annotations

import _path  # noqa: F401
import argparse
import importlib
import textwrap

import seeds11
import workflow11 as wf

PARTS = {1: ("check_finished", "check_machine"),
         2: ("check_transitions", "check_counters"),
         3: ("finish_status",)}
W = 96


def say(text, indent="    "):
    print(textwrap.fill(str(text), W, initial_indent=indent, subsequent_indent=indent + "  "))


def call(fn, run):
    try:
        ok, ev = fn(run)
        return ("ok" if ok else "fired"), ev
    except NotImplementedError:
        return "not written", ""
    except Exception as e:  # a crash is reported, never hidden
        return "crashed", f"{type(e).__name__}: {e}"


def validate_legal(legal):
    known = set(wf.STATUSES)
    bad = [k for k in legal if k not in known]
    for k, v in legal.items():
        bad += [f"{k} -> {x}" for x in v if x not in known]
    return bad


def screen_check(name, fn, clean, real):
    targets = [n for n, b in seeds11.BROKEN.items() if b["check"] == name]
    print(f"\n{name}")
    results = []
    for t in targets:
        verdict, ev = call(fn, seeds11.run_broken(t))
        kind = seeds11.BROKEN[t]["kind"]
        if verdict == "not written":
            print("    NOT WRITTEN"); return
        if verdict == "crashed":
            say(f"CRASHED on {t}: {ev}"); results.append(False); continue
        results.append(verdict == "fired")
        say(f"{'CATCHES IT ' if verdict == 'fired' else 'MISSES IT  '} {t} ({kind}) -- "
            + (ev if verdict == "fired" else "your check said this run was fine"))
    alarms = []
    for run in clean:
        verdict, ev = call(fn, run)
        if verdict in ("fired", "crashed"):
            alarms.append((run["label"], verdict, ev))
    if alarms:
        say(f"FALSE ALARM on {len(alarms)} of {len(clean)} clean runs:")
        for label, v, ev in alarms[:3]:
            say(f"{label}: {'CRASHED ' if v == 'crashed' else ''}{ev}", "      ")
        if len(alarms) > 3:
            say(f"... and {len(alarms) - 3} more", "      ")
    else:
        say(f"quiet on all {len(clean)} clean runs")
    flagged = []
    for run in real:
        verdict, ev = call(fn, run)
        if verdict in ("fired", "crashed"):
            flagged.append((run["label"], verdict, ev))
    if flagged:
        say(f"ON THE {len(real)} REAL RUNS it fired {len(flagged)} times (not scored -- "
            f"look at them and decide who is wrong):")
        for label, v, ev in flagged[:3]:
            say(f"{label}: {'CRASHED ' if v == 'crashed' else ''}{ev}", "      ")
        if len(flagged) > 3:
            say(f"... and {len(flagged) - 3} more", "      ")
    else:
        say(f"quiet on all {len(real)} real runs")
    good = all(results) and not alarms
    say("=> GOOD CHECK" if good else "=> NOT YET", "  ")


def screen_redesign(policy):
    print("\nfinish_status  (re-running the four work orders with YOUR policy)")
    before = seeds11.run_vote()
    try:
        after = seeds11.run_vote(policy=policy)
        clean_after = [wf.run_workflow(r, policy=policy) for r in seeds11.CLEAN_STUB_ROWS]
        clean_after += seeds11.live_runs(policy=policy)
    except Exception as e:
        say(f"CRASHED: {type(e).__name__}: {e}"); return
    for b, a in zip(before, after):
        say(f"{a['label']}:  before: work order {'YES' if b.get('work_order') else 'none':4s}   "
            f"now: ends {a['status']:8s} work order {'YES' if a.get('work_order') else 'none'}")
    stall_fixed = after[0]["status"] == "STALLED" and not after[0].get("work_order")
    too_strict = [r["label"] for r in clean_after if r["status"] == "STALLED"]
    if stall_fixed and not too_strict:
        say("=> FIXED: the stalled run stops, every clean run still finishes", "  ")
    elif not stall_fixed:
        say("=> NOT YET: work order 1 still gets a work order", "  ")
    if too_strict:
        say(f"=> TOO STRICT: {len(too_strict)} clean runs now stall, e.g. {too_strict[:3]}", "  ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", type=int, choices=(1, 2, 3))
    ap.add_argument("--show")
    a = ap.parse_args()

    if a.show:
        s = a.show
        if s.isdigit():
            run = seeds11.run_vote()[int(s) - 1]
        elif s.startswith("live:"):
            _, rid, rep = s.split(":")
            run = next(r for r in seeds11.live_runs() if r["label"] == f"live {rid} rep{rep}")
        elif s in seeds11.BROKEN:
            run = seeds11.run_broken(s)
        else:
            run = wf.run_workflow(s)
        print(wf.show(run)); print(); print(wf.show_state(run))
        return

    # reload: in a notebook the module stays imported, and your edits would be ignored
    mine = importlib.reload(importlib.import_module("my_state11"))
    bad = validate_legal(mine.LEGAL)
    if bad:
        say(f"LEGAL names statuses that do not exist: {bad}. Known: {list(wf.STATUSES)}", "")
        return
    clean = [wf.run_workflow(r, label=f"stub {r}") for r in seeds11.CLEAN_STUB_ROWS]
    real = seeds11.live_runs()
    for part in ([a.part] if a.part else (1, 2, 3)):
        print(f"\n===== PART {part} =====")
        for name in PARTS[part]:
            if name == "finish_status":
                screen_redesign(mine.finish_status)
            else:
                screen_check(name, getattr(mine, name), clean, real)


if __name__ == "__main__":
    main()
