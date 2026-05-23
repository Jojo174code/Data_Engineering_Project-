# Tulsa Auction Screening Project Overview

## What this repo is

This repository is a working research log and screening system for Tulsa-area tax auction properties.

The core idea is simple:
- start with raw auction property lists
- clean and structure the data
- add location, geocoding, crime, and economic context
- rank properties conservatively
- export shortlists for manual review before any bidding

It is not meant to be a black-box "buy these now" system.
It is a decision-support repo for narrowing a messy auction list into a smaller set of properties worth real human due diligence.

## What you are doing in this repo

The project is moving through iterations.
Each iteration tests a more grounded way to screen auction properties without hallucinating facts that are not actually known.

In practice, the workflow has been evolving toward this:
1. identify a source list or custom shortlist
2. preserve parcel and address fidelity
3. reuse trustworthy findings from earlier iterations when possible
4. geocode carefully and label confidence
5. add area-level economic and crime context
6. score properties with transparent rule-based logic
7. add AI review only when it stays grounded in the available data
8. export ranked workbooks for manual review, drive-bys, and watchlists

## What the repo is trying to optimize for

This repo is trying to find properties that are:
- cheap enough to matter
- clear enough to identify confidently
- likely residential or improved rather than junk land or unusable parcels
- not obviously located in the weakest area context
- worth spending manual due-diligence time on before the auction

## What the repo is explicitly not doing

This project does **not** prove:
- title is clear
- liens are acceptable
- zoning works for the intended use
- the parcel is buildable or practically usable
- the structure exists or is in good condition
- ARV, rehab cost, rent, or resale assumptions
- occupancy status
- legal ownership certainty
- code violations
- flood risk
- whether a bid is actually safe

That is why every iteration includes a due-diligence warning.

## Why there are so many iterations

The iterations are not clutter for its own sake.
They show the project maturing from broad filtering into more conservative and explainable screening.

Examples:
- earlier iterations focused on extraction and basic ranking
- later ones added stricter development matching and geocoding
- later still, area-level crime and economic context were folded directly into ranking
- iteration 12 shifted to a custom hand-selected 33-property shortlist instead of a full price-band run

## How to read this repo quickly

If you are new here, start with:
1. `README.md`
2. `PROJECT_OVERVIEW.md`
3. the latest iteration folder, currently `iterations/iteration_12_custom_33_property_ranking/`
4. that iteration's `README.md`
5. the output workbooks inside its `output_excel/` folder

## Current state

The current direction is a conservative auction screening system, not an automated buying bot.
The repo is best understood as a repeatable research pipeline that helps decide **what deserves manual attention next**.
