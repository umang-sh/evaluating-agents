"""
Session 4 — the evaluation dataset.

ONE dataset, FOUR categories, not four datasets.

The syllabus asks for evaluation datasets covering browser search, information
retrieval, multi-hop reasoning and report generation. Four separate datasets
is four times the setup for zero extra learning. One dataset with a category
on every row satisfies the line, teaches a real LangSmith feature (filtered
`list_examples`, which you pass straight in as `data=`), and lets you run an
experiment on one slice when you only care about one slice.

    data = client.list_examples(dataset_name=DATASET, metadata={"category": "multi_hop"})
    client.evaluate(target, data=data, evaluators=[...])

REFERENCE OUTPUTS ARE THE HARD PART, AND THAT IS THE LESSON
-----------------------------------------------------------
Writing the question takes ten seconds. Writing down what would count as a
correct answer is where every real disagreement lives, and it is where
Session 1 already drew blood: the "newest Claude model" probe had two
defensible answers (newest by release date vs most capable) and a reference
answer that accepted only one would mark a correct answer wrong.

So each row here carries FOUR kinds of reference, and they fail differently:

    must_contain          keywords -> outcome_keyword. Cheap, brittle, and
                          the thing that scored 1.00 on everything in S3.
    expected_tools        a SET -> tool_correctness. Order is not this one's job.
    forbidden_tools       tools that indicate a routing mistake.
    max_tool_calls        a budget -> trajectory_no_waste.
    expected_trajectory   an ORDERED list -> trajectory_match. MOSTLY ABSENT
                          ON PURPOSE: pinning an exact tool sequence turns any
                          reasonable alternative path into a failure, and then
                          you are measuring conformity, not correctness.

GROUND TRUTH GOES STALE. Versions and prices move, and a stale keyword marks a
correct answer WRONG -- which is worse than no check at all, because it looks
like a finding. Every row whose truth can move carries `verify_url`, and
preflight4 re-checks them before class. Rows with verify_url = None are
structural or documented-stable and do not rot.
"""

from __future__ import annotations

from evalkit import DATASET

__version__ = "s4-2026-09-01a"

CATEGORIES = ["browser_search", "retrieval", "multi_hop", "report_gen"]


# ==========================================================================
# The eight rows that ship.  Students add a ninth in their assigned category
# -- that is hands-on item 1, and it is deliberately the first thing they do,
# because arguing about the reference output is the point.
# ==========================================================================

EXAMPLES: list[dict] = [

    # ---- browser_search: one fact, one search, verifiable in ten seconds --
    {
        "inputs": {"question":
            "What is the latest released version of the `langgraph` package on PyPI?"},
        "outputs": {
            "must_contain": ["1.2"],          # VERIFY: preflight4 re-checks
            "expected_tools": ["web_search"],
            "forbidden_tools": ["calculator"],
            "max_tool_calls": 2,
        },
        "metadata": {"category": "browser_search", "difficulty": "easy",
                     "verify_url": "https://pypi.org/project/langgraph/"},
    },
    {
        "inputs": {"question":
            "Which environment variable replaced LANGCHAIN_TRACING_V2 for enabling "
            "LangSmith tracing?"},
        "outputs": {
            "must_contain": ["LANGSMITH_TRACING"],
            "expected_tools": ["web_search"],
            "forbidden_tools": ["calculator"],
            "max_tool_calls": 2,
        },
        # Documented rename, not a moving number. No verify_url needed.
        "metadata": {"category": "browser_search", "difficulty": "easy",
                     "verify_url": None},
    },

    # ---- retrieval: the answer exists in docs; can the agent find it? -----
    {
        "inputs": {"question":
            "In LangSmith, what does an ONLINE evaluator not receive that an "
            "offline evaluator does?"},
        "outputs": {
            "must_contain": ["reference"],
            "expected_tools": ["web_search"],
            "forbidden_tools": ["calculator"],
            "max_tool_calls": 2,
        },
        "metadata": {"category": "retrieval", "difficulty": "easy",
                     "verify_url": "https://docs.langchain.com/langsmith/evaluation-concepts"},
    },
    {
        "inputs": {"question":
            "What is the monthly search limit on Tavily's free tier?"},
        "outputs": {
            "must_contain": ["1,000"],        # VERIFY: preflight4 re-checks
            "expected_tools": ["web_search"],
            "forbidden_tools": [],
            "max_tool_calls": 2,
        },
        "metadata": {"category": "retrieval", "difficulty": "easy",
                     "verify_url": "https://tavily.com/"},
    },

    # ---- multi_hop: hop 2 CANNOT be issued until hop 1 returns -----------
    # This is what separates a model that decides from code that decides.
    # A fixed-plan workflow must emit both queries before either returns.
    {
        "inputs": {"question":
            "Find the latest released version of the `langgraph` package, then "
            "state the minimum `langchain-core` version that release requires."},
        "outputs": {
            "must_contain": ["langchain-core"],
            "expected_tools": ["web_search"],
            "forbidden_tools": ["calculator"],
            "max_tool_calls": 4,
        },
        "metadata": {"category": "multi_hop", "difficulty": "hard",
                     "verify_url": "https://pypi.org/project/langgraph/"},
    },
    {
        "inputs": {"question":
            "Which company maintains the LangGraph library, and in which year "
            "was that company founded?"},
        "outputs": {
            "must_contain": ["LangChain"],
            "expected_tools": ["web_search"],
            "forbidden_tools": [],
            "max_tool_calls": 4,
        },
        "metadata": {"category": "multi_hop", "difficulty": "hard",
                     "verify_url": "https://www.langchain.com/"},
    },

    # ---- report_gen: keyword grading is STRUCTURALLY unable to grade this -
    # Note must_contain is nearly empty. That is not laziness. Ask the room
    # what keyword would prove a comparison is any good, and let the silence
    # do the work -- this is the slide where the judge earns its place.
    {
        "inputs": {"question":
            "Write a short comparison of offline and online agent evaluation, "
            "citing at least two sources."},
        "outputs": {
            "must_contain": ["offline", "online"],
            "expected_tools": ["web_search"],
            "forbidden_tools": ["calculator"],
            "max_tool_calls": 4,
        },
        "metadata": {"category": "report_gen", "difficulty": "hard",
                     "verify_url": None},
    },
    {
        "inputs": {"question":
            "Summarise the three most common failure modes of tool-using agents, "
            "with a source for each."},
        "outputs": {
            "must_contain": ["tool"],
            "expected_tools": ["web_search"],
            "forbidden_tools": ["calculator"],
            "max_tool_calls": 4,
        },
        "metadata": {"category": "report_gen", "difficulty": "hard",
                     "verify_url": None},
    },
]


