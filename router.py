"""router.py - entity -> shape -> tool router with explicit abstention.

Design (stdlib only, deterministic, ~1 ms/query):
  1. Gates: things that are NOT lookups (write actions, how-to, analysis, missing referent).
  2. Entity: first match in an ORDERED list (specific before generic), so 'job work order'
     is a job-work thing, not a production work order.
  3. Shape: count / list / value, read from the wording (count > list > value).
  4. Per-entity resolver picks one of the 62 tools, or abstains (None) with a category.

route(query) -> (tool_name | None, confidence, reason). None = "send to fallback layer";
the reason starts with ABSTAIN[<category>] so evaluate.py can score abstention types.
Not a general NLU system: it is a readable decision table tuned on the 150 dev queries.
"""
from __future__ import annotations
import difflib, json, re
from pathlib import Path

_TOOLS = json.loads((Path(__file__).parent / "candidate_package" / "tools.json").read_text())

# ---------------------------------------------------------------- normalisation
_SYN = {"cnt": "count", "qty": "quantity", "pos": "po", "sos": "so", "wos": "wo"}
_VOCAB = {w for t in _TOOLS.values() for k in t["keywords"] for w in k.split() if len(w) >= 5}
_VOCAB |= {"pending", "approval", "employees", "purchase", "orders", "inspection", "customers"}


def _normalise(q: str) -> tuple[str, bool]:
    fixed = False
    out = []
    for tok in re.findall(r"[a-z0-9\-']+", q.lower()):
        tok = tok.strip("'")
        if tok in _SYN:
            tok = _SYN[tok]
        elif len(tok) >= 5 and tok not in _VOCAB and not re.search(r"\d", tok):
            m = difflib.get_close_matches(tok, _VOCAB, n=1, cutoff=0.84)
            if m:
                tok, fixed = m[0], True
        out.append(tok)
    return " ".join(out), fixed


# ---------------------------------------------------------------- gates
_CONTEXT = re.compile(r"\b(as per|as discussed|our discussion|that list|same list|again|earlier|previous|last time|them|those|these)\b")
_ACTION = re.compile(r"^(please |kindly |can you |could you )?(approve|delete|create|update|reject|cancel|remove|edit|modify|add|close|send|change|submit|post|raise)\b")
_HOWTO = re.compile(r"\bhow (do|does|can|should|to)\b|\bexplain\b|\bhow\b.*\bworks\b|\b(process|procedure|policy|steps|guide)\b")
_ANALYSIS = re.compile(r"\b(why|compare|versus|vs|cost|trend|best|worst|highest|lowest|most)\b|\btop \d+")

# ---------------------------------------------------------------- shapes
_COUNT = re.compile(r"how many|\bcount|number of|headcount|total number")
_LIST = re.compile(r"\b(list|show|display|which|who|give me|get me|details|numbers|recent)\b|\b(first|last|top)\s+\d+")
_VALUE = re.compile(r"value|spend|amount|revenue|valuation|worth|total")


def _shape(q: str) -> str | None:
    if _COUNT.search(q): return "count"
    if _LIST.search(q): return "list"
    if _VALUE.search(q): return "value"
    return None


# ---------------------------------------------------------------- entities (ORDER MATTERS)
_ENT = [
    ("jobwork", r"job\s?-?work"), ("gatepass", r"gate\s?pass"),
    ("action_item", r"action items?|tasks? from meeting"),
    ("mom", r"\bmoms?\b|minutes of meeting|meetings?"),
    ("store_issue", r"material issues?|issue slips?|store issues?"),
    ("indent", r"\bindents?\b"),
    ("item_master", r"item master|item catalogu?e|catalogu?e|registered items?"),
    ("wip", r"\bwip\b|work in progress"),
    ("workorder", r"work orders?|\bwo\b|production orders?"),
    ("shift", r"\bshift"), ("downtime", r"downtime|breakdown time"),
    ("output", r"production (output|quantity)|total production|output|produced"),
    ("machine", r"machines?"),
    ("attendance", r"attendance|\bpresent\b|\babsent\b"),
    ("leave", r"\bleaves?\b|on leave"),
    ("joiner", r"new joiners?|who joined|\bjoined\b|new hires?|new employees?"),
    ("employee", r"employees?|staff|headcount|people|workforce"),
    ("department", r"departments?"),
    ("ncr", r"\bncrs?\b|non[- ]?conformance"),
    ("inspection", r"inspections?"),
    ("rejection", r"reject(ion)? (rate|percentage|ratio)|percentage rejected"),
    ("coa", r"\bcoas?\b|certificates? of analysis"),
    ("grn", r"\bgrns?\b|goods receipts?|material receipts?"),
    ("po", r"purchase orders?|\bpo\b|vendor orders?"),
    ("invoice", r"invoices?"),
    ("payment", r"payments?|unpaid vendor"),
    ("outstanding", r"outstanding|receivables?|money owed"),
    ("so", r"sales orders?|\bso\b|customer orders?|sales (value|revenue|amount)|revenue"),
    ("customer", r"customers?"),
    ("lead", r"\bleads?\b|enquir(y|ies)"),
    ("pipeline", r"pipeline|opportunit(y|ies)"),
    ("stock", r"stock|inventory|reorder|shortage|warehouse|quantity of|\bitems?\b"),
    ("vendor", r"vendors?|suppliers?"),
    ("generic_order", r"\borders?\b"),
]
_ENT = [(n, re.compile(p)) for n, p in _ENT]

