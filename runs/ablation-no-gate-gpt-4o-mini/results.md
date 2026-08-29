# Evaluation — ablation-no-gate-gpt-4o-mini

Model `gpt-4o-mini` · mode `auto` · profile OFF · formats on · probes OFF · gate OFF

Analyst-minute model: confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)

## recount — per case

| case | truth | verdict | class | bug type | repair | note |
|---|---|---|---|---|---|---|
| `B1_fanout_payments_via_line_items` | BUG | BUG | TP | wrong_aggregation_grain | correct | The query under review aggregates payments based on completed orders b... |
| `B2_fanout_units_via_payments` | BUG | BUG | TP | wrong_aggregation_grain | correct | The query under review joins the payments table, which is not necessar... |
| `B3_null_swallowing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query under review counts orders with a status that is not 'cancel... |
| `B4_left_join_degraded_to_inner` | BUG | BUG | TP | wrong_aggregation_grain | correct | The query under review counts orders directly from the 'orders' table,... |
| `B5_between_loses_last_day` | BUG | BUG | TP | date_range_truncation | correct | The query under review uses a date range that includes the entire day ... |
| `B6_timezone_day_misattribution` | BUG | CLEAN | FN | - | - | The query correctly counts the number of orders placed on 31 January 2... |
| `B7_mixed_currency_unit_error` | BUG | BUG | TP | wrong_aggregation_grain | correct | The query under review aggregates payments based on completed orders w... |
| `B8_missing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query under review does not filter for completed orders, which is ... |
| `C1_clean_distinct_order_count_with_payments` | CLEAN | CLEAN | TN | - | - | The query correctly counts distinct completed orders from the 'orders'... |
| `C2_clean_units_sold_at_line_grain` | CLEAN | CLEAN | TN | - | - | Both the query under review and the independent recomputation return t... |
| `C3_clean_null_safe_active_orders` | CLEAN | CLEAN | TN | - | - | The query correctly counts the number of orders that are not cancelled... |
| `C4_clean_half_open_date_range` | CLEAN | CLEAN | TN | - | - | The query correctly counts the number of orders placed in January 2026... |

```json
{
  "system": "recount",
  "n_cases": 12,
  "n_bug": 8,
  "n_clean": 4,
  "confusion": {
    "tp": 7,
    "fp": 0,
    "fn": 1,
    "tn": 4
  },
  "precision": 1.0,
  "recall": 0.875,
  "f1": 0.9333,
  "false_alarm_rate": 0.0,
  "repair_accuracy": 0.875,
  "repairs_correct": 7,
  "repairs_attempted": 7,
  "bug_type_accuracy": 0.2857,
  "escalations_on_bug": 0,
  "escalations_on_clean": 0,
  "errors": 0,
  "net_analyst_minutes_modelled": 84.0,
  "time_model": "confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)",
  "total_cost_usd": 0.00443,
  "cost_per_case_usd": 0.000369,
  "cost_known": true,
  "total_latency_s": 0.04,
  "latency_per_case_s": 0.0,
  "llm_calls": 24,
  "tool_calls": 36
}
```
