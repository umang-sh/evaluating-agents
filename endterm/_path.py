"""Put the repo's shared folders on sys.path. Import this FIRST, before any course module.

    import _path  # noqa: F401

WHY THIS FILE EXISTS
--------------------
The repo is organised by session so you can find things. Python is not: when you run
`python session-08/preflight8.py`, Python puts **session-08/** on `sys.path`, not the repo
root — so `import evalkit` would fail even though evalkit.py is sitting in `shared/`.

This file finds the repo root by walking up until it sees `requirements.txt`, then prepends
`shared/` and `plant/`. One line at the top of a script, one line in a notebook, and every
import in the course works from anywhere.

WHAT IS IN EACH FOLDER, AND THE RULE THAT PUT IT THERE
------------------------------------------------------
    shared/   modules imported by MORE THAN ONE session — measured, not guessed:
              evalkit (sessions 4,5,6,7,8) · paired (6,7) · seeds (4,5,6) ·
              eval_dataset (4,5) · benchmark_rows · probes · check_env
    plant/    Halvard Works: the fictional plant and its four agents. Sessions 7-12 all
              build on it, so it is not "session 7's code" any more.
    session-NN/  everything only that session touches, including its notebook, its
              data files, and the one file you edit.

If you add a module and a second session starts importing it, move it to shared/. A module
in one session's folder that another session imports is the thing this layout exists to
prevent.
"""

from __future__ import annotations

import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
ROOT: Path = next((p for p in (_here, *_here.parents) if (p / "requirements.txt").exists()),
                  _here.parent)

for _sub in ("shared", "plant"):
    _p = str(ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

# The repo root too, so `import _path` keeps working from a sibling folder and so anything
# still living at the root stays importable.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def session(n: int | str) -> Path:
    """Path to another session's folder — for the data files that cross sessions.

    Session 8 calibrates its judges against Session 7's saved runs, so it needs
    `_path.session(7) / "runs7.json"` rather than a bare filename. Spelling it out is
    deliberate: a cross-session dependency should be visible in the code that has it.
    """
    return ROOT / f"session-{int(n):02d}"
