"""
Session 4 — evaluation pipeline toolkit.
Evaluating AI Agents. Self-contained: imports nothing from Sessions 1-3.

THE SPINE
---------
An evaluator is a hypothesis about a failure: it says WHERE TO LOOK and WHAT
WOULD COUNT AS FAILING. Until something has failed it, you have not measured
anything -- you have decorated.

Session 3 measured task_success = 1.00 for all three architectures while the
same runs differed 2x on cost. That grader was not measuring. It was agreeing.

WHERE TO LOOK -- the five eval types are five fields of one run object
---------------------------------------------------------------------
    outcome      -> the last message                    (offline: outputs["answer"])
    process      -> the message list                    (offline: outputs["messages"])
    trajectory   -> the ordered tool calls               (offline: outputs["tool_calls"])
    tool         -> which tool, with what arguments      (offline: outputs["tool_calls"])
    state        -> the graph state between nodes        -> SESSION 11 owns this
    safety       -> any of the above, adversarially      -> SESSION 5 owns this

OFFLINE vs ONLINE, made concrete rather than defined
-----------------------------------------------------
    OFFLINE  You control the dataset, so you have reference_outputs.
             The target function hands you the whole message list.
             No LangSmith round trip. Fast enough to iterate on.
             -> evaluators here take (inputs, outputs, reference_outputs)

    ONLINE   The run already happened in production. There IS no reference
             output. All you have is the trace.
             -> evaluators here take (run,) and walk spans

Both shapes ship below. They are the same question asked of two objects.

Gotchas applied (claude/COURSE_CONVENTIONS.md):
  #1  no temperature (current models reject it)
  #2  .text, never .content
  #5  LANGSMITH_PROJECT set before anything reads it -> env_setup()
  #6  wait_for_all_tracers() + Client().flush() before reading a trace
  #8  count OUTERMOST tool spans only (LangGraph emits two per tool call)
  #9  a graph root's `outputs` is the message list, not the answer
  #10 tool outputs are wrapped, sometimes twice
  #16 a flushed run is not a readable run -- retry on BOTH exception and empty
"""

from __future__ import annotations

import json
import os
import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

# Bump on every change. preflight4 and the notebook assert on it, so a stale
# module cached in a running kernel fails loudly instead of quietly reporting
# the previous version's verdicts.
__version__ = "s4-2026-09-01a"

PROJECT = "session-4-eval-pipeline"
DATASET = "s4-deep-research-eval"


# ==========================================================================
# 0.  Environment.  Gotcha #5: this MUST run before anything reads langsmith,
#     or traces land silently in `default` with no error at all.
# ==========================================================================

def env_setup(project: str = PROJECT) -> str:
    """Set the LangSmith project and bust the lru_cache. Returns resolved name."""
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


# ==========================================================================
# 1.  Provider handling.  ONE CHAT alias; one variable swaps provider.
#     Datasets and evaluators are provider-agnostic -- the target is just
#     `def target(inputs: dict) -> dict`. The judge is independent of the
#     agent's provider too. So Session 4 carries LESS cross-provider risk
#     than Session 3 did.
# ==========================================================================

Provider = Literal["anthropic", "openai", "google"]

MODEL_IDS: dict[Provider, str] = {
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-5.6-terra",
    "google": "gemini-3.7-flash",
}

# Pinned at the provider floor and held constant. We are not measuring
# reasoning effort. Pinning at a known floor is defensible; claiming to have
# "normalised" it across providers is not.
EFFORT_FLOOR = "low"


