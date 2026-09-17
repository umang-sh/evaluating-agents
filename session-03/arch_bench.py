"""
Session 3 — architecture benchmark harness.
Evaluating AI Agents. Verified against the course pin set (Aug 2026).

Three implementations of the SAME research agent, differing on exactly one axis:

    who decides what happens next — the model, or the code?

    react     : model decides. create_agent (a compiled StateGraph).
    toolcall  : model decides. Hand-rolled bind_tools while-loop, no graph.
    workflow  : CODE decides. Fixed plan -> search x N -> synthesize pipeline.

Everything else is held constant: same tools, same prompt, same model, same
reasoning effort. If a number differs between rows, the architecture is the
only thing that could have caused it.

Gotchas applied (see claude/COURSE_CONVENTIONS.md):
  #1  no temperature (rejected by current models)
  #2  use .text, never .content
  #5  LANGSMITH_PROJECT set before anything reads it -> see env_setup()
  #6  wait_for_all_tracers() + Client().flush() before reading the trace
  #8  count OUTERMOST tool spans only (LangGraph emits two per tool call)
  #9  never read a graph root's `outputs` as the answer
  #10 tool outputs are wrapped, sometimes twice
"""

from __future__ import annotations

import os
import time
import json
import warnings
from dataclasses import dataclass, asdict, field
from operator import add
from typing import Annotated, Any, Callable, Literal
from typing_extensions import TypedDict

# --------------------------------------------------------------------------
# 0.  Environment.  Gotcha #5: this MUST run before anything imports/reads
#     langsmith, or traces land silently in `default` with no error at all.
# --------------------------------------------------------------------------

# Bump this whenever this file changes. The notebook asserts on it, so a stale
# module cached in a running kernel fails loudly instead of silently reporting
# the previous version's numbers.
__version__ = "s3-2026-08-30j"

PROJECT = "session-3-architectures"


def env_setup(project: str = PROJECT) -> str:
    """Set the LangSmith project and bust the lru_cache. Returns the resolved name."""
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = project

    import langsmith.utils as ls_utils

    ls_utils.get_tracer_project.cache_clear()
    ls_utils.get_env_var.cache_clear()
    resolved = ls_utils.get_tracer_project()
    if resolved != project:
        raise RuntimeError(
            f"LangSmith project resolved to {resolved!r}, expected {project!r}. "
            "Something read the project before env_setup() ran. Restart the runtime."
        )
    return resolved


# --------------------------------------------------------------------------
# 1.  Provider handling.  One CHAT alias; one variable swaps provider.
# --------------------------------------------------------------------------

Provider = Literal["anthropic", "openai", "google"]

MODEL_IDS: dict[Provider, str] = {
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-5.6-terra",
    "google": "gemini-3.7-flash",
}

# We PIN reasoning effort at the provider floor and hold it constant across all
# three architectures. We are not measuring reasoning effort. As of
# langchain-core >= 1.5.2 `reasoning_effort` is a STANDARD parameter supported by
# ChatAnthropic / ChatOpenAI / ChatGoogleGenerativeAI — but LangChain standardised
# the *input*, not the economics, latency or behaviour behind it. Pinning at a
# known floor is defensible; "normalising" across providers is not.
EFFORT_FLOOR = "low"


def make_chat(provider: Provider = "anthropic", effort: str | None = EFFORT_FLOOR):
    """Build the chat model for a provider. Falls back cleanly if effort is rejected."""
    model = MODEL_IDS[provider]

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic as Cls
    elif provider == "openai":
        from langchain_openai import ChatOpenAI as Cls
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI as Cls
    else:
        raise ValueError(f"unknown provider {provider!r}")

    # NOTE: no `temperature`. Gotcha #1 — current models reject it outright, and
    # that is why you cannot make an agent deterministic.
    if effort is None:
        return Cls(model=model), False
    try:
        chat = Cls(model=model, reasoning_effort=effort)
        # Constructing is not proving. preflight3.py sends a real request.
        return chat, True
    except Exception:
        return Cls(model=model), False


PROVIDER: Provider = os.environ.get("COURSE_PROVIDER", "anthropic")  # type: ignore[assignment]
CHAT, EFFORT_PINNED = make_chat(PROVIDER)


