# Rice Village diorama

A one-file 3D model of Rice Village, Houston. Rice-owned blocks, tenants by use and square footage, a site plan, building pages with floor plans, and a tenant dashboard with a stacking plan.

Independent study. Not affiliated with Rice University, Rice Management Company or Rice Real Estate Company. Heights drawn 1.25x. Figures are true.

**This repository is private and must stay private.** Rice tenant areas come from Rice's rent roll and other listings come from CoStar. Do not make the repository public and do not turn on GitHub Pages.

## Open it

Open `index.html` in a browser. It needs no server and no network.

## Build

```
pip install shapely
python3 build/assemble.py
```

This reads `src/template.html`, `data/` and `vendor/three.iife.js` and writes `index.html`.

- `data/pack.json`: buildings, footprints, heights, suites and tenants.
- `data/yearbuilt.json`: year built from the county parcel record.
- `data/linkaudit.json`: tenant website and listing links, checked.
- `data/ownership.json`: the Rice property line, derived from the county roll. Owner names are not stored here.

To rebuild the property line, put the county parcel export with owner fields at `inputs/parcels_owner.json` (ignored by git) and run the build. It rewrites `data/ownership.json`.

## Test

```
pip install playwright && playwright install chromium
python3 tests/diorama_audit.py index.html phone
python3 tests/diorama_audit.py index.html land
python3 tests/diorama_audit.py index.html desk
```

The audit taps every control with real pointer events on phone, landscape phone and desktop. Run at most two screens at once. Last run, November 13, 2026: 44, 44 and 41 checks passed.

## Third party

three.js 0.170, MIT license, in `vendor/`.
