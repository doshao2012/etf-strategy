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

# 复制依赖文件
COPY server/requirements.txt /app/server/
COPY package.json pnpm-lock.yaml* /app/

# 安装 Python 依赖
RUN pip3 install -r server/requirements.txt

# 安装 Node.js 依赖并构建前端
RUN pnpm install --frozen-lockfile
RUN pnpm run build

# 复制应用代码
COPY . .

# 暴露端口
ENV PORT=3000

# 启动命令：同时运行 FastAPI 和 Next.js
CMD cd server && \
    python3 -m uvicorn main:app --host 0.0.0.0 --port 3000 & \
    pnpm start
