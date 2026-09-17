"""
Session 6 — Hands-on 1. YOUR success criteria, written BEFORE you see a number.

    python criteria6.py            # checks this file is filled in and sane

Three things to fill in. Every TODO must go.

  1. SUCCESS_BAR    — what an agent must reach to be production-ready at all.
  2. ACT_IF         — the smallest change you would ACT on. Not the smallest one
                      you could detect: the smallest one you would care about.
                      A 2% token rise is real and nobody ships a rollback for it.
  3. PREDICT        — for each candidate, which way you think each metric moves:
                      "HIGHER", "LOWER" or "TIE". Written now, scored in Hands-on 5.

Why before: a threshold chosen after you have seen the result is not a
threshold, it is a caption. Session 5 wrote `predict` before the screener ran
for the same reason.

TOKEN DEFINITION, in force since Session 3 -- tokens_billed = output tokens +
UNCACHED input tokens. Cached reads excluded, reasoning in its own column.
"""

AUTHOR = "TODO"          # your name(s). regress6.py and report6.py print it.

# ---- 1. The bar. pass rate (0..1) over every run, every row. ---------------
SUCCESS_BAR = {
    "outcome_keyword": "TODO",       # e.g. 0.95 — right answer
    "tool_correctness": "TODO",      # e.g. 0.95 — right tool
    "trajectory_no_waste": "TODO",   # e.g. 0.90 — no duplicate / runaway calls
}

# ---- 2. The smallest change you would act on, in % of the incumbent. -------
#         For pass rates, in percentage POINTS (5 = five points).
ACT_IF = {
    "tokens_billed": "TODO",   # e.g. 10
    "n_searches": "TODO",      # e.g. 20
    "latency_s": "TODO",       # e.g. 20
    "outcome_keyword": "TODO", # e.g. 5  (points)
}

# ---- 3. Your prediction. HIGHER / LOWER / TIE, versus healthy. -------------
#   redundant: "run every search twice"        concise: "Answer in 2 sentences."
PREDICT = {
    "redundant": {"tokens_billed": "TODO", "n_searches": "TODO",
                  "latency_s": "TODO", "outcome_keyword": "TODO"},
    "concise":   {"tokens_billed": "TODO", "n_searches": "TODO",
                  "latency_s": "TODO", "outcome_keyword": "TODO"},
}


# ==========================================================================
# Below: the checker. Nothing to edit.
# ==========================================================================

def problems() -> tuple[list[str], list[str]]:
    out, warn = [], []
    if "TODO" in str(AUTHOR):
        out.append("AUTHOR is still TODO")
    for k, v in SUCCESS_BAR.items():
        if not isinstance(v, (int, float)) or not 0 < v <= 1:
            out.append(f"SUCCESS_BAR[{k!r}] = {v!r} — want a number between 0 and 1")
    for k, v in ACT_IF.items():
        if not isinstance(v, (int, float)) or v <= 0:
            out.append(f"ACT_IF[{k!r}] = {v!r} — want a positive number")
        elif v < 3 and k != "outcome_keyword":
            warn.append(f"ACT_IF[{k!r}] = {v} — would you really roll back a release "
                        f"for {v}%? Allowed; be ready to say why.")
    for cand, d in PREDICT.items():
        for m, v in d.items():
            if v not in ("HIGHER", "LOWER", "TIE"):
                out.append(f"PREDICT[{cand!r}][{m!r}] = {v!r} — HIGHER / LOWER / TIE")
    return out, warn


if __name__ == "__main__":
    p, w = problems()
    for x in w:
        print("  note:", x)
    if p:
        print(f"  {len(p)} thing(s) to fix:")
        for x in p:
            print("   -", x)
        raise SystemExit(1)
    print(f"  criteria6.py OK — {AUTHOR}. Your predictions are locked in; "
          "Hands-on 5 scores them.")
