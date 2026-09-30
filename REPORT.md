# REPORT - Router Rescue

## 1. Numbers (`python evaluate.py`)
"Right" depends on label type (see LABELING_RULES.md): for `TOOL` rows the tool must match; for CLARIFY / gap / action / how-to / context / OOS rows, **abstaining is right and any tool is a silent wrong route**.

| | Baseline dev | router.py dev* | Baseline held-out** | router.py held-out** |
|---|---|---|---|---|
| Decision accuracy (all rows) | 72.0% | 99.3% | 65.0% | 95.0% |
| `TOOL` rows exact (n=128 / 23) | 73.4% | 100% | 65.2% | 95.7% |
| Abstention rows right (n=17 / 15) | 64.7% | 100% | 73.3% | 93.3% |
| Wrong routes (silent) | 23 (15.3%) | 0 | 7 (17.5%) | 1 (2.5%) |
| Median latency | ~2 ms | ~0.15 ms | ~2 ms | ~0.14 ms |

\* **Tuned on these 150 queries; this number is not a generalisation estimate.** \** 40 queries written after the router design, by the same author, so only mildly independent. Treat 95% as an upper bound.

**Where the baseline breaks (23 wrong + 18 missed on dev):** 9 are right entity / wrong shape ("show me the last 10 purchase orders" -> count; the verb boost only fires when a keyword already matched, and list tools are keyed on phrases like "list po", so a count tool with a generic hit always wins); 8 are wrong entity ("list job work orders" -> production work orders; "job work vendors" -> job-work PO list); 6 are non-lookups routed to a tool (`delete all draft POs` -> count tool, `total value` -> PO value, `why is our rejection rate so high`). The 18 misses are mostly phrasing gaps (`list gate passes` fails because only "gate pass list" is a keyword; gatepass 0/4, store 3/5 exact). **Baseline confidence is uninformative**: only 6 predictions reach 0.8+, so a threshold cannot separate its wrong routes. The fall-through (score < 2) is right for 11/17 abstention rows, so that design choice is sound; the failure is what happens above it.

## 2. Five worst remaining failures (dev has 0 wrong routes, so these come from held-out and probes I ran afterwards)
1. **`how many employees joined last month` -> `hr_new_joiners_list` (0.9, silent shape mismatch).** Root cause: entities with one tool skip shape logic (`_FIXED`). Structural: shape is decided *per entity by hand*, so every "single-tool" entity hides a count-vs-list hole. Not in either label set.
2. **`how many inspections failed` (h21) -> `quality_inspection_pending_count`.** The catalog has no count-with-result tool; the router sees `inspection` + count and takes the only count tool. It knows tool names but not tool filters, so it cannot see that "failed" is unrepresentable. Correct answer is a gap.
3. **`how many work orders and how many NCRs are open` -> work-order count; `show me the PO list and the GRN list` -> GRN list.** Multi-intent: the entity is the first hit in a fixed priority list, not by position, and there is no multi-tool output. Structural to a single-label router.
4. **`which items are out of stock` -> `inventory_stock_list` (0.85).** "Out of stock" means zero quantity; the closest tool is low-stock. This is phrase-level semantics my regex table does not know, so it falls into the generic list branch.
5. **`kitne employees hai` (h29) -> abstain.** Hinglish count words are not in the lexicon. It fails safe but shows the ceiling of a hand-written lexicon: every new phrasing is a code change. Similarly `how many POs did we raise for vendor Kiran Auto` routes to the by-vendor *list* tool (count wanted; confidence only 0.6 because the typo-repair layer changed a word).

## 3. Three things that did not work (`experiments/exp.py`, all scored on the same 150 queries)
| Attempt | Result (decision acc / wrong routes) | Cost |
|---|---|---|
| **E1 TF-IDF cosine**, query vs tool description + keywords, threshold sweep 0-0.35 | 66.7-74.7% / 16-42 wrong. Never clearly better than baseline: similarity finds the *entity*, but count/list/value tools of one entity have near-identical text, so shape is a coin flip; low thresholds never abstain (0/17 abstention rows right at th=0) | Low: ~30 lines of stdlib code, seconds to run |
| **E2 baseline, MIN_SCORE 2 -> 1** | 71.3% / 27 wrong (worse). Recovers a few misses but turns abstentions into wrong guesses. Confirms the gate is right and the scoring is the problem | Very low: one constant changed |
| **E3 baseline + shape penalty** (+/-2 for shape match on all tools) | 72.7% / 13 wrong: roughly halves wrong routes but does not fix misses, because missing keyword coverage is untouched. Combined with MIN_SCORE=1 (E3b): 71.3% / 17 | Low: patched copy of the scoring loop |

Lesson that shaped router.py: separate *what entity* from *what shape* from *is this even a lookup*, and make abstention a first-class outcome.

## 4. With another week (priority order)
1. **Real labels:** have 2-3 ERP users or support staff label the 150 independently; measure agreement (my labels are one opinion). Sample fresh production queries with their frequencies.
2. **Tool-capability metadata** (which filters and output shape each tool supports: date? status? city?) so routing can detect gaps like h21 and q089 instead of guessing. Cheap, and addresses failures 1-2.
3. **Multi-intent handling** (split on "and", route each part) and a count-vs-list check on single-tool entities.
4. **A learned layer for the residual** (small classifier on entity/shape features, or offline embedding kNN) trained on production queries and fallback-layer decisions, kept behind the rule gates so it stays auditable.
5. **Parameter extraction evaluation.** The exercise strips it, but many user-visible errors are wrong filters (`PARAM_GAP` rows).
6. A regression suite built from every fallback-layer resolution.

## 5. What is wrong with this assessment
- **No ground truth from production.** The "real queries" arrive unlabeled, so I only know what *I* think they should route to. Which tool actually answered the user, and whether they accepted it, would be far better.
- **One person labels, builds and evaluates.** The dev score is circular; only an independently labeled set means anything. n is small (1 query = 0.67 points).
- **Catalog gaps are mixed into router accuracy.** 17 of 150 rows are gaps / clarify / how-to / etc. that no routing fix can answer. Whether abstaining there is "right" depends on the fallback layer, which is not modelled. The real cost trade-off (wrong tool vs slower fallback) is unknown, so I could not pick a threshold; I assumed a silent wrong route is worse than abstaining.
- **Parameters are stripped**, yet many "correct routes" would return the wrong rows (`PARAM_GAP`). Routing accuracy overstates user-visible correctness.
- **Queries are unweighted.** If one query type dominates production, it matters more than the 150 uniform queries.
- **Few near-duplicates or adversarial paraphrases**, so overfitting to phrasing cannot be measured; hence the held-out set, which is itself weak.
- **A six-hour cap favours rules over evaluation design.** The interesting problem (how to define "correct") deserves the week more than the code does.

## 6. How this was produced
I used Claude (Anthropic) as the main tool for drafting the labels, the router, the evaluation script and this report, as the brief allows. I ran everything locally, checked the outputs match, and reviewed the labels and the router logic by hand, including the low-confidence labels listed at the end of LABELING_RULES.md. The labels are a first pass by one reviewer and may contain mistakes I would want to discuss on the call. Total effort stayed within the six-hour cap.