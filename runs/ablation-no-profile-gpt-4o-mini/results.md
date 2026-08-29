# Evaluation — ablation-no-profile-gpt-4o-mini

Model `gpt-4o-mini` · mode `auto` · profile OFF · probes on · gate on

Analyst-minute model: confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)

## recount — per case

| case | truth | verdict | class | bug type | repair | note |
|---|---|---|---|---|---|---|
| `B1_fanout_payments_via_line_items` | BUG | BUG | TP | wrong_aggregation_grain | wrong | The query under review aggregates payments from the payments table wit... |
| `B2_fanout_units_via_payments` | BUG | BUG | TP | mixed_unit_aggregation | correct | The query under review aggregates quantities from order_items while al... |
| `B3_null_swallowing_status_filter` | BUG | BUG | TP | null_swallowing_predicate | correct | The query under review does not account for orders with a NULL status,... |
| `B4_left_join_degraded_to_inner` | BUG | BUG | TP | left_join_degraded_to_inner | correct | The query under review incorrectly filters out non-refunded orders due... |
| `B5_between_loses_last_day` | BUG | BUG | TP | date_range_truncation | wrong | The query under review uses a date range that includes the start of Ja... |
| `B6_timezone_day_misattribution` | BUG | BUG | TP | timezone_day_boundary | wrong | The query under review does not account for the timezone difference, l... |
| `B7_mixed_currency_unit_error` | BUG | BUG | TP | missing_filter | wrong | The query under review does not filter payments based on the currency ... |
| `B8_missing_status_filter` | BUG | BUG | TP | missing_filter | wrong | The query does not filter out orders that are not completed, as eviden... |
| `C1_clean_distinct_order_count_with_payments` | CLEAN | CLEAN | TN | - | - | The query correctly counts distinct completed orders from the 'orders'... |
| `C2_clean_units_sold_at_line_grain` | CLEAN | CLEAN | TN | - | - | The query correctly sums the quantity of order_items associated with c... |
| `C3_clean_null_safe_active_orders` | CLEAN | CLEAN | TN | - | - | The query correctly counts all orders that are not cancelled, includin... |
| `C4_clean_half_open_date_range` | CLEAN | BUG | FP | timezone_day_boundary | wrong | The query under review counts orders based on the assumption that all ... |

```json
{
  "system": "recount",
  "n_cases": 12,
  "n_bug": 8,
  "n_clean": 4,
  "confusion": {
    "tp": 8,
    "fp": 1,
    "fn": 0,
    "tn": 3
  },
  "precision": 0.8889,
  "recall": 1.0,
  "f1": 0.9412,
  "false_alarm_rate": 0.25,
  "repair_accuracy": 0.375,
  "repairs_correct": 3,
  "repairs_attempted": 8,
  "bug_type_accuracy": 0.625,
  "escalations_on_bug": 0,
  "escalations_on_clean": 0,
  "errors": 0,
  "net_analyst_minutes_modelled": 88.0,
  "time_model": "confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)",
  "total_cost_usd": 0.009604,
  "cost_per_case_usd": 0.0008,
  "cost_known": true,
  "total_latency_s": 107.97,
  "latency_per_case_s": 9.0,
  "llm_calls": 37,
  "tool_calls": 73
}
```
