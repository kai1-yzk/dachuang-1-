"""
训练服务器异常预测模型（落地版）
- 数据源：GAIA metric_detection 下带 label 的 CSV
- 产物：ai_engine/models/server_anomaly_artifacts.pkl
"""

import argparse
import json
import pickle
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import f1_score, precision_recall_curve, precision_score, recall_score

from models.server_anomaly_predictor import FEATURE_COLUMNS, build_feature_frame


def load_metric_files(data_root: Path) -> List[Path]:
    files = sorted(data_root.glob("**/metric_detection/**/*.csv"))
    return [f for f in files if f.is_file()]


def file_to_xy(file_path: Path) -> Tuple[np.ndarray, np.ndarray]:
    df = pd.read_csv(file_path)
    if not {"timestamp", "value", "label"}.issubset(set(df.columns)):
        return np.empty((0, len(FEATURE_COLUMNS))), np.empty((0,))

    df = df[["timestamp", "value", "label"]].dropna()
    if len(df) < 20:
        return np.empty((0, len(FEATURE_COLUMNS))), np.empty((0,))

    feat_df = build_feature_frame(df)
    x = feat_df[FEATURE_COLUMNS].to_numpy(dtype=np.float64)
    y = (feat_df["label"].to_numpy(dtype=np.float64) > 0).astype(np.int32)
    return x, y


def balanced_sample(x: np.ndarray, y: np.ndarray, max_normal_ratio: int = 8, random_state: int = 42):
    rng = np.random.default_rng(random_state)
    pos_idx = np.where(y == 1)[0]
    neg_idx = np.where(y == 0)[0]
    if len(pos_idx) == 0 or len(neg_idx) == 0:
        return x, y

    keep_neg = min(len(neg_idx), len(pos_idx) * max_normal_ratio)
    sampled_neg = rng.choice(neg_idx, size=keep_neg, replace=False)
    idx = np.concatenate([pos_idx, sampled_neg])
    rng.shuffle(idx)
    return x[idx], y[idx]


def choose_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
    if len(thresholds) == 0:
        return 0.5
    f1 = 2 * precision[:-1] * recall[:-1] / (precision[:-1] + recall[:-1] + 1e-8)
    best_idx = int(np.argmax(f1))
    return max(float(thresholds[best_idx]), 0.08)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default=str(Path(__file__).resolve().parent / "data"))
    parser.add_argument("--max-files", type=int, default=180)
    parser.add_argument("--output", default=str(Path(__file__).resolve().parent / "models" / "server_anomaly_artifacts.pkl"))
    args = parser.parse_args()

    data_root = Path(args.data_root)
    files = load_metric_files(data_root)
    if not files:
        raise RuntimeError(f"No data files found under: {data_root}")

    files = files[: args.max_files]
    split = max(1, int(len(files) * 0.8))
    train_files = files[:split]
    val_files = files[split:]
    if not val_files:
        val_files = train_files[-max(1, len(train_files) // 5):]

    x_train_list, y_train_list = [], []
    for fp in train_files:
        x, y = file_to_xy(fp)
        if len(y) > 0:
            x_train_list.append(x)
            y_train_list.append(y)

    x_val_list, y_val_list = [], []
    for fp in val_files:
        x, y = file_to_xy(fp)
        if len(y) > 0:
            x_val_list.append(x)
            y_val_list.append(y)

    if not x_train_list or not x_val_list:
        raise RuntimeError("Insufficient labeled data after parsing")

    x_train = np.vstack(x_train_list)
    y_train = np.concatenate(y_train_list)
    x_val = np.vstack(x_val_list)
    y_val = np.concatenate(y_val_list)

    x_train, y_train = balanced_sample(x_train, y_train, max_normal_ratio=8)

    clf = RandomForestClassifier(
        n_estimators=220,
        max_depth=18,
        min_samples_leaf=2,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(x_train, y_train)

    contamination = max(0.001, min(0.08, float(np.mean(y_train))))
    iso = IsolationForest(
        n_estimators=160,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    iso.fit(x_train)

    y_prob = clf.predict_proba(x_val)[:, 1]
    threshold = choose_threshold(y_val, y_prob)
    y_pred = (y_prob >= threshold).astype(np.int32)

    metrics = {
        "files_total": len(files),
        "files_train": len(train_files),
        "files_val": len(val_files),
        "train_rows": int(len(y_train)),
        "val_rows": int(len(y_val)),
        "positive_rate_train": float(np.mean(y_train)),
        "positive_rate_val": float(np.mean(y_val)),
        "threshold": float(threshold),
        "f1": float(f1_score(y_val, y_pred, zero_division=0)),
        "precision": float(precision_score(y_val, y_pred, zero_division=0)),
        "recall": float(recall_score(y_val, y_pred, zero_division=0)),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump(
            {
                "model": clf,
                "iso_model": iso,
                "threshold": float(threshold),
                "feature_columns": FEATURE_COLUMNS,
                "metrics": metrics,
            },
            f,
        )

    summary_path = output_path.with_suffix(".json")
    summary_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Training done")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"Saved model: {output_path}")
    print(f"Saved report: {summary_path}")


if __name__ == "__main__":
    main()
