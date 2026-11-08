FROM python:3.11-alpine

WORKDIR /app

# 安装系统依赖
RUN apk add --no-cache curl

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip3 install --no-cache-dir -r requirements.txt

# 复制后端代码（context是backend，所以用.）
COPY . .

# 启动前把内置的初始配置灌进持久卷（卷非空时不动，见脚本）
RUN chmod +x /app/docker-entrypoint.sh

# 暴露端口
EXPOSE 3000

# 启动
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
