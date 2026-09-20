import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.features import FEATURE_NAMES  # noqa: E402
from app.ml.labels import TrainingExample  # noqa: E402
from app.ml.model import MLModel  # noqa: E402
from app.ml.split import chronological_split  # noqa: E402


def make_example(opportunity_score, label, entry_time):
    features = {name: 0.0 for name in FEATURE_NAMES}
    features["opportunity_score"] = opportunity_score
    return TrainingExample(symbol="TEST", entry_time=entry_time, features=features, label=label)


def test_scaler_statistics_come_only_from_training_data():
    """If the scaler were (incorrectly) fit on the full dataset, its mean
    for 'opportunity_score' would sit somewhere between the train
    distribution (~50) and the val/test distribution (~90) - i.e. pulled
    noticeably above 50. Since the model is only ever fit on the training
    split, the scaler's mean must reflect ONLY the training distribution."""
    train_examples = [make_example(50.0 + (i % 5), i % 2, entry_time=i) for i in range(40)]
    val_test_examples = [make_example(90.0 + (i % 5), i % 2, entry_time=40 + i) for i in range(40)]
    all_examples = train_examples + val_test_examples

    train, val, test = chronological_split(all_examples, train_frac=0.5, val_frac=0.25)
    assert train == train_examples  # sanity: the split boundary lines up with our construction

    model = MLModel()
    model.fit(train)  # fit on TRAIN ONLY - this is the behavior under test

    mean, _ = model.training_scaler_mean_std()
    opportunity_score_index = FEATURE_NAMES.index("opportunity_score")
    scaler_mean_for_score = mean[opportunity_score_index]

    # Train-only mean should be close to 52 (50-54 range), nowhere near
    # the ~92 the val/test data would pull it toward if leaked in.
    assert 48.0 <= scaler_mean_for_score <= 56.0
    assert scaler_mean_for_score < 70.0  # decisively rules out contamination from val/test


def test_predicting_on_val_or_test_does_not_refit_the_scaler():
    train_examples = [make_example(50.0 + (i % 5), i % 2, entry_time=i) for i in range(40)]
    model = MLModel()
    model.fit(train_examples)
    mean_before, std_before = model.training_scaler_mean_std()

    far_out_examples = [make_example(500.0, 1, entry_time=1000 + i) for i in range(10)]
    model.predict_proba(far_out_examples)

    mean_after, std_after = model.training_scaler_mean_std()
    assert mean_before == mean_after
    assert std_before == std_after


def test_no_model_method_accepts_a_combined_train_and_test_set_implicitly():
    """Structural check: MLModel.fit()'s only parameter is the example
    list it trains on - there is no separate 'test data to peek at'
    parameter anywhere in this class, so there's no API surface through
    which test data could accidentally influence fitting."""
    import inspect

    from app.ml.model import MLModel as ModelClass

    fit_signature = inspect.signature(ModelClass.fit)
    params = list(fit_signature.parameters.keys())
    assert params == ["self", "examples"]
