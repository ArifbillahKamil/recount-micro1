# Evaluation — ablation-no-profile-gpt-4o-mini

Model `gpt-4o-mini` · mode `auto` · profile OFF · probes on · gate on

Analyst-minute model: confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)

## recount — per case

| case | truth | verdict | class | bug type | repair | note |
|---|---|---|---|---|---|---|
| `B1_fanout_payments_via_line_items` | BUG | BUG | TP | wrong_aggregation_grain | wrong | The query under review aggregates payments from the payments table wit... |
| `B2_fanout_units_via_payments` | BUG | BUG | TP | mixed_unit_aggregation | correct | The query aggregates quantities from order_items, but the independent ... |
| `B3_null_swallowing_status_filter` | BUG | BUG | TP | null_swallowing_predicate | correct | The query under review does not account for orders with a NULL status,... |
| `B4_left_join_degraded_to_inner` | BUG | BUG | TP | left_join_degraded_to_inner | correct | The query under review counts only 103 orders, which is significantly ... |
| `B5_between_loses_last_day` | BUG | BUG | TP | date_range_truncation | wrong | The query under review counts orders placed in January 2026 but uses a... |
| `B6_timezone_day_misattribution` | BUG | BUG | TP | timezone_day_boundary | wrong | The query under review does not account for the timezone difference, l... |
| `B7_mixed_currency_unit_error` | BUG | BUG | TP | missing_filter | correct | The query includes payments from orders that are not in IDR currency, ... |
| `B8_missing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query does not filter out orders that are not completed, as eviden... |
| `C1_clean_distinct_order_count_with_payments` | CLEAN | CLEAN | TN | - | - | The query correctly counts distinct completed orders from the 'orders'... |
| `C2_clean_units_sold_at_line_grain` | CLEAN | CLEAN | TN | - | - | The query correctly sums the quantity of order items associated with c... |
| `C3_clean_null_safe_active_orders` | CLEAN | CLEAN | TN | - | - | The query correctly counts the number of active orders by including th... |
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
  "repair_accuracy": 0.625,
  "repairs_correct": 5,
  "repairs_attempted": 8,
  "bug_type_accuracy": 0.625,
  "escalations_on_bug": 0,
  "escalations_on_clean": 0,
  "errors": 0,
  "net_analyst_minutes_modelled": 88.0,
  "time_model": "confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)",
  "total_cost_usd": 0.009703,
  "cost_per_case_usd": 0.000809,
  "cost_known": true,
  "total_latency_s": 108.42,
  "latency_per_case_s": 9.04,
  "llm_calls": 36,
  "tool_calls": 72
}
```