def make_chat(provider: Provider = "anthropic", effort: str | None = EFFORT_FLOOR):
    """Build the chat model. Returns (chat, effort_pinned). Degrades cleanly."""
    model = MODEL_IDS[provider]

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic as Cls
    elif provider == "openai":
        from langchain_openai import ChatOpenAI as Cls
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI as Cls
    else:
        raise ValueError(f"unknown provider {provider!r}")

    # Gotcha #1: no `temperature`. Current models reject it outright, which is
    # the honest reason you cannot make an agent deterministic -- and the
    # honest reason an evaluator needs more than one sample to trust.
    if effort is None:
        return Cls(model=model), False
    try:
        return Cls(model=model, reasoning_effort=effort), True
    except Exception:
        # Gotcha #12: constructing is not proving. preflight4 sends a real
        # request; this fallback only covers construction-time rejection.
        return Cls(model=model), False


PROVIDER: Provider = os.environ.get("COURSE_PROVIDER", "anthropic")  # type: ignore[assignment]

# CHAT is built LAZILY on first use, not at import.
#
# This is not tidiness. The falsification exercise -- run your evaluator
# against a known-good and a known-bad run and see whether it can tell them
# apart -- is the block that must not be cut, and it must work with no API
# key, no network and no provider package installed. Building CHAT at import
# time would make `import evalkit` fail on a student whose Gemini install is
# broken, and take the whole session with it.
#
# Anything that actually needs a model calls get_chat(). Everything else --
# every rule-based evaluator, the whole discrimination matrix -- does not.
_CHAT = None
EFFORT_PINNED: bool | None = None       # None = not determined yet


def get_chat(provider: Provider | None = None, effort: str | None = EFFORT_FLOOR):
    """The CHAT alias. One variable swaps provider, resolved on first use."""
    global _CHAT, EFFORT_PINNED
    if provider is not None or _CHAT is None:
        chat, pinned = make_chat(provider or PROVIDER, effort)
        if provider is None:
            _CHAT, EFFORT_PINNED = chat, pinned
        return chat
    return _CHAT


def __getattr__(name: str):
    """Keeps `from evalkit import CHAT` working for anyone who wants it,
    while still deferring construction until the attribute is touched."""
    if name == "CHAT":
        return get_chat()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ==========================================================================
# 2.  The agent under test.  Deliberately boring -- Session 4 evaluates an
#     agent, it does not design one.
# ==========================================================================

from langchain_core.tools import tool  # noqa: E402

_TAVILY = None


def _tavily():
    global _TAVILY
    if _TAVILY is None:
        from langchain_tavily import TavilySearch
        _TAVILY = TavilySearch(max_results=3)
    return _TAVILY


@tool
def web_search(query: str) -> str:
    """Search the web for current information. Returns up to 3 results."""
    return json.dumps(_tavily().invoke({"query": query}))


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


def build_agent(chat=None, tools=None, system_prompt: str | None = None):
    """The agent under test. create_agent compiles to a StateGraph."""
    from langchain.agents import create_agent

    return create_agent(
        model=chat or get_chat(),
        tools=tools if tools is not None else BASE_TOOLS,
        system_prompt=system_prompt or SYSTEM_PROMPT,
    )


# ==========================================================================
# 3.  Turning an agent result into things an evaluator can read.
#
#     This is the part students underestimate. An evaluator is only as good
#     as the field it reads, and THREE of the course's six worst bugs so far
#     were the harness reading the wrong field -- not the agent misbehaving.
# ==========================================================================

def final_text(result: dict) -> str:
    """Gotcha #9: a LangGraph root's `outputs` is the whole message list, not
    the answer, and it carries usage_metadata. Dump it to text for a
    grounding check and you will read prompt-token counts as factual claims."""
    if isinstance(result, dict) and result.get("answer"):
        return str(result["answer"])
    msgs = (result or {}).get("messages", [])
    if not msgs:
        return ""
    last = msgs[-1]
    return getattr(last, "text", None) or str(getattr(last, "content", last))


