# How much do two stores actually steal from each other

A Huff gravity model trade area and cannibalisation analysis for real
Starbucks locations in Chicago, replacing a flat, fixed cannibalisation
percentage with a computed, distance and density dependent overlap.

## Headline result

Across 110 close pairs of stores, the computed population weighted trade
area overlap averages 5.9 percent of the smaller store's demand at the
baseline distance decay parameter, ranging from 2.6 to 8.2 percent across
a plausible sensitivity range for that parameter. A commonly cited flat
planning assumption of 20 percent for any pair within 1.6 kilometers
overstates the computed answer by roughly two and a half to eight times
depending on the distance decay assumption. Two nearby Starbucks locations
do compete for some of the same customers, but nowhere near as much as a
flat rule of thumb assumes.

## Data

**114 real Starbucks locations in Chicago**, from OpenStreetMap via the
Overpass API through `osmnx`, brand tag "Starbucks". 136 features were
returned by the query and 114 remained after dropping a handful tagged as
building or area geometries rather than point locations. See
`src/load_data.py`.

**Real ACS 5 year population for 860 census tracts inside the Chicago city
boundary**, out of 1331 tracts covering all of Cook County, field
B01003_001E, total population 3,038,829. The Census Bureau's regular data
API now requires a registered key on every endpoint, discovered while
first building this, see `PROGRESS.md`. A free key was requested directly
from the Census Bureau's own signup form once that was found, and the
pipeline now uses real population rather than a proxy. LEHD LODES,
residence area characteristics, field C000, the count of jobs held by
people living in each tract, is kept as a second column for comparison
since the project was originally built around it: it captures 1,223,153,
only 40.3 percent of the real population, a bigger gap than expected since
it excludes children, retirees, and anyone not currently employed.
Switching the headline overlap calculation from the LODES proxy to real
population moved the baseline result from 6.6 to 5.9 percent, a small
change, because the overlap metric is a share of each pair's own captured
demand and depends much more on the relative population distribution
across nearby tracts than on the absolute scale of any single tract's
count.

Tract boundaries: TIGER/Line cartographic boundary shapefiles via
`pygris`, also keyless, joined to the LODES proxy on GEOID.

## Method

**Huff gravity model, not a fixed radius.** A fixed radius treats every
location as drawing from an identical, symmetric catchment regardless of
how close its neighbors are, which builds in the answer a cannibalisation
analysis is supposed to be testing. The Huff model instead assigns each
population tract a probability of choosing each store based on relative
distance and attractiveness, so competitive overlap between nearby stores
falls out of the model rather than being assumed. Since every location
here is the same brand and OpenStreetMap carries no store size or sales
data, attractiveness is set to 1 for every store, a real simplification
recorded in the limitations section below.

**Close pairs, threshold justified from the data.** For every store, its
distance to its single nearest other store was computed, and the median of
those 114 nearest neighbor distances, 440 meters, is the threshold: pairs
closer than that are unusually close relative to the typical spacing in
this dataset, not a round number chosen to produce a nice looking count.
110 pairs fall under that threshold, and all 110 also fall within 1.6
kilometers, the distance the flat assumption below applies to.

**Overlap.** For each close pair, population weighted overlap is the sum
across relevant tracts of each tract's population times the smaller of the
two stores' Huff probabilities for that tract, restricted to tracts where
at least one of the two stores is among that tract's three nearest
options. That restriction was added after an early version, summing
across every tract in the city regardless of relevance, produced overlap
estimates around 95 percent for nearly every pair, which is not plausible
and is explained in full in `PROGRESS.md`.

**Flat assumption for comparison.** A commonly cited retail planning rule
of thumb: any two same brand locations within one mile, 1.6 kilometers,
are assumed to cannibalise a flat 20 percent of each other's demand,
regardless of exactly how close they are within that radius or how dense
the surrounding population is.

**Sensitivity.** The Huff model's distance decay parameter, beta, is a
real judgement call. Swept across 1.0, 1.5, 2.0, 2.5, and 3.0, a plausible
range from the retail gravity model literature, with 2.0, the classic
inverse square specification, as the baseline.

## Results

| Beta | Mean overlap, pct of smaller store's demand | Median |
|---|---|---|
| 1.0 | 2.6% | 1.5% |
| 1.5 | 4.3% | 2.1% |
| 2.0 (baseline) | 5.9% | 2.7% |
| 2.5 | 7.2% | 3.2% |
| 3.0 | 8.2% | 3.6% |

The flat assumption of 20 percent overstates every value in this table,
by a factor of about 2.4x at the high end of the sensitivity range tried
and about 7.7x at the low end. The mean sits noticeably above the median
at every beta, meaning a small number of unusually close or unusually
population dense pairs pull the average up: reporting only the mean, or
only one example pair, would hide that the overlap distribution has a
long right tail rather than being a single representative number, which
is exactly what the flat assumption's single percentage cannot represent
and the whole reason to report the full distribution instead of one pair.

See `figures/highest_overlap_cluster_map.png` for the single highest
overlap pair, showing which tracts each store wins and how the two
stores' combined pull concentrates near the boundary between them, and
`figures/citywide_pull_map.png` for how concentrated the top store's pull
is across every tract in the city, including Chicago's real, disconnected
O'Hare Airport annex in the northwest, which the city boundary and tract
clipping correctly reproduce.

## Sharpest ways this could be wrong

Attractiveness is 1 for every store. A larger location, one with more
seating or a drive through, would plausibly draw more of a shared nearby
population than an otherwise identical smaller one, and OpenStreetMap
carries no field that would let this analysis tell those apart. Every
overlap number here assumes all 114 locations are equally attractive,
which is very unlikely to be literally true.

Population is now the real ACS 5 year estimate, but an estimate still
carries a margin of error the point figure alone does not show, and the
city boundary clip is done by intersecting Cook County tract polygons
with OpenStreetMap's own boundary for Chicago rather than an authoritative
municipal source, so a tract that straddles the true city line has its
full population counted or excluded depending on which side of that
intersection its larger share falls on, not split proportionally.

The relevant population mask, restricting overlap to tracts where a store
is among the three nearest, was chosen to fix a specific, demonstrated
problem, overlap inflated by summing across irrelevant distant tracts, not
tuned against a ground truth overlap number, because no ground truth
cannibalisation figure exists for real comparison. A different top_k
choice would move the exact overlap percentages, though probably not
enough to close a two to seven times gap with the flat assumption.

The close pair threshold, close pair count, and sensitivity range are all
choices made once and reported, not swept against each other in
combination, so an interaction between an unusual threshold choice and an
unusual beta choice was not separately checked.

## Reproducing this

Needs a free Census Bureau API key in a `.env` file at the project root,
`CENSUS_API_KEY=your_key_here`, requested at
https://api.census.gov/data/key_signup.html, tied to your own email, not
shared or checked in anywhere.

```
cd retail-cannibalization-geo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd src
python3 load_data.py
python3 run_experiment.py
python3 make_maps.py
cd ..
python3 -m pytest tests/ -v
```

`load_data.py` makes live requests to OpenStreetMap, the Census Bureau's
ACS API, and the LODES file server; the rest of the pipeline runs entirely
from the files it saves to `data/` and does not need the network again.

## Test suite

15 of 15 tests pass, covering the Huff formula's core properties, the
overlap calculation's behavior including the relevant population
restriction, the close pair threshold and distance matrix helper
functions, and integrity checks on the two saved data files.
