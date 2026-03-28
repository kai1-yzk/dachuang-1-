from celery import Celery
import os
import logging

from utils.env_loader import load_local_env
from utils.db import execute_query, execute_update

load_local_env()

logger = logging.getLogger(__name__)

REDIS_URL = f"redis://{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', 6379)}/1"

celery_app = Celery(
    'aiops_tasks',
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
)

@celery_app.task(bind=True, max_retries=3)
def process_data_async(self, payload, event_id):
    """
    异步处理高并发接收到的数据
    替代原有 Java 处理器中的消息处理逻辑
    """
    try:
        logger.info(f"Processing event_id: {event_id}, payload: {payload}")
        
        # 实际场景下，此处可以进行数据清洗，并存入数据库或时序数据库
        # 例如:
        # server_name = payload.get('server_name', 'unknown')
        # cpu = payload.get('cpu_usage', 0.0)
        # execute_update("INSERT INTO server_metric (server_name, cpu_usage) VALUES (%s, %s)", (server_name, cpu))
        
        return {"status": "success", "event_id": event_id}
    except Exception as exc:
        logger.error(f"Error processing event_id: {event_id}, error: {exc}")
        self.retry(exc=exc, countdown=5)


@celery_app.task(bind=True, max_retries=3)
def collect_servers_health_async(self):
    """定时将离线服务器标记为offline。"""
    try:
        execute_update(
            """
            UPDATE servers
            SET status='offline', updated_at=NOW()
            WHERE last_seen IS NULL OR last_seen < NOW() - INTERVAL 60 SECOND
            """
        )
        return {"status": "success"}
    except Exception as exc:
        logger.error(f"collect_servers_health_async failed: {exc}")
        self.retry(exc=exc, countdown=10)


@celery_app.task(bind=True, max_retries=3)
def aggregate_recent_metrics_async(self, server_id):
    """聚合最近5分钟指标，便于后续告警模块读取。"""
    try:
        rows = execute_query(
            """
            SELECT AVG(cpu_usage) AS cpu_avg,
                   AVG(memory_usage) AS memory_avg,
                   AVG(disk_usage) AS disk_avg
            FROM server_metrics
            WHERE server_id=%s AND created_at > NOW() - INTERVAL 5 MINUTE
            """,
            (server_id,),
        )
        return rows[0] if rows else {}
    except Exception as exc:
        logger.error(f"aggregate_recent_metrics_async failed: {exc}")
        self.retry(exc=exc, countdown=10)
