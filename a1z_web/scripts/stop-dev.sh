#!/usr/bin/env -S -u LD_LIBRARY_PATH bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_PORT="${A1Z_WEB_PORT:-8000}"
FRONTEND_PORT="${A1Z_WEB_FRONTEND_PORT:-5173}"
PYTHON="${WEB_ROOT}/backend/.venv/bin/python"

listener_pids() {
  local port="$1"
  ss -H -ltnp "sport = :${port}" 2>/dev/null \
    | grep -oE 'pid=[0-9]+' \
    | cut -d= -f2 \
    | sort -u || true
}

find_project_dev_root() {
  local process_id="$1"
  local process_cwd command_line parent_id

  while [[ "${process_id}" =~ ^[0-9]+$ ]] && (( process_id > 1 )); do
    [[ -r "/proc/${process_id}/cmdline" ]] || return 1
    process_cwd="$(readlink -f "/proc/${process_id}/cwd" 2>/dev/null || true)"
    command_line="$(tr '\0' ' ' < "/proc/${process_id}/cmdline" 2>/dev/null || true)"
    if [[ "${process_cwd}" == "${WEB_ROOT}" && "${command_line}" == *"scripts/dev.sh"* ]]; then
      printf '%s\n' "${process_id}"
      return 0
    fi
    parent_id="$(awk '/^PPid:/{print $2}' "/proc/${process_id}/status" 2>/dev/null || true)"
    [[ -n "${parent_id}" ]] || return 1
    process_id="${parent_id}"
  done
  return 1
}

check_active_robot_tasks() {
  local tasks_json active_tasks

  tasks_json="$(env -u LD_LIBRARY_PATH /usr/bin/curl --silent --show-error --fail \
    --max-time 2 "http://127.0.0.1:${BACKEND_PORT}/api/tasks" 2>/dev/null || true)"
  [[ -n "${tasks_json}" ]] || return 0
  [[ -x "${PYTHON}" ]] || {
    echo "无法检查活动任务：${PYTHON} 不可用。为保护机械臂，拒绝停止后端。" >&2
    return 2
  }

  if ! active_tasks="$(printf '%s' "${tasks_json}" | "${PYTHON}" -c '
import json
import sys

active = {"created", "starting", "ready", "running", "stopping"}
tasks = json.load(sys.stdin)
for task in tasks:
    if task.get("status") in active:
        print(f"{task.get('task_id', 'unknown')} ({task.get('task_type', 'unknown')}: {task.get('status')})")
')"; then
    echo "后端正在响应，但活动任务状态无法解析。为保护机械臂，拒绝停止后端。" >&2
    return 2
  fi

  if [[ -n "${active_tasks}" ]]; then
    echo "检测到仍在运行的 A1Z 任务，未停止开发服务器：" >&2
    printf '%s\n' "${active_tasks}" >&2
    echo "请先在 Web 顶部点击“软件停止”，等待任务结束后再运行本脚本。" >&2
    return 2
  fi
}

check_active_robot_tasks

declare -A dev_roots=()
foreign_listener=0
for port in "${BACKEND_PORT}" "${FRONTEND_PORT}"; do
  while IFS= read -r listener_pid; do
    [[ -n "${listener_pid}" ]] || continue
    if root_pid="$(find_project_dev_root "${listener_pid}")"; then
      dev_roots["${root_pid}"]=1
    else
      echo "端口 ${port} 被非当前 A1Z Web 开发进程 PID ${listener_pid} 占用，未自动停止。" >&2
      foreign_listener=1
    fi
  done < <(listener_pids "${port}")
done

if (( foreign_listener )); then
  echo "请运行 ss -ltnp | grep -E ':(${BACKEND_PORT}|${FRONTEND_PORT})\\b' 确认占用者。" >&2
  exit 2
fi

if (( ${#dev_roots[@]} == 0 )); then
  echo "A1Z Web 开发服务器未运行；端口 ${BACKEND_PORT}/${FRONTEND_PORT} 均可用。"
  exit 0
fi

for root_pid in "${!dev_roots[@]}"; do
  process_group="$(ps -o pgid= -p "${root_pid}" | tr -d ' ' || true)"
  echo "正在安全停止 A1Z Web 开发服务器（PID ${root_pid}）..."
  if [[ "${process_group}" == "${root_pid}" ]]; then
    kill -TERM -- "-${process_group}" 2>/dev/null || true
  else
    kill -TERM "${root_pid}" 2>/dev/null || true
  fi
done

for _ in $(seq 1 40); do
  if [[ -z "$(listener_pids "${BACKEND_PORT}")" && -z "$(listener_pids "${FRONTEND_PORT}")" ]]; then
    echo "A1Z Web 已停止，端口 ${BACKEND_PORT}/${FRONTEND_PORT} 已释放。"
    exit 0
  fi
  sleep 0.25
done

echo "开发服务器未能在 10 秒内完全退出，未执行模糊进程清理。" >&2
echo "请运行 ss -ltnp | grep -E ':(${BACKEND_PORT}|${FRONTEND_PORT})\\b' 查看剩余进程。" >&2
exit 1
