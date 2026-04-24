# ETF 策略服务 - Dockerfile
# 用于 Railway 部署

FROM python:3.11-slim

# 安装 Node.js 20
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 安装 pnpm
RUN npm install -g pnpm

WORKDIR /app

# 复制所有代码
COPY . .

# 安装 Python 依赖
RUN pip3 install -r requirements.txt

# 安装 Node.js 依赖
RUN pnpm install --frozen-lockfile

# 构建前端
RUN pnpm run build

# 暴露端口
ENV PORT=3000

# 启动命令：同时运行 FastAPI 和 Next.js
CMD cd server && \
    python3 -m uvicorn main:app --host 0.0.0.0 --port 3000 & \
    sleep 5 && \
    pnpm start
