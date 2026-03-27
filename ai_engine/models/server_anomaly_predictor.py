import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "value",
    "delta_1",
    "roll_mean_5",
    "roll_std_5",
    "zscore_20",
]


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data = data.sort_values("timestamp").reset_index(drop=True)
    data["delta_1"] = data["value"].diff().fillna(0.0)
    data["roll_mean_5"] = data["value"].rolling(window=5, min_periods=1).mean()
    data["roll_std_5"] = data["value"].rolling(window=5, min_periods=1).std().fillna(0.0)
    mean20 = data["value"].rolling(window=20, min_periods=5).mean()
    std20 = data["value"].rolling(window=20, min_periods=5).std().replace(0, np.nan)
    data["zscore_20"] = ((data["value"] - mean20) / (std20 + 1e-6)).fillna(0.0)
    return data


@dataclass
class ServerAnomalyPredictor:
    model: object
    iso_model: object
    threshold: float

    @classmethod
    def load(cls, artifact_path: Path) -> "ServerAnomalyPredictor":
        with open(artifact_path, "rb") as f:
            payload = pickle.load(f)
        return cls(
            model=payload["model"],
            iso_model=payload["iso_model"],
            threshold=float(payload.get("threshold", 0.5)),
        )

    def _score_feature_matrix(self, x: np.ndarray) -> Dict[str, np.ndarray]:
        clf_prob = self.model.predict_proba(x)[:, 1]
        iso_raw = -self.iso_model.score_samples(x)
        iso_norm = (iso_raw - iso_raw.min()) / (iso_raw.max() - iso_raw.min() + 1e-6)
        final_score = 0.7 * clf_prob + 0.3 * iso_norm
        return {
            "clf_prob": clf_prob,
            "iso_score": iso_norm,
            "final_score": final_score,
        }

    def predict_series(self, values: List[float], timestamps: Optional[List[int]] = None) -> Dict:
        if not values or len(values) < 10:
            return {
                "ok": False,
                "message": "not enough points, at least 10 required",
            }

        if timestamps and len(timestamps) == len(values):
            ts = timestamps
        else:
            ts = list(range(len(values)))

        df = pd.DataFrame({"timestamp": ts, "value": np.asarray(values, dtype=np.float64)})
        feat_df = build_feature_frame(df)
        row = feat_df.iloc[-1][FEATURE_COLUMNS].to_numpy(dtype=np.float64).reshape(1, -1)
        score_map = self._score_feature_matrix(row)
        score = float(score_map["final_score"][0])

        return {
            "ok": True,
            "score": score,
            "threshold": self.threshold,
            "is_anomaly": score >= self.threshold,
        }

    def predict_multivariate(self, metric_series: Dict[str, List[float]], timestamps: Optional[List[int]] = None) -> Dict:
        details = {}
        scores = []
        for metric_name, values in metric_series.items():
            result = self.predict_series(values, timestamps=timestamps)
            details[metric_name] = result
            if result.get("ok"):
                scores.append(float(result["score"]))

        if not scores:
            return {
                "ok": False,
                "message": "all metric series are insufficient",
                "details": details,
            }

        final_score = float(max(scores))
        return {
            "ok": True,
            "score": final_score,
            "threshold": self.threshold,
            "is_anomaly": final_score >= self.threshold,
            "status": "warning" if final_score >= self.threshold else "normal",
            "details": details,
        }