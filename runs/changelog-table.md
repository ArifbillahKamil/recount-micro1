| run | F1 | precision | recall | false alarms | repairs | escalations | cost/case |
|---|---|---|---|---|---|---|---|
| `main-gpt-4o-mini/baseline` | 93% | 100% | 88% | 0/4 | 7/8 | 0 | $0.00019 |
| `main-gpt-4o-mini/recount` | 84% | 73% | 100% | 3/4 | 5/8 | 0 | $0.00077 |
| `ablation-no-profile-gpt-4o-mini/recount` | 94% | 89% | 100% | 1/4 | 5/8 | 0 | $0.00081 |
| `ablation-no-probes-gpt-4o-mini/recount` | 84% | 73% | 100% | 3/4 | 4/8 | 0 | $0.00033 |
| `ablation-no-recompute-gpt-4o-mini/recount` | 75% | 75% | 75% | 2/4 | 4/8 | 0 | $0.00064 |
| `ablation-no-gate-gpt-4o-mini/recount` | 84% | 73% | 100% | 3/4 | 5/8 | 0 | $0.00077 |
| `ablation-lean-gpt-4o-mini/recount` | 94% | 89% | 100% | 1/4 | 6/8 | 0 | $0.00036 |
