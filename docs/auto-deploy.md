# 自动部署（改完代码不用再登阿里云）

## 它解决什么

以前每次改完，流程是：

```
我 push → 你去阿里云 → cd 项目 → git pull → docker compose up -d --build → 等几分钟
```

现在只需要**在服务器上执行一次安装命令**，之后：

```
我 push → 服务器 3 分钟内自动 pull + build + 重启 → 你刷新页面就是新版
```

不需要给我服务器密码，也不需要装任何 Agent。

## 安装（一次性，约 1 分钟）

在阿里云服务器上：

```bash
cd /你的项目目录            # 就是那个有 docker-compose.yml 的目录
git pull                    # 先拉到最新（含本次新增的脚本）
sudo ./scripts/install-autodeploy.sh
```

装完会打印下次触发时间。想立刻试一次：

```bash
sudo systemctl start etf-autodeploy.service
tail -f logs/deploy.log
```

> 如果你的 docker 命令平时要加 sudo（`sudo docker compose build`），**不用改任何东西**。
> 脚本会自动探测：root 环境下直接用 `docker`，普通用户环境下自动切成 `sudo docker`。
> 另外 `sudo git pull` 常见的 `dubious ownership` 报错也已处理（脚本会先把仓库加进
> `safe.directory`），否则 root 操作归属普通用户的仓库时 git 会直接拒绝。

自定义检查间隔（默认 3 分钟）：

```bash
sudo ./scripts/install-autodeploy.sh --interval 5
```

不想用了：

```bash
sudo ./scripts/install-autodeploy.sh --uninstall
```

## 它到底做了什么

每 3 分钟执行一次 `scripts/autodeploy.sh`：

| 情况 | 行为 |
|---|---|
| 远端没有新提交 | 只做一次健康检查，然后退出（幂等，跑一万次也没副作用） |
| 有新提交 | `git pull --ff-only` → `docker compose build` → `up -d` → 健康检查 |
| 构建失败 | **回滚代码**，旧容器继续跑，线上不受影响 |
| 起来但不健康 | **自动回滚到上一个 commit 并重建**，恢复旧版本 |
| 代码没变但服务挂了 | 自动 `docker compose up -d` 拉起来 |
| 本地有手工改动 | 拒绝部署并写日志（绝不覆盖现场），只放过 `next-env.d.ts` 这类构建产物 |

几个刻意的设计：

- **构建在旧容器还在服务时进行**，构建失败不停服务，所以"部署失败"≠"网站挂了"。
- **单实例锁**：上一轮还没跑完（大镜像构建可能超过 3 分钟），这一轮直接跳过，不会叠着跑。
- **只认 fast-forward**：服务器上有未提交改动就停手，避免把你在服务器上手改的配置冲掉。

## 怎么确认线上是哪一版

`/api/health` 现在会带上 commit：

```bash
curl -s http://127.0.0.1/api/health
# {"status":"ok","commit":"1b86071","timestamp":"..."}
```

页面对应的就是我最后推的那个 commit。以后"改了没生效"这种事，一句 curl 就能定位。

## 顺带修掉的一个坑：数据每次重建都清零

原来 `docker-compose.yml` 没有挂卷，`docker compose up -d --build` 会重建容器，
容器里的 `share_history.json`（份额历史）、`history_cache.json`（K 线缓存）、
`etf_config.json`（你自选的那 18 只 ETF）**全部回到初始状态**。

这就是为什么份额分位老是"需 20 天，当前 7 天"——不是补不上，是每次部署都被清零了。

本次给 backend 挂了命名卷 `etf-data:/app/data`，运行时数据落到卷里，重建镜像不再丢。
首次启动会把镜像内置的 `etf_config.json` 播种进去（`backend/docker-entrypoint.sh`），
之后你在界面上改的 ETF 列表会一直保留。

> 升级提示：第一次用新 compose 启动时，旧容器里的历史数据不会自动迁移过来
> （那部分数据在旧容器里，随容器删除就没了）。所以第一次启动后份额历史是空的，
> 后台会自动回补到 60 天，等十几秒刷新即可；ETF 自选列表如果和默认的不同，
> 需要在界面上重新加一次。

## 如果你不是 Docker 部署

`autodeploy.sh` 检测不到 Docker 时会调用 `scripts/deploy-hook.sh`（自己写，需可执行），
在里面放你的重启命令，例如：

```bash
#!/usr/bin/env bash
# 裸机部署示例：重装依赖 + 重启 systemd 服务
set -e
cd "$(dirname "$0")/.."
cd backend && pip3 install -q -r requirements.txt && cd ..
cd frontend && pnpm install --frozen-lockfile && pnpm build && cd ..
systemctl restart etf-backend etf-frontend
```

健康检查仍然生效：钩子跑完如果 `/api/health` 不通，会自动回滚代码并再跑一次钩子。

## 排查

```bash
tail -50 logs/deploy.log                    # 部署日志（含 git / build 全部输出）
systemctl list-timers etf-autodeploy.timer  # 下次几点跑
journalctl -u etf-autodeploy -n 50          # 同上，走 systemd 日志
./scripts/autodeploy.sh --check             # 只看有没有新版本，不动手
./scripts/autodeploy.sh --force             # 无视 commit 相同，强制重建
```

常见卡点：

| 现象 | 原因 |
|---|---|
| 日志一直"git fetch 连续失败" | 服务器出网被拦 / 凭证失效，`git pull` 手动跑一次看报错 |
| "本地有未提交改动，跳过" | 服务器上有人改过文件，`git status` 看一眼再决定要不要 stash |
| 一直 "新版本健康检查未通过" | 新代码有 bug，已自动回滚，看 `docker compose logs backend` |