# --------------------------------------------------------------------------
# 2.  Tools.  Shared by all three architectures — held constant.
#     Gotcha: @tool requires a docstring, or ValueError at decoration time.
# --------------------------------------------------------------------------

from langchain_core.tools import tool  # noqa: E402
from langchain_tavily import TavilySearch  # noqa: E402

_tavily = TavilySearch(max_results=3)


@tool
def web_search(query: str) -> str:
    """Search the web for current information. Returns up to 3 results."""
    return json.dumps(_tavily.invoke({"query": query}))


@tool
def calculator(expression: str) -> str:
    """Evaluate a simple arithmetic expression, e.g. '1200 * 365'."""
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        return "error: unsupported characters"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))  # noqa: S307
    except Exception as exc:
        return f"error: {exc}"


BASE_TOOLS = [web_search, calculator]

SYSTEM_PROMPT = (
    "You are a research assistant. Answer the question using the tools available. "
    "Search only as many times as you need. Cite the source of any fact you state. "
    "Finish with a single short paragraph answering the question directly."
)


# --------------------------------------------------------------------------
# 3.  Three architectures.
# --------------------------------------------------------------------------

def build_react(chat=None, tools=None):
    """MODEL DECIDES. create_agent — which compiles to a StateGraph.

    This is the Session 1 endpoint. ReAct, tool-calling and 'graph-based' are
    all this one object described from three angles.
    """
    from langchain.agents import create_agent

    return create_agent(
        model=chat or CHAT,
        tools=tools or BASE_TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )


def build_toolcall(chat=None, tools=None, max_steps: int = 8):
    """MODEL DECIDES. Hand-rolled bind_tools loop. No graph, no framework.

    This is what every tutorial calls 'a tool calling agent'. Watch the trace:
    it *looks* different (no graph nodes, just LLM and tool spans) but the
    decision structure is identical to build_react. Different picture, same
    architecture.

    NOTE the @traceable. Without a parent span, every bound.invoke() and every
    tool.invoke() is its OWN root run in LangSmith — there is no trace to find,
    and the benchmark reads whichever happened to run last (observed in
    pre-flight: 0 tools, 0 tokens, no cost). create_agent gets its root for free
    because LangGraph declares one. A hand-rolled loop has to declare its own.
    Worth saying out loud in class: the framework was buying you observability,
    not just control flow.
    """
    from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
    from langsmith import traceable

    chat = chat or CHAT
    tools = tools or BASE_TOOLS
    by_name = {t.name: t for t in tools}
    bound = chat.bind_tools(tools)

    @traceable(name="ToolCallingAgent", run_type="chain")
    def _loop(question: str) -> dict:
        msgs = [SystemMessage(SYSTEM_PROMPT), HumanMessage(question)]
        for _ in range(max_steps):
            ai = bound.invoke(msgs)
            msgs.append(ai)
            if not ai.tool_calls:
                break
            for tc in ai.tool_calls:
                out = by_name[tc["name"]].invoke(tc["args"])
                msgs.append(ToolMessage(content=str(out), tool_call_id=tc["id"]))
        return {"messages": msgs}

    class _Wrapped:
        def invoke(self, payload: dict) -> dict:
            q = payload["messages"][0]
            return _loop(q if isinstance(q, str) else q.content)

    return _Wrapped()


# --- the workflow, with the one edge students wire live -------------------

FIXED_SEARCHES = 3


class WState(TypedDict):
    """Workflow state.

    MUST live at module level. `from __future__ import annotations` turns every
    annotation into a string, and LangGraph resolves node signatures with
    get_type_hints() against MODULE globals — so a class (or an `Annotated`)
    defined inside build_workflow is invisible at resolution time and raises
    `NameError: name 'WState' is not defined`. Same root cause as the Annotated
    bug one line above; it simply surfaced one layer later.
    """
    question: str
    queries: list[str]
    results: Annotated[list[str], add]
    answer: str
    done: int