def as_messages(result: dict) -> list[dict]:
    """Plain-dict, OpenAI-style message list. JSON-serialisable, so it can
    live in a dataset row or an experiment output.

    Roles: user | assistant | tool. Assistant turns carry `tool_calls`.
    This is what a trajectory evaluator compares.
    """
    out: list[dict] = []
    for m in (result or {}).get("messages", []):
        mtype = getattr(m, "type", None) or getattr(m, "role", "assistant")
        role = {"human": "user", "ai": "assistant", "tool": "tool",
                "system": "system"}.get(mtype, mtype)
        text = getattr(m, "text", None)
        if text is None:
            content = getattr(m, "content", m)
            text = content if isinstance(content, str) else str(content)
        entry: dict[str, Any] = {"role": role, "content": text}
        tcs = getattr(m, "tool_calls", None) or []
        if tcs:
            entry["tool_calls"] = [
                {"name": tc.get("name"), "args": tc.get("args", {})} for tc in tcs
            ]
        name = getattr(m, "name", None)
        if name:
            entry["name"] = name
        out.append(entry)
    return out


def tool_calls_from_messages(messages: list[dict]) -> list[dict]:
    """The ordered trajectory: [{"name": ..., "args": {...}}, ...].

    NOTE this reads the ASSISTANT's requests, not the tool spans. Offline
    that is correct and it is free. Online you must walk spans instead --
    see walk_tool_spans and gotcha #8, where the same count read the wrong
    way is double.
    """
    calls: list[dict] = []
    for m in messages or []:
        for tc in m.get("tool_calls", []) or []:
            calls.append({"name": tc.get("name"), "args": tc.get("args", {})})
    return calls


def evidence_from_messages(messages: list[dict]) -> list[str]:
    """Every tool result, in order. This is what a groundedness judge checks
    the answer against -- and it is the reason a judge can say something a
    keyword grader cannot."""
    return [m.get("content", "") for m in (messages or []) if m.get("role") == "tool"]


def make_target(agent=None) -> Callable[[dict], dict]:
    """The `target` passed to client.evaluate().

    Signature is fixed by LangSmith: `def target(inputs: dict) -> dict`.
    Everything an offline evaluator needs must come out of here, because
    offline evaluators never touch LangSmith. Returning the message list is
    what makes process/trajectory/tool evaluation possible without a round
    trip -- and what makes the iterate-on-evaluators loop fast enough to do
    three times in a 90-minute class.
    """
    agent = agent or build_agent()

    def target(inputs: dict) -> dict:
        result = agent.invoke({"messages": [inputs["question"]]})
        messages = as_messages(result)
        return {
            "answer": final_text(result),
            "messages": messages,
            "tool_calls": tool_calls_from_messages(messages),
            "evidence": evidence_from_messages(messages),
        }

    return target


# ==========================================================================
# 4.  OFFLINE evaluators.
#
#     Current LangSmith signature is KEYWORD-MATCHED: declare only the
#     parameters you need, from
#         inputs, outputs, reference_outputs, run, example
#     Verified against docs.langchain.com/langsmith/code-evaluator-sdk
#     (Aug 2026). The legacy (run, example) form still works but is not
#     what current docs teach.
#
#     Return: bool | int | float (function name becomes the metric name),
#     str (categorical), dict {"key":..,"score":..,"comment":..}, or a
#     list of dicts for several metrics from one function.
# ==========================================================================

# ---- 4a. OUTCOME.  The decoration.  Ships deliberately weak. --------------

def outcome_keyword(outputs: dict, reference_outputs: dict) -> dict:
    """Does the answer contain every required keyword?

    THIS IS THE SESSION'S ANTAGONIST. It is eight lines, it has no model in
    it, it is the cheapest thing you can write -- and in Session 3 it scored
    1.00 for all three architectures while their costs differed 2x.

    Keep it. Run it. Then look at what it could not see.
    """
    answer = (outputs.get("answer") or "").lower()
    required = reference_outputs.get("must_contain", []) or []
    hits = [k for k in required if k.lower() in answer]
    return {
        "key": "outcome_keyword",
        "score": len(hits) == len(required),
        "comment": f"{len(hits)}/{len(required)} keywords present",
    }


# ---- 4b. TOOL CORRECTNESS.  Students write the predicate. -----------------

