| run | F1 | precision | recall | false alarms | repairs | escalations | cost/case |
|---|---|---|---|---|---|---|---|
| `main-gpt-4o-mini/baseline` | 93% | 100% | 88% | 0/4 | 6/8 | 0 | $0.00019 |
| `main-gpt-4o-mini/recount` | 94% | 89% | 100% | 1/4 | 6/8 | 0 | $0.00037 |
| `ablation-no-recompute-gpt-4o-mini/recount` | 55% | 100% | 38% | 0/4 | 3/8 | 2 | $0.00021 |
| `ablation-no-gate-gpt-4o-mini/recount` | 94% | 89% | 100% | 1/4 | 6/8 | 0 | $0.00037 |
| `ablation-add-formats-gpt-4o-mini/recount` | 93% | 100% | 88% | 0/4 | 7/8 | 0 | $0.00038 |
| `ablation-add-profile-gpt-4o-mini/recount` | 84% | 73% | 100% | 3/4 | 5/8 | 0 | $0.00034 |
| `ablation-add-probes-gpt-4o-mini/recount` | 94% | 89% | 100% | 1/4 | 4/8 | 0 | $0.00081 |
