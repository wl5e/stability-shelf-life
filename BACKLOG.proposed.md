# Proposed items (awaiting promotion)

# scripts/replenish.py appends conforming proposals here and promotes them
# automatically with scripts/backlog.py:promote_safe().
- [ ] `q1e-confidence-level` Add --confidence to select 90, 95 or 99 percent shelf-life bounds. Acceptance: the 90 percent lower bound is greater than the 95 percent lower bound on the same data; a test asserts it. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --confidence 0.90 --json`. Files: stability_shelf_life/model.py, main.py, tests/test_model.py — ICH Q1E uses 95 percent, but other internal specifications use different confidence levels. | proposed
- [ ] `q1e-assay-cv` Add coefficient of variation to batch descriptive statistics. Acceptance: JSON summary contains cv equal to sd/mean and a CLI test checks it. Demo: `python main.py q1e --input examples/stability_data.csv --limit 90 --json`. Files: stability_shelf_life/model.py, main.py, tests/test_model.py — Assay variability is often reviewed as percent CV, not raw standard deviation. | proposed
