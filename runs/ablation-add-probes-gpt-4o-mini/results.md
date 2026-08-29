# Evaluation — ablation-add-probes-gpt-4o-mini

Model `gpt-4o-mini` · mode `auto` · profile OFF · formats on · probes on · gate on

Analyst-minute model: confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)

## recount — per case

| case | truth | verdict | class | bug type | repair | note |
|---|---|---|---|---|---|---|
| `B1_fanout_payments_via_line_items` | BUG | BUG | TP | wrong_aggregation_grain | correct | The query aggregates payments at the order item level, which can lead ... |
| `B2_fanout_units_via_payments` | BUG | BUG | TP | missing_filter | correct | The query under review includes orders that are not completed due to t... |
| `B3_null_swallowing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query under review does not account for orders with a NULL status,... |
| `B4_left_join_degraded_to_inner` | BUG | BUG | TP | left_join_degraded_to_inner | correct | The query under review counts only 103 orders, which is inconsistent w... |
| `B5_between_loses_last_day` | BUG | BUG | TP | date_range_truncation | correct | The query under review uses a date range that excludes the last day of... |
| `B6_timezone_day_misattribution` | BUG | CLEAN | FN | - | - | Checked and no discrepancy found. A query written independently from t... |
| `B7_mixed_currency_unit_error` | BUG | BUG | TP | missing_filter | correct | The query under review does not filter for orders in IDR currency, lea... |
| `B8_missing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query does not filter for completed orders, which is essential to ... |
| `C1_clean_distinct_order_count_with_payments` | CLEAN | CLEAN | TN | - | - | The query correctly counts distinct completed orders from the 'orders'... |
| `C2_clean_units_sold_at_line_grain` | CLEAN | CLEAN | TN | - | - | The query correctly sums the quantities of order items from completed ... |
| `C3_clean_null_safe_active_orders` | CLEAN | CLEAN | TN | - | - | The query correctly counts the number of active orders by including th... |
| `C4_clean_half_open_date_range` | CLEAN | CLEAN | TN | - | - | Checked and no discrepancy found. A query written independently from t... |

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
  "bug_type_accuracy": 0.4286,
  "escalations_on_bug": 0,
  "escalations_on_clean": 0,
  "errors": 0,
  "net_analyst_minutes_modelled": 84.0,
  "time_model": "confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)",
  "total_cost_usd": 0.009827,
  "cost_per_case_usd": 0.000819,
  "cost_known": true,
  "total_latency_s": 67.81,
  "latency_per_case_s": 5.65,
  "llm_calls": 37,
  "tool_calls": 85
}
```
