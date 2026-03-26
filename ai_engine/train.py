"""
AI 模型训练脚本
功能: 读取 GAIA 数据集，训练 Isolation Forest 和 LSTM 融合模型，并保存模型权重
"""
import os
import pandas as pd
import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset
import pickle
from models.fusion_model import AIOpsFusionModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据集路径
DATA_DIR = r"C:\Users\熊二\Desktop\大创\ai_engine\data\GAIA-DataSet-main（智能运维数据集）\metric_detection\linear_data"
MODEL_SAVE_DIR = r"C:\Users\熊二\Desktop\大创\ai_engine\models"

def load_data():
    """读取并预处理数据集"""
    logger.info("Loading dataset...")
    all_values = []
    all_labels = []
    
    # 读取前 5 个 csv 文件作为训练集示例
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')][:5]
    
    for file in files:
        file_path = os.path.join(DATA_DIR, file)
        df = pd.read_csv(file_path)
        
        # 处理缺失值
        df['value'] = df['value'].fillna(method='ffill').fillna(method='bfill')
        
        # 标准化 (Z-score)
        val = df['value'].values
        val = (val - np.mean(val)) / (np.std(val) + 1e-8)
        
        all_values.extend(val)
        if 'label' in df.columns:
            all_labels.extend(df['label'].values)
            
    all_values = np.array(all_values, dtype=np.float32)
    return all_values

def create_sequences(data, seq_length=10):
    """创建时间序列数据用于 LSTM 训练"""
    xs = []
    ys = []
    for i in range(len(data) - seq_length):
        x = data[i:(i + seq_length)]
        y = data[i + seq_length]
        xs.append(x)
        ys.append(y)
    return np.array(xs), np.array(ys)

def main():
    os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
    
    # 1. 加载数据
    data = load_data()
    if len(data) == 0:
        logger.error("No data found!")
        return
        
    # 我们使用单变量数据，特征维度为 1
    input_features = 1
    fusion_model = AIOpsFusionModel(input_features=input_features)
    
    # 2. 训练 Isolation Forest (使用 reshape 转换为 2D 数组)
    X_train_iso = data.reshape(-1, 1)
    fusion_model.train_isolation_forest(X_train_iso)
    
    # 3. 训练 LSTM
    seq_length = 10
    X_seq, y_seq = create_sequences(data, seq_length)
    
    # 转换形状为 (batch_size, seq_length, input_features)
    X_seq = X_seq.reshape(-1, seq_length, input_features)
    y_seq = y_seq.reshape(-1, 1)
    
    tensor_x = torch.tensor(X_seq)
    tensor_y = torch.tensor(y_seq)
    
    dataset = TensorDataset(tensor_x, tensor_y)
    dataloader = DataLoader(dataset, batch_size=64, shuffle=True)
    
    fusion_model.train_lstm(dataloader, epochs=5, lr=0.005)  # 为了演示，设置 epoch=5
    
    # 4. 执行轻量化优化 (剪枝 + 量化)
    fusion_model.apply_lightweight_optimization()
    
    # 5. 保存模型
    # 保存 Isolation Forest
    iso_model_path = os.path.join(MODEL_SAVE_DIR, "isolation_forest.pkl")
    with open(iso_model_path, 'wb') as f:
        pickle.dump(fusion_model.iso_forest, f)
        
    # 保存 LSTM (保存 state_dict)
    lstm_model_path = os.path.join(MODEL_SAVE_DIR, "lstm_quantized.pth")
    torch.save(fusion_model.lstm_model.state_dict(), lstm_model_path)
    
    logger.info(f"Models saved to {MODEL_SAVE_DIR}")

if __name__ == "__main__":
    main()
