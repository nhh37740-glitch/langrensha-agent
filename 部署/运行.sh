#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_root"
config_file="$project_root/.env"
local_flags=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      [[ $# -ge 2 ]] || { echo '缺少配置文件路径。' >&2; exit 2; }
      config_file="$2"; shift 2 ;;
    --local)
      local_flags=(--local)
      export MIST_BIND_ADDRESS=127.0.0.1
      shift ;;
    *) break ;;
  esac
done
[[ -f "$config_file" ]] || { echo '私密配置文件不存在。' >&2; exit 2; }
config_file="$(cd -- "$(dirname -- "$config_file")" && pwd)/$(basename -- "$config_file")"
export MIST_ENV_FILE="$config_file"
compose=(docker compose --project-name "${MIST_PROJECT:-mist-town}" --env-file "$config_file" -f "$project_root/部署/compose.yaml")
operation="${1:-status}"
[[ $# -eq 0 ]] || shift
case "$operation" in
  build) "${compose[@]}" build ;;
  check) "${compose[@]}" run --rm --no-deps town langrensha-ops check-config "${local_flags[@]}" ;;
  start)
    "${compose[@]}" run --rm --no-deps town langrensha-ops check-config "${local_flags[@]}"
    "${compose[@]}" up -d --no-build --wait ;;
  stop) "${compose[@]}" stop ;;
  status) "${compose[@]}" ps ;;
  logs) "${compose[@]}" logs --tail=100 ;;
  backup|restore|verify)
    name="${1:-$(date -u +%Y%m%dT%H%M%SZ).sqlite3}"
    [[ "$name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*\.sqlite3$ ]] || { echo '只接受不含路径的 .sqlite3 备份名。' >&2; exit 2; }
    if [[ "$operation" == backup ]]; then
      "${compose[@]}" exec -T town sh -c 'exec langrensha-ops backup --database "$LANGRENSHA_DATABASE" --output "$1"' -- "/data/backups/$name"
    elif [[ "$operation" == verify ]]; then
      "${compose[@]}" run --rm --no-deps town langrensha-ops verify --database "/data/backups/$name"
    else
      "${compose[@]}" run --rm --no-deps town langrensha-ops restore --backup "/data/backups/$name" --database "/data/restored/$name"
      echo "已生成全新恢复库。原库保持原样；激活命令：MIST_DATABASE='/data/restored/$name' 部署/运行.sh start"
      echo '确认后将 MIST_DATABASE 写入原私密配置以保持下次启动一致。'
    fi ;;
  *) echo '用法：部署/运行.sh [--env-file 路径] [--local] build|check|start|stop|status|logs|backup|verify|restore [备份名.sqlite3]' >&2; exit 2 ;;
esac
