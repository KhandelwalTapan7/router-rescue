# Labeling rules

Ground truth answers one question: **given only these 62 tools, what should the system do with this query?**
It is *not* "what would the baseline do" and *not* "which keyword appears". Keys are `q001`..`q150`; a 40-query
held-out set (`heldout.csv`, ids `h01`..) uses the same rules.

## Columns of `labels.csv`
`query_id, query, label_type, primary_tool, acceptable_alts, confidence, flags, notes`

| label_type | meaning | "right" for a router |
|---|---|---|
| `TOOL` | exactly one tool answers it (alts allowed if two are genuinely defensible) | returns primary or an alt |
| `TOOL_PARTIAL` | a tool answers only *part* (compound, comparison, wrong output shape) | returns primary/alt = partial credit; abstaining = safe |
| `CLARIFY` | in-domain but under-specified across tools (`stock`, `total value`, `pending orders`); `acceptable_alts` holds the candidate tools | abstain (ask / fallback) |
| `NO_TOOL_GAP` | a legitimate data question the catalog cannot answer | abstain |
| `NO_TOOL_ACTION` | asks to change data (approve, delete...) | abstain |
| `NO_TOOL_HOWTO` | procedural / explanatory | abstain |
| `NO_TOOL_ANALYSIS` | "why", judgment, recommendation | abstain |
| `NO_TOOL_CONTEXT` | needs earlier conversation to resolve a referent | abstain |
| `NO_TOOL_OOS` | not about the ERP | abstain |

`confidence`: **H** = I would defend it in ten seconds and expect a second reviewer to agree; **M** = one reasonable
alternative exists; **L** = close to a coin flip. `flags`: `PARAM_GAP`, `SHAPE_MISMATCH`, `COMPOUND`, `MULTI_CALL`,
`TYPO`, `HINGLISH`, `SESSION_USER`.

## Rules (and why)
1. **Output shape is part of correctness.** "how many" = count tool, "list/show/which/give me" = list tool, "total value/spend" = scalar tool. `show me all pending payments` is `finance_payment_list`, not the pending-count tool, even though the count tool's keywords fit better. (q075)
2. **The verb outranks the noun only when it names a shape.** `give me the report on how leave approval works` contains a rows-verb but is a how-to (q056).
3. **Filters the tool cannot express (dates, city, value threshold, negation, status on a list tool) do not change the tool.** Label the tool, flag `PARAM_GAP`, note the consequence (user gets a superset). Reason: routing and parameter extraction are separate problems and the exercise strips parameter extraction. (q013, q046, q062, q089, q092, q110, q113, q115...)
4. **"Pending" is entity-relative.** PO -> approval status PENDING (`purchase_po_count`); payments -> awaiting release; inspections/indents/leave -> their own pending tools; job work -> awaiting return. Never map "pending" to a fixed tool. (q001, q041, q054, q074, q096)
5. **Writes are never routed to a read tool, even when a read tool matches the noun.** `delete all draft POs` is `NO_TOOL_ACTION`, not `purchase_po_count`. A router that guesses here is a safety problem, not an accuracy problem. (q017, q052)
6. **Single-document lookups are a gap.** `status of PO 97`: no tool takes a document number. (q022)
7. **Aggregations the catalog does not compute are a gap:** top-N by vendor, distinct vendors with pending orders, cost of downtime. (q069, q073, q081)
8. **Group-by / comparison answerable by several calls = `TOOL_PARTIAL` + `MULTI_CALL`.** Primary tool is the first call. (q047, q141)
9. **Compound question with one answerable half = `TOOL_PARTIAL` + `COMPOUND`.** (q039)
10. **Wrong-shape only-available tool = `TOOL_PARTIAL` + `SHAPE_MISMATCH`.** `which returnable gate passes are overdue` wants rows; only a count tool covers it. `how many job work vendors` has only a list tool. (q091, q122)
11. **Under-specified within the domain = `CLARIFY`, never a guess.** One word (`stock`), a total of unknown thing (`total value`), `orders` spread over four modules, `PO status?` with no id/shape. Correct behaviour is to ask or hand to the fallback. (q006, q035, q043, q061)
12. **Missing referent = `NO_TOOL_CONTEXT`.** `how many are there?`, `as per our discussion...`. (q010, q077)
13. **Two defensible tools = one primary + `acceptable_alts` and confidence <= M.** (q021 WO status vs WIP, q074 and q082 'pending/open', q135 headcount by department). I limited alts to cases where I could argue either in one sentence.
14. **"Job work orders" = job work POs.** The catalog has no separate job-work order tool, and production work orders are a different entity. Baseline sends q037 to production work orders. (q037, medium)
15. **Typos and Hinglish are labeled with the intended tool** and flagged. (q028; `po ka status kya hai` q043 is still CLARIFY because the intent, not the language, is under-specified.)
16. **"Real" data quirks I accepted:** `hr_attendance_today` handles "yesterday" because it has a `date` param (q124); status words like open/active/overdue/draft are parameters, not routing signals; `sales_invoice_count` is the only invoice-count tool so unpaid invoices go there (q030, M).

## Changes of mind (honest log)
- **Before labeling any row** I planned to mark queries with unsupported filters (dates, city, threshold) as `TOOL_PARTIAL`. While labeling `q046`, `q062`, `q110` I changed that to `TOOL` + `PARAM_GAP` (rule 3): the *routing* decision is unambiguous and mixing it with a parameter limitation would have made "partial" mean two things. All 11 such rows were labeled under the final rule; nothing needed relabeling.
- **After building the router** I audited every disagreement between it and the labels. There was one on the dev set (q096); it was a router bug (a how-to regex matching the word `work`), label unchanged. On the held-out set the two disagreements (`h21`, `h29`) are router failures, labels unchanged. I did **not** change any label to make the router look better.
- Labels I am least sure of (worth arguing about): q021, q030, q037, q074, q082, q086 (is `OVERDUE` a valid status value?), q089, q091, q122, q135.

## Known limits of these labels
Single labeler who also wrote the router; no production usage data to say what users actually wanted; 1 query = 0.67 points on the dev set.
