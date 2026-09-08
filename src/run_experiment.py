"""
Main experiment driver. Builds the Huff model trade areas at a baseline
distance decay parameter, identifies close pairs of stores using a
threshold justified from the data itself, computes population weighted
overlap for every close pair, compares that against a flat assumption
retail planning teams commonly use, and sweeps the distance decay
parameter across a plausible range from the gravity model literature to
show how much the headline overlap number depends on that judgement call.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from huff_model import huff_probabilities, pairwise_overlap, relevant_population_mask, store_captured_demand

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"

BASELINE_BETA = 2.0  # classic inverse square Huff specification
BETA_SWEEP = [1.0, 1.5, 2.0, 2.5, 3.0]  # plausible range from retail gravity model literature
FLAT_ASSUMPTION_DISTANCE_KM = 1.6  # roughly one mile, a commonly cited planning rule of thumb
FLAT_ASSUMPTION_SHARE = 0.20  # a commonly cited flat cannibalisation share for that distance


def load_inputs():
    stores = gpd.read_file(DATA_DIR / "stores.geojson")
    tracts = gpd.read_file(DATA_DIR / "tracts_population.geojson")
    tracts["centroid"] = tracts.geometry.centroid
    return stores, tracts


def build_distance_matrix(tracts: gpd.GeoDataFrame, stores: gpd.GeoDataFrame) -> np.ndarray:
    pop_coords = np.array([[p.x, p.y] for p in tracts["centroid"]])
    store_coords = np.array([[p.x, p.y] for p in stores.geometry])
    diff = pop_coords[:, np.newaxis, :] - store_coords[np.newaxis, :, :]
    dist = np.sqrt((diff ** 2).sum(axis=-1))
    return np.maximum(dist, 1.0)  # avoid division by zero for a population cell exactly at a store


def store_distance_matrix(stores: gpd.GeoDataFrame) -> np.ndarray:
    coords = np.array([[p.x, p.y] for p in stores.geometry])
    diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
    return np.sqrt((diff ** 2).sum(axis=-1))


def find_close_pairs(store_dist: np.ndarray) -> tuple[list[tuple[int, int]], float]:
    n = store_dist.shape[0]
    nearest_neighbor_dist = np.array(
        [np.min(store_dist[i][np.arange(n) != i]) for i in range(n)]
    )
    threshold = float(np.median(nearest_neighbor_dist))
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            if store_dist[i, j] <= threshold:
                pairs.append((i, j))
    return pairs, threshold


def run_at_beta(distances: np.ndarray, attractiveness: np.ndarray, population: np.ndarray,
                 beta: float, close_pairs: list[tuple[int, int]]) -> dict:
    probs = huff_probabilities(distances, attractiveness, beta)
    captured = store_captured_demand(probs, population)
    overlaps = []
    for i, j in close_pairs:
        mask = relevant_population_mask(distances, i, j, top_k=3)
        raw_overlap = pairwise_overlap(probs, population, i, j, relevant_mask=mask)
        smaller_demand = min(captured[i], captured[j])
        pct_of_smaller = raw_overlap / smaller_demand if smaller_demand > 0 else 0.0
        overlaps.append({
            "store_i": i, "store_j": j,
            "overlap_population": raw_overlap,
            "store_i_captured": float(captured[i]),
            "store_j_captured": float(captured[j]),
            "overlap_pct_of_smaller_store": pct_of_smaller,
        })
    return {"beta": beta, "overlaps": overlaps, "captured_demand": captured.tolist()}


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    stores, tracts = load_inputs()
    n_stores = len(stores)
    n_tracts = len(tracts)
    print(f"stores: {n_stores}, tracts: {n_tracts}")

    distances = build_distance_matrix(tracts, stores)
    population = tracts["population"].to_numpy(dtype=float)
    attractiveness = np.ones(n_stores)

    store_dist = store_distance_matrix(stores)
    close_pairs, threshold_m = find_close_pairs(store_dist)
    print(f"close pair distance threshold: {threshold_m:.0f} meters "
          f"(median nearest neighbor distance across all stores)")
    print(f"close pairs found: {len(close_pairs)}")

    baseline_result = run_at_beta(distances, attractiveness, population, BASELINE_BETA, close_pairs)
    overlap_pcts = [o["overlap_pct_of_smaller_store"] for o in baseline_result["overlaps"]]
    mean_overlap_pct = float(np.mean(overlap_pcts)) if overlap_pcts else 0.0
    median_overlap_pct = float(np.median(overlap_pcts)) if overlap_pcts else 0.0

    print(f"\nbaseline beta={BASELINE_BETA}")
    print(f"computed overlap, mean of pct of smaller store's demand: {mean_overlap_pct:.1%}")
    print(f"computed overlap, median: {median_overlap_pct:.1%}")
    print(f"flat assumption in retail planning practice: {FLAT_ASSUMPTION_SHARE:.0%} "
          f"for any pair within {FLAT_ASSUMPTION_DISTANCE_KM} km")

    within_flat_distance = [
        o for o in baseline_result["overlaps"]
        if store_dist[o["store_i"], o["store_j"]] <= FLAT_ASSUMPTION_DISTANCE_KM * 1000
    ]
    if within_flat_distance:
        computed_for_flat_range = np.mean([o["overlap_pct_of_smaller_store"] for o in within_flat_distance])
        print(f"\nfor the {len(within_flat_distance)} pairs within {FLAT_ASSUMPTION_DISTANCE_KM} km "
              f"(where the flat rule would apply):")
        print(f"flat assumption says: {FLAT_ASSUMPTION_SHARE:.0%}")
        print(f"computed Huff overlap averages: {computed_for_flat_range:.1%}")

    sensitivity = []
    for beta in BETA_SWEEP:
        result = run_at_beta(distances, attractiveness, population, beta, close_pairs)
        pcts = [o["overlap_pct_of_smaller_store"] for o in result["overlaps"]]
        sensitivity.append({
            "beta": beta,
            "mean_overlap_pct": float(np.mean(pcts)) if pcts else 0.0,
            "median_overlap_pct": float(np.median(pcts)) if pcts else 0.0,
        })
        print(f"beta={beta}: mean overlap pct = {np.mean(pcts):.1%}" if pcts else f"beta={beta}: no pairs")

    output = {
        "n_stores": n_stores,
        "n_tracts": n_tracts,
        "close_pair_threshold_meters": threshold_m,
        "n_close_pairs": len(close_pairs),
        "baseline_beta": BASELINE_BETA,
        "baseline_overlaps": baseline_result["overlaps"],
        "baseline_mean_overlap_pct": mean_overlap_pct,
        "baseline_median_overlap_pct": median_overlap_pct,
        "flat_assumption_distance_km": FLAT_ASSUMPTION_DISTANCE_KM,
        "flat_assumption_share": FLAT_ASSUMPTION_SHARE,
        "pairs_within_flat_distance": len(within_flat_distance),
        "computed_overlap_within_flat_distance": float(computed_for_flat_range) if within_flat_distance else None,
        "sensitivity_sweep": sensitivity,
    }
    with open(RESULTS_DIR / "overlap_results.json", "w") as f:
        json.dump(output, f, indent=2)

    captured_df = pd.DataFrame({
        "store_id": stores["store_id"],
        "captured_demand": baseline_result["captured_demand"],
    })
    captured_df.to_csv(RESULTS_DIR / "captured_demand_by_store.csv", index=False)

    print(f"\ndone, results written to {RESULTS_DIR}")


if __name__ == "__main__":
    main()
