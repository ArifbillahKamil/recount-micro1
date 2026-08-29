# Evaluation — ablation-no-recompute-gpt-4o-mini

Model `gpt-4o-mini` · mode `auto` · profile on · probes on · gate on

Analyst-minute model: confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)

## recount — per case

| case | truth | verdict | class | bug type | repair | note |
|---|---|---|---|---|---|---|
| `B1_fanout_payments_via_line_items` | BUG | BUG | TP | fanout_join | correct | The query joins payments and orders, but there are 327 payments associ... |
| `B2_fanout_units_via_payments` | BUG | BUG | TP | mixed_unit_aggregation | correct | The query aggregates quantities from order_items while filtering on co... |
| `B3_null_swallowing_status_filter` | BUG | BUG | TP | null_swallowing_predicate | correct | The query does not account for orders with a NULL status, which should... |
| `B4_left_join_degraded_to_inner` | BUG | CLEAN | FN | - | - | The query correctly counts all orders and sums the refunded amounts, i... |
| `B5_between_loses_last_day` | BUG | BUG | TP | timezone_day_boundary | correct | The query does not correctly account for orders placed on January 31, ... |
| `B6_timezone_day_misattribution` | BUG | CLEAN | FN | - | - | Checked and no discrepancy found: a rewritten version of this query re... |
| `B7_mixed_currency_unit_error` | BUG | BUG | TP | mixed_unit_aggregation | correct | The query aggregates payments from the payments table without filterin... |
| `B8_missing_status_filter` | BUG | BUG | TP | missing_filter | correct | The query does not filter for completed orders, which is necessary to ... |
| `C1_clean_distinct_order_count_with_payments` | CLEAN | BUG | FP | fanout_join | wrong | The query counts distinct orders but aggregates payments, which can le... |
| `C2_clean_units_sold_at_line_grain` | CLEAN | CLEAN | TN | - | - | The query correctly aggregates the total quantity of units sold from t... |
| `C3_clean_null_safe_active_orders` | CLEAN | CLEAN | TN | - | - | Checked and no discrepancy found: a rewritten version of this query re... |
| `C4_clean_half_open_date_range` | CLEAN | BUG | FP | missing_filter | wrong | The query counts all orders regardless of their status, but 482 orders... |

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
  "repair_accuracy": 0.75,
  "repairs_correct": 6,
  "repairs_attempted": 6,
  "bug_type_accuracy": 0.6667,
  "escalations_on_bug": 0,
  "escalations_on_clean": 0,
  "errors": 0,
  "net_analyst_minutes_modelled": 56.0,
  "time_model": "confirmed bug +12 min, false alarm -8 min, escalation -4 min, missed bug 0 min (counted as recall, not time)",
  "total_cost_usd": 0.007527,
  "cost_per_case_usd": 0.000627,
  "cost_known": true,
  "total_latency_s": 22.97,
  "latency_per_case_s": 1.91,
  "llm_calls": 24,
  "tool_calls": 82
}
```
