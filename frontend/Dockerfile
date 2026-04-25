FROM node:20-alpine

# 安装 pnpm
RUN npm install -g pnpm@9

WORKDIR /app

# 复制依赖文件
COPY package.json pnpm-lock.yaml ./

# 安装依赖（使用更少内存）
RUN pnpm install --frozen-lockfile --prefer-offline

# 复制代码
COPY . .

# 构建
RUN pnpm build

# 暴露端口
EXPOSE 5000

# 启动
CMD ["pnpm", "start"]
