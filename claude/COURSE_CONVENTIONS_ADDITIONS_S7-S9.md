# COURSE_CONVENTIONS — additions from Sessions 7, 8 and 9

**STATUS: written 20 Sep 2026, NOT yet merged into `COURSE_CONVENTIONS.md`.**

Why this is a separate file rather than an edit: the master document exists **only as a
project doc** — there is no copy of it in the repo — and the only way to change a project
doc is to rewrite it whole. Retyping a twelve-thousand-word reference to append seven
gotchas risks silently corrupting the part nobody is checking. The additions are finished
below; the merge is a one-line decision for Umang. **See "Loose ends" at the bottom.**

Two corrections to the Session 9 kickoff's account of what was outstanding:

- **The four Session 6 findings are already in the master document**, as gotchas #18–21
  under *"Four more, from running Session 6"*. That item can be struck.
- What is genuinely missing is **#22** and everything from Sessions 7–9, below.

---

## Five more, from Sessions 7 and 8

**22. `load_dotenv()` at import turns LangSmith tracing ON, and a `tracing_off` helper that
flips the environment variable is a no-op.** `bench7.py` calls `load_dotenv()` at import,
which reads `LANGSMITH_TRACING=true` out of `.env` and into the process. Any helper that
then tries to disable tracing by setting the variable back has no effect on a client that
has already been constructed, because `langsmith.utils.get_env_var` is `lru_cache`d — the
same caching family as gotcha #5, one layer down. Use the context manager, which does not
go through the environment at all:

```python
from langsmith.run_helpers import tracing_context
with tracing_context(enabled=False):
    ...                      # genuinely untraced
```

Symptom if you get this wrong: a "free, offline" pre-flight quietly posting every stub run
to LangSmith, and a project full of runs with zero tokens. [Certain — Session 7]

**23. The prompt and the parser must agree about the format, and neither one is the
authority on its own.** Session 8's judge prompt said `LINE 1: one word…`; the model replied
`LINE 1: UNSOUND`, doing exactly as told; the parser required a bare word and scored **all
192 live verdicts INSUFFICIENT-EVIDENCE**. The gate reported four unusable judges. The judge
had been right every time.

Two rules came out of it, and the second is the general one:

- **Assert that the prompt does not contain the format the parser forbids.** `preflight8`
  now checks the literal string `LINE 1:` is absent from the prompt, and that a labelled
  verdict still parses. Both halves, or you have only moved the bug.
- **Be tolerant of FORMAT and strict about SUBSTANCE.** Three providers do not format
  alike — one fences in markdown, one bolds, one numbers the lines, one puts the verdict and
  the evidence on one line. A parser tuned on one provider is a parser that works for one
  provider, and it fails *silently and only* for the students least able to diagnose it.

[Certain — 192 verdicts discarded, Session 8]

**24. Derive call costs from the code that makes the calls. Never type them.**
`screen_my_attack.py` was documented in four separate files as costing "one model call per
attempt". It calls `run_all` twice, and `run_all` is a dict comprehension over all four
judges: **eight**. The run sheet budgeted five calls per pair against a true cost of forty.

The fix is structural, not editorial: a function that computes the count from the same
tuples the run iterates, and a sweep check that fails when any file claims a number that
disagrees with it. Session 9's `traj_bench9.calls_for()` and `sweep9.py` check [6] are that
pattern. **Anything that quotes a call count — the run sheet, the notebook, the homework
email — calls the function.** [Certain — Session 8]

**25. A comment is not a measurement. Recompute counts; never read them.**
`judge_seeds8.build()` returned **seven** arms while four files still said six;
`judge_bench8.py` advertised "24 verdicts" while producing 28. Nothing downstream was wrong,
and that is the interesting part: `agree8.py` counts records rather than trusting the
comment, so the stale numbers were invisible until someone read them aloud.

**Sweep must recompute, never read.** [Certain — Session 8]

**26. Never truncate a finding. Wrap it.** `comment[:74]` in one place and `comment[:88]` in
another threw away the judge's evidence line — the only part of a verdict you can argue
with. Session 8's entire diagnosis of a 192-call wasted run was done from the saved `comment`
field with **no extra calls**, and would have been impossible against a truncated one.
Corollary: a file that hands a student a string must give them a free way to read it
(`--show`), or their only anchor is a docstring example. [Certain — Session 8]

---

## Three more, from building Session 9

