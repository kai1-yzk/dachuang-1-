import multiprocessing
import os

# 绑定端口
bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:5000')

# 工作进程数，建议为 CPU 核心数的 2 倍加 1，这里保持高并发配置
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))

# 工作模式，采用 gevent 提升高并发下 I/O 密集型接口的处理能力
worker_class = 'gevent'

# 单个进程的最大并发连接数
worker_connections = int(os.environ.get('GUNICORN_WORKER_CONNECTIONS', 1000))

# 超时时间 (秒)
timeout = int(os.environ.get('GUNICORN_TIMEOUT', 30))

# 保持活动连接的超时时间
keepalive = int(os.environ.get('GUNICORN_KEEPALIVE', 2))

# 日志配置
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('GUNICORN_LOGLEVEL', 'info')