def build_workflow(chat=None, tools=None, searches: int = FIXED_SEARCHES,
                   route_fn: Callable[[dict], str] | None = None):
    """CODE DECIDES. plan -> search (fixed N) -> synthesize.

    The model never chooses how many searches happen. That is the whole point,
    and it is also the staged bottleneck: on a question answerable in one
    search this burns three. On a hard question it beats ReAct, because it
    never re-bills a growing message history.

    `route_fn` is the conditional-edge routing function. In class it arrives as
    a `# TODO` and students write it — that is Hands-on B.
    """
    from langgraph.graph import StateGraph, START, END

    chat = chat or CHAT
    search_tool = (tools or BASE_TOOLS)[0]

    def plan(state: WState) -> dict:
        msg = chat.invoke(
            f"Write exactly {searches} distinct web search queries that together "
            f"answer this question. One per line, no numbering.\n\n{state['question']}"
        )
        qs = [q.strip() for q in msg.text.splitlines() if q.strip()][:searches]
        return {"queries": qs, "done": 0}

    def search(state: WState) -> dict:
        i = state["done"]
        out = search_tool.invoke({"query": state["queries"][i]})
        return {"results": [str(out)], "done": i + 1}

    def synthesize(state: WState) -> dict:
        joined = "\n\n---\n\n".join(state["results"])
        msg = chat.invoke(
            f"{SYSTEM_PROMPT}\n\nQuestion: {state['question']}\n\n"
            f"Search results:\n{joined}\n\nAnswer:"
        )
        return {"answer": msg.text}  # gotcha #2: .text, never .content

    def _default_route(state: WState) -> str:
        return "search" if state["done"] < len(state["queries"]) else "synthesize"

    g = StateGraph(WState)
    g.add_node("plan", plan)
    g.add_node("search", search)
    g.add_node("synthesize", synthesize)
    g.add_edge(START, "plan")
    g.add_edge("plan", "search")
    g.add_conditional_edges(
        "search",
        route_fn or _default_route,
        {"search": "search", "synthesize": "synthesize"},
    )
    g.add_edge("synthesize", END)
    compiled = g.compile()

    class _Wrapped:
        graph = compiled

        def invoke(self, payload: dict) -> dict:
            q = payload["messages"][0]
            q = q if isinstance(q, str) else q.content
            return compiled.invoke({"question": q, "queries": [], "results": [],
                                    "answer": "", "done": 0})

    return _Wrapped()


ARCHITECTURES: dict[str, Callable] = {
    "react": build_react,
    "toolcall": build_toolcall,
    "workflow": build_workflow,
}


# --------------------------------------------------------------------------
# 4.  Trace reading.  This is the highest-risk code in the session — a
#     double-counted tool span silently corrupts every number in the table.
# --------------------------------------------------------------------------

def walk_tool_spans(run, in_tool: bool = False, acc: list | None = None) -> list:
    """Collect OUTERMOST tool spans only.

    Gotcha #8: LangGraph emits TWO spans per tool call — the tools-node span and
    the @tool function's own span nested inside it, same name, same arguments.
    Count both and every single-search run looks like it issued a duplicate
    query, and you get nonsense 'sibling latency differs 2798x' findings.
    """
    acc = [] if acc is None else acc
    if run.run_type == "tool" and not in_tool:
        acc.append(run)
    for child in (run.child_runs or []):
        walk_tool_spans(child, in_tool or run.run_type == "tool", acc)
    return acc


def count_spans(run) -> int:
    """Total spans in a run tree, root included."""
    return 1 + sum(count_spans(c) for c in (run.child_runs or []))


def unwrap(obj: Any, depth: int = 4) -> Any:
    """Gotcha #10: tool outputs are wrapped, sometimes twice.

    LangSmith may return {"output": {"content": "[]", ...}} — a serialised
    ToolMessage. One unwrap leaves a dict that json.dumps into something
    non-empty, so an empty search never registers as empty.
    """
    for _ in range(depth):
        if isinstance(obj, dict):
            for key in ("output", "content", "result"):
                if key in obj:
                    obj = obj[key]
                    break
            else:
                return obj
        else:
            return obj
    return obj


def dump_tree(run, indent: int = 0, _root: bool = True) -> None:
    """Print a run tree the way LangSmith draws it — for when a count disagrees
    with the UI. Feed it LAST_SERVER_ROOT after a run_one() call.

    tools visible here but the count is 0 -> the WALK is wrong.
    tools not visible here               -> the wrong ROOT was resolved.
    Two different bugs, ten seconds to tell them apart.
    """
    if run is None:
        print("(nothing captured — run run_one() first)")
        return
    if _root:
        print(f"--- run tree ({count_spans(run)} spans) ---")
    print("   " * indent + f"{run.name}  [{run.run_type}]")
    for c in (run.child_runs or []):
        dump_tree(c, indent + 1, _root=False)


