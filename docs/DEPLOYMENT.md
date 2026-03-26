# Deployment Guide

## 1. 环境准备
- Python 3.10+
- Node.js 18+
- MySQL 8+
- Redis 6+

## 2. 初始化数据库

```bash
mysql -u root -p < deploy/init.sql
```

## 3. 启动后端

```bash
cd backend
pip install -r requirements.txt
python app.py
```

## 4. 启动 Celery Worker

```bash
cd backend
celery -A tasks worker --loglevel=info
```

## 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

## 6. 启动 Agent（可选）

```bash
cd agent
pip install -r requirements.txt
python agent_client.py
```

## 7. 生产部署建议
- 使用 Nginx 反向代理并开启 WebSocket Upgrade。
- 使用 Gunicorn + Gevent 运行 Flask-SocketIO。
- 使用 Redis 作为 SocketIO 消息队列与会话缓存。
- 使用 MySQL 主从或托管 RDS 提升可用性。
