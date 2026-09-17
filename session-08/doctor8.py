#!/usr/bin/env python
"""Session 8 student self-check. Run this FIRST.

    cd session-08
    python doctor8.py

Prints GO or NO-GO and, for anything that fails, the one line that fixes it. Costs
nothing and needs no API key -- the key is checked last and only warned about, because
you need it for the hands-on and for nothing before that.

There are exactly three things that go wrong after a repo reorganisation: you are in
the wrong folder, a file did not arrive, or your key is not loaded. This tells you
which, in about a second, instead of you reading a traceback.
"""

from __future__ import annotations

import os
import sys

FAILS: list[str] = []
WARNS: list[str] = []


def ok(label: str) -> None:
    print(f"  ok    {label}")


def bad(label: str, fix: str) -> None:
    FAILS.append(label)
    print(f"  FAIL  {label}\n        FIX: {fix}")


def warn(label: str, fix: str) -> None:
    WARNS.append(label)
    print(f"  warn  {label}\n        {fix}")


print("Session 8 doctor\n")

# ---------------------------------------------------------------- 1. the folder
here = os.path.basename(os.getcwd())
if here == "session-08":
    ok("you are in session-08/")
else:
    bad(f"you are in {here!r}, not session-08",
        "cd into the repo, then:  cd session-08 && python doctor8.py")
    raise SystemExit(1)

# ---------------------------------------------------------------- 2. the bootstrap
try:
    import _path  # noqa: F401
    ok(f"_path found the repo root ({_path.ROOT.name}/)")
except Exception as exc:                                   # noqa: BLE001
    bad(f"_path.py did not import ({type(exc).__name__})",
        "bash update.sh   — _path.py is missing, so the pull did not finish")
    raise SystemExit(1)

# ---------------------------------------------------------------- 3. the imports
for mod, where in (("evalkit", "shared/"), ("plant7", "plant/"),
                   ("coord_eval7", "plant/"), ("delegation_rows7", "plant/"),
                   ("judge8", "session-08/"), ("judge_seeds8", "session-08/")):
    try:
        __import__(mod)
        ok(f"import {mod}  (from {where})")
    except Exception as exc:                               # noqa: BLE001
        bad(f"import {mod} failed: {type(exc).__name__}: {str(exc)[:60]}",
            "bash update.sh   — then re-run this. If it still fails, message me.")

# ---------------------------------------------------------------- 4. the data files
try:
    runs7 = _path.session(7) / "runs7.json"
    if runs7.exists():
        ok(f"session-07/runs7.json is here ({runs7.stat().st_size // 1024} KB)")
    else:
        bad("session-07/runs7.json is missing",
            "bash update.sh   — today's judges are calibrated against it")
    live = os.path.exists("judge_runs8.json")
    (ok if live else warn)(
        "judge_runs8.json (the instructor's live verdicts)",
        "bash update.sh   — without it the notebook falls back to stub numbers"
    ) if not live else ok("judge_runs8.json (the instructor's live verdicts)")
except Exception as exc:                                   # noqa: BLE001
    bad(f"could not check the data files: {exc}", "bash update.sh")

# ---------------------------------------------------------------- 5. your file
if not os.path.exists("my_attack8.py"):
    bad("my_attack8.py is missing", "bash update.sh")
else:
    src = open("my_attack8.py", encoding="utf-8").read()
    ok("my_attack8.py is here  <- this is the file you edit today")
    if "TODO" in src:
        ok("it still has its TODOs (expected before class)")

# ---------------------------------------------------------------- 6. the screener
try:
    import judge8
    import judge_seeds8 as seeds8
    arms = seeds8.build()
    res = judge8.run_all(arms["healthy"], None, stub=True)
    if len(res) == 4:
        ok(f"the free stub judge runs ({len(arms)} report arms built)")
    else:
        bad("the stub judge returned the wrong shape", "message me")
except Exception as exc:                                   # noqa: BLE001
    bad(f"the stub judge failed: {type(exc).__name__}: {str(exc)[:70]}",
        "bash update.sh, then re-run this")

# ---------------------------------------------------------------- 7. your key
try:
    from dotenv import load_dotenv
    load_dotenv(_path.ROOT / ".env")
except ImportError:
    pass
provider = os.environ.get("COURSE_PROVIDER", "anthropic")
keyname = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
           "google": "GOOGLE_API_KEY"}.get(provider, "ANTHROPIC_API_KEY")
if os.environ.get(keyname):
    ok(f"{keyname} is loaded (provider: {provider})")
else:
    warn(f"{keyname} is NOT loaded (provider: {provider})",
         "Nothing before the hands-on needs it. For the hands-on: check that .env "
         "exists at the repo root and has your key in it. cp .env.example .env")

# ---------------------------------------------------------------- verdict
print()
if FAILS:
    print(f"NO-GO — {len(FAILS)} problem(s). Fix the first one and run this again.")
    raise SystemExit(1)
if WARNS:
    print("GO for the session. One warning above — it only matters for the hands-on.")
else:
    print("GO. Everything today needs is here, and you can run the whole notebook "
          "without spending anything.")
