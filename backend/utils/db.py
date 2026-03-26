import pymysql
import os
from dbutils.pooled_db import PooledDB
import logging

logger = logging.getLogger(__name__)

# 获取数据库配置，优先从环境变量读取
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "185886038Kai.")
DB_NAME = os.environ.get("DB_NAME", "aiops_db")

try:
    # 使用连接池
    pool = PooledDB(
        creator=pymysql,
        maxconnections=10,
        mincached=2,
        maxcached=5,
        blocking=True,
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
except Exception as e:
    logger.error(f"Failed to initialize database connection pool: {e}")
    pool = None

def get_connection():
    """获取数据库连接"""
    if pool:
        return pool.connection()
    return None

def execute_query(sql, args=None):
    """执行查询 (SELECT)"""
    conn = get_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Database query error: {e}")
        return []
    finally:
        conn.close()

def execute_update(sql, args=None):
    """执行更新 (INSERT/UPDATE/DELETE)"""
    conn = get_connection()
    if not conn:
        return 0
    try:
        with conn.cursor() as cursor:
            affected_rows = cursor.execute(sql, args)
        conn.commit()
        return affected_rows
    except Exception as e:
        conn.rollback()
        logger.error(f"Database update error: {e}")
        return 0
    finally:
        conn.close()


def execute_many(sql, args_list):
    """批量执行更新语句"""
    conn = get_connection()
    if not conn:
        return 0
    try:
        with conn.cursor() as cursor:
            affected_rows = cursor.executemany(sql, args_list)
        conn.commit()
        return affected_rows
    except Exception as e:
        conn.rollback()
        logger.error(f"Database executemany error: {e}")
        return 0
    finally:
        conn.close()
