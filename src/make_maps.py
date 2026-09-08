"""
A map for the single highest overlap pair of stores and their surrounding
cluster: a scatter of points on a basemap is not an analysis, so this maps
the actual Huff model output, which tract each nearby store wins and how
concentrated the combined pull of the two overlapping stores is, not just
where the stores are.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np

from huff_model import huff_probabilities, relevant_population_mask
from run_experiment import BASELINE_BETA, build_distance_matrix, load_inputs, store_distance_matrix

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"
FIG_DIR = ROOT / "figures"


def main() -> None:
    FIG_DIR.mkdir(exist_ok=True)
    with open(RESULTS_DIR / "overlap_results.json") as f:
        results = json.load(f)

    top_pair = max(results["baseline_overlaps"], key=lambda o: o["overlap_population"])
    i, j = top_pair["store_i"], top_pair["store_j"]
    print(f"mapping highest overlap pair: store {i} and store {j}, "
          f"overlap population {top_pair['overlap_population']:.0f}")

    stores, tracts = load_inputs()
    distances = build_distance_matrix(tracts, stores)
    n_stores = len(stores)
    probs = huff_probabilities(distances, np.ones(n_stores), BASELINE_BETA)
    mask = relevant_population_mask(distances, i, j, top_k=3)

    tracts = tracts.copy()
    tracts["p_i"] = probs[:, i]
    tracts["p_j"] = probs[:, j]
    tracts["combined_pull"] = probs[:, i] + probs[:, j]
    tracts["winner"] = np.where(probs[:, i] > probs[:, j], f"store_{i}", f"store_{j}")

    local = tracts[mask].copy()
    if len(local) < 5:
        # widen slightly for a legible map if the top-3 mask is very small
        store_dist = store_distance_matrix(stores)
        radius = max(2000.0, store_dist[i, j] * 4)
        local = tracts[
            (distances[:, i] < radius) | (distances[:, j] < radius)
        ].copy()

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))

    local.plot(column="combined_pull", cmap="Reds", legend=True, ax=axes[0], edgecolor="grey", linewidth=0.2)
    stores.iloc[[i, j]].plot(ax=axes[0], color="black", marker="*", markersize=200)
    axes[0].set_title(f"Combined pull of store {i} and store {j}\n(Huff probability sum, beta={BASELINE_BETA})")
    axes[0].set_axis_off()

    local.plot(column="winner", categorical=True, legend=True, ax=axes[1], edgecolor="grey", linewidth=0.2)
    stores.iloc[[i, j]].plot(ax=axes[1], color="black", marker="*", markersize=200)
    axes[1].set_title(f"Which of the two stores wins each tract\n"
                       f"overlap = {top_pair['overlap_pct_of_smaller_store']:.1%} of smaller store's demand")
    axes[1].set_axis_off()

    plt.tight_layout()
    plt.savefig(FIG_DIR / "highest_overlap_cluster_map.png", dpi=150)
    plt.close()
    print(f"map written to {FIG_DIR / 'highest_overlap_cluster_map.png'}")

    tracts["top_store_share"] = probs.max(axis=1)
    fig2, ax2 = plt.subplots(figsize=(9, 9))
    tracts.plot(column="top_store_share", cmap="viridis", legend=True, ax=ax2, edgecolor="grey", linewidth=0.1)
    stores.plot(ax=ax2, color="red", markersize=8)
    ax2.set_title(f"Each tract's most likely store's Huff share, city wide (beta={BASELINE_BETA})\n"
                  "higher means one store dominates that tract's choice, lower means a contested area")
    ax2.set_axis_off()
    plt.tight_layout()
    plt.savefig(FIG_DIR / "citywide_pull_map.png", dpi=150)
    plt.close()
    print(f"map written to {FIG_DIR / 'citywide_pull_map.png'}")


if __name__ == "__main__":
    main()
