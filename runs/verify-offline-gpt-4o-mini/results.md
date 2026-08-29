# Evaluation — verify-offline-gpt-4o-mini

Model `gpt-4o-mini` · mode `replay` · profile on · probes on · gate on

Analyst-minute model: confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)

## Headline comparison

| metric | baseline | Recount | change |
|---|---|---|---|
| **F1 on bug detection** (primary) | 93% | 84% | -9 pt |
| Precision | 100% | 73% | -27 pt |
| Recall | 88% | 100% | +12 pt |
| **False alarms** on the 4 correct queries (lower is better) | 0/4 (0%) | 3/4 (75%) | +75 pt |
| **Repair accuracy** (correction returns the true number) | 7/8 (88%) | 5/8 (62%) | -25 pt |
| Bug type named correctly | 43% | 50% | +7 pt |
| Escalations (bug / clean) | 0 / 0 | 0 / 0 | - |
| Net analyst minutes (modelled) | +84 | +72 | -12 |
| Cost per case | $0.00019 | $0.00077 | - |
| Wall clock per case | 0.0s | 0.0s | - |
| Model calls / tool calls | 12 / 0 | 36 / 84 | - |

## baseline — per case

| case | truth | verdict | class | bug type | repair | note |
|---|---|---|---|---|---|---|
| `B1_fanout_payments_via_line_items` | BUG | BUG | TP | wrong_aggregation_grain | correct | The query sums the payment amounts for completed orders, but it also j... |
| `B2_fanout_units_via_payments` | BUG | CLEAN | FN | - | - | The query correctly sums the quantity of units sold from the order_ite... |
| `B3_null_swallowing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query counts all orders where the status is not 'cancelled', but i... |
| `B4_left_join_degraded_to_inner` | BUG | BUG | TP | left_join_degraded_to_inner | correct | The query uses a LEFT JOIN between orders and refunds, but the WHERE c... |
| `B5_between_loses_last_day` | BUG | BUG | TP | timezone_day_boundary | correct | The query does not account for the full day of January 31, 2026, as it... |
| `B6_timezone_day_misattribution` | BUG | BUG | TP | timezone_day_boundary | correct | The query does not account for the timezone difference of UTC+7 for th... |
| `B7_mixed_currency_unit_error` | BUG | BUG | TP | missing_filter | correct | The query does not filter for Indonesian orders, as it lacks a conditi... |
| `B8_missing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query sums the payment amounts from the payments table but does no... |
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
  "bug_type_accuracy": 0.4286,
  "escalations_on_bug": 0,
  "escalations_on_clean": 0,
  "errors": 0,
  "net_analyst_minutes_modelled": 84.0,
  "time_model": "confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)",
  "total_cost_usd": 0.00227,
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
| `B1_fanout_payments_via_line_items` | BUG | BUG | TP | missing_filter | correct | The query includes payments for orders that are not completed, as evid... |
| `B2_fanout_units_via_payments` | BUG | BUG | TP | mixed_unit_aggregation | wrong | The query aggregates units sold from order_items while filtering on co... |
| `B3_null_swallowing_status_filter` | BUG | BUG | TP | null_swallowing_predicate | correct | The query under review does not account for orders with a NULL status,... |
| `B4_left_join_degraded_to_inner` | BUG | BUG | TP | wrong_aggregation_grain | wrong | The query under review counts orders based on the refunds table, which... |
| `B5_between_loses_last_day` | BUG | BUG | TP | timezone_day_boundary | correct | The query under review does not account for orders placed on the last ... |
| `B6_timezone_day_misattribution` | BUG | BUG | TP | timezone_day_boundary | wrong | The query under review counts orders based on UTC timestamps without a... |
| `B7_mixed_currency_unit_error` | BUG | BUG | TP | mixed_unit_aggregation | correct | The query aggregates payments without filtering for the IDR currency, ... |
| `B8_missing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query does not filter out orders that are not completed, as eviden... |
| `C1_clean_distinct_order_count_with_payments` | CLEAN | BUG | FP | fanout_join | wrong | The query under review counts distinct orders and sums payments, but t... |
| `C2_clean_units_sold_at_line_grain` | CLEAN | BUG | FP | wrong_aggregation_grain | wrong | The query under review aggregates units sold from the order_items tabl... |
| `C3_clean_null_safe_active_orders` | CLEAN | CLEAN | TN | - | - | The query correctly counts orders that are not cancelled, including th... |
| `C4_clean_half_open_date_range` | CLEAN | BUG | FP | missing_filter | wrong | The query under review does not filter out orders with a NULL status, ... |

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
  "repair_accuracy": 0.625,
  "repairs_correct": 5,
  "repairs_attempted": 8,
  "bug_type_accuracy": 0.5,
  "escalations_on_bug": 0,
  "escalations_on_clean": 0,
  "errors": 0,
  "net_analyst_minutes_modelled": 72.0,
  "time_model": "confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)",
  "total_cost_usd": 0.009209,
  "cost_per_case_usd": 0.000767,
  "cost_known": true,
  "total_latency_s": 0.14,
  "latency_per_case_s": 0.01,
  "llm_calls": 36,
  "tool_calls": 84
}
```
