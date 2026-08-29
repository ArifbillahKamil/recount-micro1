# Evaluation — verify-offline-gpt-4o-mini

Model `gpt-4o-mini` · mode `replay` · profile OFF · formats on · probes OFF · gate on

Analyst-minute model: confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)

## Headline comparison

| metric | baseline | Recount | change |
|---|---|---|---|
| **F1 on bug detection** (primary) | 93% | 93% | +0 pt |
| Precision | 100% | 100% | +0 pt |
| Recall | 88% | 88% | +0 pt |
| **False alarms** on the 4 correct queries (lower is better) | 0/4 (0%) | 0/4 (0%) | +0 pt |
| **Repair accuracy** (correction returns the true number) | 7/8 (88%) | 7/8 (88%) | +0 pt |
| Bug type named correctly | 29% | 29% | +0 pt |
| Escalations (bug / clean) | 0 / 0 | 0 / 0 | - |
| Net analyst minutes (modelled) | +84 | +84 | +0 |
| Cost per case | $0.00019 | $0.00037 | - |
| Wall clock per case | 0.0s | 0.0s | - |
| Model calls / tool calls | 12 / 0 | 24 / 36 | - |

## baseline — per case

| case | truth | verdict | class | bug type | repair | note |
|---|---|---|---|---|---|---|
| `B1_fanout_payments_via_line_items` | BUG | BUG | TP | wrong_aggregation_grain | correct | The query sums the payment amounts for completed orders, but it also j... |
| `B2_fanout_units_via_payments` | BUG | CLEAN | FN | - | - | The query correctly sums the quantity of units sold from the order_ite... |
| `B3_null_swallowing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query counts all orders where the status is not 'cancelled', but i... |
| `B4_left_join_degraded_to_inner` | BUG | BUG | TP | wrong_aggregation_grain | correct | The query counts the total number of orders but incorrectly filters ou... |
| `B5_between_loses_last_day` | BUG | BUG | TP | timezone_day_boundary | correct | The query does not account for the full day of January 31, 2026, as it... |
| `B6_timezone_day_misattribution` | BUG | BUG | TP | timezone_day_boundary | correct | The query does not account for the timezone difference of UTC+7 for th... |
| `B7_mixed_currency_unit_error` | BUG | BUG | TP | missing_filter | correct | The query does not filter for Indonesian orders, as it lacks a conditi... |
| `B8_missing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query sums the payment amounts from the payments table, but it doe... |
| `C1_clean_distinct_order_count_with_payments` | CLEAN | CLEAN | TN | - | - | The query correctly counts the number of completed orders from the 'or... |
| `C2_clean_units_sold_at_line_grain` | CLEAN | CLEAN | TN | - | - | The query correctly sums the quantity of units sold from the order_ite... |
| `C3_clean_null_safe_active_orders` | CLEAN | CLEAN | TN | - | - | The query correctly counts the number of orders from the 'orders' tabl... |
| `C4_clean_half_open_date_range` | CLEAN | CLEAN | TN | - | - | The query correctly counts the number of orders placed in January 2026... |

```json
{
  "system": "baseline",
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
  "total_cost_usd": 0.002272,
  "cost_per_case_usd": 0.000189,
  "cost_known": true,
  "total_latency_s": 0.01,
  "latency_per_case_s": 0.0,
  "llm_calls": 12,
  "tool_calls": 0
}
```

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
  "total_latency_s": 0.05,
  "latency_per_case_s": 0.0,
  "llm_calls": 24,
  "tool_calls": 36
}
```
