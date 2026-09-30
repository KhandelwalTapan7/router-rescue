"""evaluate.py - baseline vs router.py against labels.csv (dev) and heldout.csv.

    python3 evaluate.py            # summary
    python3 evaluate.py --errors   # also list every disagreement
Python 3.9+, standard library only. Run from the repo root.

Scoring, per query (label_type decides what "right" means):
  TOOL          right = predicted tool in {primary} + acceptable_alts. Abstaining = MISS (safe, not right).
  TOOL_PARTIAL  right = primary/alt ("partial credit" bucket). Abstaining = SAFE. Other tool = WRONG.
  everything else (CLARIFY, NO_TOOL_*): right = abstain. Any tool = WRONG ("silent wrong route").
The baseline's "<no match>" counts as an abstention (production sends it to the fallback layer).
"""
from __future__ import annotations
import csv, importlib.util, statistics, sys, time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
PKG = ROOT / "candidate_package"
sys.path.insert(0, str(ROOT))


def load_baseline():
    spec = importlib.util.spec_from_file_location("baseline", PKG / "baseline.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    def f(q):
        tool, score = m.route(q)
        return tool, min(1.0, score / 9), f"keyword score {score}"
    return f


def load_labels(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def accepted(row):
    return {t for t in [row["primary_tool"], *row["acceptable_alts"].split("|")] if t and row["label_type"] in ("TOOL", "TOOL_PARTIAL")}


def outcome(row, pred):
    lt = row["label_type"]
    if lt in ("TOOL", "TOOL_PARTIAL"):
        if pred in accepted(row): return "right"
        if pred is None: return "miss" if lt == "TOOL" else "safe"
        return "wrong"
    return "right" if pred is None else "wrong"


def run(router, rows):
    res, lat = [], []
    for r in rows:
        t0 = time.perf_counter(); pred, conf, why = router(r["query"]); lat.append((time.perf_counter() - t0) * 1000)
        res.append((r, pred, conf, why, outcome(r, pred)))
    return res, statistics.median(lat)


def pct(n, d): return f"{100 * n / d:5.1f}%" if d else "  n/a"


def summarize(name, res, med):
    tool_rows = [x for x in res if x[0]["label_type"] == "TOOL"]
    abst_rows = [x for x in res if x[0]["label_type"] not in ("TOOL", "TOOL_PARTIAL")]
    part_rows = [x for x in res if x[0]["label_type"] == "TOOL_PARTIAL"]
    c = Counter(x[4] for x in res)
    routed = [x for x in res if x[1] is not None]
    hi = [x for x in routed if x[2] >= 0.8]
    print(f"  {name:<9} decision-acc {pct(c['right'], len(res))} | TOOL rows exact {pct(sum(x[4]=='right' for x in tool_rows), len(tool_rows))}"
          f" (missed/abstained {sum(x[4]=='miss' for x in tool_rows)}) | abstain rows right {pct(sum(x[4]=='right' for x in abst_rows), len(abst_rows))}"
          f" | partial ok {sum(x[4]=='right' for x in part_rows)}/{len(part_rows)}")
    print(f"  {'':<9} WRONG routes {c['wrong']} of {len(res)} ({pct(c['wrong'], len(res))}) = silent-wrong rate | precision when it routes {pct(sum(x[4]=='right' for x in routed), len(routed))}"
          f" | precision at conf>=0.8 {pct(sum(x[4]=='right' for x in hi), len(hi))} (n={len(hi)}) | median latency {med:.3f} ms")


def breakdown(res_by_name):
    print("\n  By label type (right/total):")
    types = sorted({x[0]["label_type"] for x in next(iter(res_by_name.values()))})
    print(f"  {'label_type':<18}" + "".join(f"{n:>14}" for n in res_by_name))
    for t in types:
        line = f"  {t:<18}"
        for res in res_by_name.values():
            sub = [x for x in res if x[0]["label_type"] == t]
            line += f"{sum(x[4]=='right' for x in sub):>9}/{len(sub):<4}"
        print(line)
    print("\n  TOOL rows by module (right/total):")
    mods = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for n, res in res_by_name.items():
        for r, pred, conf, why, o in res:
            if r["label_type"] == "TOOL":
                m = r["primary_tool"].split("_")[0]; mods[m][n][1] += 1; mods[m][n][0] += o == "right"
    print(f"  {'module':<12}" + "".join(f"{n:>14}" for n in res_by_name))
    for m in sorted(mods):
        print(f"  {m:<12}" + "".join(f"{mods[m][n][0]:>9}/{mods[m][n][1]:<4}" for n in res_by_name))
    print("\n  Baseline wrong-route causes (wrong tool though a tool was right, or routed a non-lookup):")
    for n, res in res_by_name.items():
        if n != "baseline": continue
        k = Counter()
        for r, pred, conf, why, o in res:
            if o != "wrong": continue
            if r["label_type"] in ("TOOL", "TOOL_PARTIAL"):
                same_entity = pred.rsplit("_", 1)[0] == r["primary_tool"].rsplit("_", 1)[0]
                k["right entity, wrong shape (count/list/value)" if same_entity else "wrong entity/tool"] += 1
            else:
                k[f"routed a {r['label_type']} query to a tool"] += 1
        for a, b in k.most_common(): print(f"    {b:>3}  {a}")


def show_errors(name, res):
    print(f"\n--- {name}: disagreements ---")
    for r, pred, conf, why, o in res:
        if o in ("wrong", "miss"):
            exp = r["primary_tool"] or ("abstain:" + r["label_type"])
            print(f"  [{o:<5}] {r['query_id']} {r['query'][:58]!r:<62} exp={exp:<34} got={pred} ({conf:.2f}) {why[:70]}")


def main():
    base, mine = load_baseline(), None
    import router
    mine = router.route
    for title, path in (("DEV  labels.csv (150; router was tuned on these)", ROOT / "labels.csv"),
                        ("HELD-OUT heldout.csv (40; written after the router design, same author - NOT independent)", ROOT / "heldout.csv")):
        rows = load_labels(path)
        rb, mb = run(base, rows); rm, mm = run(mine, rows)
        print(f"\n=== {title} ===")
        summarize("baseline", rb, mb); summarize("router.py", rm, mm)
        breakdown({"baseline": rb, "router.py": rm})
        if "--errors" in sys.argv:
            show_errors("router.py", rm)
            if path.name == "labels.csv": show_errors("baseline", rb)


if __name__ == "__main__":
    main()
