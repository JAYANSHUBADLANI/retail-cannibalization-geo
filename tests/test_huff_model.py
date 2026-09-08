import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from huff_model import huff_probabilities, pairwise_overlap, relevant_population_mask, store_captured_demand


def test_probabilities_sum_to_one_per_cell():
    distances = np.array([[100.0, 200.0, 300.0], [500.0, 100.0, 50.0]])
    attractiveness = np.array([1.0, 1.0, 1.0])
    probs = huff_probabilities(distances, attractiveness, beta=2.0)
    assert probs.shape == (2, 3)
    np.testing.assert_allclose(probs.sum(axis=1), 1.0)


def test_closer_store_gets_higher_probability():
    distances = np.array([[100.0, 1000.0]])
    attractiveness = np.array([1.0, 1.0])
    probs = huff_probabilities(distances, attractiveness, beta=2.0)
    assert probs[0, 0] > probs[0, 1]


def test_higher_beta_sharpens_the_closer_stores_advantage():
    distances = np.array([[100.0, 200.0]])
    attractiveness = np.array([1.0, 1.0])
    low_beta = huff_probabilities(distances, attractiveness, beta=1.0)
    high_beta = huff_probabilities(distances, attractiveness, beta=4.0)
    assert high_beta[0, 0] > low_beta[0, 0]


def test_higher_attractiveness_increases_share_at_equal_distance():
    distances = np.array([[100.0, 100.0]])
    attractiveness = np.array([1.0, 3.0])
    probs = huff_probabilities(distances, attractiveness, beta=2.0)
    assert probs[0, 1] > probs[0, 0]


def test_store_captured_demand_matches_manual_calculation():
    probs = np.array([[0.7, 0.3], [0.4, 0.6]])
    population = np.array([100.0, 50.0])
    captured = store_captured_demand(probs, population)
    expected_store_0 = 100 * 0.7 + 50 * 0.4
    expected_store_1 = 100 * 0.3 + 50 * 0.6
    np.testing.assert_allclose(captured, [expected_store_0, expected_store_1])


def test_pairwise_overlap_is_zero_when_probabilities_never_overlap():
    probs = np.array([[1.0, 0.0], [0.0, 1.0]])
    population = np.array([10.0, 10.0])
    overlap = pairwise_overlap(probs, population, 0, 1)
    assert overlap == 0.0


def test_pairwise_overlap_is_positive_when_probabilities_are_similar():
    probs = np.array([[0.5, 0.5], [0.5, 0.5]])
    population = np.array([10.0, 10.0])
    overlap = pairwise_overlap(probs, population, 0, 1)
    assert overlap == pytest.approx(10.0)


def test_relevant_mask_excludes_distant_cells():
    # two population cells: one near stores 0 and 1, one far from both
    # with many closer alternative stores (indices 2, 3, 4)
    distances = np.array([
        [50.0, 60.0, 1000.0, 1001.0, 1002.0],   # near stores 0 and 1
        [900.0, 950.0, 10.0, 20.0, 30.0],       # near stores 2, 3, 4 instead
    ])
    mask = relevant_population_mask(distances, i=0, j=1, top_k=3)
    assert mask[0] == True
    assert mask[1] == False


def test_relevant_mask_restriction_reduces_or_keeps_overlap():
    probs = np.array([[0.5, 0.5], [0.4, 0.4], [0.01, 0.01]])
    population = np.array([10.0, 10.0, 1000.0])
    distances = np.array([
        [50.0, 60.0],
        [70.0, 65.0],
        [5000.0, 5000.0],
    ])
    unrestricted = pairwise_overlap(probs, population, 0, 1)
    mask = relevant_population_mask(distances, 0, 1, top_k=1)
    restricted = pairwise_overlap(probs, population, 0, 1, relevant_mask=mask)
    assert restricted <= unrestricted
