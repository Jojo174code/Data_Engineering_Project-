# Iteration 12 - Custom 33 Property Ranking

## Purpose

This iteration ranks only 33 hand-selected Tulsa auction properties. It does not pull a fresh price band, does not rank the full auction list, and does not introduce extra parcels outside the provided shortlist.

## What this iteration does

- starts from the exact 33-property custom list
- preserves all 33 rows through the pipeline
- merges prior iteration data by parcel ID first, then exact normalized address when needed
- reuses prior geocoding, crime, economic, and AI signals where available
- fills geocoding gaps with public no-key geocoders
- adds area-level crime and Census-based economic context
- produces a combined rule-based and AI-informed final ranking

## Technical summary

This iteration is implemented as a staged batch pipeline.
Each script writes a concrete CSV artifact so the run can be inspected, debugged, or rerun from intermediate checkpoints.

The technical design choices in this iteration include:
- locked source-list creation to prevent accidental drift beyond the 33 selected properties
- parcel-first enrichment joins with normalized-address fallback
- prior-coordinate reuse before live geocoding
- tract/ZIP geographic fallback for economic joins
- explicit confidence labeling for geocoding, crime, and economics
- weighted rule scoring before AI review
- structured AI output schema with deterministic fallback
- final validation of row counts, enums, workbook readability, and git hygiene

## Data flow

1. `prepare_custom_33.py`
   - creates the locked input CSV and base CSV
   - validates that the row count is exactly 33

2. `enrich_from_prior_iterations.py`
   - searches prior iteration outputs for parcel or exact normalized address matches
   - carries forward property, geocode, crime, economic, and AI context when available

3. `geocode_custom_33.py`
   - uses prior coordinates first
   - otherwise geocodes with Census Geocoder and Nominatim

4. `collect_area_intelligence_custom_33.py`
   - attaches Census ACS style economic context where geographies are available
   - attaches best-available area crime context from prior iterations or public city-level proxy data

5. `rank_custom_33.py`
   - applies the weighted rule-based screening model
   - after AI review exists, also calculates final score and final tier

6. `ai_review_custom_33.py`
   - reviews all 33 properties with OpenAI using only row-level data
   - expects structured JSON output
   - validates that reasoning references concrete bid, property, crime, economic, and confidence fields
   - falls back to rule-based output if the API is unavailable or returns unusable output

7. `write_custom_33_excel.py`
   - writes the ranked master workbook plus focused export workbooks

8. `validate_custom_33.py`
   - checks row counts, parcel coverage, enums, workbook readability, reasoning quality, and git hygiene

## Output workbooks

- `output_excel/custom_33_property_investment_ranking.xlsx`
  - all 33 properties ranked best to worst
- `output_excel/custom_top_10_priority_targets.xlsx`
  - the top 10 final ranked targets
- `output_excel/custom_drive_by_list.xlsx`
  - properties flagged as Bid Candidate, Research First, or Drive By
- `output_excel/custom_high_risk_watchlist.xlsx`
  - Tier 3 Watch, Tier 4 High Risk, and Avoid rows

## AI integration notes

The AI layer in this iteration is intentionally constrained.
It is not allowed to invent ARV, rehab, rent, title status, liens, property condition, or unsupported crime/economic claims.

The script passes only the row-level facts already present in the pipeline and then checks whether the model response is specific enough to be useful.
If not, the run can retry once and then fall back to a deterministic record.

## Limitations

- crime context is still screening-grade and may rely on area-level or city-level proxy data rather than parcel-level counts
- economic context is geographic-area data, not parcel-specific value proof
- geocoding confidence varies by property clarity and prior data availability
- AI review is constrained to the attached row data and does not verify external title, legal, or physical-condition facts

## Due diligence warning

This tool is a screening system only. It does not verify title, liens, code violations, zoning, flood zone, property condition, occupancy, structure quality, ARV, rehab cost, rentability, legal ownership, or whether the parcel is practically usable. Crime and economic data are area-level screening signals, not guarantees. Before bidding, manually verify through Tulsa County Assessor, Tulsa County Treasurer, title/lien research, code violation checks, zoning records, Google Street View, drive-by inspection, and nearby sold comps.
