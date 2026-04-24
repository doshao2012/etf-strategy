# ETF 策略服务 - Dockerfile
# 用于 Railway 部署

FROM node:20-slim

WORKDIR /app

# 安装 Python、curl、psmisc（fuser）
RUN apt-get update && apt-get install -y python3 python3-pip curl psmisc && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 安装 pnpm
RUN npm install -g pnpm

# 复制所有代码
COPY . .

# 安装 Python 依赖
RUN pip3 install --no-cache-dir --break-system-packages -r server/requirements.txt

# 安装 Node.js 依赖
RUN pnpm install

# 构建前端
RUN pnpm run build

# 暴露端口
ENV PORT=3000

# 启动命令
ENTRYPOINT ["sh", "-c", "cd server && python3 -m uvicorn main:app --host 0.0.0.0 --port 3000 & pnpm start"]