# Set by run_one() so you can inspect what the counting actually saw.
LAST_LOCAL_ROOT = None    # first fragment from collect_runs — often NOT the root
LAST_SERVER_ROOT = None   # the assembled tree from LangSmith — walk this one


# Set once we learn this provider's model has no pricing row. Without it, a
# missing pricing row costs ~30s of backoff on EVERY run.
_COST_UNAVAILABLE = False


def find_trace_root(client, since, project: str = PROJECT, attempts: int = 8,
                    base_delay: float = 1.5):
    """Ask LangSmith which run is the root. Do not try to work it out locally.

    Two local approaches were tried and both failed, on real runs:

      * `cb.traced_runs[0]` — the collector returned FOUR parentless fragments
        for one `create_agent(...).invoke(...)`, and [0] was the first LLM call.
        Reading it back gave 667 tokens / $0.0018 / 0 tools for a run whose real
        totals were 2.9K / $0.0073 / 1 tool.
      * grouping those fragments by `trace_id` — they do not share one. Falling
        back to "biggest fragment" then picked the `web_search` tool subtree:
        2 spans, no LLM spans at all, so 0 tokens and no cost.

    The exporter (`LangChainTracer`) keeps the parent links that the collector
    loses — the LangSmith UI shows one assembled trace — so the server knows the
    answer even when the client does not. Ask it: the newest root run in this
    project started at or after `since`.
    """
    for attempt in range(attempts):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")   # list_runs deprecation, #6
                runs = list(client.list_runs(project_name=project, is_root=True,
                                             start_time=since, limit=10))
        except Exception:
            runs = []
        if runs:
            return max(runs, key=lambda r: r.start_time).id
        time.sleep(base_delay * (attempt + 1))
    return None


def read_run_when_ready(client, run_id, *, want_cost: bool = True,
                        min_spans: int = 2, attempts: int = 8,
                        base_delay: float = 1.5):
    """Read a run back from LangSmith once the trace has finished landing.

    Three waits, and the third is the one that quietly corrupts numbers:

      1. **The run may not exist yet.** `wait_for_all_tracers()` + `flush()` push
         it out of the local queue; they do not wait for ingestion. `read_run`
         *raises* `LangSmithNotFoundError` until it lands.
      2. **`total_cost` may not be computed yet.**
      3. **The tree may still be filling in.** LangSmith aggregates a root's
         tokens and cost from children as they arrive, so a mid-ingestion read
         returns a real run with a plausible cost and missing children.

    Readiness test: the span count must be **stable across two consecutive
    reads** and greater than 1. We cannot use the local tree as the expected
    count — see `resolve_trace_root_id`, it is fragmented.

    Returns `(run, note)`. `run` is None only if it never appeared.
    """
    from langsmith.utils import LangSmithNotFoundError

    global _COST_UNAVAILABLE
    if _COST_UNAVAILABLE:
        want_cost = False

    run, note, prev_spans = None, "", -1
    for attempt in range(attempts):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")   # deprecated; conventions #6
                run = client.read_run(str(run_id), load_child_runs=True)
        except LangSmithNotFoundError:
            time.sleep(base_delay * (attempt + 1))
            continue

        spans = count_spans(run)
        # min_spans=2 for an agent run (a root with no children means the wrong
        # root); min_spans=1 for a bare chat.invoke, which legitimately has one.
        settled = spans >= min_spans and spans == prev_spans
        prev_spans = spans
        if settled and (not want_cost or run.total_cost):
            return run, note
        time.sleep(base_delay * (attempt + 1))

    if run is None:
        note = (f"run {run_id} never appeared in LangSmith after {attempts} "
                f"attempts — ingestion lag, a wrong project, or a tracing key "
                f"without write access")
    elif count_spans(run) < min_spans:
        note = (f"root {run_id} came back with no children. If the LangSmith UI "
                f"shows a tree here, the wrong run id was resolved — check "
                f"resolve_trace_root_id against cb.traced_runs")
    elif want_cost and not run.total_cost:
        _COST_UNAVAILABLE = True
        note = ("total_cost is empty for this model — add a custom pricing row in "
                "LangSmith settings (Settings -> Models -> + Model) BEFORE the run; "
                "it does not reprice traces already logged. Skipping the cost wait "
                "on subsequent runs so the benchmark still finishes on time")
    return run, note


