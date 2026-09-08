import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from run_experiment import build_distance_matrix, find_close_pairs, store_distance_matrix

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def test_stores_file_has_valid_point_geometries():
    stores = gpd.read_file(DATA_DIR / "stores.geojson")
    assert len(stores) > 50
    assert (stores.geometry.type == "Point").all()
    assert stores["store_id"].is_unique


def test_tracts_file_has_positive_population_and_valid_geometry():
    tracts = gpd.read_file(DATA_DIR / "tracts_population.geojson")
    assert len(tracts) > 100
    assert (tracts["population"] >= 0).all()
    assert tracts.geometry.is_valid.all()
    assert tracts["population"].sum() > 0


def test_load_summary_matches_actual_file_row_counts():
    with open(DATA_DIR / "load_summary.json") as f:
        summary = json.load(f)
    stores = gpd.read_file(DATA_DIR / "stores.geojson")
    tracts = gpd.read_file(DATA_DIR / "tracts_population.geojson")
    assert summary["n_stores"] == len(stores)
    assert summary["n_tracts"] == len(tracts)


def test_store_distance_matrix_is_symmetric_with_zero_diagonal():
    class FakeGeom:
        def __init__(self, x, y):
            self.x, self.y = x, y

    import pandas as pd

    class FakeGDF:
        def __init__(self, points):
            self.geometry = points

    stores = FakeGDF([FakeGeom(0, 0), FakeGeom(3, 4), FakeGeom(6, 8)])
    dist = store_distance_matrix(stores)
    assert dist.shape == (3, 3)
    np.testing.assert_allclose(np.diag(dist), 0.0)
    np.testing.assert_allclose(dist, dist.T)
    assert dist[0, 1] == pytest.approx(5.0)


def test_find_close_pairs_threshold_is_median_nearest_neighbor():
    dist = np.array([
        [0.0, 10.0, 100.0],
        [10.0, 0.0, 90.0],
        [100.0, 90.0, 0.0],
    ])
    pairs, threshold = find_close_pairs(dist)
    # nearest neighbor distances are 10, 10, 90, median is 10
    assert threshold == pytest.approx(10.0)
    assert (0, 1) in pairs
    assert (0, 2) not in pairs
    assert (1, 2) not in pairs


def test_distance_matrix_never_zero_to_avoid_division_errors():
    class FakePoint:
        def __init__(self, x, y):
            self.x, self.y = x, y

    class FakeSeries(list):
        pass

    tracts = {"centroid": FakeSeries([FakePoint(0, 0)])}
    stores_geom = FakeSeries([FakePoint(0, 0)])

    import pandas as pd
    tracts_df = pd.DataFrame({"centroid": tracts["centroid"]})

    class FakeStores:
        geometry = stores_geom

    dist = build_distance_matrix(tracts_df, FakeStores())
    assert (dist > 0).all()