_FIXED = {  # entities with exactly one tool: shape is irrelevant
    "machine": "production_machine_status_list", "downtime": "production_downtime_total",
    "output": "production_output_total", "shift": "production_shift_output",
    "wip": "production_wip_count", "attendance": "hr_attendance_today",
    "joiner": "hr_new_joiners_list", "rejection": "quality_rejection_rate",
    "coa": "quality_coa_count", "department": "hr_department_list",
    "pipeline": "crm_opportunity_total_value", "outstanding": "finance_outstanding_total",
    "indent": "store_indent_pending_count",
}
_TABLE = {  # entity -> {shape: tool}
    "po": {"count": "purchase_po_count", "list": "purchase_po_list", "value": "purchase_po_total_value"},
    "grn": {"count": "purchase_grn_count", "list": "purchase_grn_list"},
    "item_master": {"count": "inventory_item_master_count", "list": "inventory_item_master_list"},
    "so": {"count": "sales_so_count", "list": "sales_so_list", "value": "sales_so_total_value"},
    "customer": {"count": "sales_customer_count", "list": "sales_customer_list"},
    "employee": {"count": "hr_employee_count", "list": "hr_employee_list"},
    "ncr": {"count": "quality_ncr_count", "list": "quality_ncr_list"},
    "workorder": {"count": "production_workorder_count", "list": "production_workorder_list"},
    "mom": {"count": "mom_count", "list": "mom_list"},
    "action_item": {"count": "mom_action_item_count", "list": "mom_action_item_list"},
    "store_issue": {"count": "store_issue_count", "list": "store_issue_list"},
    "lead": {"count": "crm_lead_count", "list": "crm_lead_list"},
}
for _t in [t for d in _TABLE.values() for t in d.values()] + list(_FIXED.values()):
    assert _t in _TOOLS, f"router references unknown tool {_t}"

_PO_ID = re.compile(r"\bpo\s*-?\s*\d+|\bpo\d+")
_VENDOR_NAMED = re.compile(r"\b(for|from|to|by|of)\s+(vendor|supplier)s?\s+(?!wise|list|name)\w+")
_ITEM_CODE = re.compile(r"\b[a-z]{1,4}-?\d{2,}\b|\b\d{4,}\b")


def _ab(cat: str, conf: float, why: str):
    return None, conf, f"ABSTAIN[{cat}]: {why}"


