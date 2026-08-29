# Evaluation — ablation-lean-gpt-4o-mini

Model `gpt-4o-mini` · mode `auto` · profile OFF · probes OFF · gate on

Analyst-minute model: confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)

## recount — per case

| case | truth | verdict | class | bug type | repair | note |
|---|---|---|---|---|---|---|
| `B1_fanout_payments_via_line_items` | BUG | BUG | TP | wrong_aggregation_grain | correct | The query under review aggregates payments based on order items, which... |
| `B2_fanout_units_via_payments` | BUG | BUG | TP | mixed_unit_aggregation | correct | The query under review joins the payments table, which is not necessar... |
| `B3_null_swallowing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query under review counts orders with a status that is not 'cancel... |
| `B4_left_join_degraded_to_inner` | BUG | BUG | TP | wrong_aggregation_grain | correct | The query under review counts orders based on the refunds table, which... |
| `B5_between_loses_last_day` | BUG | BUG | TP | date_range_truncation | wrong | The query under review uses a date range that includes the entire day ... |
| `B6_timezone_day_misattribution` | BUG | BUG | TP | timezone_day_boundary | wrong | The query under review does not account for the timezone difference wh... |
| `B7_mixed_currency_unit_error` | BUG | BUG | TP | missing_filter | correct | The query under review does not filter for the currency 'IDR', which i... |
| `B8_missing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query under review does not filter for completed orders, which is ... |
| `C1_clean_distinct_order_count_with_payments` | CLEAN | CLEAN | TN | - | - | The query correctly counts distinct completed orders from the 'orders'... |
| `C2_clean_units_sold_at_line_grain` | CLEAN | CLEAN | TN | - | - | The query correctly sums the quantity of order items from the order_it... |
| `C3_clean_null_safe_active_orders` | CLEAN | CLEAN | TN | - | - | The query correctly counts the number of active orders from the 'order... |
| `C4_clean_half_open_date_range` | CLEAN | BUG | FP | timezone_day_boundary | wrong | The query under review uses a date range that does not account for the... |

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
  "repair_accuracy": 0.75,
  "repairs_correct": 6,
  "repairs_attempted": 8,
  "bug_type_accuracy": 0.375,
  "escalations_on_bug": 0,
  "escalations_on_clean": 0,
  "errors": 0,
  "net_analyst_minutes_modelled": 88.0,
  "time_model": "confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)",
  "total_cost_usd": 0.004334,
  "cost_per_case_usd": 0.000361,
  "cost_known": true,
  "total_latency_s": 25.95,
  "latency_per_case_s": 2.16,
  "llm_calls": 24,
  "tool_calls": 24
}
```
