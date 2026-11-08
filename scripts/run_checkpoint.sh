#!/usr/bin/env bash
# Integration checkpoint runner (REQUIREMENTS.md I1 / I4 / I5a).
# Usage:
#   ./scripts/run_checkpoint.sh I1
#   NESSIE_LIVE_TEST=1 ./scripts/run_checkpoint.sh I4
#   RUN_LIVE_GROK=1 ./scripts/run_checkpoint.sh I5a
#
# On failure: reports likely module + error. Do not patch other owners' code here.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}:${ROOT}/brain${PYTHONPATH:+:$PYTHONPATH}"

CP="${1:-}"
if [[ "$CP" != "I1" && "$CP" != "I4" && "$CP" != "I5a" ]]; then
  echo "usage: $0 I1|I4|I5a" >&2
  exit 2
fi

PY="${ROOT}/.venv/bin/pytest"
PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" || ! -x "$PYTHON" ]]; then
  echo "CHECKPOINT ${CP}: FAIL"
  echo "module: unknown"
  echo "error: .venv missing; run: python3 -m venv .venv && .venv/bin/pip install -r brain/requirements.txt"
  echo "action: fix local setup; do not patch other owners' code"
  exit 1
fi

if [[ -f "$ROOT/.env" ]]; then
  # Like the brain's load_dotenv: .env never overrides variables already exported by the caller.
  _caller_env="$(export -p)"
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
  eval "$_caller_env"
fi

map_module() {
  local log="$1"
  if echo "$log" | grep -qE 'app\.db|SqliteStore|test_store'; then echo store
  elif echo "$log" | grep -qE 'app\.indicators|test_indicators'; then echo indicators
  elif echo "$log" | grep -qE 'app\.tools|test_tools|test_expected'; then echo tools
  elif echo "$log" | grep -qE 'app\.nessie|LiveNessie|test_nessie|NESSIE_'; then echo nessie
  elif echo "$log" | grep -qE 'app\.treasurer|test_treasurer'; then echo treasurer
  elif echo "$log" | grep -qE 'app\.agents\.llm|wellness\.llm|GrokLLM|llm_fallback|test_llm|XAI_|GROK_'; then echo llm
  elif echo "$log" | grep -qE 'app\.outbox|HttpOutbox|/send'; then echo outbox
  elif echo "$log" | grep -qE 'app\.agents\.auditor|auditor fallback'; then echo auditor
  else echo unknown
  fi
}

report() {
  local status="$1" module="$2" error="$3"
  echo
  echo "CHECKPOINT ${CP}: ${status}"
  echo "module: ${module}"
  echo "error: ${error}"
  if [[ "$status" == "FAIL" ]]; then
    echo "action: flip failing module back to stub on main; do not patch other owners' code"
  else
    echo "action: none"
  fi
}

LOG="$(mktemp)"
trap 'rm -f "$LOG"' EXIT

if ! "$PYTHON" -c "from app import registry; from contracts.models import Proposal" 2>>"$LOG"; then
  report FAIL unknown "brain imports failed; install brain/requirements.txt in .venv"
  cat "$LOG" >&2
  exit 1
fi

run_and_report() {
  set +e
  "$PY" "$@" -v --tb=short > >(tee "$LOG") 2>&1
  local rc=$?
  set -e
  if [[ $rc -ne 0 ]]; then
    local err
    err="$(grep -E '^(E |FAILED |ERROR )' "$LOG" | tail -n 8 | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g')"
    [[ -z "$err" ]] && err="pytest failed (see output above)"
    report FAIL "$(map_module "$(cat "$LOG")")" "$err"
    exit 1
  fi
  report PASS none none
  exit 0
}

case "$CP" in
  I1)
    echo "==> I1: DB=sqlite INDICATORS=real TOOLS=real (others stub)"
    run_and_report \
      brain/tests/test_checkpoints.py::test_I1_health_modes \
      brain/tests/test_checkpoints.py::test_I1_expected_numbers \
      brain/tests/test_checkpoints.py::test_I1_demo_reset_restores_clock \
      brain/tests/test_store_security.py \
      brain/tests/test_indicators_security.py \
      brain/tests/test_tools_security.py \
      brain/tests/test_expected.py
    ;;
  I4)
    if [[ "${NESSIE_LIVE_TEST:-}" != "1" ]]; then
      report FAIL nessie "NESSIE_LIVE_TEST=1 is required for I4"
      exit 1
    fi
    if [[ -z "${NESSIE_API_KEY:-}" ]]; then
      report FAIL nessie "NESSIE_API_KEY is required for I4"
      exit 1
    fi
    echo "==> I4: ALL_REAL + NESSIE_MODE=live (opt-in)"
    run_and_report \
      brain/tests/test_checkpoints.py::test_I4_live_nessie_rent_fronting \
      "brain/tests/contracts/test_nessie.py::test_nessie_contract[live]"
    ;;
  I5a)
    if [[ "${RUN_LIVE_GROK:-}" != "1" ]]; then
      report FAIL llm "RUN_LIVE_GROK=1 is required for I5a"
      exit 1
    fi
    if [[ -z "${XAI_API_KEY:-}" ]]; then
      report FAIL llm "XAI_API_KEY is required for I5a"
      exit 1
    fi
    if [[ -z "${NESSIE_API_KEY:-}" ]]; then
      report FAIL nessie "NESSIE_API_KEY is required for I5a"
      exit 1
    fi
    echo "==> I5a: I4 + LLM_MODE=grok + OUTBOX_MODE=http (GROK_MODEL=${GROK_MODEL:-unset}, opt-in)"
    run_and_report -s \
      brain/tests/contracts/test_llm.py::test_live_grok_returns_tool_call \
      "brain/tests/contracts/test_llm.py::test_llm_contract[grok]" \
      brain/tests/test_checkpoint_i5a.py::test_I5a_live_grok_full_flow
    ;;
esac
