# Evaluation — ablation-no-gate-gpt-4o-mini

Model `gpt-4o-mini` · mode `auto` · profile on · probes on · gate OFF

Analyst-minute model: confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)

## recount — per case

| case | truth | verdict | class | bug type | repair | note |
|---|---|---|---|---|---|---|
| `B1_fanout_payments_via_line_items` | BUG | BUG | TP | wrong_aggregation_grain | correct | The query aggregates payments based on completed orders but includes o... |
| `B2_fanout_units_via_payments` | BUG | BUG | TP | mixed_unit_aggregation | correct | The query aggregates quantities from order_items while filtering on co... |
| `B3_null_swallowing_status_filter` | BUG | BUG | TP | null_swallowing_predicate | correct | The query in the SQL under review does not account for orders with a N... |
| `B4_left_join_degraded_to_inner` | BUG | BUG | TP | left_join_degraded_to_inner | correct | The query under review incorrectly counts the number of orders as 103 ... |
| `B5_between_loses_last_day` | BUG | BUG | TP | timezone_day_boundary | correct | The query under review does not correctly account for orders placed on... |
| `B6_timezone_day_misattribution` | BUG | BUG | TP | timezone_day_boundary | correct | The query under review counts orders based on UTC timestamps without a... |
| `B7_mixed_currency_unit_error` | BUG | BUG | TP | mixed_unit_aggregation | correct | The query under review aggregates payments for completed orders but in... |
| `B8_missing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query does not filter for completed orders, which is necessary to ... |
| `C1_clean_distinct_order_count_with_payments` | CLEAN | BUG | FP | fanout_join | wrong | The query under review counts distinct orders and sums payments, but t... |
| `C2_clean_units_sold_at_line_grain` | CLEAN | BUG | FP | wrong_aggregation_grain | correct | The query under review aggregates units sold from order_items, but the... |
| `C3_clean_null_safe_active_orders` | CLEAN | CLEAN | TN | - | - | The query correctly counts orders that are not cancelled, including th... |
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
  "repair_accuracy": 1.0,
  "repairs_correct": 8,
  "repairs_attempted": 8,
  "bug_type_accuracy": 0.625,
  "escalations_on_bug": 0,
  "escalations_on_clean": 0,
  "errors": 0,
  "net_analyst_minutes_modelled": 80.0,
  "time_model": "confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)",
  "total_cost_usd": 0.009095,
  "cost_per_case_usd": 0.000758,
  "cost_known": true,
  "total_latency_s": 0.18,
  "latency_per_case_s": 0.01,
  "llm_calls": 36,
  "tool_calls": 84
}
```
