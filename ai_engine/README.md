# ai_engine — 数据集与模型

本目录的**数据集与模型产物不入 git**（体积达数百 MB）。克隆仓库后需按下列步骤自行获取或生成。

## 目录结构

```
ai_engine/
├── models/
│   ├── fusion_model.py                 # Isolation Forest + LSTM 融合模型定义
│   ├── server_anomaly_predictor.py     # 上层预测器（特征工程 + 加载/推理）
│   ├── server_anomaly_artifacts.json   # 训练指标报告（已入库，仅元数据）
│   └── server_anomaly_artifacts.pkl    # 模型本体（.gitignore，需自行生成）
├── data/                               # 数据集（.gitignore，需自行下载）
└── train.py                            # 训练脚本
```

## 数据集

训练脚本从 `ai_engine/data/**/metric_detection/**/*.csv` 读取带 `timestamp` / `value` / `label`
三列的指标数据。

### GAIA 数据集（智能运维）

- 用途：指标异常检测、日志解析与语义异常检测训练数据。
- 来源：GAIA（AIOps Challenge 公开数据集），按仓库原命名 `GAIA-DataSet-main` 放置。
- 放置路径：`ai_engine/data/GAIA-DataSet-main（智能运维数据集）/`
- 必需子集：`metric_detection/` 下的 `*.csv`（训练脚本仅依赖此部分）。
  `log/` 下的日志解析与 NER 数据为可选，仅用于扩展实验。

### UNSW-NB15（网络入侵检测）

- 用途：网络流量异常检测扩展实验。
- 来源：UNSW-NB15 公开数据集，按仓库原命名 `UNSW_NB15-master` 放置。
- 放置路径：`ai_engine/data/UNSW_NB15-master（网络入侵）/`
- 主文件：`UNSW_NB15_training-set.csv`、`UNSW_NB15_testing-set.csv`

> 两个数据集均为公开学术数据集，请遵守其各自的许可与引用要求。

## 生成模型

```bash
cd ai_engine
python train.py
```

默认产物：`ai_engine/models/server_anomaly_artifacts.pkl`

可用参数：

```bash
python train.py --output models/my_artifacts.pkl
```

## 模型缺失时的行为

后端 `routes/ai_analysis.py` 的加载顺序为 `.pkl` → `.json`：

- **找到 `.pkl`**：加载模型推理。
- **只有 `.json`**：`.json` 仅为训练指标报告（F1、阈值等），**不含模型权重**，
  实际会走规则化预测（`_rule_based_prediction`）作为降级路径。
- **两者都不存在**：抛 `FileNotFoundError`，接口返回错误。

因此未生成 `.pkl` 时，AI 预测功能会自动降级为规则预测，不影响其他模块。

## 当前模型表现（来自 server_anomaly_artifacts.json）

| 指标 | 值 |
|------|-----|
| 训练文件 / 验证文件 | 96 / 24 |
| 训练样本 / 验证样本 | 28,791 / 213,120 |
| 正样本率（训练 / 验证） | 11.1% / 2.9% |
| 阈值 | 0.08 |
| Precision | 0.0090 |
| Recall | 0.0956 |
| **F1** | **0.0164** |

> **注意**：当前 F1 仅约 0.016，接近随机水平，说明该模型在实际数据上尚不具备可用的
> 预测能力。异常检测模型的效果高度依赖标签质量与特征工程，后续需重点改进：
> 特征构造（滑动窗口统计量）、类别不平衡处理（重采样 / 代价敏感）、阈值选择策略。
> 答辩与文档中不应将该模型描述为"已具备生产级故障预测能力"。

## 融合模型说明

`models/fusion_model.py` 提供 Isolation Forest（静态异常点）与 LSTM（时序趋势预测）
的模型定义及轻量化封装（剪枝、量化函数骨架），属于**研究性代码**，尚未接入
`train.py` 的生产训练流程。`train.py` 当前实际训练的是 RandomForest + IsolationForest。