def final_text(result: dict) -> str:
    """Gotcha #9: a LangGraph root's `outputs` is the whole message list, not
    the answer, and it carries usage_metadata. Dump it to text for a grounding
    check and you will read prompt-token counts as factual claims."""
    if "answer" in result and result["answer"]:
        return result["answer"]
    msgs = result.get("messages", [])
    if not msgs:
        return ""
    last = msgs[-1]
    return getattr(last, "text", None) or str(getattr(last, "content", last))


# --------------------------------------------------------------------------
# 5.  The benchmark.
# --------------------------------------------------------------------------

@dataclass
class Probe:
    question: str
    must_contain: list[str]       # deterministic grader. Code first, judges later.
    difficulty: Literal["easy", "hard"] = "easy"


@dataclass
class Result:
    arch: str
    provider: str
    question: str
    difficulty: str
    latency_s: float = 0.0
    tool_calls: int = 0
    tokens_in_uncached: int = 0
    tokens_out: int = 0
    tokens_reasoning: int = 0
    tokens_cached_read: int = 0
    cost_usd: float | None = None
    success: bool = False
    spans: int = 0
    run_url: str = ""
    notes: str = ""

    @property
    def tokens_billed(self) -> int:
        """WHAT WE COMPARE: output + uncached input. Cached reads excluded,
        reasoning reported separately. Say this out loud before putting two
        numbers side by side — token accounting is not comparable across
        providers by default."""
        return self.tokens_in_uncached + self.tokens_out


def grade(answer: str, probe: Probe) -> bool:
    """The cheapest grader is the one with no model in it. (Session 1.)"""
    low = answer.lower()
    return all(k.lower() in low for k in probe.must_contain)


def _token_details(run) -> dict:
    """Per-type token counts for one LLM span, from a LangSmith Run.

    A LangSmith `Run` exposes `prompt_tokens` / `completion_tokens` directly;
    those are the reliable fields. `usage_metadata` — when present in `outputs`
    — is what carries the cache-read and reasoning breakdown, so use it to
    refine, never as the only source. (An earlier version read only
    usage_metadata and reported 0 tokens for every span.)
    """
    d = {"in_uncached": 0, "out": 0, "reasoning": 0, "cached_read": 0}

    d["in_uncached"] = int(getattr(run, "prompt_tokens", 0) or 0)
    d["out"] = int(getattr(run, "completion_tokens", 0) or 0)

    outs = run.outputs if isinstance(run.outputs, dict) else {}
    usage = outs.get("usage_metadata") or {}
    if not usage:
        meta = (run.extra or {}).get("metadata", {}) if run.extra else {}
        usage = meta.get("usage_metadata") or {}
    if usage:
        ind = usage.get("input_token_details", {}) or {}
        outd = usage.get("output_token_details", {}) or {}
        d["cached_read"] = int(ind.get("cache_read", 0) or 0)
        total_in = int(usage.get("input_tokens", 0) or 0) or d["in_uncached"]
        d["in_uncached"] = max(total_in - d["cached_read"], 0)
        d["out"] = int(usage.get("output_tokens", 0) or 0) or d["out"]
        d["reasoning"] = int(outd.get("reasoning", 0) or 0)
    return d