def tool_correctness(outputs: dict, reference_outputs: dict) -> dict:
    """Did the agent use the tool the task actually needed?

    reference_outputs["expected_tools"] is a SET, not a sequence -- order is
    the trajectory evaluator's job, not this one's. Keeping the two apart is
    what stops one evaluator failing for two unrelated reasons, which is the
    fastest way to make a metric uninterpretable.
    """
    used = {tc["name"] for tc in outputs.get("tool_calls", [])}
    expected = set(reference_outputs.get("expected_tools", []) or [])
    forbidden = set(reference_outputs.get("forbidden_tools", []) or [])

    missing = expected - used
    wrong = used & forbidden
    return {
        "key": "tool_correctness",
        "score": not missing and not wrong,
        "comment": (f"used={sorted(used)} missing={sorted(missing)} "
                    f"forbidden_used={sorted(wrong)}"),
    }


# ---- 4c. TRAJECTORY.  Pre-built; read, not written. ----------------------

def _norm_query(args: dict) -> str:
    q = (args or {}).get("query") or (args or {}).get("expression") or ""
    return " ".join(str(q).lower().split())


def trajectory_no_waste(outputs: dict, reference_outputs: dict) -> dict:
    """Did the agent reach the answer without redundant or runaway work?

    Two failure shapes, both invisible in the final paragraph:
      * the SAME query issued twice  -> redundant work
      * more calls than the task can justify -> runaway / loop

    Session 2's seed C is the honest caveat here: it issued FOUR calls with
    FOUR DIFFERENT queries, so duplicate-detection cannot see it. A code rule
    catches the shapes it was written for and no others. That ceiling is the
    argument for a judge, and it is why Session 8 exists.
    """
    calls = outputs.get("tool_calls", [])
    budget = int(reference_outputs.get("max_tool_calls", 4) or 4)

    seen: set[tuple[str, str]] = set()
    dupes = 0
    for tc in calls:
        key = (tc["name"], _norm_query(tc.get("args", {})))
        if key in seen:
            dupes += 1
        seen.add(key)

    over = max(len(calls) - budget, 0)
    return {
        "key": "trajectory_no_waste",
        "score": dupes == 0 and over == 0,
        "comment": f"{len(calls)} calls (budget {budget}), {dupes} duplicate, {over} over",
    }


def trajectory_match(outputs: dict, reference_outputs: dict) -> dict:
    """Ordered comparison against a reference trajectory, when one exists.

    Modes mirror the openevals vocabulary so Session 8 can swap in the real
    package without re-teaching the concept:
        strict     exact sequence
        unordered  same multiset, any order
        subset     every call made appears in the reference
        superset   every reference call was made

    Most dataset rows should NOT set a reference trajectory. Pinning an exact
    tool sequence turns any reasonable alternative path into a failure, and
    then the metric measures conformity rather than correctness.
    """
    ref = reference_outputs.get("expected_trajectory")
    if not ref:
        return {"key": "trajectory_match", "score": None,
                "comment": "no reference trajectory for this example - skipped"}

    mode = reference_outputs.get("trajectory_match_mode", "superset")
    got = [tc["name"] for tc in outputs.get("tool_calls", [])]
    ref = list(ref)

    if mode == "strict":
        ok = got == ref
    elif mode == "unordered":
        ok = sorted(got) == sorted(ref)
    elif mode == "subset":
        ok = set(got) <= set(ref)
    else:  # superset
        ok = set(ref) <= set(got)

    return {"key": "trajectory_match", "score": ok,
            "comment": f"mode={mode} got={got} ref={ref}"}


# ---- 4d. THE JUDGE.  Hand-rolled, twelve lines, no new dependency. --------

