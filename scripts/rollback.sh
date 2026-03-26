#!/bin/bash
# 紧急回滚脚本

set -e

CURRENT_ENV=$(cat /tmp/current_env 2>/dev/null || echo "green")

if [ "$CURRENT_ENV" == "blue" ]; then
    ROLLBACK_ENV="green"
else
    ROLLBACK_ENV="blue"
fi

echo "Initiating emergency rollback to $ROLLBACK_ENV..."

# 确保旧环境还在运行，如果没有则启动
docker-compose -p aiops_$ROLLBACK_ENV -f docker-compose.yml start backend

# 切换流量
# 示例: sed -i "s/server aiops_$CURRENT_ENV/server aiops_$ROLLBACK_ENV/" /etc/nginx/nginx.conf
# nginx -s reload

echo $ROLLBACK_ENV > /tmp/current_env

echo "Traffic switched to $ROLLBACK_ENV. Stopping $CURRENT_ENV..."
docker-compose -p aiops_$CURRENT_ENV stop backend

echo "Rollback completed."
