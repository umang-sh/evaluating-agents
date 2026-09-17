# Session 5 files — unpack into `course-repo/`

    cd course-repo
    unzip -o session5_files.zip
    git add row_screen.py seeds5.py preflight5.py benchmark_rows.py \
            screen_my_rows.py n_for.py push_pool.py instructor_pool.py \
            build_form5.gs deck/ SESSION5_README.md
    git commit -m "Session 5: benchmark suites — row screener, adversarial seed, preflight5"

## What each file is

| file | role | needs a key? |
|---|---|---|
| `row_screen.py` | the screener. Replays 5 measured failure shapes against a row and reports which ones the row's own expectations catch. | no |
| `benchmark_rows.py` | **students edit this.** 3 worked examples (open), 2 TODO rows. | no |
| `screen_my_rows.py` | **students run this.** Terminal, ~2s, exits 0/1. | no |
| `n_for.py` | the sample-size calculator. `--demo` is the projector cell. | no |
| `seeds5.py` | the prompt-injection seed **plus its clean control**. Additive — `seeds.py` untouched. | yes (to run) |
| `push_pool.py` | screens, pushes and version-tags the class pool. `--dry` / `--tag` / `--show`. | yes (except `--dry`) |
| `instructor_pool.py` | the zero-submission fallback. 12 rows, all SHIP. | no |
| `preflight5.py` | 7 checks. `--offline` runs 2/3/4 with no keys and no cost. | partly |
| `build_form5.gs` | Google Apps Script form builder. Run ONCE — it makes a new form with a new URL every run. | n/a |
| `deck/make_deck5.js` | regenerates the 22-slide deck. `node make_deck5.js` | no |
| `deck/make_stagecard5.py` | regenerates the 3-page stage card. | no |

## Check it works right now, offline

    python preflight5.py --offline      # expect: GO (offline)
    python screen_my_rows.py --worked   # expect: 3 ship, 2 TODO rows retire
    python n_for.py --demo              # expect: 12 vs 1,537

None of those three touch the network or spend a Tavily search.

## Before class

    python preflight5.py --runs 5 --save

Needs `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `LANGSMITH_API_KEY`. It writes
`deck_numbers5.json` — copy that next to `deck/make_deck5.js` and rerun
`node make_deck5.js`, and the three data slides stop stamping themselves
ILLUSTRATIVE in red.

`--save` refuses to write anything if any check is NO-GO. That is deliberate.

## Known open item, not fixed here

`evalkit.Discrimination.verdict` returns `None` for an ALL-PASS evaluator — there is an
unreachable `return` after the ALL-SKIP branch, so the ALL-PASS / ALL-FAIL strings never
print. That is a Session 4 file and has not been touched. ALL-PASS is exactly what
Session 5 exists to explain, so fix it before class.
