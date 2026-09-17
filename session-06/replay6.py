"""
Session 6 — Hands-on 2. Put the instructor's 180 runs into YOUR LangSmith.

    python replay6.py              # push the v1 pool if you lack it, then replay 3 versions
    python replay6.py --dry        # check runs6.json + your .env, touch nothing

WHY A REPLAY
------------
The instructor ran 3 versions x 12 rows x 5 repetitions last night: 180 agent
runs, ~360 searches. Those experiments live in the instructor's workspace and
your key cannot read them. So the runs ship as runs6.json, and this script
feeds them back through `client.evaluate` with a target that RETURNS a saved
output instead of calling a model. Zero model cost, zero Tavily, and three
real experiments in your own workspace to open, sort and compare.

THE TRAP -- read before you open the UI
---------------------------------------
LangSmith will show ~0.0s latency and 0 tokens on every replayed run, because
nothing was called. Those columns describe the REPLAY, not the agent. The true
numbers were recorded when the agent ran, and the metric evaluators copy them
onto the experiment as feedback: read `tokens_billed`, `n_searches`,
`latency_s` in the feedback columns, never the built-in ones.
"""

from __future__ import annotations


import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first
import argparse
import json
import os
import sys


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()     # push_pool.py forgot this once; nothing got pushed.
    except ImportError:
        print("(python-dotenv not installed — relying on the ambient environment)")

    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs6.json")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--versions", nargs="*", default=["healthy", "redundant", "concise"])
    args = ap.parse_args()

    if not os.path.exists(args.runs):
        print(f"  {args.runs} not found. `git pull` — it ships with the repo.")
        return 1
    with open(args.runs) as fh:
        blob = json.load(fh)
    runs, reps = blob["runs"], blob["reps"]
    print(f"  {args.runs}: {len(runs)} runs, {reps} reps, made {blob.get('generated')} "
          f"on {blob['dataset']}@{blob['tag']}")

    if not os.environ.get("LANGSMITH_API_KEY"):
        print("  LANGSMITH_API_KEY not set — is .env in this folder? Everything after "
              "this block works from runs6.json alone; LangSmith is optional today.")
        return 1
    if args.dry:
        print("  --dry: key present, file readable. Nothing touched.")
        return 0

    import evalkit
    import seeds6
    evalkit.env_setup(seeds6.PROJECT)
    from langsmith import Client
    client = Client()

    # 1. The regression set. You probably do not have it: Session 5's push
    #    step failed silently for anyone whose key lived only in .env.
    if not client.has_dataset(dataset_name=seeds6.POOL):
        print(f"  {seeds6.POOL!r} not in your workspace — pushing and tagging it now")
        import subprocess
        rc = subprocess.call([sys.executable, "push_pool.py", "instructor_pool.py",
                              "--tag", seeds6.POOL_TAG])
        if rc:
            return rc
    examples = list(client.list_examples(dataset_name=seeds6.POOL, as_of=seeds6.POOL_TAG))
    print(f"  {seeds6.POOL}@{seeds6.POOL_TAG}: {len(examples)} examples")
    missing = {e.inputs["question"] for e in examples} - {r["question"] for r in runs}
    if missing:
        print(f"  {len(missing)} question(s) in your dataset have no saved run — your "
              "pool is not the instructor's v1. Stop and tell the instructor.")
        return 1

    # 2. One experiment per version. Same examples, same tag, same evaluators.
    for v in args.versions:
        res = client.evaluate(
            seeds6.make_replay_target(runs, v), data=examples,
            evaluators=seeds6.QUALITY_EVALUATORS + seeds6.METRIC_EVALUATORS,
            num_repetitions=reps, max_concurrency=4,
            experiment_prefix=f"s6-replay-{v}",
            metadata={"version": v, "replay_of": blob["experiments"].get(v),
                      "dataset_tag": seeds6.POOL_TAG})
        print(f"  {v:<10} -> {res.experiment_name}")

    print("\n  Open LangSmith -> Datasets -> s5-class-benchmark-pool -> Experiments.\n"
          "  Tick two experiments -> Compare. Then read the FEEDBACK columns, not the\n"
          "  built-in latency and tokens (see the trap at the top of this file).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