JUDGE_PROMPT = """You are grading whether an ANSWER is supported by the EVIDENCE that was
actually retrieved. You are not grading whether the answer is true in general,
and you are not grading style.

QUESTION:
{question}

EVIDENCE RETRIEVED BY THE AGENT:
{evidence}

ANSWER:
{answer}

Reply with exactly one word on the first line -- GROUNDED or UNGROUNDED -- then
one sentence naming the specific claim that is or is not supported.

GROUNDED means every factual claim in the answer traces to the evidence above.
UNGROUNDED means at least one claim does not, including the case where the
evidence is empty and the answer states facts anyway."""


def make_groundedness_judge(chat=None, feedback_key: str = "groundedness"):
    """An LLM-as-a-Judge for the one thing code cannot express: is this answer
    actually supported by what the agent retrieved?

    Written by hand on purpose. It uses the CHAT alias, so it works on every
    provider in the course for free, and it adds no package to a pin set
    forty students installed as homework (gotcha #15).

    WHAT SESSION 4 DOES NOT DO: check whether the judge is right. A judge is
    an evaluator, and this course's rule is that an evaluator is validated
    against a known-good run before you trust it. Doing that -- rubrics,
    position bias, verbosity bias, self-preference -- is Session 8.
    Say that out loud. Do not let a judge score become a fact today.
    """
    chat = chat or get_chat()

    def groundedness(inputs: dict, outputs: dict) -> dict:
        evidence = "\n\n---\n\n".join(outputs.get("evidence", []) or [])[:6000]
        msg = chat.invoke(JUDGE_PROMPT.format(
            question=inputs.get("question", ""),
            evidence=evidence or "(the agent retrieved nothing)",
            answer=outputs.get("answer", ""),
        ))
        verdict = msg.text.strip()          # gotcha #2: .text, never .content
        return {
            "key": feedback_key,
            "score": verdict.upper().startswith("GROUNDED"),
            "comment": verdict[:500],
        }

    groundedness.__name__ = feedback_key
    return groundedness


# What ships. Order matters on the slide: cheapest first, model last.
#
# trajectory_match is NOT here, and that is a decision rather than an
# oversight. No shipping dataset row sets an `expected_trajectory`, so it
# would skip every example -- and an evaluator that never applies is worse
# than one that is absent, because a column of blanks on the experiment table
# reads as a column of passes. It stays importable for the row where someone
# genuinely wants an ordered comparison; it does not go on the projector
# scoring nothing.
#
# This is the spine applied to our own toolkit: an evaluator that cannot
# fail has not earned its column.
OFFLINE_EVALUATORS: list[Callable] = [
    outcome_keyword,
    tool_correctness,
    trajectory_no_waste,
]

# Evaluators exempt from the discriminate-or-retire rule, and WHY -- because
# an exemption without a reason is how a rule dies.
#
# outcome_keyword is expected to be blind ACROSS SEEDS. Every seed produces a
# plausible-looking paragraph, so the keyword grader waves all four through.
# That is not a defect in the evaluator, it is the measurement the session is
# built on: Session 3 got task_success = 1.00 on three architectures whose
# costs differed 2x, and this is the same result reproduced on demand.
#
# Note the exemption is scoped to the SEED matrix. Across the DATASET,
# outcome_keyword must still discriminate -- some questions the agent gets
# wrong -- and if it passes every dataset row too, it is retired like
# anything else. Two different discrimination questions, one metric.
BLIND_BY_DESIGN: set[str] = {"outcome_keyword"}


# ==========================================================================
# 5.  ONLINE evaluators -- same questions, asked of a trace.
#
#     A production run has no reference output. This is not a limitation to
#     apologise for, it is the definition: online evaluation is what you can
#     still say when nobody wrote down the right answer.
# ==========================================================================

def walk_tool_spans(run, in_tool: bool = False, acc: list | None = None) -> list:
    """Collect OUTERMOST tool spans only.

    Gotcha #8: LangGraph emits TWO spans per tool call -- the tools-node span
    and the @tool function's own span nested inside it, same name, same
    arguments. Count both and every single-search run looks like it issued a
    duplicate query, and a healthy control gets classified as broken.
    """
    acc = [] if acc is None else acc
    if getattr(run, "run_type", None) == "tool" and not in_tool:
        acc.append(run)
    for child in (getattr(run, "child_runs", None) or []):
        walk_tool_spans(child, in_tool or run.run_type == "tool", acc)
    return acc


