# End-Term Assessment — the case study

Groups of 3, assigned by roll number. One case per group. **Presentations Fri 30 Oct.**
Submissions **Wed 28 Oct, 23:59**.

Read `../endterm_case_brief.md` for the situation and the marking. This file is only
about getting the code to run.

---

## Which case is yours

Your group number, counted round 1 to 5:

| group | case |
|---|---|
| 1, 6, 11 | 1 |
| 2, 7, 12 | 2 |
| 3, 8, 13 | 3 |
| 4, 9, 14 | 4 |
| 5, 10, 15 | 5 |

---

## Setup

Nothing new to install. If Session 12 ran on your machine, this runs.

```bash
git pull
```

**No API key is needed and nothing costs money.** Every number comes from replaying runs
saved on disk, so your laptop gives the same answer as everyone else's.

---

## The three commands

```bash
# 1. copy the template, name it for your group
cp endterm/my_release_TEMPLATE.py endterm/my_release_G7.py

# 2. write the three marked functions in it

# 3. produce your scorecard  (replace 3 with YOUR case id)
python endterm/run_endterm.py 3 endterm/my_release_G7.py > scorecard.txt
```

That is the whole pipeline: it evaluates both versions, builds both scorecards, compares
them question by question, runs your regression suite, and prints your decision.

---

## What you submit

A folder named for your group, containing exactly three files:

| File | What it is |
|---|---|
| `my_release_G7.py` | your code |
| `scorecard.txt` | the output of the command above — **redirected, not retyped** |
| `decision.md` | one page: your call, the measurement under it, what would have reversed it |

**I re-run your file against your case.** If the output does not match your
`scorecard.txt`, the measurement section is capped. Redirect it; do not copy numbers by
hand.

---

## What is in your case folder

```
endterm/case-<N>/runs_a.json    version A -- 24 REAL runs, the version in production
endterm/case-<N>/runs.json      your candidate -- 24 runs, SEEDED
```

Both files hold the same 12 maintenance requests, two repeats each.

**SEEDED** means the candidate was built from version A's saved runs by code. One thing
about it was changed on purpose. Where a step survived, its report is A's report, because
the agents were not re-run. A real re-run could come out better or worse than what you
see. That is a limit on what you can conclude from these runs, and saying so in
`decision.md` is worth marks. It is not a reason to have no number.

`endterm12.provenance(case_id, "A")` prints the one line you should put on a slide before
you quote anything off these runs.

---

## Three things that will cost you marks

1. **A number without a spread.** `fmt()` prints every interval for you. Use them.
2. **A number on a slide that is not in `scorecard.txt`.** Deducted per number.
3. **A scorecard where everything passes, read as good news.** It is evidence your
   evaluator is not discriminating. Say so — that is the whole course in one line.

---

## If it will not run

| Error | Fix |
|---|---|
| `ModuleNotFoundError: no module named _path` | run it from the repo root, not from inside `endterm/` |
| `no working resolved, must_hold, decide` | one of the three still raises `NotImplementedError` |
| `KeyError: case 7` | case ids are 1 to 5 |
| `No module named ipykernel` / notebook will not open | `pip install -r requirements.txt` |
