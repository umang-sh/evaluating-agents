"""
Session 11 -- three short demos of what LangGraph itself does with state.
Each prints a result you can predict BEFORE you run it. Free, no model.

    reducer_demo()     a list with no reducer vs a list with a reducer
    recursion_demo()   a loop with no stop condition: what does LangGraph do?
    interrupt_demo()   pause a graph for a human, save it, resume it later
                       (instructor demo -- the approval step done for real)
"""
from __future__ import annotations

import _path  # noqa: F401
import operator
import time
from typing import Annotated, TypedDict


def reducer_demo():
    """Two nodes each write ["x"] and then ["y"] into two lists."""
    from langgraph.graph import END, START, StateGraph

    class S(TypedDict):
        no_reducer: list
        with_reducer: Annotated[list, operator.add]

    g = StateGraph(S)
    g.add_node("first", lambda s: {"no_reducer": ["first"], "with_reducer": ["first"]})
    g.add_node("second", lambda s: {"no_reducer": ["second"], "with_reducer": ["second"]})
    g.add_edge(START, "first"); g.add_edge("first", "second"); g.add_edge("second", END)
    out = g.compile().invoke({"no_reducer": [], "with_reducer": []})
    print("no_reducer   :", out["no_reducer"], "   <- the last writer wins; 'first' is gone")
    print("with_reducer :", out["with_reducer"], "   <- operator.add appended both")
    return out


def recursion_demo(limit: int | None = None):
    """A node that points back at itself, forever. No MAX_STEPS, no stop condition."""
    from langgraph.errors import GraphRecursionError
    from langgraph.graph import START, StateGraph

    class S(TypedDict):
        n: int

    g = StateGraph(S)
    g.add_node("again", lambda s: {"n": s["n"] + 1})
    g.add_edge(START, "again"); g.add_edge("again", "again")
    app = g.compile()
    cfg = {"recursion_limit": limit} if limit else {}
    t0 = time.perf_counter()
    try:
        app.invoke({"n": 0}, cfg)
        print("finished?!")
    except GraphRecursionError as e:
        first = str(e).split(".")[0]
        print(f"GraphRecursionError after {time.perf_counter() - t0:.1f}s: {first}.")
        print("LangGraph DID stop it, and it said so loudly. But look at the number:"
              " each of those steps could have been an LLM call.")
    return app


def interrupt_demo(decision: str = "yes"):
    """The approval step done properly: the graph PAUSES, is saved under a thread id,
    and resumes when a person answers. Needs a checkpointer."""
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt

    class S(TypedDict):
        work_order: str
        status: str

    def ask_engineer(s):
        answer = interrupt({"question": f"Approve {s['work_order']}?"})
        return {"status": "APPROVED" if answer == "yes" else "REJECTED"}

    g = StateGraph(S)
    g.add_node("ask_engineer", ask_engineer)
    g.add_edge(START, "ask_engineer"); g.add_edge("ask_engineer", END)
    app = g.compile(checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": "WO-HW-001"}}

    first = app.invoke({"work_order": "WO-HW-001", "status": "AWAITING_APPROVAL"}, cfg)
    print("1. graph paused. It is asking:", first["__interrupt__"][0].value)
    print("2. saved under thread", cfg["configurable"]["thread_id"],
          "- next node waiting to run:", app.get_state(cfg).next)
    done = app.invoke(Command(resume=decision), cfg)
    print(f"3. engineer answered {decision!r} -> status:", done["status"])
    return done


if __name__ == "__main__":
    reducer_demo(); print(); recursion_demo(); print(); interrupt_demo()