def count_spans(run) -> int:
    """Total spans in a run tree, root included."""
    return 1 + sum(count_spans(c) for c in (getattr(run, "child_runs", None) or []))


def unwrap(obj: Any, depth: int = 4) -> Any:
    """Gotcha #10: tool outputs are wrapped, sometimes twice. LangSmith may
    return {"output": {"content": "[]", ...}} -- a serialised ToolMessage.
    One unwrap leaves a dict that json.dumps into something non-empty, so an
    empty search never registers as empty."""
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


def online_empty_retrieval(run) -> dict:
    """ONLINE. No reference output exists. Can we still say something?

    Yes: an agent that answered at length while every one of its searches
    came back empty is broken, and you can see that without knowing the
    right answer. This is the shape most production online evaluators take.
    """
    spans = walk_tool_spans(run)
    searches = [s for s in spans if (s.name or "").startswith("web_search")]
    if not searches:
        return {"key": "online_empty_retrieval", "score": None,
                "comment": "no search spans - rule does not apply"}
    empty = 0
    for s in searches:
        body = unwrap(s.outputs)
        text = body if isinstance(body, str) else json.dumps(body or "")
        if text.strip() in ("", "[]", "{}", "null", '""'):
            empty += 1
    return {"key": "online_empty_retrieval", "score": empty < len(searches),
            "comment": f"{empty}/{len(searches)} searches returned empty"}


def online_tool_budget(run, budget: int = 4) -> dict:
    """ONLINE. Runaway detection. Session 9 turns this into a cost argument."""
    n = len(walk_tool_spans(run))
    return {"key": "online_tool_budget", "score": n <= budget,
            "comment": f"{n} outermost tool spans (budget {budget})"}


ONLINE_EVALUATORS: list[Callable] = [online_empty_retrieval, online_tool_budget]


# ==========================================================================
# 6.  Reading a trace back.  Only needed for the ONLINE path.
# ==========================================================================

def find_trace_root(client, since, project: str = PROJECT, attempts: int = 8,
                    base_delay: float = 1.5):
    """Ask LangSmith which run is the root. Do not work it out locally.

    Gotcha #17: collect_runs() returns FOUR parentless fragments for one
    create_agent().invoke(), and traced_runs[0] is the first LLM call. Read
    that id back and everything is consistent and wrong -- right shape,
    wrong magnitude, nothing raises.
    """
    for attempt in range(attempts):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")   # list_runs deprecation
                runs = list(client.list_runs(project_name=project, is_root=True,
                                             start_time=since, limit=10))
        except Exception:
            runs = []
        if runs:
            return max(runs, key=lambda r: r.start_time).id
        time.sleep(base_delay * (attempt + 1))
    return None


def read_run_when_ready(client, run_id, *, min_spans: int = 2, attempts: int = 8,
                        base_delay: float = 1.5):
    """Gotcha #16: a flushed run is not a readable run, and read_run RAISES
    rather than returning None. There are two independent waits -- does it
    exist yet, and has the tree finished filling in -- so retry on the
    EXCEPTION and on the empty value. A loop that only tests the value never
    runs, because the call threw first.

    Readiness: span count stable across two consecutive reads, and > 1.
    Returns (run, note) so the caller degrades instead of crashing.
    """
    from langsmith.utils import LangSmithNotFoundError

    run, note, prev = None, "", -1
    for attempt in range(attempts):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                run = client.read_run(str(run_id), load_child_runs=True)
        except LangSmithNotFoundError:
            time.sleep(base_delay * (attempt + 1))
            continue
        spans = count_spans(run)
        if spans >= min_spans and spans == prev:
            return run, note
        prev = spans
        time.sleep(base_delay * (attempt + 1))

    if run is None:
        note = (f"run {run_id} never appeared after {attempts} attempts - "
                "ingestion lag, wrong project, or a key without write access")
    elif count_spans(run) < min_spans:
        note = (f"root {run_id} came back with no children. If the LangSmith UI "
                "shows a tree here, the wrong run id was resolved")
    return run, note


