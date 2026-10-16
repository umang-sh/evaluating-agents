# End-Term Assessment — Case Study

**Evaluating AI Agents**

Groups of 3, assigned by roll number. One case per group.
**Submissions Wed 28 Oct, 23:59. Presentations Fri 30 Oct.**

---

## The situation

Halvard Works runs the four-agent maintenance assistant you have worked with all term:
**Planner → Diagnostics → Documentation → Maintenance**.

**Version A** has been in production since 25 September. It is the version currently
answering maintenance requests. Its 24 runs are real.

Engineering has proposed a replacement. Your group has been given **one candidate
version** and the 24 runs it produced against the same 12 requests, two repeats each.

Three things have landed on the maintenance lead's desk this week:

1. An engineer says a work order came through for the wrong machine.
2. A second engineer says the assistant "has got faster but says less".
3. The plant manager wants the new version live before the next shutdown.

Not all three are about your candidate. Part of the job is working out which, if any, are.

**You are the evaluation team. The decision is yours to make and defend.**

---

## What you must decide

Ship the candidate version, or do not ship it.

A third answer is available and on at least one of the five cases it is the correct one:
**the evidence does not support either call.** If that is your conclusion, say so and
show why — it scores exactly as well as a SHIP or a REJECT that is properly supported.

---

## What you are given

```
endterm/case-<N>/runs_a.json    version A -- 24 REAL runs, the version in production
endterm/case-<N>/runs.json      your candidate -- 24 runs, SEEDED
```

Your case number is your group number counted round 1 to 5 — see `endterm/README.md`.

**SEEDED** means your candidate was built from version A's saved runs by code: one thing
about it was changed on purpose, and the agents were not re-run. Where a step survived,
its report is A's report. A real re-run could come out better or worse than what you see.

That is a limit on what you can conclude, and stating it is worth marks. It is not an
excuse for having no number.

Nothing calls a model. **No API keys. Nothing costs money.** Every number comes from
replaying runs saved on disk, so your laptop gives the same answer as everyone else's.

---

## How you produce your numbers

```bash
cp endterm/my_release_TEMPLATE.py endterm/my_release_G7.py
# write the three marked functions
python endterm/run_endterm.py 3 endterm/my_release_G7.py > scorecard.txt
```

That one command evaluates both versions, builds both scorecards, compares them question
by question, runs your regression suite, and prints your decision.

---

## What you submit

One folder named for your group, containing exactly three files:

| File | What it is |
|---|---|
| `my_release_G7.py` | your code |
| `scorecard.txt` | the output of the command above — **redirected, not retyped** |
| `decision.md` | **one page, maximum** |

**The one-page limit is enforced.** A second page is not read.

`decision.md` answers three questions and nothing else:

1. **What is your call?** SHIP, HOLD, REJECT, or NOT MEASURABLE.
2. **Which single measurement does it rest on?** One number, with its spread, and the
   file it came from.
3. **What result would have reversed it?** A specific result the data could plausibly
   have produced — not "if it had been worse".

**I re-run your file against your case.** If the output does not match your
`scorecard.txt`, the measurement section is capped. Redirect it; do not copy by hand.

---

## What you present

**7 minutes, then 3 minutes of questions.**

The deck is the wrapper. The scorecard is the work. A deck with no numbers in it scores
near zero regardless of how it looks.

Every number on a slide must exist in your submitted `scorecard.txt`. If you say it and
it is not in the file, it did not happen, and it is deducted.

**Questions are directed, not volunteered.** I pick who answers. Every member will be
asked at least one question about the work and will answer it alone. Expect:

- Where did this number come from?
- What would have changed your recommendation?
- Why this measurement and not the other one?

A member who cannot answer a question about their own submission takes a **15-mark
deduction on their personal total**, not the group's. Split the work so all three of you
can speak to all of it.

---

## Where the marks are

| Section | Marks |
|---|---|
| Measurement — numbers produced by your code | 30 |
| The decision and the measurement under it | 25 |
| What would have reversed your call | 15 |
| Live defence (individual) | 20 |
| Deck | **10** |

**The measurement is worth more than the decision, and the decision is worth more than
the deck.** A group that recommends REJECT with a number behind it beats a group that
recommends SHIP with a better-looking slide.

Three groups share each case. The cases are **not** the same as each other. Comparing
notes is allowed and will not help you much — you still have to defend your own numbers,
alone, when I ask.

---

## Three things worth saying plainly

- **A number without a spread is not a measurement.** `fmt()` prints every interval for
  you. Use them.

- **A scorecard where everything passes is not good news.** It is evidence your evaluator
  is not discriminating. If that is what you find, say so.

- **An aggregate can hide one broken request inside it.** A rate over 24 runs and a
  paired difference over 12 questions do not answer the same question, and on some of
  these cases they disagree. Work out which one your decision needs.

---

## One thing worth saying plainly

You have spent twelve sessions on a single idea: **a check that has never failed anything
has not measured anything.**

The fastest way to lose marks here is to produce a scorecard where everything passes and
treat that as evidence the version is good.
