#!/bin/sh
# 容器启动前把「初始数据」灌进持久卷。
# 持久卷首次挂载时是空的，直接起服务会被当成「全新安装」——
# 自选 ETF 会退回代码里的默认 9 只，用户改过的列表就没了。
set -e

DATA_DIR="${ETF_DATA_DIR:-/app/data}"
IMAGE_ROOT="${IMAGE_ROOT:-/app}"
mkdir -p "$DATA_DIR"

seed() {
    name="$1"
    if [ -f "$IMAGE_ROOT/$name" ] && [ ! -f "$DATA_DIR/$name" ]; then
        cp "$IMAGE_ROOT/$name" "$DATA_DIR/$name"
        echo "[entrypoint] 初始化 $DATA_DIR/$name（来自镜像内置版本）"
    fi
}

seed etf_config.json

exec "$@"
