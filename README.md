# Evaluating AI Agents — course repo

From Session 4 onward we work here rather than in Colab. Session 4 opens with
`git pull`.

## Setup (once)

```bash
bash setup.sh
source .venv/bin/activate
cp .env.example .env      # then paste your keys in
python check_env.py
```

`check_env.py` prints one line. Paste it into the homework form exactly as printed
— `GO` or `NO-GO`, both are useful.

You need **Python 3.11+**. Pick one provider and set `COURSE_PROVIDER` in `.env` to
match: `anthropic`, `openai` or `google`.

## What is here

| File | What it is |
|---|---|
| `arch_bench.py` | Three implementations of the same research agent, and the benchmark harness |
| `probes.py` | The probe set. Easy and hard, deliberately |
| `preflight3.py` | Instructor GO/NO-GO verifier. Run it before a session that depends on staged behaviour. Also writes `deck_numbers.json`, which the deck reads so its charts show measured figures instead of an illustrative shape |
| `check_env.py` | Your environment check |
| `requirements.txt` | The pin set. Do not float these |

## Running the pre-flight (instructors)

There is **no separate requirements file** — `preflight3.py` uses the same
`requirements.txt` and the same `.env` as everything else in this repo.

```bash
source .venv/bin/activate
python preflight3.py --all-providers --save session3_preflight_runs.json
```

Run it **from this directory** — it imports `arch_bench` and `probes` as local
modules.

**Environment it needs**, from `.env` or the shell:

| Variable | Needed for |
|---|---|
| `COURSE_PROVIDER` | `anthropic` \| `openai` \| `google` (ignored with `--all-providers`) |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` | whichever providers you are checking. `--all-providers` silently skips any whose key is absent |
| `TAVILY_API_KEY` | the search tool |
| `LANGSMITH_API_KEY` | tracing, cost and every trace-derived check |

**Cost and time:** it runs the four-probe benchmark **twice** across three
architectures — roughly 24 agent runs per provider, a few minutes and a few cents
each, plus about 25–30 Tavily searches. Budget against the 1,000/month free tier.

**What it produces:**

| File | What it is |
|---|---|
| `session3_preflight_runs.json` | both runs, saved. Your API-outage fallback, and the input to `--reclassify` |
| `deck_numbers.json` | the figures slides 12–13 plot. Copy it next to `make_deck.js`, rerun `node make_deck.js` |

`--reclassify session3_preflight_runs.json` re-scores a saved run with no API cost.
Exit code is 0 for GO, non-zero for NO-GO, so it works in a shell conditional.

## The three architectures

They differ on exactly one axis: **who decides what happens next.**

```python
from arch_bench import build_react, build_toolcall, build_workflow, run_bench, summarise
import probes

df = run_bench(probes.CLASS_SET)
summarise(df)
```

| | control flow | shape in a trace |
|---|---|---|
| `build_react` | the model | a graph: `agent` → `tools` → `agent` |
| `build_toolcall` | the model | a flat list: LLM, tool, LLM, tool |
| `build_workflow` | **the code** | `plan` → `search` ×N → `synthesize` |

Everything else is held constant — same tools, same prompt, same model, same
reasoning effort pinned at the provider floor. If a number differs between rows,
the architecture is the only thing that could have caused it.

## What the numbers mean

`tokens_billed` = output tokens + **uncached** input tokens. Cached reads excluded.
Reasoning tokens reported in their own column.

Providers do not count tokens the same way, so a blended number across providers is
meaningless. Compare **orderings**, not absolutes: cheapest-to-most-expensive should
survive a change of provider even though the absolute figures will not.

`reasoning_effort` is a standard parameter from `langchain-core` 1.5.2 onward, but
LangChain standardised the *input*, not the economics behind it. We pin it at a
floor and hold it constant rather than claiming to have normalised it.

## Two things that will bite you

**Set `LANGSMITH_PROJECT` before anything reads it.** `get_tracer_project` is
`lru_cache`d. Get this wrong and your traces land in `default` with **no error at
all**. `arch_bench.env_setup()` clears the cache and raises if the project did not
resolve — call it first.

**LangGraph emits two spans per tool call.** The tools-node span, and the `@tool`
function's own span nested inside it — same name, same arguments. Count both and
every single-search run looks like it fired a duplicate query. `walk_tool_spans`
counts outermost only. Read it before you write your own trace analysis.
