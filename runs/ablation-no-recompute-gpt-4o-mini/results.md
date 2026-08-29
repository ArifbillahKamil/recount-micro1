# Evaluation — ablation-no-recompute-gpt-4o-mini

Model `gpt-4o-mini` · mode `auto` · profile on · probes on · gate on

Analyst-minute model: confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)

## recount — per case

| case | truth | verdict | class | bug type | repair | note |
|---|---|---|---|---|---|---|
| `B1_fanout_payments_via_line_items` | BUG | BUG | TP | mixed_unit_aggregation | wrong | The query aggregates payment amounts from the payments table but does ... |
| `B2_fanout_units_via_payments` | BUG | CLEAN | FN | - | - | The query correctly sums the quantities from order_items for completed... |
| `B3_null_swallowing_status_filter` | BUG | BUG | TP | null_swallowing_predicate | correct | The query does not account for orders with a NULL status, which are st... |
| `B4_left_join_degraded_to_inner` | BUG | CLEAN | FN | - | - | The query correctly counts all orders and sums the refunded amounts, w... |
| `B5_between_loses_last_day` | BUG | BUG | TP | timezone_day_boundary | correct | The query does not account for orders placed on the last day of Januar... |
| `B6_timezone_day_misattribution` | BUG | BUG | TP | timezone_day_boundary | wrong | The query does not account for the timezone difference, leading to an ... |
| `B7_mixed_currency_unit_error` | BUG | BUG | TP | mixed_unit_aggregation | correct | The query aggregates payments without filtering for the IDR currency, ... |
| `B8_missing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query does not filter for completed orders, which is necessary to ... |
| `C1_clean_distinct_order_count_with_payments` | CLEAN | BUG | FP | fanout_join | wrong | The query aggregates payments for completed orders, but the payments t... |
| `C2_clean_units_sold_at_line_grain` | CLEAN | CLEAN | TN | - | - | The query correctly aggregates the total quantity of units sold from t... |
| `C3_clean_null_safe_active_orders` | CLEAN | CLEAN | TN | - | - | The query correctly counts orders that are not cancelled, including th... |
| `C4_clean_half_open_date_range` | CLEAN | BUG | FP | timezone_day_boundary | wrong | The original query counts orders based on a timestamp format that does... |

```json
{
  "system": "recount",
  "n_cases": 12,
  "n_bug": 8,
  "n_clean": 4,
  "confusion": {
    "tp": 6,
    "fp": 2,
    "fn": 2,
    "tn": 2
  },
  "precision": 0.75,
  "recall": 0.75,
  "f1": 0.75,
  "false_alarm_rate": 0.5,
  "repair_accuracy": 0.5,
  "repairs_correct": 4,
  "repairs_attempted": 6,
  "bug_type_accuracy": 0.6667,
  "escalations_on_bug": 0,
  "escalations_on_clean": 0,
  "errors": 0,
  "net_analyst_minutes_modelled": 56.0,
  "time_model": "confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)",
  "total_cost_usd": 0.007657,
  "cost_per_case_usd": 0.000638,
  "cost_known": true,
  "total_latency_s": 25.49,
  "latency_per_case_s": 2.12,
  "llm_calls": 24,
  "tool_calls": 80
}
```
