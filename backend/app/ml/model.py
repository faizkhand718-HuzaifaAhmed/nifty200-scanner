"""
The experimental ML model: logistic regression over the engineered
features, chosen deliberately over a more complex model (gradient
boosting, neural net) for the same reason this whole project prefers
transparent, explainable signals - a logistic regression's coefficients
are directly interpretable (which feature pushes toward "win"), unlike a
black-box ensemble.

LEAKAGE PREVENTION IS STRUCTURAL, NOT A CONVENTION: wrapping the scaler
and classifier in one sklearn Pipeline means `.fit(X_train, y_train)`
fits the StandardScaler's mean/std ONLY on the training data; every
subsequent `.predict_proba(X_val_or_test)` call reuses those training-set
statistics. There is no code path in this module that fits the scaler on
validation or test data - see tests/test_ml_no_leakage.py's
test_scaler_statistics_come_only_from_training_data for the proof.

THE ML OUTPUT IS A PROBABILITY-LIKE SCORE, NOT A GUARANTEE: predict_proba
returns the model's estimated probability of a winning trade GIVEN THE
FEATURES IT WAS TRAINED ON. It reflects patterns in past (or synthetic)
data, not a calibrated real-world probability - see comparison.py and
the module-level warning repeated there.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.features import FEATURE_NAMES
from app.ml.labels import TrainingExample, to_feature_matrix


class MLModel:
    def __init__(self, random_state: int = 42, max_iter: int = 1000):
        self.pipeline = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("classifier", LogisticRegression(random_state=random_state, max_iter=max_iter)),
            ]
        )
        self._fitted = False

    def fit(self, examples: List[TrainingExample]) -> None:
        if len(examples) < 2:
            raise ValueError("need at least 2 training examples")
        labels = {ex.label for ex in examples}
        if len(labels) < 2:
            raise ValueError("training examples must include both win and loss labels")
        X, y = to_feature_matrix(examples)
        self.pipeline.fit(X, y)
        self._fitted = True

    def predict_proba(self, examples: List[TrainingExample]) -> List[float]:
        """Returns the predicted probability of a WIN (label=1) for each
        example, using scaler statistics from training only."""
        if not self._fitted:
            raise RuntimeError("model has not been fit yet")
        if not examples:
            return []
        X, _ = to_feature_matrix(examples)
        return [p[1] for p in self.pipeline.predict_proba(X)]

    def feature_coefficients(self) -> dict:
        """Interpretable coefficients (in scaled-feature space) - which
        features push the model toward predicting a win, and by how much.
        Positive = associated with more wins; negative = fewer, given
        this module's favorable-direction-relative feature framing."""
        if not self._fitted:
            raise RuntimeError("model has not been fit yet")
        classifier: LogisticRegression = self.pipeline.named_steps["classifier"]
        return dict(zip(FEATURE_NAMES, classifier.coef_[0].tolist()))

    def training_scaler_mean_std(self) -> Tuple[Optional[list], Optional[list]]:
        """Exposes the fitted scaler's mean/scale - used by
        test_ml_no_leakage.py to prove these come only from training data."""
        if not self._fitted:
            return None, None
        scaler: StandardScaler = self.pipeline.named_steps["scaler"]
        return scaler.mean_.tolist(), scaler.scale_.tolist()
