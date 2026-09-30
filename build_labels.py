"""Builds labels.csv (dev set) and heldout.csv from compact tables. Query text is pulled from queries.txt by id."""
import csv, re
from pathlib import Path
T = dict(T="TOOL", P="TOOL_PARTIAL", C="CLARIFY", G="NO_TOOL_GAP", A="NO_TOOL_ACTION",
         H="NO_TOOL_HOWTO", O="NO_TOOL_OOS", X="NO_TOOL_CONTEXT", Y="NO_TOOL_ANALYSIS")
# id|type|primary_tool (or candidates for C)|acceptable_alts|confidence|flags|notes
DEV = """
q001|T|purchase_po_count||H||approval_status=PENDING
q002|T|purchase_po_list||H||limit=10. Baseline misses: 'show me the last 10 purchase orders' matches no list keyword, so count tool wins
q003|H|||H||procedural, not data
q004|T|purchase_po_total_value||H||APPROVED
q005|T|inventory_stock_count||H||
q006|C|purchase_po_list|sales_so_list|production_workorder_list|jobwork_po_list||M||'pending orders' spans 4 modules; guessing is worse than asking
q007|T|purchase_po_by_vendor||H||
q008|T|hr_employee_count||H||
q009|T|inventory_low_stock_list||H||
q010|X|||H||no referent; needs chat history
q011|T|inventory_stock_list||H||
q012|T|sales_so_count||H||status=CONFIRMED
q013|T|purchase_po_list||M|PARAM_GAP|'not approved' is a negation; tool takes one approval_status. Pending-approval list would be a subset (drops DRAFT/REJECTED) so not accepted as alt
q014|T|inventory_stock_by_item||H||
q015|T|hr_employee_list||H||department=production
q016|T|quality_ncr_count||H||
q017|A|||H||write action; 'PO097' identifier
q018|T|inventory_stock_value_total||H||
q019|T|hr_attendance_today||H||'people' = employees
q020|T|quality_ncr_list||H||'list' asks for rows. Baseline returns count
q021|T|production_workorder_count|production_wip_count|M||'work orders in progress' = WO status; WIP tool counts items, not WOs, but a reviewer could accept it
q022|G|||H||single-document lookup; no tool takes a PO number
q023|T|sales_customer_list||H||
q024|H|||H||how-to and also a write
q025|T|hr_leave_pending_count||H||
q026|T|sales_so_total_value||H||period=quarter
q027|T|production_machine_status_list||H||status filter 'down'
q028|T|purchase_po_count||M|TYPO|'pendin po cnt' -> pending PO count
q029|T|production_workorder_list||H||status=released. Baseline returns count
q030|T|sales_invoice_count||M||payment_status=UNPAID. Only invoice tool in catalog is sales; could mean vendor bills
q031|T|hr_department_list||H||
q032|O|||H||
q033|T|production_output_total||H||period=yesterday
q034|T|mom_action_item_count||H||status=open
q035|C|purchase_po_total_value|sales_so_total_value|inventory_stock_value_total|crm_opportunity_total_value||H||no entity. Baseline silently picks PO value
q036|T|hr_new_joiners_list||H||
q037|T|jobwork_po_list||M||'job work orders' = job work POs; NOT production work orders
q038|T|gatepass_count||H||period=this month
q039|P|purchase_po_count||H|COMPOUND|count part answerable; 'what does pending mean' is explanation
q040|T|mom_list||H||
q041|T|finance_payment_pending_count||H||
q042|T|quality_rejection_rate||H||
q043|C|purchase_po_count|purchase_po_list||L|HINGLISH|'PO status?' with no document id and no shape; ambiguous
q044|T|finance_invoice_overdue_list||H||
q045|T|crm_lead_count||H||
q046|T|quality_inspection_list||M|PARAM_GAP|list tool has no date filter
q047|P|production_output_total||M|MULTI_CALL|comparison = 2 calls (this month, last month) + arithmetic
q048|T|production_downtime_total||H||
q049|T|store_issue_list||H||
q050|T|inventory_item_master_count||H||
q051|T|hr_leave_list||M|PARAM_GAP|no period param on list tool
q052|A|||H||destructive write. Baseline routes it to a count tool
q053|T|production_shift_output||H||Baseline picks output_total
q054|T|store_indent_pending_count||H||
q055|T|crm_lead_list||H||stage=qualified
q056|H|||H||'give me the report' is a list verb trap; content is how-to
q057|T|finance_outstanding_total||H||
q058|T|production_wip_count||H||
q059|T|jobwork_vendor_list||H||Baseline picks jobwork_po_list
q060|T|purchase_po_count||H||REJECTED
q061|C|inventory_stock_list|inventory_stock_count|inventory_stock_by_item|inventory_stock_value_total||H||one word
q062|T|purchase_po_list||M|PARAM_GAP|value threshold not a param
q063|T|sales_customer_count||H||active=false
q064|T|quality_inspection_list||H||result=FAIL
q065|Y|||H||causal question; rate tool is context, not an answer
q066|T|gatepass_list||H||
q067|T|inventory_stock_by_item||H||
q068|T|mom_count||H||
q069|G|||H||needs distinct-vendor aggregation; po_by_vendor needs a name
q070|T|finance_payment_list||H||
q071|T|purchase_grn_count||H||
q072|T|mom_action_item_list||H|SESSION_USER|owner = current user, comes from session not query
q073|G|||M|COMPOUND|historical machine status (tool is current only) plus cost; nothing computes cost
q074|T|jobwork_po_count|jobwork_pending_count|L||'pending' = status or awaiting return; both defensible
q075|T|finance_payment_list||H||'show me all' wants rows. Baseline returns count
q076|T|hr_employee_count||H||
q077|X|||H||
q078|T|quality_inspection_list||H||result=PASS
q079|T|quality_coa_count||H||
q080|T|sales_so_list||H||status=CANCELLED. Baseline returns count
q081|G|||H||top-N by vendor aggregation; not in catalog
q082|T|gatepass_count|gatepass_pending_return_count|M||'open' = status, but could mean not returned
q083|T|hr_new_joiners_list||H||days=30
q084|T|inventory_stock_by_item||H||
q085|T|production_workorder_count||H||
q086|T|mom_action_item_list||M||status=OVERDUE assumed valid value
q087|T|store_issue_count||H||
q088|T|crm_opportunity_total_value||H||
q089|T|hr_employee_list||L|PARAM_GAP|list tool has no status param; would return all employees
q090|T|purchase_po_total_value||H||status=PENDING. Baseline returns count
q091|P|gatepass_pending_return_count|gatepass_list|L|SHAPE_MISMATCH|wants rows, only a count tool covers 'not returned'
q092|T|purchase_po_list||M|PARAM_GAP|no date filter
q093|T|sales_invoice_count||H||
q094|T|inventory_low_stock_list||H||
q095|T|hr_attendance_today||H||
q096|T|jobwork_pending_count||M||'how much' phrased as count
q097|T|crm_lead_list||H||
q098|T|production_downtime_total||H||
q099|T|purchase_grn_list||H|PARAM_GAP|no date filter
q100|T|purchase_po_count||H||DRAFT
q101|T|purchase_po_count||H||
q102|T|purchase_po_list||H||
q103|T|hr_employee_count||H||status=active
q104|T|inventory_stock_list||H||
q105|T|quality_ncr_count||H||severity=critical
q106|T|production_workorder_list||H||Baseline returns count
q107|T|purchase_po_total_value||H||Baseline returns count
q108|T|production_machine_status_list||H||
q109|T|quality_inspection_pending_count||H||
q110|T|sales_customer_list||M|PARAM_GAP|city not a param
q111|T|inventory_item_master_list||H||
q112|T|mom_action_item_count||H||
q113|T|finance_payment_list||H|PARAM_GAP|no date filter
q114|T|production_wip_count||H||line=2
q115|T|crm_lead_list||M|PARAM_GAP|source filter exists only on the count tool
q116|T|purchase_grn_count||H||status=DRAFT
q117|T|hr_employee_list||H||
q118|T|finance_outstanding_total||H||
q119|T|inventory_low_stock_list||H||
q120|T|quality_rejection_rate||H||
q121|T|sales_so_list||H||
q122|P|jobwork_vendor_list||M|SHAPE_MISMATCH|no vendor count tool; row count of list answers it
q123|T|crm_opportunity_total_value||H||
q124|T|hr_attendance_today||M||tool name says today but has a date param
q125|T|purchase_po_by_vendor||H||
q126|T|inventory_item_master_count||H||
q127|T|production_output_total||H||
q128|T|purchase_po_pending_approval_list||H||
q129|T|purchase_po_expiring||H||days=7
q130|T|purchase_po_count||H||po_type=OPEN
q131|T|purchase_grn_list||H||Baseline returns count
q132|T|production_shift_output||H||
q133|T|sales_customer_count||H||
q134|T|mom_list||H||
q135|T|hr_department_list|hr_employee_count|M||department list carries headcount per department
q136|T|gatepass_list||H||Baseline: no match
q137|T|store_issue_count||H||Baseline: no match
q138|T|inventory_stock_value_total||H||Baseline: no match
q139|T|purchase_po_list||H||Baseline returns count
q140|T|jobwork_vendor_list||H||
q141|P|quality_ncr_count||M|MULTI_CALL|group by severity = one call per severity
q142|T|hr_employee_list||H||
q143|T|production_workorder_count||H||
q144|T|store_indent_pending_count||H||
q145|T|quality_inspection_pending_count||H||
q146|T|sales_so_list||H|PARAM_GAP|
q147|T|sales_so_total_value||H||
q148|T|production_workorder_count||H||status=PLANNED
q149|T|inventory_item_master_list||H||
q150|T|mom_action_item_list||H||
"""
HELD = """
h01|what's the number of employees we currently have|T|hr_employee_count||
h02|any POs waiting for approval?|T|purchase_po_pending_approval_list|purchase_po_count|no shape word
h03|how many goods receipt notes have we posted|T|purchase_grn_count||
h04|list of all machines|T|production_machine_status_list||
h05|delete PO 55|A||
h06|how to raise an NCR|H||
h07|what's the capital of France|O||
h08|how much is our inventory worth|T|inventory_stock_value_total||
h09|which items should we reorder|T|inventory_low_stock_list||
h10|number of gate passes issued today|T|gatepass_count||
h11|please show pending leave requests|T|hr_leave_list|hr_leave_pending_count|
h12|how many POs expire this month|P|purchase_po_expiring||count wanted, list tool
h13|total downtime of M-7 yesterday|T|production_downtime_total||
h14|give me sales orders for customer Mehta Enterprises|T|sales_so_list||no customer param
h15|what did I ask earlier|X||
h16|how many of them are approved|X||
h17|employees count|T|hr_employee_count||
h18|stock of item BRG-220|T|inventory_stock_by_item||
h19|list of new hires this quarter|T|hr_new_joiners_list||
h20|sales revenue this month|T|sales_so_total_value||
h21|how many inspections failed|G||no count tool with result filter
h22|purchase order|C|purchase_po_count|purchase_po_list|bare noun
h23|how many job work vendors do we have|P|jobwork_vendor_list||
h24|outstanding from customer Mehta|T|finance_outstanding_total||
h25|what is the po approval process|H||
h26|cancel sales order SO-88|A||
h27|who all are absent today|T|hr_attendance_today||
h28|meetings list for this week|T|mom_list||
h29|kitne employees hai|T|hr_employee_count||Hinglish
h30|pending payments|C|finance_payment_pending_count|finance_payment_list|no shape
h31|how many work orders are late|T|production_workorder_count||
h32|show me overdue|C|finance_invoice_overdue_list|mom_action_item_list|gatepass_pending_return_count|no entity
h33|total production this week|T|production_output_total||
h34|list all POs|T|purchase_po_list||
h35|gate pass details|T|gatepass_list||
h36|reject PO 12|A||
h37|which vendor has the most pending orders|G||
h38|inventory|C|inventory_stock_list|inventory_stock_count|inventory_stock_value_total|one word
h39|how many are overdue|C|finance_invoice_overdue_list|mom_action_item_list||no entity
h40|give me stock of RM-2201 and RM-2202|T|inventory_stock_by_item||two items
"""
q = {}
for l in Path("candidate_package/queries.txt").read_text().splitlines():
    if l.startswith("q"): i, _, t = l.partition("\t"); q[i] = t.strip()