def route(query: str) -> tuple[str | None, float, str]:
    q, typo = _normalise(query)
    tc = 0.6 if typo else 0.0  # confidence haircut when we had to guess spelling

    if _ACTION.search(q): return _ab("action", 0.9, "write/mutating request; read-only tools cannot do it")
    has_count = bool(_COUNT.search(q))
    if _CONTEXT.search(q): return _ab("context", 0.85, "refers to earlier conversation or an unresolved referent")
    if _ANALYSIS.search(q): return _ab("analysis", 0.8, "comparison/ranking/causal question; no single lookup answers it")
    if _HOWTO.search(q) and not has_count: return _ab("howto", 0.85, "procedural or explanatory question")

    ent = next((n for n, rx in _ENT if rx.search(q)), None)
    shape = _shape(q)
    compound = bool(re.search(r"\band what\b|what does .* mean", q))
    note = " (compound question: only the data part is routed)" if compound else ""

    if ent is None:
        if shape == "value": return _ab("clarify", 0.6, "a total was asked for but not of what")
        if shape in ("count", "list") and len(q.split()) <= 5:
            return _ab("context", 0.7, "count/list with no entity; probably a follow-up")
        return _ab("oos", 0.75, "no ERP entity recognised")

    def hit(tool, conf, why):
        c = min(conf, tc) if typo else conf
        return tool, c, f"{ent}+{shape or 'no-shape'} -> {why}{note}"

    if ent in _FIXED:
        return hit(_FIXED[ent], 0.9, "entity has a single tool")
    if ent == "generic_order":
        return _ab("clarify", 0.6, "'orders' could be purchase, sales, work or job-work orders")
    if ent == "vendor":
        return _ab("gap", 0.6, "per-vendor aggregation not in catalog (by_vendor needs a named vendor)")

    if ent == "po":
        if _PO_ID.search(q): return _ab("gap", 0.7, "single PO lookup by number; no tool takes a document id")
        if "expir" in q: return hit("purchase_po_expiring", 0.9, "expiry wording")
        if _VENDOR_NAMED.search(q): return hit("purchase_po_by_vendor", 0.9, "named vendor")
        if re.search(r"vendors?|suppliers?", q) and not shape == "count":
            return _ab("gap", 0.6, "vendor mentioned without a name")
        pend = re.search(r"pending approval|awaiting approval|waiting for approval|stuck in approval|unapproved", q)
        if shape in ("list", None) and pend: return hit("purchase_po_pending_approval_list", 0.8, "approval-queue wording")
        if shape is None: return _ab("clarify", 0.6, "PO mentioned but no count/list/value intent")
        return hit(_TABLE["po"][shape], 0.9, "shape table")

    if ent == "stock":
        if re.search(r"stock (of|for|level)|quantity of|how much stock|available quantity", q) and _ITEM_CODE.search(q):
            return hit("inventory_stock_by_item", 0.9, "stock of a specific item code")
        if re.search(r"valuation|worth|value", q): return hit("inventory_stock_value_total", 0.9, "value wording")
        if re.search(r"low|reorder|shortage|running out|below", q): return hit("inventory_low_stock_list", 0.9, "low-stock wording")
        if shape == "count": return hit("inventory_stock_count", 0.85, "count of stock items")
        if shape == "list": return hit("inventory_stock_list", 0.85, "list of stock")
        return _ab("clarify", 0.6, "stock mentioned but intent unclear (list/count/one item/value)")

    if ent == "jobwork":
        if re.search(r"vendors?|suppliers?", q): return hit("jobwork_vendor_list", 0.85, "job-work vendors")
        if re.search(r"pending|not returned|outstanding|awaited|yet|overdue", q): return hit("jobwork_pending_count", 0.75, "awaiting return")
        if shape in ("count", "list"): return hit("jobwork_po_" + shape, 0.85, "shape table")
        return _ab("clarify", 0.6, "job work mentioned, intent unclear")

    if ent == "gatepass":
        if re.search(r"returnable|not (been )?returned|pending return|overdue", q):
            return hit("gatepass_pending_return_count", 0.7, "pending-return wording (count only)")
        if shape in ("count", "list"): return hit("gatepass_" + shape, 0.85, "shape table")
        return _ab("clarify", 0.6, "gate pass mentioned, intent unclear")

    if ent == "leave":
        if shape == "list": return hit("hr_leave_list", 0.85, "leave rows")
        if shape == "count": return hit("hr_leave_pending_count", 0.8, "leave count")
        return _ab("clarify", 0.6, "leave mentioned, intent unclear")

    if ent == "employee" and re.search(r"(by|wise)\s+department|department\s?wise", q):
        return hit("hr_department_list", 0.75, "per-department headcount")

    if ent == "inspection":
        if shape == "list": return hit("quality_inspection_list", 0.85, "inspection rows")
        if shape == "count" or "pending" in q: return hit("quality_inspection_pending_count", 0.8, "pending inspections")
        return _ab("clarify", 0.6, "inspection mentioned, intent unclear")

    if ent == "invoice":
        if re.search(r"overdue|past due|late", q): return hit("finance_invoice_overdue_list", 0.9, "overdue")
        if shape == "count": return hit("sales_invoice_count", 0.85, "invoice count")
        return _ab("gap", 0.6, "no general invoice list tool")

    if ent == "payment":
        if not re.search(r"pending|due|unpaid|outstanding", q) and shape != "list":
            return _ab("gap", 0.6, "only pending-payment count and payment list exist")
        if shape == "list": return hit("finance_payment_list", 0.85, "payment rows")
        if shape == "count": return hit("finance_payment_pending_count", 0.85, "pending payments count")
        return _ab("clarify", 0.6, "payments mentioned, intent unclear")

    table = _TABLE.get(ent)
    if table is None: return _ab("clarify", 0.5, f"no resolver for {ent}")
    if shape is None: return _ab("clarify", 0.6, f"{ent} mentioned but no count/list/value intent")
    if shape not in table: shape = "list" if "list" in table else "count"
    return hit(table[shape], 0.85, "shape table")


if __name__ == "__main__":
    import sys
    print(route(" ".join(sys.argv[1:])))
