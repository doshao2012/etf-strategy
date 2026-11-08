#!/usr/bin/env bash
# =============================================================================
# ETF 策略站 · 自动部署
#
# 由 systemd timer / cron 定时调用。做什么：
#   1. 拉远端 → 代码没变就只做健康检查，直接退出（幂等，跑一万次也没副作用）
#   2. 代码变了 → 构建镜像 → 换容器 → 健康检查
#   3. 构建失败 / 健康检查失败 → 自动回滚到上一个版本并把它重新跑起来
#
# 设计原则：**宁可部署不成功，也不能把线上搞挂**。
# 构建在旧容器还在跑的时候进行，构建失败只回滚代码，不停服务；
# 只有构建成功才 up -d；up 完不健康立刻回滚。
#
# 手动执行：  ./scripts/autodeploy.sh            # 正常部署
#             ./scripts/autodeploy.sh --check    # 只看有没有新版本，不动手
#             ./scripts/autodeploy.sh --force    # 无视 commit 是否相同，强制重建
# =============================================================================
set -uo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BRANCH="${BRANCH:-main}"
REMOTE="${REMOTE:-origin}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1/api/health}"
LOG_FILE="${LOG_FILE:-$APP_DIR/logs/deploy.log}"
LOCK_FILE="${LOCK_FILE:-/tmp/etf-autodeploy.lock}"
HEALTH_TRIES="${HEALTH_TRIES:-40}"     # 40 × 3s = 最多等 2 分钟
HEALTH_GAP="${HEALTH_GAP:-3}"
LOG_MAX_LINES=3000

MODE="deploy"
case "${1:-}" in
  --check) MODE="check" ;;
  --force) MODE="force" ;;
  "") ;;
  *) echo "用法: $0 [--check|--force]" >&2; exit 2 ;;
esac

mkdir -p "$(dirname "$LOG_FILE")"

log() {
  printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE" >&2
}

# 日志别无限长
if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE")" -gt "$LOG_MAX_LINES" ]; then
  tail -n "$((LOG_MAX_LINES / 2))" "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

# 单实例：上一轮还没跑完就不要叠加（大镜像构建可能超过定时周期）
exec 9>"$LOCK_FILE" || { echo "无法创建锁文件 $LOCK_FILE" >&2; exit 1; }
if ! flock -n 9; then
  log "上一轮部署仍在进行，本轮跳过"
  exit 0
fi

cd "$APP_DIR" || { log "进不去项目目录 $APP_DIR"; exit 1; }

# root 操作「属于其他用户」的仓库时，Git 2.35+ 会以 dubious ownership 直接拒绝，
# 这在「目录归 ubuntu、git pull 都要 sudo」的机器上必现，不显式放行整个脚本都跑不动。
git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true

if [ ! -d .git ]; then
  log "$APP_DIR 不是 git 仓库，无法自动部署"
  exit 1
fi

# 选择容器编排命令。
# 注意不能用 `docker compose version` 探测权限——那是纯客户端命令，不连 daemon，
# 普通用户跑它照样成功，真正 build 时才 permission denied（线上踩过）。
# 必须用 `docker info` 确认能连上 daemon，再决定要不要加 sudo。
compose_cmd=""
if docker compose version >/dev/null 2>&1; then
  compose_cmd="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  compose_cmd="docker-compose"
fi

if [ -n "$compose_cmd" ]; then
  if docker info >/dev/null 2>&1; then
    DC="$compose_cmd"
  elif sudo -n docker info >/dev/null 2>&1; then
    DC="sudo $compose_cmd"
  else
    DC=""
  fi
else
  DC=""
fi

if [ -z "$DC" ] && [ -n "$compose_cmd" ]; then
  log "检测到 docker 但无法连接 daemon（当前身份 $(id -un)），需要免密 sudo 或加入 docker 组"
fi

