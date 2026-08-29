# Evaluation — ablation-no-recompute-gpt-4o-mini

Model `gpt-4o-mini` · mode `auto` · profile OFF · formats on · probes OFF · gate on

Analyst-minute model: confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)

## recount — per case

| case | truth | verdict | class | bug type | repair | note |
|---|---|---|---|---|---|---|
| `B1_fanout_payments_via_line_items` | BUG | CLEAN | FN | - | - | The SQL query correctly sums the amount captured from completed orders... |
| `B2_fanout_units_via_payments` | BUG | CLEAN | FN | - | - | The SQL query correctly sums the quantity of order items from complete... |
| `B3_null_swallowing_status_filter` | BUG | CLEAN | FN | - | - | The SQL query correctly counts the number of active orders by filterin... |
| `B4_left_join_degraded_to_inner` | BUG | BUG | TP | left_join_degraded_to_inner | correct | The query uses a LEFT JOIN between orders and refunds, but the WHERE c... |
| `B5_between_loses_last_day` | BUG | ESCALATE | FN | - | - | The SQL query is attempting to count orders placed in January 2026, bu... |
| `B6_timezone_day_misattribution` | BUG | BUG | TP | timezone_day_boundary | correct | The query counts orders based on the UTC date without considering the ... |
| `B7_mixed_currency_unit_error` | BUG | BUG | TP | mixed_unit_aggregation | correct | The query aggregates payments from completed orders without filtering ... |
| `B8_missing_status_filter` | BUG | BUG | TP | missing_filter | correct | The SQL query does not filter for completed orders, which is necessary... |
| `C1_clean_distinct_order_count_with_payments` | CLEAN | CLEAN | TN | - | - | The SQL query correctly counts the distinct completed orders from the ... |
| `C2_clean_units_sold_at_line_grain` | CLEAN | CLEAN | TN | - | - | The SQL query correctly sums the quantity of order items from the orde... |
| `C3_clean_null_safe_active_orders` | CLEAN | CLEAN | TN | - | - | The SQL query correctly counts the number of orders that are not cance... |
| `C4_clean_half_open_date_range` | CLEAN | CLEAN | TN | - | - | The SQL query correctly counts the number of orders placed in January ... |

```json
{
  "system": "recount",
  "n_cases": 12,
  "n_bug": 8,
  "n_clean": 4,
  "confusion": {
    "tp": 4,
    "fp": 0,
    "fn": 4,
    "tn": 4
  },
  "precision": 1.0,
  "recall": 0.5,
  "f1": 0.6667,
  "false_alarm_rate": 0.0,
  "repair_accuracy": 0.5,
  "repairs_correct": 4,
  "repairs_attempted": 4,
  "bug_type_accuracy": 1.0,
  "escalations_on_bug": 1,
  "escalations_on_clean": 0,
  "errors": 0,
  "net_analyst_minutes_modelled": 44.0,
  "time_model": "confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)",
  "total_cost_usd": 0.002474,
  "cost_per_case_usd": 0.000206,
  "cost_known": true,
  "total_latency_s": 17.15,
  "latency_per_case_s": 1.43,
  "llm_calls": 12,
  "tool_calls": 28
}
```
