# Evaluation — ablation-add-profile-gpt-4o-mini

Model `gpt-4o-mini` · mode `auto` · profile on · formats OFF · probes OFF · gate on

Analyst-minute model: confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)

## recount — per case

| case | truth | verdict | class | bug type | repair | note |
|---|---|---|---|---|---|---|
| `B1_fanout_payments_via_line_items` | BUG | BUG | TP | wrong_aggregation_grain | correct | The query under review aggregates payments based on completed orders b... |
| `B2_fanout_units_via_payments` | BUG | BUG | TP | mixed_unit_aggregation | correct | The query under review aggregates units sold from the order_items tabl... |
| `B3_null_swallowing_status_filter` | BUG | BUG | TP | null_swallowing_predicate | correct | The query under review counts orders with a status that is not 'cancel... |
| `B4_left_join_degraded_to_inner` | BUG | BUG | TP | wrong_aggregation_grain | wrong | The query under review counts the number of refunds (103) instead of t... |
| `B5_between_loses_last_day` | BUG | BUG | TP | date_range_truncation | wrong | The query under review counts orders placed between '2026-01-01' and '... |
| `B6_timezone_day_misattribution` | BUG | BUG | TP | date_range_truncation | wrong | The query under review counts orders based on the date of the timestam... |
| `B7_mixed_currency_unit_error` | BUG | BUG | TP | missing_filter | correct | The query under review does not filter for the currency 'IDR', which i... |
| `B8_missing_status_filter` | BUG | BUG | TP | missing_filter | wrong | The query under review does not filter out orders with a NULL status o... |
| `C1_clean_distinct_order_count_with_payments` | CLEAN | BUG | FP | wrong_aggregation_grain | wrong | The query under review counts distinct orders from the 'orders' table ... |
| `C2_clean_units_sold_at_line_grain` | CLEAN | BUG | FP | missing_filter | wrong | The query under review only counts units from completed orders, while ... |
| `C3_clean_null_safe_active_orders` | CLEAN | CLEAN | TN | - | - | The query correctly counts the number of active orders by including th... |
| `C4_clean_half_open_date_range` | CLEAN | BUG | FP | missing_filter | wrong | The query under review counts all orders regardless of their status, w... |

```json
{
  "system": "recount",
  "n_cases": 12,
  "n_bug": 8,
  "n_clean": 4,
  "confusion": {
    "tp": 8,
    "fp": 3,
    "fn": 0,
    "tn": 1
  },
  "precision": 0.7273,
  "recall": 1.0,
  "f1": 0.8421,
  "false_alarm_rate": 0.75,
  "repair_accuracy": 0.5,
  "repairs_correct": 4,
  "repairs_attempted": 8,
  "bug_type_accuracy": 0.375,
  "escalations_on_bug": 0,
  "escalations_on_clean": 0,
  "errors": 0,
  "net_analyst_minutes_modelled": 72.0,
  "time_model": "confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)",
  "total_cost_usd": 0.004008,
  "cost_per_case_usd": 0.000334,
  "cost_known": true,
  "total_latency_s": 22.45,
  "latency_per_case_s": 1.87,
  "llm_calls": 24,
  "tool_calls": 36
}
```
