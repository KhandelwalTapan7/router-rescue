import math, re, sys, json, importlib.util
from pathlib import Path
from collections import Counter
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
import evaluate as ev
tools = json.loads((ROOT / "candidate_package/tools.json").read_text())
rows = ev.load_labels(ROOT / "labels.csv")
def report(name, fn):
    res, med = ev.run(fn, rows); c = Counter(x[4] for x in res); routed = sum(x[1] is not None for x in res)
    print(f"{name:<34} decision-acc {100*c['right']/150:5.1f}%  wrong-routes {c['wrong']:>3}  routed {routed:>3}/150  abstain-rows-right "
          f"{sum(x[4]=='right' for x in res if x[0]['label_type'] not in ('TOOL','TOOL_PARTIAL'))}/{sum(r['label_type'] not in ('TOOL','TOOL_PARTIAL') for r in rows)}")
# ---- E1
tok = lambda s: re.findall(r"[a-z0-9]+", s.lower())
docs = {i: tok(t["description"] + " " + " ".join(t["keywords"]) + " " + t["module"] + " " + t["entity"]) for i, t in tools.items()}
df = Counter(w for d in docs.values() for w in set(d)); N = len(docs)
idf = lambda w: math.log((N + 1) / (df.get(w, 0) + 1)) + 1
def vec(ws): c = Counter(ws); return {w: n * idf(w) for w, n in c.items()}
dv = {i: vec(d) for i, d in docs.items()}
def cos(a, b):
    num = sum(v * b.get(w, 0) for w, v in a.items()); den = math.sqrt(sum(v*v for v in a.values())) * math.sqrt(sum(v*v for v in b.values()))
    return num / den if den else 0
def e1(th):
    def f(q):
        v = vec([w.rstrip("s") for w in tok(q)]); dvv = {i: vec([w.rstrip("s") for w in d]) for i, d in docs.items()} if False else dv
        s = sorted(((cos(v, d), i) for i, d in dv.items()), reverse=True)
        return (s[0][1], s[0][0], "tfidf") if s[0][0] >= th else (None, s[0][0], "ABSTAIN low sim")
    return f
for th in (0.0, 0.15, 0.25, 0.35): report(f"E1 tf-idf cosine th={th}", e1(th))
# ---- E2 / E3 (patch a copy of the baseline module)
def patched(min_score=2, shape_fix=False):
    spec = importlib.util.spec_from_file_location("b2", ROOT / "candidate_package/baseline.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.MIN_SCORE = min_score
    if shape_fix:
        def sel(query):
            q = query.lower(); wr = bool(re.search(r"\b(list|show|display|see|which|ids?|details)\b|\b(give|get)\s+me\b", q)); wc = bool(re.search(r"\b(how many|count|number of|total number)\b", q))
            best, bs = None, 0
            for t in m.TOOL_REGISTRY.values():
                s = m._kw_score(t, q)
                if s > 0:
                    o = t["output_type"]
                    if wr: s += 2 if o == "list" else -2
                    if wc: s += 2 if o in ("count", "scalar") else -2
                if s > bs: bs, best = s, t
            return (best, bs) if best and bs >= m.MIN_SCORE else None
        m.select_tool = sel
        m.route = lambda q: (lambda h: (h[0]["id"], h[1]) if h else (None, 0))(sel(q))
    return lambda q: (lambda r: (r[0], min(1, r[1] / 9), "kw"))(m.route(q))
report("baseline (as shipped)", patched())
report("E2 baseline MIN_SCORE=1", patched(1))
report("E3 baseline + shape penalty", patched(2, True))
report("E3b shape penalty + MIN_SCORE=1", patched(1, True))
report("router.py", __import__("router").route)
