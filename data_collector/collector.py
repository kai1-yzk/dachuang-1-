"""
数据采集与预处理模块
创建时间: 2026-03-24
功能说明: 通过 requests 对接 Node Exporter 抓取监控数据，使用 Pandas 完成数据清洗、对齐与标准化
"""
import requests
import pandas as pd
import numpy as np
import time
import logging
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

class MetricsCollector:
    """
    轻量级服务器指标采集器
    目标: 对接 Node Exporter, 解析 Prometheus 格式指标
    """
    def __init__(self, target_url="http://localhost:9100/metrics"):
        self.target_url = target_url
        self.scaler = StandardScaler()
        self.historical_data = []

    def fetch_metrics(self):
        """
        采集 Node Exporter 原始数据
        核心逻辑: 仅提取 CPU、内存、磁盘和网络核心指标
        """
        try:
            response = requests.get(self.target_url, timeout=5)
            response.raise_for_status()
            raw_data = response.text
            return self._parse_prometheus_text(raw_data)
        except requests.RequestException as e:
            logger.error(f"Failed to fetch metrics: {e}")
            return None

    def _parse_prometheus_text(self, text):
        """
        解析 Node Exporter 数据 (简易实现)
        """
        metrics = {}
        for line in text.split('\n'):
            if line.startswith('#') or not line:
                continue
            
            # 提取 CPU 负载、内存等核心字段
            if line.startswith('node_cpu_seconds_total'):
                metrics['cpu'] = float(line.split(' ')[1])
            elif line.startswith('node_memory_MemAvailable_bytes'):
                metrics['mem_avail'] = float(line.split(' ')[1])
            elif line.startswith('node_memory_MemTotal_bytes'):
                metrics['mem_total'] = float(line.split(' ')[1])
        
        # 计算利用率
        if 'mem_avail' in metrics and 'mem_total' in metrics:
            metrics['memory_usage'] = (metrics['mem_total'] - metrics['mem_avail']) / metrics['mem_total']
            
        metrics['timestamp'] = time.time()
        return metrics

    def preprocess_data(self, raw_metrics_list):
        """
        多源数据时间戳对齐、清洗与缺失值填充
        """
        df = pd.DataFrame(raw_metrics_list)
        
        # 时间戳对齐与降采样 (如 10s 一次)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        df.set_index('datetime', inplace=True)
        df_resampled = df.resample('10S').mean()
        
        # 缺失值填充 (前向填充)
        df_cleaned = df_resampled.ffill().bfill()
        
        # 提取特征
        features = df_cleaned[['cpu', 'memory_usage']].values
        
        # 特征标准化 (Z-score)
        normalized_features = self.scaler.fit_transform(features)
        
        return normalized_features
        
if __name__ == "__main__":
    collector = MetricsCollector()
    metrics = collector.fetch_metrics()
    print("Fetched:", metrics)
