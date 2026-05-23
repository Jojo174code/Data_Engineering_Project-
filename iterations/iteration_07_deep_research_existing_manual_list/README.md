# Iteration 07 - Deep Research on Existing Manual Review List

This iteration works from the existing manual-review list PDF directly, without applying the old $3,000 to $8,000 filter.

## Input
- `input/final_manual_review_top_candidates_final.pdf`

## Outputs
- Parsed manual-review CSV
- Assessor lookup CSV with grounded fallback/manual links when parcel details are not exposed automatically
- NeighborhoodScout area-level context CSV
- OSM/Nominatim/Overpass location-intelligence CSV
- Combined research CSV
- AI deep-review CSV
- Final ranked Excel workbooks

## Notes and limitations
- The input PDF appears to reflect the same 50-row final manual-review list produced in iteration 06.
- Tulsa County Assessor search endpoints were reachable, but detailed property-card values were not reliably exposed to this automation path, so the pipeline records manual lookup links and does not hallucinate valuation fields.
- NeighborhoodScout was treated as area-level Tulsa context only unless more granular data was plainly available.
- Map/location intelligence is based on public OpenStreetMap/Nominatim/Overpass data and should be treated as preliminary screening context.