# 前端 80 是用户入口，后端 3000 才反映「代码是否真的活着」（它的 /api/health
# 会带上 commit）。后端端口可达时它的状态必须正常；端口根本不通（某些部署没
# 映射 3000）就跳过这一项，只认前端入口，避免误判成部署失败。
BACKEND_HEALTH_URL="${BACKEND_HEALTH_URL:-http://127.0.0.1:3000/api/health}"

healthy() {
  local code
  code=$(curl -s -m 6 -o /dev/null -w '%{http_code}' "$BACKEND_HEALTH_URL" 2>/dev/null || echo 000)
  if [ -z "$code" ]; then code=000; fi
  if [ "$code" != "000" ] && [ "$code" != "200" ]; then
    return 1
  fi
  code=$(curl -s -m 6 -o /dev/null -w '%{http_code}' "$HEALTH_URL" 2>/dev/null || echo 000)
  if [ -z "$code" ]; then code=000; fi
  [ "$code" = "200" ]
}

wait_healthy() {
  local i
  for i in $(seq 1 "$HEALTH_TRIES"); do
    if healthy; then
      return 0
    fi
    sleep "$HEALTH_GAP"
  done
  return 1
}

# ---------------------------------------------------------------- 1. 拉远端
fetched=0
for i in 1 2 3; do
  if git fetch --quiet "$REMOTE" "$BRANCH" 2>>"$LOG_FILE"; then
    fetched=1
    break
  fi
  log "git fetch 第 $i 次失败，$((i * 5))s 后重试"
  sleep $((i * 5))
done
if [ "$fetched" -ne 1 ]; then
  log "git fetch 连续失败（网络或凭证问题），本轮跳过，线上保持原样"
  exit 1
fi

LOCAL="$(git rev-parse HEAD)"
TARGET="$(git rev-parse "$REMOTE/$BRANCH" 2>/dev/null || echo '')"
if [ -z "$TARGET" ]; then
  log "找不到 $REMOTE/$BRANCH，检查分支名"
  exit 1
fi

# ------------------------------------------------- 2. 无变化：只做健康巡检
if [ "$LOCAL" = "$TARGET" ] && [ "$MODE" != "force" ]; then
  if [ -z "$DC" ]; then
    exit 0
  fi
  if healthy; then
    exit 0
  fi
  # 代码没变但服务不健康：可能容器挂了 / 宿主机重启过
  log "代码已是最新（${LOCAL:0:7}），但健康检查失败，尝试拉起容器"
  $DC up -d >>"$LOG_FILE" 2>&1
  if wait_healthy; then
    log "容器已恢复"
    exit 0
  fi
  log "拉起后仍不健康，需要人工介入（docker compose logs backend）"
  exit 1
fi

if [ "$MODE" = "check" ]; then
  log "有新版本：${LOCAL:0:7} → ${TARGET:0:7}（--check 模式，不执行）"
  git log --oneline "$LOCAL..$TARGET" | head -20 | tee -a "$LOG_FILE" >&2
  exit 0
fi

PREV="$(git rev-parse HEAD)"

# ---------------------------------------------------------------- 3. 更新代码
log "发现新版本 ${PREV:0:7} → ${TARGET:0:7}"

# 裸机上跑过 npm run build 的话，next-env.d.ts 会被 Next 自动改写，
# 每次 pull 都会因为这点无关痛痒的改动失败。只在这种情况下自动 checkout，
# 其他任何本地改动一律不动（那可能是人手工改的配置，覆盖了就是事故）。
clean_generated() {
  local dirty
  dirty="$(git status --porcelain --untracked-files=no | awk '{print $2}')"
  [ -z "$dirty" ] && return 1
  if echo "$dirty" | grep -qvE '^(frontend/next-env\.d\.ts|.*\.tsbuildinfo)$'; then
    return 1
  fi
  log "清理构建自动改写的文件：$(echo "$dirty" | tr '\n' ' ')"
  echo "$dirty" | xargs -r git checkout --
  return 0
}

