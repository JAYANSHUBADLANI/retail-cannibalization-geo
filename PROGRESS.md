# Progress log

Chose Chicago Starbucks locations over a network shortest path style
analysis, since that is already the site selection project. This one asks
what happens once several locations already exist near each other, so I
needed a chain dense enough in one city that locations plausibly compete.
Starbucks in Chicago via OpenStreetMap, brand tag, fits that.

Real data sourcing, in order attempted:

Store locations: OpenStreetMap through osmnx, brand=Starbucks, Chicago.
Worked immediately, keyless, 136 raw points, 114 after dropping non point
geometries during cleanup (a few tagged features were buildings or areas,
not point nodes).

Population: planned to use the Census Bureau's ACS 5 year data through
their regular data API. Every single endpoint under api.census.gov now
returns a "Missing Key" HTML page instead of JSON, including the older
2020 decennial redistricting endpoint I tried as a fallback, which I did
not expect since that one has historically been more open. Getting a key
means registering an account, which I am treating the same as any other
credential I should not be adding for a portfolio project. Confirmed the
gate applies to the whole api.census.gov data API, not just the ACS
product, before looking for an alternative rather than assuming.

Tried and rejected: hand parsing the Census Bureau's PL 94-171
redistricting bulk file directly, confirmed downloadable without a key at
64.7 MB for Illinois. Technically possible but the fixed width format has
several joined segment files and I do not have the exact byte layout
memorized reliably enough to trust a hand rolled parser not to silently
produce wrong population numbers, which would be a worse outcome than
spending more time finding a cleaner source. Also tried the `uszipcode`
package for offline bundled zip level population, which failed on an
incompatibility between its pinned sqlalchemy_mate dependency and the
installed SQLAlchemy version, unrelated to data availability.

Settled on LEHD LODES, residence area characteristics, field C000, total
jobs held by people living in each census tract. This is a Census Bureau
product distributed as flat files outside the api.census.gov gate, fetched
through pygris's get_lodes, no key needed, worked on the first real
attempt, 3263 Illinois tracts. It is not literally population: it excludes
children, retirees, and anyone not currently employed, so it undercounts
the true population, especially in tracts with an older or younger than
average age profile. Recorded as a limitation in README.md rather than
presented as equivalent to population.

Joined LODES to TIGER cartographic boundary tracts on GEOID, then clipped
to the Chicago city boundary using osmnx's own geocoded boundary polygon:
860 of the county's 1331 tracts fall inside the city, capturing about
1.22 million in the population proxy, which is a plausible fraction of
Chicago's actual population of roughly 2.7 million given the proxy only
counts employed residents.

First full run of the Huff model plus overlap calculation gave overlap
percentages around 95 to 97 percent of the smaller store's demand for
essentially every close pair, at every beta tried. That is not plausible:
it would mean two nearby Starbucks locations capture almost identical
customers, which does not match how trade areas actually behave even for
very close competitors. Traced it to summing the shared probability,
minimum of P_i and P_j, across all 860 tracts in the city, including
tracts on the far side of Chicago from both stores. With 114 stores all
given equal attractiveness, a population cell far from both store i and
store j still gets some nonzero, near identical, near zero probability
assigned to both of them by the softmax like Huff formula, and summing
that tiny shared sliver over hundreds of irrelevant tracts adds up to a
large number that has nothing to do with real local competition between
that specific pair.

Fixed by restricting the overlap sum to population cells where store i or
store j is actually among that cell's three nearest stores, meaning a
physically plausible option for that population rather than a distant,
unlikely one. After that fix, overlap for the 110 close pairs at the
baseline beta of 2.0 averages 6.6 percent of the smaller store's demand,
a result that is actually consistent with how close competing locations
behave in the retail gravity model literature.

Close pair threshold: median nearest neighbor distance across all 114
stores, 440 meters. Every one of the 110 pairs under that threshold also
falls within 1.6 kilometers, the distance a commonly cited flat planning
assumption of 20 percent cannibalisation would apply to, so the comparison
against the flat assumption covers the full set of computed pairs, not a
subset.

Swept beta from 1.0 to 3.0. Mean overlap moves from 3.0 percent to 8.9
percent across that range, real movement but nowhere close to closing the
gap with the flat assumption's 20 percent at any value in the plausible
range from the literature.

Wrote a pytest suite: the Huff formula's core properties, closer stores
and higher attractiveness getting higher probability, higher beta
sharpening the closer store's advantage, the overlap calculation's
behavior at the extremes, the relevant population mask actually excluding
distant cells, the close pair threshold and distance matrix helper
functions, and integrity checks on the two saved data files. 15 of 15
pass. Did not write network dependent tests that re-fetch from OpenStreetMap
or LODES on every run, both because that would make the suite slow and
flaky against an external service, and because the actual fetched files
are checked directly for validity instead.

Update: got a free Census Bureau API key after all, requested directly
through their own signup form, tied to my own email, not a workaround of
the gate described above. Switched the population field from the LODES
proxy to real ACS 5 year total population (B01003_001E), kept LODES as a
second column for comparison rather than deleting that work. Real
population for the 860 tracts inside the city is 3,038,829, and the LODES
employed resident proxy was 40.3 percent of that, a bigger gap than I
expected. The headline overlap number barely moved switching population
sources, 6.6 percent to 5.9 percent at the baseline beta: makes sense in
hindsight, the overlap metric is a share of each pair's own captured
demand, so it depends much more on the relative population distribution
across nearby tracts than on the absolute scale of any one tract's count,
and LODES and ACS are correlated enough in their relative distribution
across tracts that the ratio barely shifted even though the totals differ
by 60 percent. Re-ran load_data.py, run_experiment.py, make_maps.py, and
the full test suite after the switch, 15 of 15 still pass.

Left undone: attractiveness is 1 for every store, since OpenStreetMap
carries no store size, seating count, or sales data for a like for like
comparison. A more attractive location, bigger, with a drive through,
would draw more of a shared population cell than an otherwise identical
smaller one, and treating every location as identical here is a real
simplification, not something I found a way to fix with data actually
available. Did not attempt Voronoi tessellation as an alternative to the
Huff model, since the assignment specifically motivates why a fixed radius
is the wrong tool and Huff is the standard next step; a full comparison
between Huff and weighted Voronoi was out of scope for the time available.
