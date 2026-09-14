"""
Session 7 — the measurement harness.

One call shape for both arms, one run record shape for `paired.py`, so the
Session 6 machinery (paired interval by question text, tie rule) works here
unchanged. Nothing about the interval maths is re-derived; if it was right in
Session 6 it is right here, and if it was wrong it is wrong in both.

WHAT IS MEASURED, SAID BEFORE ANY TWO NUMBERS GO SIDE BY SIDE
-------------------------------------------------------------
  arm            "pipeline" (four agents) or "single" (one agent, five tools).
                 `paired.py` calls this the VERSION.
  a run          one request sent to one arm, once. Repetitions of the same
                 request against the same arm are `rep` 1..k.
  tokens_billed  output tokens + UNCACHED input tokens, summed over every LLM
                 call in the trace. Cached reads excluded. Course definition
                 since Session 3; a four-agent pipeline makes four times as
                 many LLM calls, so this number is where the pipeline's price
                 shows up.
  n_agent_calls  specialist invocations. The single arm is 1 by definition.
  latency_s      wall clock, measured locally, not from the trace.
  cost_usd       LangSmith's number, when it has a pricing row.

THE COST COMPARISON IS ARITHMETIC, NOT A FINDING
-------------------------------------------------
Four agents make more model calls than one agent. That the pipeline costs more
is not a discovery and must not be presented as one. The measurable question is
whether the extra spend BUYS anything: does the pipeline get more rows right,
and is that difference bigger than the noise? `outcome_match` is the column
that matters. Cost is the column that tells you what it cost.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

# Load .env at import, before anything reads os.environ.
#
# Session 6 lost a whole push to this: `push_pool.py` never called
# load_dotenv(), so it 401'd for everyone whose key lived only in .env and the
# dataset silently never existed. Session 7's first live pre-flight hit the
# identical bug from the other direction -- a HARD STOP for "missing
# ANTHROPIC_API_KEY" on a machine where the key was sitting in .env two
# directories up the call stack.
#
# It lives HERE rather than in the pre-flight because every Session 7 entry
# point imports bench7: the pre-flight, the notebook, the comparison cell.
# Fixing one caller would have left the others to find it again.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:      # python-dotenv absent: fall back to the ambient env
    pass

import coord_eval7
import evalkit
import seeds7
from delegation_rows7 import ROWS
from plant_agents7 import run_pipeline, run_single

__version__ = "s7-2026-09-13a"

PROJECT = "session-7-multi-agent"

# Gotcha #13/#16 consequence: if the model has no pricing row, the cost wait is
# paid on EVERY run. Latch it after the first miss -- twelve runs x 30 s is six
# minutes of a room watching a column that will never fill.
_COST_AVAILABLE: bool | None = None


class tracing_off:
    """Suppress LangSmith tracing for a block.

    Loading `.env` also loads LANGSMITH_TRACING=true, which means the STUB runs
    -- 120 of them on an --offline pre-flight, 180 on a live one -- get logged
    to the class project as real traces. They are not real: no model was
    called, the answers are read out of plant7, and a room opening
    `session-7-multi-agent` would find it full of fixtures.

    So the matrix runs with tracing off and the live checks run with it on.


    FLIPPING THE ENV VAR DOES NOT WORK, AND FAILS SILENTLY -- the first version
    of this class did exactly that. `langsmith.utils.get_env_var` is
    @lru_cache'd (conventions #5, the same cache that sends traces to
    `default`), so once anything has read LANGSMITH_TRACING the value is
    frozen for the process. `env_setup()` reads it at startup, so on a LIVE run
    the flip was a no-op and every stub fixture was logged anyway. On an
    --offline run nothing had read it yet, the cache took `false`, and it
    appeared to work perfectly -- which is how it passed review.

    `tracing_context(enabled=False)` is the supported mechanism: it sets a
    context var that `tracing_is_enabled` checks FIRST, before the run tree,
    the global fallback and the cached env var.
    """

    def __init__(self, off: bool = True):
        self.off = off
        self._cm = None

    def __enter__(self):
        if self.off:
            from langsmith.run_helpers import tracing_context
            self._cm = tracing_context(enabled=False)
            self._cm.__enter__()
        return self

    def __exit__(self, *exc):
        if self._cm is not None:
            self._cm.__exit__(*exc)
            self._cm = None
        return False


def _token_fields(run) -> dict:
    """tokens_billed = completion + uncached prompt tokens (course definition)."""
    out = int(getattr(run, "completion_tokens", 0) or 0)
    inp = int(getattr(run, "prompt_tokens", 0) or 0)
    return {"tokens_out": out, "tokens_in_uncached": inp, "tokens_billed": out + inp}


def measure(row: dict, arm: str, impl: str = "llm", seed: str = "healthy",
            rep: int = 1, trace: bool = True) -> dict:
    """Run one row through one arm and return a paired.py-shaped record."""
    global _COST_AVAILABLE
    seed_fn = seeds7.get(seed)
    t0 = time.perf_counter()
    since = datetime.now(timezone.utc)

    if arm == "pipeline":
        out = run_pipeline(row["request"], impl=impl, seed=seed_fn)
    elif arm == "single":
        if seed != "healthy":
            raise ValueError("the single arm has no coordination to break; "
                             "seeds apply to the pipeline only")
        out = run_single(row["request"], impl=impl)
    else:
        raise ValueError(f"unknown arm {arm!r}")

    latency = time.perf_counter() - t0
    metrics = {
        "latency_s": round(latency, 3),
        "n_agent_calls": len([a for a in out["agent_calls"]
                              if a in coord_eval7.SPECIALISTS]) or (1 if arm == "single" else 0),
        "n_tool_calls": len(out.get("tool_calls", [])),
        "answer_chars": len(out.get("answer", "")),
    }
    note = ""

    if trace and impl == "llm":
        evalkit.flush_traces()
        from langsmith import Client
        client = Client()
        root_id = evalkit.find_trace_root(client, since=since, project=PROJECT)
        if root_id is None:
            note = "no root run resolved; token and cost columns unavailable"
        else:
            root, note = evalkit.read_run_when_ready(client, root_id)
            if root is not None:
                metrics.update(_token_fields(root))
                if _COST_AVAILABLE is not False:
                    cost = getattr(root, "total_cost", None)
                    if cost:
                        _COST_AVAILABLE = True
                        metrics["cost_usd"] = float(cost)
                    elif _COST_AVAILABLE is None:
                        _COST_AVAILABLE = False
                        note = (note + "; " if note else "") + (
                            "no cost on the first run -- add a custom pricing row in "
                            "LangSmith BEFORE the run (it does not reprice logged "
                            "traces). Cost column skipped for the rest of this batch.")

    scores = {k: v["score"] for k, v in coord_eval7.run_all(out, row).items()}
    comments = {k: v["comment"] for k, v in coord_eval7.run_all(out, row).items()}

    return {
        "version": arm if seed == "healthy" else f"{arm}:{seed}",
        "arm": arm,
        "seed": seed,
        "question": row["request"],
        "row_id": row["id"],
        "rep": rep,
        "error": None,
        "note": note,
        "outputs": {"answer": out["answer"], "metrics": metrics,
                    "agent_calls": out["agent_calls"],
                    "handoffs": out["handoffs"], "plan": out["plan"],
                    "tail": out["tail"],
                    # Only the COUNT was persisted before, so a saved run could
                    # not answer "which tool did which agent call" -- which is
                    # the whole of Session 10. The list is small; keep it.
                    "tool_calls": out.get("tool_calls", [])},
        "scores": scores,
        "comments": comments,
    }


def run_matrix(arms=("pipeline", "single"), seeds=("healthy",), rows=None,
               reps: int = 1, impl: str = "llm", trace: bool = True,
               verbose: bool = True, phase: str = "unlabelled") -> list[dict]:
    """`phase` labels WHICH measurement these records belong to.

    runs7.json is the concatenation of three different measurements -- the stub
    seed matrix, the live tail-contract probe, and the live comparison -- and
    they are NOT poolable. They were saved untagged once, and the notebook's
    COMPARE cell then averaged two different pipeline batches against one
    single batch: the deck read -4% on outcome, the notebook printed -25%, and
    both were arithmetically correct on the runs they were given. Anything that
    reads this file for a comparison must filter on `phase`.
    """
    rows = rows if rows is not None else ROWS
    recs: list[dict] = []
    # trace=False means "this is not a real run" -- so it must not be logged
    # as one either. See tracing_off.
    with tracing_off(not trace):
      for rep in range(1, reps + 1):
          for arm in arms:
            for seed in (seeds if arm == "pipeline" else ("healthy",)):
                for row in rows:
                    rec = measure(row, arm, impl=impl, seed=seed, rep=rep, trace=trace)
                    rec["phase"] = phase
                    recs.append(rec)
                    if verbose:
                        # "." pass · "X" fail · "-" SKIPPED. The first version
                        # printed "X" for a None score, so the single-agent arm
                        # read as failing four coordination checks when in fact
                        # four checks had declined to score it. A progress line
                        # that misreports is worse than no progress line.
                        ok = "".join("-" if rec["scores"][k] is None
                                     else ("." if rec["scores"][k] else "X")
                                     for k in sorted(rec["scores"]))
                        print(f"  rep{rep} {arm:8s} {seed:16s} {row['id']}  {ok}"
                              + (f"  [{rec['note'][:60]}]" if rec.get("note") else ""),
                              flush=True)   # flush: a buffered progress line is not progress
    return recs


def save(recs: list[dict], path: str = "runs7.json", **meta) -> str:
    missing = [r for r in recs if not r.get("phase")]
    if missing:
        raise ValueError(f"{len(missing)} record(s) have no `phase`. An untagged "
                         f"runs file is the bug that made slide 20 and the "
                         f"COMPARE cell disagree -- see run_matrix.__doc__.")
    payload = {"version": __version__,
               "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
               "project": PROJECT, **meta, "runs": recs}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=str)
    return path


if __name__ == "__main__":
    recs = run_matrix(arms=("pipeline",), seeds=("healthy",) + seeds7.BROKEN,
                      reps=1, impl="stub", trace=False, verbose=False)
    by = {}
    for r in recs:
        by.setdefault(r["seed"], []).append(r)
    keys = sorted(recs[0]["scores"])
    print(f"{'seed':18s} " + " ".join(f"{k[:13]:>14s}" for k in keys) + "   (stub, 12 rows)")
    for seed, rs in by.items():
        cells = " ".join(f"{sum(1 for r in rs if r['scores'][k]):>10d}/{len(rs):<3d}"
                         for k in keys)
        print(f"{seed:18s} {cells}")