if ! git pull --ff-only --quiet "$REMOTE" "$BRANCH" >>"$LOG_FILE" 2>&1; then
  if clean_generated && git pull --ff-only --quiet "$REMOTE" "$BRANCH" >>"$LOG_FILE" 2>&1; then
    :   # 清理后拉取成功，继续
  else
    log "git pull 失败（本地有未提交改动或非快进）——为免覆盖现场，跳过本次部署"
    log "如需强制对齐远端：cd $APP_DIR && git stash && git reset --hard $REMOTE/$BRANCH"
    exit 1
  fi
fi
NEW="$(git rev-parse --short HEAD)"
log "代码已更新到 $NEW"
git log --oneline -1 | tee -a "$LOG_FILE" >&2

# 以 root 跑时，git 新建的文件会归 root 所有——日积月累之后普通用户就再也
# pull 不动了（典型报错 "insufficient permission for adding an object"）。
# 所以每次更新完把属主还给原来的主人。
if [ "$(id -u)" -eq 0 ]; then
  owner="$(stat -c '%u:%g' "$APP_DIR" 2>/dev/null || echo '')"
  if [ -n "$owner" ] && [ "$owner" != "0:0" ]; then
    chown -R "$owner" "$APP_DIR" 2>/dev/null || true
  fi
fi

# 供 /api/health 显示线上跑的是哪个 commit
printf '%s\n' "$NEW" > "$APP_DIR/backend/DEPLOY_SHA"

# --------------------------------------------------- 4. 构建 + 切换（Docker）
if [ -n "$DC" ]; then
  log "开始构建镜像（前端 pnpm build 较慢，通常 1~5 分钟）"
  if ! $DC build >>"$LOG_FILE" 2>&1; then
    log "构建失败，回滚代码到 ${PREV:0:7}（旧容器仍在运行，线上未受影响）"
    git reset --hard --quiet "$PREV"
    printf '%s\n' "${PREV:0:7}" > "$APP_DIR/backend/DEPLOY_SHA"
    exit 1
  fi

  log "构建完成，切换容器"
  if ! $DC up -d >>"$LOG_FILE" 2>&1; then
    log "容器启动失败，回滚"
    git reset --hard --quiet "$PREV"
  elif wait_healthy; then
    log "部署成功：$NEW 已上线（健康检查通过）"
    printf '%s %s OK\n' "$(date '+%F %T')" "$NEW" > "$APP_DIR/logs/deploy.state"
    exit 0
  else
    log "新版本健康检查 ${HEALTH_TRIES} 次未通过，开始回滚到 ${PREV:0:7}"
  fi

  # ---------------------------------------------------------------- 5. 回滚
  git reset --hard --quiet "$PREV"
  printf '%s\n' "${PREV:0:7}" > "$APP_DIR/backend/DEPLOY_SHA"
  $DC build >>"$LOG_FILE" 2>&1 && $DC up -d >>"$LOG_FILE" 2>&1
  if wait_healthy; then
    log "已回滚到 ${PREV:0:7} 并恢复正常——新版本有 bug，请看上面构建/启动日志"
  else
    log "回滚后仍不健康，需人工介入：cd $APP_DIR && docker compose logs --tail 100 backend"
  fi
  printf '%s %s ROLLBACK\n' "$(date '+%F %T')" "$NEW" > "$APP_DIR/logs/deploy.state"
  exit 1
fi

# ----------------------------------------------------- 4'. 裸机：走自定义钩子
if [ -x "$APP_DIR/scripts/deploy-hook.sh" ]; then
  log "未检测到 Docker，执行 scripts/deploy-hook.sh"
  if "$APP_DIR/scripts/deploy-hook.sh" >>"$LOG_FILE" 2>&1 && wait_healthy; then
    log "部署成功：$NEW"
    exit 0
  fi
  log "钩子执行失败或健康检查未通过，回滚代码"
  git reset --hard --quiet "$PREV"
  "$APP_DIR/scripts/deploy-hook.sh" >>"$LOG_FILE" 2>&1
  exit 1
fi

log "未检测到 Docker，也没有 scripts/deploy-hook.sh —— 不知道该怎么重启服务，已回滚代码"
git reset --hard --quiet "$PREV"
exit 1
