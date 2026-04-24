# ETF 轮动策略 - Railway 部署指南

## 前置准备

1. **注册 Railway 账号**: https://railway.app
2. **注册 GitHub 账号**: https://github.com
3. **将代码推送到 GitHub 仓库**

## 部署步骤

### 1. 推送代码到 GitHub

```bash
cd /workspace/projects
git init
git add .
git commit -m "feat: ETF轮动策略网页版"
git branch -M main
git remote add origin https://github.com/你的用户名/etf-strategy.git
git push -u origin main
```

### 2. Railway 部署

1. 登录 https://railway.app
2. 点击 "New Project" → "Deploy from GitHub repo"
3. 选择刚才创建的仓库
4. Railway 会自动检测到 Dockerfile 并开始构建

### 3. 配置持久化存储

1. 在 Railway 项目中，点击 "Storage" → "Add Persistent Disk"
2. 选择或创建 volume，命名为 `data`
3. 在服务设置中，将 volume 挂载到 `/data`
4. **重要**: 设置环境变量 `RAILWAY_VOLUME_MOUNT_PATH=/data`

### 4. 等待部署完成

部署时间约 3-5 分钟，完成后会获得一个 `.railway.app` 域名。

## 目录结构

```
.
├── server/                    # FastAPI 后端
│   ├── main.py               # FastAPI 应用
│   ├── database.sqlite       # SQLite 数据库（需要持久化）
│   ├── requirements.txt      # Python 依赖
│   └── scripts/              # Python 脚本
├── src/                      # Next.js 前端
│   └── app/                  # Next.js App Router
├── scripts/                  # 启动脚本
├── Dockerfile               # Docker 构建文件
├── railway.json             # Railway 配置
└── package.json             # Node.js 依赖
```

## 环境变量

| 变量 | 说明 | 默认值 |
|-----|------|-------|
| `PORT` | 服务端口 | `3000` |
| `RAILWAY_VOLUME_MOUNT_PATH` | 持久化存储路径 | `/data` |
| `NODE_ENV` | 运行环境 | `production` |

## 故障排查

### 部署失败
- 检查 Dockerfile 语法
- 确保 requirements.txt 格式正确
- 查看 Railway 构建日志

### 数据库无法写入
- 确保已配置持久化存储
- 检查 volume 挂载路径

### 前端无法访问后端 API
- 检查 CORS 配置
- 确认 FastAPI 服务端口正确

## 更新部署

推送新代码到 GitHub 后，Railway 会自动重新部署。
