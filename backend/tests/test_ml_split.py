import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.labels import TrainingExample  # noqa: E402
from app.ml.split import chronological_split  # noqa: E402


def make_examples(n):
    # deliberately shuffled input order - split must sort by entry_time itself
    times = list(range(n))
    random.Random(0).shuffle(times)
    return [TrainingExample(symbol="TEST", entry_time=t, features={}, label=t % 2) for t in times]


def test_split_respects_proportions():
    examples = make_examples(100)
    train, val, test = chronological_split(examples, train_frac=0.6, val_frac=0.2)
    assert len(train) == 60
    assert len(val) == 20
    assert len(test) == 20


def test_split_is_strictly_chronological_no_overlap():
    examples = make_examples(50)
    train, val, test = chronological_split(examples, train_frac=0.6, val_frac=0.2)

    max_train_time = max(ex.entry_time for ex in train)
    min_val_time = min(ex.entry_time for ex in val)
    max_val_time = max(ex.entry_time for ex in val)
    min_test_time = min(ex.entry_time for ex in test)

    assert max_train_time < min_val_time
    assert max_val_time < min_test_time


def test_split_never_shuffles_regardless_of_input_order():
    examples = make_examples(30)
    train1, val1, test1 = chronological_split(examples, train_frac=0.6, val_frac=0.2)
    reshuffled = examples[:]
    random.Random(99).shuffle(reshuffled)
    train2, val2, test2 = chronological_split(reshuffled, train_frac=0.6, val_frac=0.2)

    assert [ex.entry_time for ex in train1] == [ex.entry_time for ex in train2]
    assert [ex.entry_time for ex in val1] == [ex.entry_time for ex in val2]
    assert [ex.entry_time for ex in test1] == [ex.entry_time for ex in test2]


def test_split_covers_every_example_exactly_once():
    examples = make_examples(37)  # not evenly divisible, exercises rounding
    train, val, test = chronological_split(examples, train_frac=0.6, val_frac=0.2)
    all_times = [ex.entry_time for ex in train + val + test]
    assert sorted(all_times) == list(range(37))


def test_split_rejects_invalid_fractions():
    examples = make_examples(10)
    with pytest.raises(ValueError):
        chronological_split(examples, train_frac=0.7, val_frac=0.4)  # sums > 1
    with pytest.raises(ValueError):
        chronological_split(examples, train_frac=0.0, val_frac=0.5)
