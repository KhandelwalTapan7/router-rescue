# REPORT - Router Rescue

## 1. Numbers (`python3 evaluate.py`)
"Right" depends on label type (see LABELING_RULES.md): for `TOOL` rows the tool must match; for CLARIFY / gap / action / how-to / context / OOS rows, **abstaining is right and any tool is a silent wrong route**.

| | Baseline dev | router.py dev* | Baseline held-out** | router.py held-out** |
|---|---|---|---|---|
| Decision accuracy (all rows) | 72.0% | 99.3% | 65.0% | 95.0% |
| `TOOL` rows exact (n=128 / 23) | 73.4% | 100% | 65.2% | 95.7% |
| Abstention rows right (n=17 / 15) | 64.7% | 100% | 73.3% | 93.3% |
| Wrong routes (silent) | 23 (15.3%) | 0 | 7 (17.5%) | 1 (2.5%) |
| Median latency | 1.7 ms | 0.13 ms | 1.6 ms | 0.12 ms |

\* **Tuned on these 150 queries; this number is not a generalisation estimate.** \** 40 queries I wrote after designing the router, same author, so only mildly independent. Treat 95% as an upper bound.

**Where the baseline breaks (23 wrong + 18 missed on dev):** 9 right entity/wrong shape ("show me the last 10 purchase orders" -> count; the verb boost only fires when a keyword already matched, and list tools are keyed on phrases like "list po", so a count tool with a generic hit always wins); 8 wrong entity ("list job work orders" -> production work orders; "job work vendors" -> job-work PO list); 6 non-lookups routed to a tool (`delete all draft POs` -> count tool, `total value` -> PO value, `why is our rejection rate so high`). The 18 misses are mostly phrasing gaps (`list gate passes` fails because only "gate pass list" is a keyword; gatepass 0/4, store 3/5 exact). **Baseline confidence is uninformative**: only 6 predictions reach 0.8+, so a threshold cannot separate its wrong routes. The fall-through (score < 2) is right for 11/17 abstention rows, so that design choice is sound; the failure is what happens above it.

## 2. Five worst remaining failures (dev has 0 wrong routes, so these come from held-out and probes I ran after)
1. **`how many employees joined last month` -> `hr_new_joiners_list` (0.9, silent shape mismatch).** Root cause: entities with one tool skip shape logic (`_FIXED`). Structural: shape is decided *per entity by hand*, so every "single-tool" entity hides a count-vs-list hole. Not in either label set.
2. **`how many inspections failed` (h21) -> `quality_inspection_pending_count`.** The catalog has no count-with-result tool; the router sees `inspection`+count and takes the only count tool. It has no notion of *the tool's filters* (only names), so it cannot see that "failed" is unrepresentable. Correct answer is a gap.
3. **`how many work orders and how many NCRs are open` -> work-order count; `show me the PO list and the GRN list` -> GRN list.** Multi-intent: entity is the first in a fixed priority list, not by position, and there is no multi-tool output. Structural to a single-label router.
4. **`which items are out of stock` -> `inventory_stock_list` (0.85).** "out of stock" means zero quantity; the closest tool is low-stock. Phrase-level semantics my regex table does not know; it falls into the generic `list` branch.
5. **`kitne employees hai` (h29) -> abstain.** Hinglish count words are not in the lexicon. It fails safe (abstains) but shows the ceiling of a hand-written lexicon: every new phrasing is a code change. Similarly `how many POs did we raise for vendor Kiran Auto` routes to the by-vendor *list* tool (count wanted; confidence only 0.6 because the typo-repair layer changed a word).

## 3. Three things that did not work (`experiments/exp.py`, all scored on the same 150)
| Attempt | Result (decision acc / wrong routes) | Cost |
|---|---|---|
| **E1 TF-IDF cosine** query vs tool description+keywords, threshold sweep 0-0.35 | 66.7-74.7% / 16-42 wrong. Never better than baseline: similarity finds the *entity*, but count/list/value tools of one entity are near-identical text, so shape is a coin flip; low thresholds never abstain (0/17 abstention rows right at th=0) | [FILL: minutes] |
| **E2 baseline, MIN_SCORE 2 -> 1** | 71.3% / 27 wrong (worse). Recovers a few misses, converts abstentions into wrong guesses. Confirms the gate is right and the scoring is the problem | [FILL] |
| **E3 baseline + shape penalty** (+/-2 for shape match, all tools) | 72.7% / 13 wrong: halves wrong routes but does not fix misses, because missing keyword coverage is untouched. Combined with MIN_SCORE=1 (E3b): 71.3% / 17 | [FILL] |

Lesson that shaped router.py: separate *what entity* from *what shape* from *is this even a lookup*, and make abstention a first-class outcome.

## 4. With another week (priority order)
1. **Real labels**: ask 2-3 ERP users/support staff to label the 150 independently; measure agreement; my labels are one opinion. Sample fresh production queries with frequencies.
2. **Tool-capability metadata** (which filters each tool supports: date? status? city?) so routing can detect gaps like h21/q089 instead of guessing. Cheap and solves failures 1-2.
3. **Multi-intent handling** (split on "and", route each part) and count-vs-list shape check on single-tool entities.
4. **A learned layer for the residual** (small classifier on entity/shape features, or offline embedding kNN) trained on production queries + fallback-layer decisions, kept behind the rule gates so it stays auditable.
5. **Parameter extraction** evaluation (the exercise strips it, but half of the failures users see are wrong filters: `PARAM_GAP` rows).
6. Regression suite from every fallback-layer resolution.

## 5. What is wrong with this assessment
- **No ground truth from production.** "Real queries" arrive unlabeled; I only know what *I* think they should route to. Which tool actually answered the user, and whether they accepted it, would be far better.
- **Same person labels, builds and evaluates.** The dev score is circular; only an independently labeled set means anything. n is small (1 query = 0.67 points).
- **Catalog gaps are mixed into router accuracy.** 17 of 150 rows are gaps/clarify/how-to/etc. that no routing fix can answer; whether abstaining there is "right" depends on the fallback layer, which is not modelled. The real cost trade-off (wrong tool vs slower fallback) is unknown, so I could not pick a threshold; I assumed silent wrong > abstain.
- **Parameters are stripped**, yet many "correct routes" return the wrong rows (`PARAM_GAP`). Routing accuracy overstates user-visible correctness.
- **Queries are unweighted.** One frequent query type dominating production would matter more than the 150 uniform ones.
- **Few near-duplicates / adversarial paraphrases**, so overfitting to phrasing cannot be measured; hence the held-out set, which is itself weak.
- **Six hours favours rules over evaluation design**; the interesting problem (how to define correct) deserves the week, not the code.

*How this was produced: [FILL: which AI tools you used, what you reviewed by hand, and the actual time spent.]*