def run_one(arch: str, probe: Probe, builder_kwargs: dict | None = None,
            provider: str | None = None, cost_retries: int = 3) -> Result:
    """Run one architecture against one probe and read its trace."""
    from langchain_core.tracers.context import collect_runs
    from langchain_core.tracers.langchain import wait_for_all_tracers
    from langsmith import Client

    agent = ARCHITECTURES[arch](**(builder_kwargs or {}))
    res = Result(arch=arch, provider=provider or PROVIDER,
                 question=probe.question, difficulty=probe.difficulty)

    from datetime import datetime, timezone, timedelta
    _t_start = datetime.now(timezone.utc) - timedelta(seconds=5)

    t0 = time.time()
    with collect_runs() as cb:
        out = agent.invoke({"messages": [probe.question]})
    res.latency_s = round(time.time() - t0, 2)

    # Gotcha #6: traces send on a background thread.
    wait_for_all_tracers()
    client = Client()
    client.flush()

    res.success = grade(final_text(out), probe)

    if not cb.traced_runs:
        res.notes = "no traced run collected"
        return res
    # The LOCAL run tree is complete the instant invoke() returns — collect_runs
    # builds it in-process and _persist_run only fires for a parentless run, so
    # traced_runs[0] IS the true root. Take structure from here, never from the
    # server: the server's copy can be half-ingested and will not say so.
    global LAST_LOCAL_ROOT, LAST_SERVER_ROOT
    LAST_LOCAL_ROOT = cb.traced_runs[0] if cb.traced_runs else None

    # Ask the SERVER which run is the root — see find_trace_root for why the two
    # local approaches both produced confidently wrong numbers.
    root_id = find_trace_root(client, since=_t_start)
    if root_id is None:
        res.notes = ("no root run found in LangSmith for this time window — "
                     "check LANGSMITH_PROJECT and that tracing is enabled")
        return res

    root, note = read_run_when_ready(client, root_id, attempts=cost_retries + 5)
    LAST_SERVER_ROOT = root
    if root is None:
        # Degrade, do not crash. Latency and task success were measured locally
        # and stand; the trace-derived columns are lost.
        res.notes = note
        return res

    res.tool_calls = len(walk_tool_spans(root))
    res.spans = count_spans(root)
    res.cost_usd = float(root.total_cost) if root.total_cost else None
    res.notes = note

    def _sum_llm(r, acc):
        if r.run_type == "llm":
            d = _token_details(r)
            for k in acc:
                acc[k] += d[k]
        for c in (r.child_runs or []):
            _sum_llm(c, acc)
        return acc

    tot = _sum_llm(root, {"in_uncached": 0, "out": 0, "reasoning": 0, "cached_read": 0})
    res.tokens_in_uncached = tot["in_uncached"]
    res.tokens_out = tot["out"]
    res.tokens_reasoning = tot["reasoning"]
    res.tokens_cached_read = tot["cached_read"]

    # Gotcha #7: never hand-build a run URL — the path contains a per-tenant
    # organisation id you cannot guess.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            res.run_url = client.get_run_url(run=root, project_name=PROJECT)
        except Exception:
            res.run_url = ""
    return res


def run_bench(probes: list[Probe], archs: list[str] | None = None,
              builder_kwargs: dict | None = None, provider: str | None = None):
    """Run every architecture against every probe. Returns a pandas DataFrame."""
    import pandas as pd

    rows: list[dict] = []
    for arch in (archs or list(ARCHITECTURES)):
        for probe in probes:
            r = run_one(arch, probe, builder_kwargs, provider)
            d = asdict(r)
            d["tokens_billed"] = r.tokens_billed
            rows.append(d)
            print(f"  {arch:9s} {probe.difficulty:5s} "
                  f"{r.latency_s:6.2f}s  {r.tool_calls} tools  "
                  f"{r.tokens_billed:6d} tok  "
                  f"{('$%.4f' % r.cost_usd) if r.cost_usd else '  n/a ':>8s}  "
                  f"{'PASS' if r.success else 'fail'}")
    return pd.DataFrame(rows)


def summarise(df):
    """One row per architecture. This is the table that goes on the projector."""
    g = df.groupby("arch").agg(
        latency_s=("latency_s", "mean"),
        tool_calls=("tool_calls", "mean"),
        tokens_billed=("tokens_billed", "mean"),
        tokens_reasoning=("tokens_reasoning", "mean"),
        cost_usd=("cost_usd", "mean"),
        task_success=("success", "mean"),
    ).round(4)
    return g.reindex([a for a in ARCHITECTURES if a in g.index])


def ordering(df, metric: str = "cost_usd") -> list[str]:
    """The architecture ordering on a metric. THIS is what should be stable
    across providers — not the absolute numbers. If a student's ordering
    differs from the instructor's, that is a finding: go open the trace."""
    s = df.groupby("arch")[metric].mean().sort_values()
    return list(s.index)
