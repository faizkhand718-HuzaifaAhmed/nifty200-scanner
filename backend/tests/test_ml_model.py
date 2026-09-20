import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.features import FEATURE_NAMES  # noqa: E402
from app.ml.labels import TrainingExample  # noqa: E402
from app.ml.model import MLModel  # noqa: E402


def make_example(opportunity_score, label, entry_time):
    features = {name: 0.0 for name in FEATURE_NAMES}
    features["opportunity_score"] = opportunity_score
    features["adx"] = 20.0
    features["atr_pct"] = 0.01
    return TrainingExample(symbol="TEST", entry_time=entry_time, features=features, label=label)


def make_separable_dataset(n=60):
    """High opportunity_score -> win, low -> loss - a deliberately easy,
    clearly-separable synthetic pattern so a correctly-implemented model
    should recover it easily. This tests the ML PLUMBING (does training
    and prediction work correctly end to end), not whether ML helps on
    real trading data - that's comparison.py's job on real backtest data."""
    examples = []
    for i in range(n):
        if i % 2 == 0:
            examples.append(make_example(opportunity_score=85.0 + (i % 5), label=1, entry_time=i))
        else:
            examples.append(make_example(opportunity_score=20.0 + (i % 5), label=0, entry_time=i))
    return examples


def test_model_recovers_a_clearly_separable_pattern():
    examples = make_separable_dataset(60)
    model = MLModel()
    model.fit(examples)

    high_score_example = make_example(opportunity_score=90.0, label=1, entry_time=1000)
    low_score_example = make_example(opportunity_score=15.0, label=0, entry_time=1001)
    probs = model.predict_proba([high_score_example, low_score_example])

    assert probs[0] > 0.7   # confidently predicts a win for a clearly-favorable case
    assert probs[1] < 0.3   # confidently predicts a loss for a clearly-unfavorable case


def test_model_coefficients_are_interpretable_and_directionally_sensible():
    examples = make_separable_dataset(60)
    model = MLModel()
    model.fit(examples)
    coefficients = model.feature_coefficients()

    assert set(coefficients.keys()) == set(FEATURE_NAMES)
    # opportunity_score was the only informative feature in this synthetic
    # dataset - it should have a clearly positive coefficient (higher
    # score -> more likely to predict a win).
    assert coefficients["opportunity_score"] > 0


def test_fit_requires_at_least_two_examples():
    with pytest.raises(ValueError):
        MLModel().fit([make_example(80.0, 1, 0)])


def test_fit_requires_both_classes_present():
    examples = [make_example(80.0, 1, i) for i in range(5)]  # all wins, no losses
    with pytest.raises(ValueError):
        MLModel().fit(examples)


def test_predict_before_fit_raises():
    model = MLModel()
    with pytest.raises(RuntimeError):
        model.predict_proba([make_example(80.0, 1, 0)])


def test_predict_proba_empty_list_returns_empty():
    examples = make_separable_dataset(10)
    model = MLModel()
    model.fit(examples)
    assert model.predict_proba([]) == []
