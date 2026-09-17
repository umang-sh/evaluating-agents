"""
The pool that runs with ZERO student submissions.

    python push_pool.py instructor_pool.py --dry
    python push_pool.py instructor_pool.py --tag v1

RULE, established when Session 3's opener had to be rebuilt from scratch: an
opener runs on instructor data. Student submissions may improve a block; they
may never be the thing a block stands on. The class pool is the better version
of this block and it is what the room will remember -- but if six people
submitted instead of forty, this file is what gets pushed and tagged, the
versioning demo is identical, and nobody in the room can tell.
"""

from __future__ import annotations


import _path  # noqa: F401  -- puts shared/ and plant/ on sys.path; must be first
from eval_dataset import EXAMPLES
from seeds5 import INJECTION_ROW
import benchmark_rows

AUTHOR = "instructor"


def rows_for_pool() -> list[dict]:
    rows = list(EXAMPLES) + list(benchmark_rows.WORKED) + [INJECTION_ROW]
    out = []
    for r in rows:
        row = dict(r)
        row["metadata"] = dict(row.get("metadata", {}))
        row["metadata"].setdefault("author", AUTHOR)
        row["metadata"]["source"] = "session5-instructor-pool"
        out.append(row)
    return out
