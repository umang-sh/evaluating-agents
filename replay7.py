#!/usr/bin/env python
"""
Session 7 — put the instructor's runs into YOUR LangSmith.

    python replay7.py --dry     # check runs7.json and your key, touch nothing
    python replay7.py           # create the dataset if needed, replay every arm

WHY A REPLAY
------------
The instructor ran the four-agent pipeline, the four seeded coordination
failures and the single-agent control across 12 rows, several times each. Those
experiments live in the instructor's workspace and your key cannot read them.
So the runs ship as runs7.json and this script feeds them back through
`client.evaluate` with a target that RETURNS a saved output instead of calling
a model. Zero model cost, zero Tavily, real experiments in your own workspace.

THE TRAP — read this before you open the UI (conventions #20)
--------------------------------------------------------------
LangSmith will show 0 s latency and 0 tokens on every replayed run, because
nothing was called. Those columns describe the REPLAY, not the agents. The real
numbers were recorded when the agents ran and are copied onto the experiment as
feedback: read `tokens_billed`, `latency_s`, `n_agent_calls` in the FEEDBACK
columns, never the built-in ones.

AND THE SECOND TRAP (conventions #19)
--------------------------------------
The Compare view colours every column as though higher is better, and shows no
intervals at all. A slower, costlier arm renders green. Do not read a winner
off that screen. The interval is computed by paired.py, in the notebook.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

DATASET = "s7-halvard-delegation"


# Which saved runs each replayed experiment is allowed to draw on.
#
# `pipeline` appears in TWO phases and they mean different things: the stub
# seed matrix (the control the four seeded arms are compared against) and the
# live comparison (the arm `single` is compared against). Pooling them is not
# a rounding error -- the stub runs carry 0 tokens and 0.01 s, so a replayed
# `pipeline` experiment drawing on them renders a four-agent pipeline as FREE
# and INSTANT next to the single agent. Every arm below is pinned to one phase.
ARMS = [
    # label pushed to LangSmith   version in runs7.json     phase
    ("pipeline",                  "pipeline",               "comparison"),
    ("single",                    "single",                 "comparison"),
    ("pipeline-healthy",          "pipeline",               "matrix"),
    ("pipeline-wrong_delegation", "pipeline:wrong_delegation", "matrix"),
    ("pipeline-lost_handoff",     "pipeline:lost_handoff",  "matrix"),
    ("pipeline-redundant_call",   "pipeline:redundant_call", "matrix"),
    ("pipeline-delegation_loop",  "pipeline:delegation_loop", "matrix"),
]


def make_replay_target(runs: list[dict], version: str, phase: str):
    """Return saved outputs for this arm AND phase, matched by REQUEST TEXT.

    Matched by text, never by position: two experiments do not return their
    rows in the same order, and a positional lookup would pair unrelated
    requests and still produce a perfectly plausible table (paired.py carries
    the same warning for the same reason).
    """
    saved: dict[str, list[dict]] = {}
    for r in runs:
        if (r.get("version") == version and r.get("phase") == phase
                and not r.get("error")):
            saved.setdefault(r["question"], []).append(r["outputs"])
    counters: dict[str, int] = {}

    def target(inputs: dict) -> dict:
        q = inputs["request"]
        pool = saved.get(q)
        if not pool:
            return {"answer": "", "agent_calls": [], "handoffs": [],
                    "plan": [], "tail": {}, "metrics": {},
                    "replay_error": f"no saved run for {q[:40]!r} in arm {version!r}"}
        i = counters.get(q, 0)
        counters[q] = i + 1
        return pool[i % len(pool)]

    return target


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()      # push_pool.py forgot this once and pushed nothing
    except ImportError:
        print("(python-dotenv not installed — relying on the ambient environment)")

    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs7.json")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--arms", nargs="*", default=None,
                    help="labels from ARMS; default: all of them")
    args = ap.parse_args()

    if not os.path.exists(args.runs):
        print(f"  {args.runs} not found. `git pull` — it ships with the repo.")
        return 1
    blob = json.load(open(args.runs))
    runs = blob["runs"]
    if any(not r.get("phase") for r in runs):
        print(f"  {args.runs} has untagged runs. Run `python phase_runs7.py` "
              f"first — replaying an unphased file mixes stub and live runs "
              f"into one experiment. Refusing.")
        return 1
    specs = [a for a in ARMS if args.arms is None or a[0] in args.arms]
    have = {(r["version"], r["phase"]) for r in runs}
    specs = [a for a in specs if (a[1], a[2]) in have]
    print(f"  {args.runs}: {len(runs)} runs, made {blob.get('generated')}")
    for lab, ver, ph in specs:
        n = sum(1 for r in runs if r["version"] == ver and r["phase"] == ph)
        print(f"    {lab:28s} <- {ver} / phase={ph}  ({n} runs)")

    if not os.environ.get("LANGSMITH_API_KEY"):
        print("  LANGSMITH_API_KEY not set — is .env in this folder? Everything "
              "after this block works from runs7.json alone; LangSmith is optional.")
        return 1
    if args.dry:
        print("  --dry: key present, file readable. Nothing touched.")
        return 0

    import bench7
    import coord_eval7
    import evalkit
    from delegation_rows7 import ROWS
    evalkit.env_setup(bench7.PROJECT)
    from langsmith import Client
    client = Client()

    if not client.has_dataset(dataset_name=DATASET):
        print(f"  {DATASET!r} not in your workspace — creating it from the 12 rows")
        ds = client.create_dataset(dataset_name=DATASET,
                                   description="Halvard Works delegation rows, Session 7")
        client.create_examples(
            dataset_id=ds.id,
            inputs=[{"request": r["request"], "row_id": r["id"]} for r in ROWS],
            outputs=[{k: r[k] for k in
                      ("expected_agents", "expected_order", "forbidden_agents",
                       "expected_calls", "handoff_facts", "expected_outcome")}
                     for r in ROWS])
    examples = list(client.list_examples(dataset_name=DATASET))
    print(f"  {DATASET}: {len(examples)} examples")

    def _url(obj):
        """Ask the SDK for the link; never construct one.

        The workspace id is part of every LangSmith URL and it is different for
        every student, so a hard-coded link in the repo would be wrong for all
        of them. If the SDK does not hand one over, print the click path
        instead of a guess.
        """
        for attr in ("url", "session_url"):
            u = getattr(obj, attr, None)
            if u:
                return str(u)
        return None

    try:
        ds_url = _url(client.read_dataset(dataset_name=DATASET))
    except Exception:
        ds_url = None

    def metric(name):
        def fn(outputs: dict, **_):
            v = (outputs.get("metrics") or {}).get(name)
            return {"key": name, "score": None if v is None else float(v)}
        fn.__name__ = name
        return fn

    evaluators = list(coord_eval7.OFFLINE) + [
        metric("tokens_billed"), metric("latency_s"), metric("n_agent_calls"),
        metric("n_tool_calls")]

    for lab, ver, ph in specs:
        res = client.evaluate(
            make_replay_target(runs, ver, ph), data=examples,
            evaluators=evaluators, max_concurrency=4,
            experiment_prefix=f"s7-replay-{lab}",
            metadata={"arm": ver, "phase": ph,
                      "replay_of": blob.get("generated")})
        link = None
        try:
            link = _url(client.read_project(project_name=res.experiment_name))
        except Exception:
            pass
        print(f"  {lab:<28} -> {res.experiment_name}"
              + (f"\n      {link}" if link else ""))

    print("\n  YOUR dataset, with all seven experiments on it:")
    print("    " + (ds_url or
                    "smith.langchain.com -> Datasets & Testing -> " + DATASET
                    + " -> Experiments   (the link is workspace-specific, so it "
                      "is not in the repo)"))
    print("\n  LangSmith -> Datasets -> " + DATASET + " -> Experiments.\n"
          "  Two comparisons live there, and they do not mix:\n"
          "    s7-replay-pipeline      vs  s7-replay-single       (live, slide 20)\n"
          "    s7-replay-pipeline-healthy vs the four seeded arms (stub, slide 15)\n"
          "  Read the FEEDBACK columns. Do not read a winner off the Compare view.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
