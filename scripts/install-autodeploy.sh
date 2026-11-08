#!/usr/bin/env bash
# =============================================================================
# 一键安装自动部署（在阿里云服务器上执行一次即可）
#
#   sudo ./scripts/install-autodeploy.sh              # 默认每 3 分钟检查一次
#   sudo ./scripts/install-autodeploy.sh --interval 5 # 改成每 5 分钟
#   sudo ./scripts/install-autodeploy.sh --uninstall  # 卸载
#
# 装完之后：我在仓库里 push，服务器最多 3 分钟自动拉取、构建、重启，
# 不需要你再登录阿里云做任何事。
# =============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
INTERVAL=3
ACTION="install"

while [ $# -gt 0 ]; do
  case "$1" in
    --interval) INTERVAL="${2:-3}"; shift 2 ;;
    --uninstall|--remove) ACTION="uninstall"; shift ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
done

UNIT_NAME="etf-autodeploy"

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "需要 root：sudo $0 $*"
[ -d "$APP_DIR/.git" ] || die "$APP_DIR 不是 git 仓库（可用 APP_DIR=/你的路径 指定）"
chmod +x "$APP_DIR/scripts/autodeploy.sh"

# ---------------------------------------------------------------- 卸载
if [ "$ACTION" = "uninstall" ]; then
  if command -v systemctl >/dev/null 2>&1; then
    systemctl disable --now "$UNIT_NAME.timer" 2>/dev/null || true
    rm -f "/etc/systemd/system/$UNIT_NAME.timer" "/etc/systemd/system/$UNIT_NAME.service"
    systemctl daemon-reload
  fi
  rm -f "/etc/cron.d/$UNIT_NAME"
  say "已卸载自动部署"
  exit 0
fi

# ------------------------------------------------------- 前置检查（不阻断）
command -v git >/dev/null 2>&1 || die "没装 git"
if docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1; then
  say "检测到 Docker"
else
  warn "没检测到 Docker：将以裸机模式运行，需要你自己提供 scripts/deploy-hook.sh"
fi
if ! command -v curl >/dev/null 2>&1; then
  die "没装 curl（健康检查要用）"
fi

# 先跑一次，把问题暴露在安装阶段
say "先手动跑一次，确认能正常部署"
if "$APP_DIR/scripts/autodeploy.sh" --check; then
  say "自检通过"
else
  warn "自检没通过（可能只是暂时拉不到远端），不影响安装，后面看日志"
fi

# ------------------------------------------------------------ systemd 优先
if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  say "安装 systemd timer（每 ${INTERVAL} 分钟）"

  cat > "/etc/systemd/system/$UNIT_NAME.service" <<EOF
[Unit]
Description=ETF strategy auto deploy (git pull + docker compose build)
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
Environment=APP_DIR=$APP_DIR
ExecStart=$APP_DIR/scripts/autodeploy.sh
TimeoutStartSec=1800
Nice=10
EOF

  cat > "/etc/systemd/system/$UNIT_NAME.timer" <<EOF
[Unit]
Description=Check ETF strategy repo every ${INTERVAL} minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=${INTERVAL}min
AccuracySec=30s
Persistent=true

[Install]
WantedBy=timers.target
EOF

  systemctl daemon-reload
  systemctl enable --now "$UNIT_NAME.timer" >/dev/null
  say "已启用：systemctl list-timers $UNIT_NAME.timer"
  say "下次触发：$(systemctl show "$UNIT_NAME.timer" -p NextElapseUSecRealtime --value 2>/dev/null || echo '见 list-timers')"

# --------------------------------------------------------------- cron 兜底
elif command -v crontab >/dev/null 2>&1 || [ -d /etc/cron.d ]; then
  warn "系统没有 systemd，改用 cron"
  cat > "/etc/cron.d/$UNIT_NAME" <<EOF
# ETF 策略站自动部署（由 install-autodeploy.sh 生成）
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
*/${INTERVAL} * * * * root APP_DIR=$APP_DIR $APP_DIR/scripts/autodeploy.sh >/dev/null 2>&1
EOF
  chmod 644 "/etc/cron.d/$UNIT_NAME"
  say "已写入 /etc/cron.d/$UNIT_NAME"
else
  die "既没有 systemd 也没有 cron，无法定时执行"
fi

cat <<EOF

────────────────────────────────────────────────────────────
装好了。之后我 push 代码，服务器最多 ${INTERVAL} 分钟自动上线。

查看是否生效：
  tail -f $APP_DIR/logs/deploy.log
  curl -s http://127.0.0.1/api/health     # 会带上线上 commit

手动触发一次（不用等）：
  sudo systemctl start $UNIT_NAME.service

暂停自动部署：
  sudo systemctl stop $UNIT_NAME.timer

彻底卸载：
  sudo $0 --uninstall
────────────────────────────────────────────────────────────
EOF
