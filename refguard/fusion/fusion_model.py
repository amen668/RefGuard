"""FusionModel: LR + Platt scaling, output P(match). Fallback heuristic if no model."""
import json
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from refguard.models import BibEntry, SourceHit, MatchFeatures
from refguard.fusion.feature_builder import FeatureBuilder, FEATURE_NAMES


# Default weights (approximate: title/author/doi matter most); len = len(FEATURE_NAMES)
DEFAULT_WEIGHTS = [
    0.25, 0.2, 0.1, 0.2, 0.15, 0.05, 0.02, 0.0, 0.0, 0.0, 0.01, 0.01, 0.0, 0.0,
]
DEFAULT_BIAS = 1.0


class FusionModel:
    """
    Predict P(match) for each candidate. Uses loaded sklearn LR+calibration or default heuristic.
    """

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

    def predict_proba(self, features_list: List[MatchFeatures]) -> List[float]:
        """Return P(match) for each feature vector (sigmoid over linear combination)."""
        if not features_list:
            return []
        X = np.array([f.to_vector() for f in features_list], dtype=np.float64)
        # Pad if needed
        if X.shape[1] < len(self._weights):
            X = np.pad(X, ((0, 0), (0, len(self._weights) - X.shape[1])))
        logit = X @ self._weights[: X.shape[1]] + self._bias
        # Platt: already in logit form; sigmoid
        p = 1.0 / (1.0 + np.exp(-np.clip(logit, -20, 20)))
        return p.tolist()

    def predict_and_explain(
        self, entry: BibEntry, candidates: List[SourceHit], top_k: int = 5
    ) -> Tuple[List[float], List[dict], Optional[dict]]:
        """
        Build features for each candidate, predict P(match), return probs, per-candidate explanations, and top-feature summary.
        """
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
        # Top features (global: which matter most - use weights)
        top_features = dict(zip(FEATURE_NAMES[: len(self._weights)], self._weights.tolist()))
        top_features = dict(sorted(top_features.items(), key=lambda x: -abs(x[1]))[:5])
        return probs, explanations, {"top_features": top_features}
