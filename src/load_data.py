"""
Fetches everything this project needs and saves it to data/ so the rest of
the pipeline never has to hit the network again.

Store locations: OpenStreetMap, via the Overpass API through osmnx, real
Starbucks locations in Chicago. Chosen because it is a chain with enough
density in one city for locations to plausibly compete, and because OSM
needs no API key or account.

Population: real ACS 5 year total population (B01003_001E) by tract, via
the Census Bureau's regular data API. That API now requires a registered
key on every endpoint, discovered while first building this, see
PROGRESS.md. The key used here is free, requested directly from the
Census Bureau, tied to the user's own email, not a workaround. LODES
residence area characteristics, total jobs held by residents, field C000,
is also fetched and kept as a second column for comparison, since the
project was originally built around that proxy before the key was
available and the gap between the two is itself an interesting number,
see PROGRESS.md.

Tract boundaries: TIGER/Line cartographic boundary shapefiles, keyless,
joined to both population fields on GEOID.
"""

from __future__ import annotations

import os
from pathlib import Path

import geopandas as gpd
import osmnx as ox
import pandas as pd
import requests
from pygris import tracts
from pygris.data import get_lodes

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PLACE = "Chicago, Illinois, USA"
BRAND = "Starbucks"
STATE = "il"
STATE_FIPS = "17"
COUNTY_FIPS = "031"  # Cook County
ACS_YEAR = 2022
LODES_YEAR = 2021
PROJECTED_CRS = "EPSG:32616"  # UTM zone 16N, meters, correct for Chicago


def load_census_api_key() -> str:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("CENSUS_API_KEY="):
                return line.split("=", 1)[1].strip()
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        raise RuntimeError("CENSUS_API_KEY not found in .env or the environment")
    return key


def fetch_stores() -> gpd.GeoDataFrame:
    gdf = ox.features_from_place(PLACE, {"brand": BRAND})
    gdf = gdf[gdf.geometry.type == "Point"].copy()
    gdf = gdf.reset_index()[["osmid", "name", "geometry"]] if "osmid" in gdf.columns else gdf.reset_index()
    gdf = gdf.set_geometry("geometry")
    gdf = gdf.to_crs(PROJECTED_CRS)
    gdf["store_id"] = range(len(gdf))
    return gdf[["store_id", "name", "geometry"]] if "name" in gdf.columns else gdf[["store_id", "geometry"]]


def fetch_acs_population(api_key: str) -> pd.DataFrame:
    url = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
    params = {
        "get": "B01003_001E",
        "for": "tract:*",
        "in": f"state:{STATE_FIPS} county:{COUNTY_FIPS}",
        "key": api_key,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    rows = resp.json()
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df["GEOID"] = df["state"] + df["county"] + df["tract"]
    df["population"] = df["B01003_001E"].astype(int)
    return df[["GEOID", "population"]]


def fetch_tracts_with_population(api_key: str) -> gpd.GeoDataFrame:
    tract_geo = tracts(state=STATE, county=COUNTY_FIPS, cb=True, year=2022)
    tract_geo = tract_geo.to_crs(PROJECTED_CRS)
    tract_geo["GEOID"] = tract_geo["GEOID"].astype(str)

    acs = fetch_acs_population(api_key)
    acs["GEOID"] = acs["GEOID"].astype(str)

    lodes = get_lodes(state=STATE, year=LODES_YEAR, lodes_type="rac", agg_level="tract", return_geometry=False)
    lodes = lodes.rename(columns={"h_geocode": "GEOID", "C000": "population_proxy_lodes"})
    lodes["GEOID"] = lodes["GEOID"].astype(str)

    merged = tract_geo.merge(acs, on="GEOID", how="inner")
    merged = merged.merge(lodes[["GEOID", "population_proxy_lodes"]], on="GEOID", how="left")
    merged["population"] = merged["population"].fillna(0)
    merged["population_proxy_lodes"] = merged["population_proxy_lodes"].fillna(0)
    merged["centroid"] = merged.geometry.centroid
    return merged


def clip_tracts_to_place(tract_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    boundary = ox.geocode_to_gdf(PLACE).to_crs(PROJECTED_CRS)
    clipped = gpd.overlay(tract_gdf, boundary[["geometry"]], how="intersection")
    return clipped


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    api_key = load_census_api_key()

    print("fetching store locations from OpenStreetMap")
    stores = fetch_stores()
    print(f"stores fetched: {len(stores)}")
    stores.to_file(DATA_DIR / "stores.geojson", driver="GeoJSON")

    print("fetching tract boundaries, real ACS population, and LODES for comparison")
    tracts_pop = fetch_tracts_with_population(api_key)
    print(f"tracts fetched (county wide): {len(tracts_pop)}")

    print("clipping tracts to the city boundary")
    clipped = clip_tracts_to_place(tracts_pop)
    print(f"tracts within city boundary: {len(clipped)}")
    total_pop = clipped["population"].sum()
    total_proxy = clipped["population_proxy_lodes"].sum()
    print(f"total real ACS population captured: {total_pop:,.0f}")
    print(f"total LODES employed resident proxy, for comparison: {total_proxy:,.0f}")
    print(f"proxy was {total_proxy / total_pop:.1%} of the real population")

    clipped_to_save = clipped.drop(columns=["centroid"])
    clipped_to_save.to_file(DATA_DIR / "tracts_population.geojson", driver="GeoJSON")

    summary = {
        "n_stores": len(stores),
        "n_tracts": len(clipped),
        "total_population": float(total_pop),
        "total_population_proxy_lodes": float(total_proxy),
        "lodes_pct_of_real_population": float(total_proxy / total_pop),
        "place": PLACE,
        "brand": BRAND,
        "acs_year": ACS_YEAR,
        "lodes_year": LODES_YEAR,
    }
    pd.Series(summary).to_json(DATA_DIR / "load_summary.json", indent=2)
    print("done, summary written to data/load_summary.json")


if __name__ == "__main__":
    main()
