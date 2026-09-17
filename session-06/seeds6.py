"""
Session 6 — the three agent VERSIONS under regression test.

NAMING, because Session 5 already had two things called "a benchmark":
    * `v1` is a DATASET tag (the 12-row pool, `s5-class-benchmark-pool`).
    * The agent versions below are called healthy / redundant / concise.
      They are deliberately NOT called v0/v1/v2, so "v1" only ever means
      one thing in this session.

THE THREE VERSIONS -- each differs from `healthy` by ONE appended prompt line.
Same model, same tools, same `evalkit.SYSTEM_PROMPT` underneath. We never
edit SYSTEM_PROMPT itself: it is shared with every seed and every saved
fixture since Session 4 (Session 5 refused to break it for a demo, too).

    healthy     the incumbent. What is in production today.
    redundant   Session 4's seed: "run every search twice". A regression that
                changes COST and not the ANSWER. The detectable one.
    concise     "Answer in 2 sentences." The kind of harmless-looking edit a
                real team ships on a Friday. Its effect is NOT known in advance
                -- preflight6 measures it and does not gate on its sign.

WHAT THE TARGET RECORDS THAT SESSION 4'S DID NOT
------------------------------------------------
`evalkit.make_target` returns the answer and the trajectory. A regression test
also needs tokens and latency, so `make_measured_target` adds a `metrics`
block, read LOCALLY from each AIMessage's `usage_metadata` and a wall clock.
No LangSmith round trip, so gotchas 13, 16 and 17 (cost not yet written, run
not yet readable, wrong root) cannot bite here. preflight6 still cross-checks
one run against LangSmith, because a local measurer is still a measurer.

TOKEN DEFINITION (Session 3's, still in force -- say it before any two numbers
go side by side):  tokens_billed = output + UNCACHED input.
Cached reads excluded; reasoning tokens in their own column.
"""

from __future__ import annotations


import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first
import threading
import time
from typing import Callable

import evalkit
from evalkit import BASE_TOOLS, SYSTEM_PROMPT, build_agent
from seeds import REDUNDANT_PROMPT

__version__ = "s6-2026-09-10a"

POOL = "s5-class-benchmark-pool"
POOL_TAG = "v1"
PROJECT = "session-6-regression"

CONCISE_PROMPT = SYSTEM_PROMPT + "\n\nAnswer in 2 sentences."

PROMPTS: dict[str, str] = {
    "healthy": SYSTEM_PROMPT,
    "redundant": REDUNDANT_PROMPT,
    "concise": CONCISE_PROMPT,
}
INCUMBENT = "healthy"
CANDIDATES = ["redundant", "concise"]


def build_version(name: str):
    return build_agent(tools=BASE_TOOLS, system_prompt=PROMPTS[name])


# ==========================================================================
# Measuring a run.
# ==========================================================================

def usage_from_result(result: dict) -> dict:
    """Sum usage over every model call in one agent run.

    Same arithmetic as arch_bench._token_details (Session 3): LangChain's
    `input_tokens` INCLUDES cache reads, so uncached = input - cache_read.
    """
    d = {"in_uncached": 0, "out": 0, "cached_read": 0, "reasoning": 0, "llm_calls": 0}
    for m in (result or {}).get("messages", []):
        u = getattr(m, "usage_metadata", None)
        if not u:
            continue
        d["llm_calls"] += 1
        ind = u.get("input_token_details") or {}
        outd = u.get("output_token_details") or {}
        cr = int(ind.get("cache_read", 0) or 0)
        d["cached_read"] += cr
        d["in_uncached"] += max(int(u.get("input_tokens", 0) or 0) - cr, 0)
        d["out"] += int(u.get("output_tokens", 0) or 0)
        d["reasoning"] += int(outd.get("reasoning", 0) or 0)
    d["tokens_billed"] = d["in_uncached"] + d["out"]
    return d


def make_measured_target(version: str) -> Callable[[dict], dict]:
    """evalkit.make_target, plus a `metrics` block.

    HONEST CAVEAT on latency: preflight6 runs with max_concurrency > 1, so a
    run's wall clock includes waiting for rate limits and for other runs.
    Compare latency between versions measured the SAME way, never against a
    number measured sequentially.
    """
    agent = build_version(version)

    def target(inputs: dict) -> dict:
        t0 = time.perf_counter()
        result = agent.invoke({"messages": [inputs["question"]]})
        latency = time.perf_counter() - t0
        messages = evalkit.as_messages(result)
        calls = evalkit.tool_calls_from_messages(messages)
        metrics = {
            "latency_s": round(latency, 3),
            "n_tool_calls": len(calls),
            "n_searches": sum(1 for c in calls if c["name"] == "web_search"),
            "answer_chars": len(evalkit.final_text(result)),
            **usage_from_result(result),
        }
        return {
            "version": version,
            "answer": evalkit.final_text(result),
            "messages": messages,
            "tool_calls": calls,
            "evidence": evalkit.evidence_from_messages(messages),
            "metrics": metrics,
        }

    return target


# ==========================================================================
# Replay.  How students get the instructor's runs into THEIR workspace.
#
# The instructor's experiments live in the instructor's LangSmith workspace;
# a student's key cannot read them. So the runs are saved to runs6.json and
# REPLAYED: a target that returns a saved output instead of calling a model.
#     client.evaluate(make_replay_target(runs, "redundant"),
#                     data=<the v1 examples>, num_repetitions=5, ...)
# Zero model cost, zero Tavily, and a real experiment in their own workspace.
#
# THE TRAP -- say it before they open the UI: LangSmith will show ~0s latency
# and 0 tokens for every replayed run, because nothing was called. The true
# figures are in outputs["metrics"], and the metric evaluators below copy them
# onto the experiment as feedback columns.
# ==========================================================================

def make_replay_target(runs: list[dict], version: str) -> Callable[[dict], dict]:
    queues: dict[str, list[dict]] = {}
    for r in runs:
        if r["version"] == version and r.get("outputs"):
            queues.setdefault(r["question"], []).append(r["outputs"])
    if not queues:
        raise ValueError(f"no saved runs for version {version!r} -- wrong file?")
    lock = threading.Lock()

    def target(inputs: dict) -> dict:
        q = inputs["question"]
        with lock:
            if q not in queues:
                raise KeyError(f"no saved run for this question: {q[:60]!r}. "
                               "Your dataset is not the v1 tag the runs were made on.")
            if not queues[q]:
                raise RuntimeError(f"saved runs exhausted for {q[:60]!r}: "
                                   "num_repetitions is higher than the saved reps.")
            return queues[q].pop(0)

    return target


def _metric(name: str):
    def ev(outputs: dict) -> dict:
        v = (outputs.get("metrics") or {}).get(name)
        return {"key": name, "score": v}
    ev.__name__ = name
    return ev


# Rule-based metric columns: they read the recorded numbers, not LangSmith's.
METRIC_EVALUATORS = [_metric(k) for k in
                     ("tokens_billed", "n_searches", "latency_s", "answer_chars")]
QUALITY_EVALUATORS = [evalkit.outcome_keyword, evalkit.tool_correctness,
                      evalkit.trajectory_no_waste]
