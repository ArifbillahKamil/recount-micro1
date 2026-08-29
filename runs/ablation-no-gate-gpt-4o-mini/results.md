# Evaluation — ablation-no-gate-gpt-4o-mini

Model `gpt-4o-mini` · mode `auto` · profile on · probes on · gate OFF

Analyst-minute model: confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)

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
| `C2_clean_units_sold_at_line_grain` | CLEAN | BUG | FP | wrong_aggregation_grain | correct | The query under review aggregates units sold from the order_items tabl... |
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
  "total_latency_s": 0.16,
  "latency_per_case_s": 0.01,
  "llm_calls": 36,
  "tool_calls": 84
}
```
