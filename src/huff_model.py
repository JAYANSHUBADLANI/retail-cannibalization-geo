"""
A Huff gravity model trade area, chosen over a fixed radius circle because a
fixed radius treats every location as drawing from an identical, symmetric
area regardless of how close its neighbors are, which is exactly the
assumption a cannibalisation analysis needs to test rather than build in.
A Huff model instead lets nearby competing locations split a population
cell's probability between them based on relative distance, so overlap
falls directly out of the model rather than being asserted.

All stores here are the same brand and no franchise size or sales data is
available from OpenStreetMap, so attractiveness is set to 1 for every
store: a bigger location with more seating or a drive through would
reasonably draw more of a nearby population cell than a small one, and
treating all stores as equally attractive is a real modeling limitation
carried into the sensitivity and limitations sections, not hidden.
"""

from __future__ import annotations

import numpy as np


def huff_probabilities(distances: np.ndarray, attractiveness: np.ndarray, beta: float) -> np.ndarray:
    """
    distances: (n_population_cells, n_stores) matrix, meters, must be > 0.
    attractiveness: (n_stores,) vector.
    beta: distance decay exponent, larger means distance matters more.
    Returns: (n_population_cells, n_stores) matrix of choice probabilities,
    each row summing to 1.
    """
    utility = attractiveness[np.newaxis, :] / np.power(distances, beta)
    row_sums = utility.sum(axis=1, keepdims=True)
    return utility / row_sums


def store_captured_demand(probabilities: np.ndarray, population: np.ndarray) -> np.ndarray:
    """population weighted demand captured by each store, shape (n_stores,)"""
    return population @ probabilities


def pairwise_overlap(probabilities: np.ndarray, population: np.ndarray, i: int, j: int,
                      relevant_mask: np.ndarray | None = None) -> float:
    """
    Population weighted overlap between store i and store j's trade areas:
    for every population cell, the demand that could plausibly have gone to
    either store, min(P_i, P_j) times the cell's population, summed.

    relevant_mask restricts the sum to population cells where i or j is a
    genuinely plausible nearby choice for that cell, for example being
    among its nearest few stores. Without this restriction, summing min(P_i,
    P_j) across every population cell in the whole city picks up a large
    amount of near identical, near zero probability mass from cells that
    are nowhere near either store and have many closer alternatives, which
    inflates every pair's overlap toward the low single percent tail every
    other pair also shares rather than measuring genuine local competition.
    This was found and fixed during development, see PROGRESS.md.
    """
    shared_share = np.minimum(probabilities[:, i], probabilities[:, j])
    if relevant_mask is not None:
        shared_share = shared_share * relevant_mask
    return float((shared_share * population).sum())


def relevant_population_mask(distances: np.ndarray, i: int, j: int, top_k: int = 3) -> np.ndarray:
    """
    True for population cells where store i or store j is among the top_k
    nearest stores to that cell, meaning a real, physically plausible
    alternative for that population rather than a distant, unlikely one.
    """
    ranks = np.argsort(distances, axis=1)[:, :top_k]
    in_top_k = (ranks == i).any(axis=1) | (ranks == j).any(axis=1)
    return in_top_k
