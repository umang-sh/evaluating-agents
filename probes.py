"""
Session 3 probe set.

Rules inherited from Sessions 1-2:
  * Verifiable in ten seconds by an undergrad. If they cannot check the answer
    themselves, "is this true?" becomes "I'm not an expert" instead of
    "nobody can tell from the output."
  * No semiconductor / EUV domain questions yet — deferred to Session 5.
  * Ground truth is re-verified by preflight3.py the night before. Prices and
    version numbers move; a stale key phrase marks a correct answer wrong.
    (This is the Session 1 GROUND_TRUTH ambiguity lesson, previewed.)

The easy/hard split is load-bearing. It is what makes the recommendation
exercise non-trivial: neither architecture wins on both halves.
"""

from arch_bench import Probe

EASY = [
    Probe(
        question="What is the latest released version of the langgraph package on PyPI?",
        must_contain=["1.2"],
        difficulty="easy",
    ),
    Probe(
        question="What is the published input price, per million tokens, of Claude Opus 5?",
        must_contain=["5"],
        difficulty="easy",
    ),
    Probe(
        question="On what date was Claude Fable 5 released?",
        must_contain=["june"],
        difficulty="easy",
    ),
]

HARD = [
    # DEPENDENT multi-hop: query 2 cannot be written until result 1 is known.
    # This is the probe class that separates the architectures, and it took a
    # failed pre-flight to find. The previous "hard" probes were answerable in a
    # single search, so ReAct never took more than one step, its context never
    # compounded, and workflow-vs-ReAct came out within 2.5% — noise dressed as
    # a finding.
    #
    # It also exposes a sharper architecture-specific failure than cost:
    # build_workflow plans ALL its queries up front, before it has seen a single
    # result, so it structurally CANNOT follow a dependency. Expect it to fail
    # these on task success, not merely to cost more.
    Probe(
        question=(
            "What is the latest released version of the langgraph package on "
            "PyPI, and what minimum version of langchain-core does that release "
            "require?"
        ),
        must_contain=["1.2", "langchain-core"],
        difficulty="hard",
    ),
    Probe(
        question=(
            "Identify the most recently released Claude model, then state its "
            "published input price per million tokens."
        ),
        must_contain=["opus", "5"],
        difficulty="hard",
    ),
    Probe(
        question=(
            "Which costs more per input token, Claude Opus 5 or Claude Fable 5, "
            "and by what multiple?"
        ),
        must_contain=["fable", "2"],
        difficulty="hard",
    ),
]

ALL = EASY + HARD

# Class-time set. Six probes x three architectures x ~25s is roughly 8 minutes of
# wall clock — budget 1.5x for a room of 40 waiting on API calls (Session 1 rule).
CLASS_SET = [EASY[0], EASY[1], HARD[0], HARD[1]]   # 2 easy, 2 DEPENDENT hard
