#!/usr/bin/env bash
#
# One command to produce every number the submission reports.
#
#   export OPENAI_API_KEY=sk-...
#   ./run_all.sh                      # default model
#   ./run_all.sh gpt-5.4-mini 0.75 4.50   # model, $/1M input, $/1M output
#
# Passing the two prices pins the rate you were actually billed. Without them
# the built-in table is used, and a model missing from it reports cost as
# "unpriced" rather than guessing.
#
# Total cost is roughly 4x one full run: about $0.05 on gpt-4o-mini, about
# $1.10 on gpt-5.4. Runtime is dominated by API latency, roughly 10-20 minutes.

set -euo pipefail

MODEL="${1:-gpt-4o-mini}"
PRICE_IN="${2:-}"
PRICE_OUT="${3:-}"

PRICE_ARGS=()
if [[ -n "$PRICE_IN" && -n "$PRICE_OUT" ]]; then
  PRICE_ARGS=(--price-in "$PRICE_IN" --price-out "$PRICE_OUT")
fi

cd "$(dirname "$0")"

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is not set." >&2
  echo "To reproduce from committed cassettes instead, run:" >&2
  echo "  python3 -m recount.evaluate --system both --offline" >&2
  exit 2
fi

step "1/7  Build the warehouse (deterministic, seeded)"
python3 -m recount.warehouse --db data/warehouse.db
python3 - <<'PY'
from recount import warehouse
digest = warehouse.content_digest("data/warehouse.db")
print(f"  content digest = {digest}")
if digest != warehouse.CONTENT_DIGEST:
    raise SystemExit(
        f"  MISMATCH: expected {warehouse.CONTENT_DIGEST}. "
        "Stop; results would not be comparable."
    )
print("  matches the published digest")
PY

step "2/7  Validate the eval set against the data"
python3 -m recount.cases --db data/warehouse.db | tail -4

step "3/7  Test suites (scripted model, no API calls)"
python3 -m tests.test_pipeline | tail -2
python3 -m tests.test_harness  | tail -2

step "4/7  Headline run: baseline vs Recount"
python3 -m recount.evaluate \
  --system both --model "$MODEL" --record \
  --label "main-${MODEL}" "${PRICE_ARGS[@]}"

step "5/7  Ablation: no verification gate (replays the main run's cassettes)"
python3 -m recount.evaluate \
  --system recount --model "$MODEL" --no-gate \
  --label "ablation-no-gate-${MODEL}" "${PRICE_ARGS[@]}"

step "6/7  Ablation: no probes  /  no profiling (these need fresh calls)"
python3 -m recount.evaluate \
  --system recount --model "$MODEL" --no-probes \
  --label "ablation-no-probes-${MODEL}" "${PRICE_ARGS[@]}"
python3 -m recount.evaluate \
  --system recount --model "$MODEL" --no-profile \
  --label "ablation-no-profile-${MODEL}" "${PRICE_ARGS[@]}"

step "7/7  Confirm a reviewer with no API key gets the same numbers"
python3 -m recount.evaluate \
  --system both --model "$MODEL" --offline \
  --label "verify-offline-${MODEL}" "${PRICE_ARGS[@]}"

step "Changelog table"
python3 -m recount.evaluate --compare \
  "runs/main-${MODEL}/results.json" \
  "runs/ablation-no-profile-${MODEL}/results.json" \
  "runs/ablation-no-probes-${MODEL}/results.json" \
  "runs/ablation-no-gate-${MODEL}/results.json" \
  | tee runs/changelog-table.md

cat <<EOF

$(printf '=%.0s' {1..66})
Done. Send these back so the changelog can be written from real numbers:

  runs/main-${MODEL}/results.json
  runs/ablation-no-profile-${MODEL}/results.json
  runs/ablation-no-probes-${MODEL}/results.json
  runs/ablation-no-gate-${MODEL}/results.json
  runs/changelog-table.md

Commit cassettes/ as well -- that is what lets judges reproduce for free,
and it doubles as the agent trajectory evidence.

Quick look at the headline:
  cat runs/main-${MODEL}/results.md
EOF
