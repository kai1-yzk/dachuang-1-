import pymysql
import os
from dbutils.pooled_db import PooledDB
import logging

from utils.env_loader import load_local_env

load_local_env()

logger = logging.getLogger(__name__)

# 获取数据库配置，优先从环境变量读取
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "aiops_db")

pool = None
_last_db_error = None


def init_pool(force=False):
    """初始化数据库连接池；失败时记录错误并返回 False。"""
    global pool, _last_db_error
    if pool is not None and not force:
        return True
    try:
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
            cursorclass=pymysql.cursors.DictCursor,
        )
        _last_db_error = None
        return True
    except Exception as e:
        pool = None
        _last_db_error = str(e)
        logger.error(f"Failed to initialize database connection pool: {e}")
        return False


# 启动时尝试一次；后续请求会在 get_connection 中自动重试。
init_pool()

def get_connection():
    """获取数据库连接"""
    if pool is None and not init_pool():
        return None
    if pool:
        try:
            return pool.connection()
        except Exception as e:
            logger.error(f"Failed to get database connection from pool: {e}")
            # 连接池失效时强制重建一次
            if init_pool(force=True):
                return pool.connection()
    return None


def is_db_available():
    """检查数据库当前是否可用。"""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_last_db_error():
    """返回最近一次数据库连接错误，便于接口层诊断。"""
    return _last_db_error

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