def split(line, n): return line.split("|", n - 1)
rows = []
for l in DEV.strip().splitlines():
    p = l.split("|")
    qid, t = p[0], p[1]
    if t == "C":   # candidates occupy several fields until conf (H/M/L)
        ci = next(i for i in range(3, len(p)) if p[i] in "HML" and len(p[i]) == 1 and i >= 4)
        cands, conf, flags, notes = [x for x in p[2:ci] if x], p[ci], p[ci+1], "|".join(p[ci+2:])
        rows.append([qid, q[qid], T[t], "", "|".join(cands), conf, flags, notes]); continue
    tool, alts, conf, flags, notes = p[2], p[3], p[4], p[5], "|".join(p[6:])
    rows.append([qid, q[qid], T[t], tool, alts, conf, flags, notes])
assert len(rows) == 150 and [r[0] for r in rows] == sorted(q), "id mismatch"
with open("labels.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["query_id","query","label_type","primary_tool","acceptable_alts","confidence","flags","notes"]); w.writerows(rows)
hrows = []
for l in HELD.strip().splitlines():
    p = l.split("|"); qid, text, t = p[:3]
    if t == "C":
        cands = [x for x in p[3:] if x.startswith(("purchase_","finance_","mom_","gatepass_","inventory_","sales_"))]
        note = [x for x in p[3:] if x not in cands]
        hrows.append([qid, text, T[t], "", "|".join(cands), "|".join(note)])
    else:
        tool = p[3] if len(p) > 3 else ""; alts = p[4] if len(p) > 4 else ""; note = "|".join(p[5:])
        hrows.append([qid, text, T[t], tool, alts, note])
with open("heldout.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["query_id","query","label_type","primary_tool","acceptable_alts","notes"]); w.writerows(hrows)
from collections import Counter
print(Counter(r[2] for r in rows)); print(Counter(r[2] for r in hrows))
