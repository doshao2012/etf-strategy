# ETF 策略服务 - Dockerfile
# 用于 Railway 部署

FROM node:18-slim

WORKDIR /app

# 安装 Python
RUN apt-get update && apt-get install -y python3 python3-pip curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 复制 Python 依赖文件并安装
COPY server/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 复制所有代码
COPY . .

# 安装 pnpm 并构建
RUN npm install -g pnpm && \
    pnpm install && \
    pnpm run build

# 暴露端口
ENV PORT=3000

# 启动命令
ENTRYPOINT ["sh", "-c", "cd server && python3 -m uvicorn main:app --host 0.0.0.0 --port 3000 & pnpm start"]
