# Router Rescue

Python 3.9+, standard library only. Run from the repo root:

    python3 evaluate.py            # baseline vs router.py on labels.csv (dev) and heldout.csv
    python3 evaluate.py --errors   # list every disagreement
    python3 experiments/exp.py     # the abandoned approaches (TF-IDF, baseline patches)
    python3 router.py "how many purchase orders are pending"
    python3 build_labels.py        # regenerates labels.csv / heldout.csv from the tables inside it

| File | What |
|---|---|
| `labels.csv`, `LABELING_RULES.md` | ground truth and the rules behind it |
| `router.py` | gates -> entity -> shape -> per-entity resolver, abstains explicitly |
| `evaluate.py` | scoring; `REPORT.md` has the numbers and analysis |
| `candidate_package/` | original files, untouched |