def flush_traces() -> None:
    """Gotcha #6: traces send on a background thread."""
    from langchain_core.tracers.langchain import wait_for_all_tracers
    from langsmith import Client
    wait_for_all_tracers()
    Client().flush()


# ==========================================================================
# 7.  DISCRIMINATION.  The spine, as code.
#
#     An evaluator that returns the same verdict on every example has not
#     measured anything. It cannot distinguish a good run from a bad one,
#     so its score carries no information -- however much you like the number.
# ==========================================================================

@dataclass
class Discrimination:
    key: str
    n: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    verdicts: list = field(default_factory=list)

    @property
    def discriminates(self) -> bool:
        return self.passed > 0 and self.failed > 0

    @property
    def verdict(self) -> str:
        if self.n == 0:
            return "NO DATA"
        if self.passed and self.failed:
            return "DISCRIMINATES"
        if self.passed == 0 and self.failed == 0:
            # Never applied to a single row. Worse than absent: it puts a
            # column of blanks on the experiment table, and students read
            # blanks as passes.
            return "ALL-SKIP (never applied - do not ship it)"
        return "ALL-PASS (decoration)" if self.passed else "ALL-FAIL (impossible or broken)"


def discrimination_report(rows: list[dict]) -> dict[str, Discrimination]:
    """rows: [{"key": str, "score": bool|None}, ...] flattened from any source.

    Deliberately NOT a LangSmith summary_evaluator. The summary_evaluator
    signature is the one piece of this API I could not verify against current
    docs, and asserting a signature from memory is what cost Session 3
    multiple round trips. Computing it locally is boring and certain.
    """
    out: dict[str, Discrimination] = {}
    for r in rows:
        d = out.setdefault(r["key"], Discrimination(key=r["key"]))
        d.n += 1
        s = r.get("score")
        if s is None:
            d.skipped += 1
        elif s:
            d.passed += 1
        else:
            d.failed += 1
        d.verdicts.append(s)
    return out


def print_discrimination(report: dict[str, Discrimination]) -> bool:
    """Print the table and return True if EVERY evaluator discriminates."""
    print(f"\n{'evaluator':<24} {'pass':>5} {'fail':>5} {'skip':>5}   verdict")
    print("-" * 72)
    ok = True
    for d in report.values():
        if not d.discriminates and d.n > d.skipped:
            ok = False
        print(f"{d.key:<24} {d.passed:>5} {d.failed:>5} {d.skipped:>5}   {d.verdict}")
    print("-" * 72)
    return ok


def run_offline_evaluators(inputs: dict, outputs: dict, reference_outputs: dict,
                           evaluators: list[Callable] | None = None) -> list[dict]:
    """Run evaluators locally against one (inputs, outputs, reference) triple.

    Same keyword-matching LangSmith does, so an evaluator that works here
    works in an experiment. This is what makes the falsification exercise
    possible without spending an experiment on it.
    """
    import inspect

    results: list[dict] = []
    available = {"inputs": inputs, "outputs": outputs,
                 "reference_outputs": reference_outputs}
    for ev in (evaluators if evaluators is not None else OFFLINE_EVALUATORS):
        params = inspect.signature(ev).parameters
        kwargs = {k: v for k, v in available.items() if k in params}
        try:
            r = ev(**kwargs)
        except Exception as exc:
            r = {"key": getattr(ev, "__name__", "unknown"), "score": None,
                 "comment": f"evaluator raised: {exc!r}"}
        results.extend(r if isinstance(r, list) else [r])
    return results