# The one row students write. Left here as a TODO on purpose -- it is the
# first thing their hands do, it costs no API calls, and it forces the
# question "what would count as correct?" before any experiment runs.
STUDENT_TEMPLATE = {
    "inputs": {"question": "TODO: your question"},
    "outputs": {
        "must_contain": [],          # TODO: what words MUST appear?
        "expected_tools": [],        # TODO: which tool does this NEED?
        "forbidden_tools": [],       # TODO: which tool would be a mistake?
        "max_tool_calls": 3,         # TODO: what is a fair budget?
    },
    "metadata": {"category": "TODO", "difficulty": "easy", "verify_url": None},
}


# ==========================================================================
# Pushing it to LangSmith.
#
# CURRENT SHAPE, verified Aug 2026 against
# reference.langchain.com/python/langsmith/client/Client/create_examples:
#     client.create_examples(dataset_id=..., examples=[{"inputs":..,"outputs":..}])
# The old parallel-lists form (inputs=[...], outputs=[...]) is gone from the
# signature and survives only via **kwargs. Every 2024-25 tutorial students
# find uses the old one.
# ==========================================================================

def push(client=None, dataset_name: str = DATASET, examples: list[dict] | None = None,
         description: str | None = None):
    """Create (or reuse) the dataset and upload the rows. Idempotent-ish:
    reuses the dataset if it exists, and skips upload if it already has rows.

    Returns (dataset, n_uploaded).
    """
    from langsmith import Client

    client = client or Client()
    examples = EXAMPLES if examples is None else examples

    if client.has_dataset(dataset_name=dataset_name):
        dataset = client.read_dataset(dataset_name=dataset_name)
        existing = len(list(client.list_examples(dataset_name=dataset_name)))
        if existing:
            print(f"dataset {dataset_name!r} already has {existing} examples - "
                  "not re-uploading. Delete it in the UI to start clean.")
            return dataset, 0
    else:
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description=description or (
                "Session 4 - Deep Research agent evaluation. Four categories: "
                + ", ".join(CATEGORIES)),
        )

    client.create_examples(dataset_id=dataset.id, examples=examples)
    print(f"uploaded {len(examples)} examples to {dataset_name!r}")
    return dataset, len(examples)


def slice_for(client, category: str, dataset_name: str = DATASET):
    """One category's rows, ready to pass straight in as `data=`.

    Filtering by example METADATA is the verified path. LangSmith also has a
    first-class `splits` concept (`list_examples(..., splits=[...])`); setting
    a split at creation time is NOT verified here, so this uses metadata,
    which is. If you want real splits, set them in the UI and switch this
    one line -- do not assert the creation kwarg from memory.
    """
    return client.list_examples(dataset_name=dataset_name,
                                metadata={"category": category})


def local_rows(category: str | None = None) -> list[dict]:
    """The same rows without touching LangSmith -- for the falsification
    exercise, which must work with no network and no API key."""
    return [e for e in EXAMPLES
            if category is None or e["metadata"]["category"] == category]
