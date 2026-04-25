FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip3 install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY . .

# 暴露端口
EXPOSE 3000

# 启动
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
