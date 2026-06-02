"""融合模型：输出参考文献与候选结果的匹配概率。"""
import json
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from refguard.models import BibEntry, SourceHit, MatchFeatures
from refguard.fusion.feature_builder import FeatureBuilder, FEATURE_NAMES


# 默认权重偏向题名、作者和 DOI，用作没有训练模型时的启发式判断。
DEFAULT_WEIGHTS = [
    0.25, 0.2, 0.1, 0.2, 0.15, 0.05, 0.02, 0.0, 0.0, 0.0, 0.01, 0.01, 0.0, 0.0,
]
DEFAULT_BIAS = 1.0


class FusionModel:
    """为每个候选结果预测匹配概率。"""

    def __init__(self, model_dir: Optional[str] = None) -> None:
        self.model_dir = Path(model_dir) if model_dir else None
        self._estimator = None
        self._calibrator = None
        n = len(FEATURE_NAMES)
        w = DEFAULT_WEIGHTS[:n] + [0.0] * (n - len(DEFAULT_WEIGHTS))
        self._weights = np.array(w[:n])
        self._bias = DEFAULT_BIAS
        if self.model_dir and (self.model_dir / "fusion_model.json").exists():
            self._load_default_weights(self.model_dir)

    def _load_default_weights(self, path: Path) -> None:
        try:
            with open(path / "fusion_model.json", "r") as f:
                data = json.load(f)
                w = data.get("weights")
                if w and len(w) == len(FEATURE_NAMES):
                    self._weights = np.array(w)
                self._bias = data.get("bias", DEFAULT_BIAS)
        except Exception:
            pass

    def predict_proba_matrix(self, X: np.ndarray) -> np.ndarray:
        """对原始特征矩阵直接打分（供消融/单源分析复用，避免构造 MatchFeatures）。"""
        X = np.asarray(X, dtype=np.float64)
        if X.ndim == 1:
            X = X[None, :]
        if X.shape[1] < len(self._weights):
            X = np.pad(X, ((0, 0), (0, len(self._weights) - X.shape[1])))
        logit = X @ self._weights[: X.shape[1]] + self._bias
        return 1.0 / (1.0 + np.exp(-np.clip(logit, -20, 20)))

    def predict_proba(self, features_list: List[MatchFeatures]) -> List[float]:
        """返回每个特征向量的匹配概率。"""
        if not features_list:
            return []
        X = np.array([f.to_vector() for f in features_list], dtype=np.float64)
        return self.predict_proba_matrix(X).tolist()

    def predict_and_explain(
        self, entry: BibEntry, candidates: List[SourceHit], top_k: int = 5
    ) -> Tuple[List[float], List[dict], Optional[dict]]:
        """生成候选特征、匹配概率、单候选解释和主要特征摘要。"""
        total = len(candidates)
        features_list = [
            FeatureBuilder.build(entry, h, rank=i + 1, total_candidates=total)
            for i, h in enumerate(candidates)
        ]
        probs = self.predict_proba(features_list)
        explanations = []
        for f, p in zip(features_list, probs):
            explanations.append({
                "title_sim": f.title_sim,
                "author_sim": f.author_sim,
                "year_match": f.year_match,
                "doi_match": f.doi_match,
                "source_prior": f.source_prior,
                "probability": p,
            })
        # 按权重绝对值取本次解释里最重要的特征。
        top_features = dict(zip(FEATURE_NAMES[: len(self._weights)], self._weights.tolist()))
        top_features = dict(sorted(top_features.items(), key=lambda x: -abs(x[1]))[:5])
        return probs, explanations, {"top_features": top_features}
