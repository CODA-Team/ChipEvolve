#!/usr/bin/env bash
# Restart the EDA-AI sprint platform on one recorded version.
#
# Why this file exists (phase A):
#   * a hand restart raced with the previous group's shutdown and the gateway
#     died on "database is locked" (PRAGMA journal_mode = DELETE), which took
#     the whole group down through the launcher's EXIT trap;
#   * the shared /home xfs was sitting at 70-90% iowait from other users, so a
#     sqlite write made the data foundation hang in D state for minutes.
# So: stop, wait until the state root is released, start on an uncontended
# filesystem, then wait for real readiness instead of assuming it.
#
# The sprint state root defaults to /dev/shm (tmpfs, RAM-backed).  Everything
# in it is derivable: raw artifacts live in the execution foundation state root
# and snapshots can be re-imported, so losing it on reboot costs a re-run, not
# data.  Override with OPENROAD_PLATFORM_STATE_ROOT.
set -uo pipefail

platform_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
state_root="${OPENROAD_PLATFORM_STATE_ROOT:-/dev/shm/eda-ai-sprint}"
plugins_root="${OPENROAD_PLATFORM_PLUGINS_ROOT:-/home/wjyuan/toolkits}"
capacity_cores="${OPENROAD_PLATFORM_CAPACITY_CPU_CORES:-16}"
capacity_memory="${OPENROAD_PLATFORM_CAPACITY_MEMORY_BYTES:-34359738368}"
pattern="openroad-(platform-gateway|app-|platform-worker)"

count_matches() {
  pgrep -u "$(id -un)" -f "$pattern" 2>/dev/null | wc -l
}

echo "== stopping any previous group =="
pids="$(pgrep -u "$(id -un)" -f "$pattern" 2>/dev/null | tr '\n' ' ')"
if [[ -n "${pids// /}" ]]; then
  echo "   sending TERM to: $pids"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
fi
remaining=1
for _ in $(seq 1 45); do
  remaining="$(count_matches)"
  [[ "$remaining" -eq 0 ]] && break
  sleep 1
done
if [[ "$remaining" -ne 0 ]]; then
  echo "   still running after 45s, sending KILL: $(pgrep -u "$(id -un)" -f "$pattern" | tr '\n' ' ')"
  # shellcheck disable=SC2046
  kill -9 $(pgrep -u "$(id -un)" -f "$pattern") 2>/dev/null || true
  sleep 5
fi
echo "   state root released (remaining=$(count_matches))"

echo "== starting platform =="
mkdir -p "$state_root"
if [[ "$state_root" == /dev/shm/* ]]; then
  avail_kb=$(df -Pk /dev/shm | awk 'NR==2 {print $4}')
  echo "   tmpfs available: $((avail_kb / 1024 / 1024)) GiB"
fi
cd "$platform_root" || exit 1
setsid nohup env \
  OPENROAD_PLATFORM_STATE_ROOT="$state_root" \
  OPENROAD_PLATFORM_PLUGINS_ROOT="$plugins_root" \
  OPENROAD_PLATFORM_CAPACITY_CPU_CORES="$capacity_cores" \
  OPENROAD_PLATFORM_CAPACITY_MEMORY_BYTES="$capacity_memory" \
  bash tools/start-platform.sh > "$state_root/services.log" 2>&1 < /dev/null &

echo "== waiting for readiness =="
for i in $(seq 1 90); do
  sleep 2
  if curl -s --max-time 3 http://127.0.0.1:8700/health >/dev/null 2>&1 \
     && curl -s --max-time 3 http://127.0.0.1:8860/health >/dev/null 2>&1; then
    echo "   gateway + data foundation healthy after $((i * 2))s"
    echo "   state root: $state_root"
    echo "   plugins root: $plugins_root"
    exit 0
  fi
  # A request handler can log a broken-pipe traceback when this probe times
  # out, so liveness of the group - not any traceback - is the failure signal.
  if [[ "$i" -gt 3 && "$(count_matches)" -eq 0 ]]; then
    echo "   LAUNCH DIED, log follows:"
    sed -n '1,60p' "$state_root/services.log"
    exit 1
  fi
done
echo "   TIMED OUT waiting for readiness, log follows:"
sed -n '1,60p' "$state_root/services.log"
exit 1
