| run | F1 | precision | recall | false alarms | repairs | escalations | cost/case |
|---|---|---|---|---|---|---|---|
| `main-gpt-4o-mini/baseline` | 93% | 100% | 88% | 0/4 | 7/8 | 0 | $0.00019 |
| `main-gpt-4o-mini/recount` | 89% | 80% | 100% | 2/4 | 8/8 | 0 | $0.00076 |
| `ablation-no-profile-gpt-4o-mini/recount` | 94% | 89% | 100% | 1/4 | 3/8 | 0 | $0.00080 |
| `ablation-no-probes-gpt-4o-mini/recount` | 89% | 80% | 100% | 2/4 | 7/8 | 0 | $0.00033 |
| `ablation-no-recompute-gpt-4o-mini/recount` | 75% | 75% | 75% | 2/4 | 6/8 | 0 | $0.00063 |
| `ablation-no-gate-gpt-4o-mini/recount` | 89% | 80% | 100% | 2/4 | 8/8 | 0 | $0.00076 |
| `ablation-lean-gpt-4o-mini/recount` | 94% | 89% | 100% | 1/4 | 6/8 | 0 | $0.00036 |
