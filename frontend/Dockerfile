# 指定 Node.js 20
FROM node:20-slim

# 安装 pnpm
RUN npm install -g pnpm@9

# 设置工作目录
WORKDIR /app

# 先复制依赖文件
COPY package.json pnpm-lock.yaml ./

# 安装依赖
RUN pnpm install --frozen-lockfile

# 复制剩余代码
COPY . .

# 构建
RUN pnpm run build

# 暴露端口
EXPOSE 5000

# 启动
CMD ["pnpm", "start"]
