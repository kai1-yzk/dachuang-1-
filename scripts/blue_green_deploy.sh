#!/bin/bash
# 蓝绿发布脚本 (Blue-Green Deployment)
# 原理: 通过 Nginx upstream 切换流量实现 0 停机更新

set -e

# 当前运行环境 (blue 或 green)
CURRENT_ENV=$(cat /tmp/current_env 2>/dev/null || echo "blue")

if [ "$CURRENT_ENV" == "blue" ]; then
    NEW_ENV="green"
    OLD_ENV="blue"
    PORT=5001
else
    NEW_ENV="blue"
    OLD_ENV="green"
    PORT=5000
fi

echo "Deploying to $NEW_ENV environment..."

# 启动新环境
docker-compose -p aiops_$NEW_ENV -f docker-compose.yml up -d --build backend

echo "Waiting for $NEW_ENV to become healthy..."
sleep 15

# 执行健康检查
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/api/metrics/current)

if [ "$HTTP_CODE" == "200" ]; then
    echo "Health check passed. Switching traffic to $NEW_ENV..."
    
    # 这里应通过脚本或配置管理工具更新 Nginx/HAProxy 的 upstream
    # 示例: sed -i "s/server aiops_$OLD_ENV/server aiops_$NEW_ENV/" /etc/nginx/nginx.conf
    # nginx -s reload

    echo $NEW_ENV > /tmp/current_env
    
    echo "Stopping old environment $OLD_ENV..."
    docker-compose -p aiops_$OLD_ENV stop backend
    
    echo "Deployment successful."
else
    echo "Health check failed with HTTP $HTTP_CODE! Aborting deployment and rolling back."
    docker-compose -p aiops_$NEW_ENV stop backend
    exit 1
fi
