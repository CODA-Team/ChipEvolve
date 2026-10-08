#!/usr/bin/env bash
set -euo pipefail
platform_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
platform_venv="$platform_root/.venv"
state_root="${OPENROAD_PLATFORM_STATE_ROOT:-$platform_root/../var/execution-foundation}"
plugins_root="${OPENROAD_PLATFORM_PLUGINS_ROOT:-$platform_root/plugins}"
admissions_root="${OPENROAD_PLATFORM_ADMISSIONS_ROOT:-$platform_root/admissions}"
export PYTHONNOUSERSITE=1
unset PYTHONPATH PYTHONHOME
export NO_PROXY="127.0.0.1,localhost,::1"
export no_proxy="$NO_PROXY"
mkdir -p "$state_root"
pids=()
cleanup() {
  trap - EXIT INT TERM
  if ((${#pids[@]})); then
    kill "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM
"$platform_venv/bin/openroad-platform-worker" --state-root "$state_root" \
  --plugins-root "$plugins_root" --admissions-root "$admissions_root" &
pids+=("$!")
"$platform_venv/bin/openroad-app-plan_executor" --host 127.0.0.1 --port 18840 \
  --kernel-url http://127.0.0.1:18700 --db "$state_root/plan_executor.sqlite" &
pids+=("$!")
"$platform_venv/bin/openroad-platform-gateway" --host 127.0.0.1 --port 18700 --no-auth \
  --state-root "$state_root" --plugins-root "$plugins_root" \
  --admissions-root "$admissions_root" --config "$platform_root/examples/gateway-agent.json" &
pids+=("$!")
printf 'gateway: http://127.0.0.1:18700\nplan service: http://127.0.0.1:18840\n'
wait -n
