# Evaluation — ablation-no-probes-gpt-4o-mini

Model `gpt-4o-mini` · mode `auto` · profile on · probes OFF · gate on

Analyst-minute model: confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)

## recount — per case

| case | truth | verdict | class | bug type | repair | note |
|---|---|---|---|---|---|---|
| `B1_fanout_payments_via_line_items` | BUG | BUG | TP | wrong_aggregation_grain | correct | The query under review aggregates payments based on completed orders b... |
| `B2_fanout_units_via_payments` | BUG | BUG | TP | missing_filter | correct | The query under review only counts units sold from completed orders, w... |
| `B3_null_swallowing_status_filter` | BUG | BUG | TP | null_swallowing_predicate | correct | The query under review counts orders with a status that is not 'cancel... |
| `B4_left_join_degraded_to_inner` | BUG | BUG | TP | wrong_aggregation_grain | correct | The query under review counts only the number of refunds (103) instead... |
| `B5_between_loses_last_day` | BUG | BUG | TP | date_range_truncation | correct | The query under review uses a date range that includes the entire day ... |
| `B6_timezone_day_misattribution` | BUG | BUG | TP | timezone_day_boundary | correct | The query under review does not account for the local timezone (Asia/J... |
| `B7_mixed_currency_unit_error` | BUG | BUG | TP | missing_filter | correct | The query under review does not filter for the currency 'IDR', which i... |
| `B8_missing_status_filter` | BUG | BUG | TP | missing_filter | wrong | The query under review does not filter for completed orders, as it lac... |
| `C1_clean_distinct_order_count_with_payments` | CLEAN | BUG | FP | missing_filter | wrong | The query under review counts completed orders but does not account fo... |
| `C2_clean_units_sold_at_line_grain` | CLEAN | BUG | FP | missing_filter | wrong | The query under review only filters for completed orders, while the in... |
| `C3_clean_null_safe_active_orders` | CLEAN | CLEAN | TN | - | - | The query correctly counts the number of active orders by including th... |
| `C4_clean_half_open_date_range` | CLEAN | CLEAN | TN | - | - | The query correctly counts the number of orders placed in January 2026... |

```json
{
  "system": "recount",
  "n_cases": 12,
  "n_bug": 8,
  "n_clean": 4,
  "confusion": {
    "tp": 8,
    "fp": 2,
    "fn": 0,
    "tn": 2
  },
  "precision": 0.8,
  "recall": 1.0,
  "f1": 0.8889,
  "false_alarm_rate": 0.5,
  "repair_accuracy": 0.875,
  "repairs_correct": 7,
  "repairs_attempted": 8,
  "bug_type_accuracy": 0.5,
  "escalations_on_bug": 0,
  "escalations_on_clean": 0,
  "errors": 0,
  "net_analyst_minutes_modelled": 80.0,
  "time_model": "confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)",
  "total_cost_usd": 0.003997,
  "cost_per_case_usd": 0.000333,
  "cost_known": true,
  "total_latency_s": 22.13,
  "latency_per_case_s": 1.84,
  "llm_calls": 24,
  "tool_calls": 36
}
```
