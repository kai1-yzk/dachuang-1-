FROM python:3.10-slim

WORKDIR /app

# 安装必要的系统依赖 (针对部分 Python 包的编译)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 暴露端口
EXPOSE 5000

# 默认启动命令：通过 gunicorn 配合 gevent 提供高并发服务
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:create_app()"]