**27. `paired.pct` divides by `mean_base`, so swapping `base` and `cand` is NOT a sign
flip.** Session 7's deck printed `outcome_match` as **−4.35%** with `base=pipeline,
cand=single`. Negating that to get the other orientation gives −4.5%, not +4.35%, because
the denominator changed with the base. Worse, the sign is easy to read backwards: **−4.35%
means the SINGLE arm scored lower**, i.e. the pipeline was slightly ahead — and printed next
to "the pipeline costs 29% more" it reads as "more money, less quality", which is the
opposite of what the number says.

Three rules:

- **State a difference in percentage POINTS when the metric is a proportion.** +2.8 pp is
  unambiguous; −4.35% relative is not.
- **Fix the orientation once, in code, with a comment saying which way is which.**
  `cost9.BASE/CAND` does this.
- **Assert the published triple.** `cost9.reproduces_session7()` checks the exact
  `(pct, lo, hi)` the Session 7 deck shipped, so a future edit to `paired.py` or to the runs
  file fails pre-flight rather than silently contradicting a slide that is already taught.

[Certain — recomputed against `deck_numbers7.json`, 20 Sep]

**28. A ratio whose denominator is undefined is not a measurement.** `n_agent_calls` in
`runs7.json` counts **specialists and excludes the planner**. Quoted as-is the pipeline makes
"2.00× the agent calls" of the single arm; counting actual invocations it is **3.0×**. Both
numbers are correct and they describe different things. **Report the definition with the
ratio, or report both.** `cost9.agent_call_counts()` returns both, each labelled.
[Certain — 108 vs 36 invocations, 72 vs 36 specialists]

**29. A check that greps source text will fire on the documentation telling you not to do
the thing.** Session 9's sweep grew two checks that read files as text: one scanning for
stale counts, one for truncated findings. The count check flagged a slide titled *"Session 8
judged the report"* as claiming "8 judges". The truncation check flagged a docstring whose
whole purpose is to say **do not write `payload[:120]`**.

A false positive on your own documentation is not a harmless annoyance — it is how a check
gets weakened or switched off. **Tokenize and blank comments and string literals before
scanning code**, and blank them **in place** so line numbers survive: the first fix here
joined the surviving tokens and reported a real failure at `agree9.py:2014`, in a file of 290
lines. The same applies to a term-definition check: a glossary table row (`| **term** | … |`)
is a definition, and a checker that only recognises `term:` will flag fourteen terms that are
defined perfectly well. [Certain — both caught by the sweep itself, 20 Sep]

---

## The sentences the course is building on — Sessions 4 to 9

Append to the existing list in the master document:

> **Session 4:** A check is only a claim until something fails it.
>
> **Session 5:** A claim measured once is a coin flipped once.
>
> **Session 6:** Comparing two versions is flipping two coins — report the interval, not the
> winner, and when it crosses zero the tie goes to the cheaper agent.
>
> **Session 7:** Every agent you add is a decision you added, and every decision is somewhere
> to be wrong.
>
> **Session 8:** You cannot measure a difference smaller than your judge's own noise.
>
> **Session 9:** Code can tell you the path was wrong — but only if someone already wrote
> down what right was.

---

## Loose ends, as of 20 Sep 2026

| item | state |
|---|---|
| **Merge this file into `COURSE_CONVENTIONS.md`** | **Open — Umang's call.** The master is a project doc only; merging means rewriting it whole. Say the word and it gets done in one pass. |
| **The master document has no copy in the repo** | Open. Everything else the course depends on is version-controlled; this is not, and the Session 9 kickoff referred to it as `claude/COURSE_CONVENTIONS.md` as though it were. Worth resolving with the merge. |
| Four Session 6 findings | **Done already** — they are #18–21 in the master. The kickoff's claim that they were missing is out of date. |
| Gotcha #22 (`load_dotenv` / tracing) | Written above, unmerged. |
| Session 8's three (#23, #24, #25/#26) | Written above, unmerged. |
| Session 9's three (#27, #28, #29) | Written above, unmerged. |
| **The S4–S6 phase-pooling audit** | **Still not done.** Deferred three times now. `save(a + b + c)` with no phase field exists in Sessions 4, 5 and 6, and Session 7 proved what it costs: two different wrong numbers on two different screens. Sessions 7, 8 and 9 all stamp `phase` at creation and raise without it. The older sessions do not, and nobody has checked whether their numbers moved. |
| LangSmith deprecation banner | Unchanged — `list_runs` and `get_run_url` kept on purpose; migrate before 31 Jan 2027; **plan before Session 12.** |
