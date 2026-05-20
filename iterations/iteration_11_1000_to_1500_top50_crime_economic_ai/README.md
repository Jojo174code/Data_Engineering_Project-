# Iteration 11, $1,000-$1,500 top 50 with crime and economic area intelligence

## Purpose

This iteration rebuilds the Tulsa-area auction screen for properties with bid costs between $1,000 and $1,500.

It keeps crime, economic context, geocoding confidence, property clarity, and AI review baked directly into the ranking instead of leaving them as disconnected side research.

## Filter range

This run keeps only rows where:
- `bid_cost >= 1000`
- `bid_cost <= 1500`

## Why crime and economic data are baked into the ranking

At this price range, low bid cost alone is not enough.

A property can still be weak because of:
- unclear address or parcel data
- non-residential or unclear property type
- weak geocoding confidence
- high area crime risk
- weak local economic conditions
- low-confidence area coverage

This iteration pushes those signals into both the pre-AI score and the final AI-adjusted score.

## Data sources used

### Base property source order

Preferred source order:
1. `iterations/iteration_06_final_robust_ai_due_diligence/cleaned_data/final_property_base.csv`
2. `iterations/iteration_04_development_intelligence_ai_review/cleaned_data/cleaned_auction_properties.csv`
3. `iterations/iteration_03_openai_ai_review/cleaned_data/cleaned_auction_properties.csv`
4. `auction_lists/2026_tulsa_auction_list.pdf`

This iteration is designed to reuse cleaned CSVs first and avoid PDF re-extraction unless needed.

### Geocoding

Primary source order:
1. U.S. Census Geocoder
2. Nominatim / OpenStreetMap fallback

The pipeline attempts to capture:
- latitude / longitude
- geocode status
- geocode confidence
- matched address display name
- census tract
- block group
- confirmed ZIP code
- neighborhood or area label when available

### Economic data

Economic data uses ACS 5-year tables through the Census Reporter API, which exposes Census ACS releases without requiring a local key in the pipeline.

Preferred geography order:
1. census tract
2. ZIP / ZCTA fallback

Fields attached include:
- median household income
- poverty rate
- unemployment rate
- median home value
- median gross rent
- vacancy rate
- owner occupied rate
- population estimate
- economic source, year, and confidence

### Crime context

Preferred order:
1. official Tulsa Police / Tulsa open-data incident source if queryable
2. other already-available public source
3. NeighborhoodScout city-level crime page as a low-confidence area proxy
4. Unknown if no usable source was available

If exact 0.5-mile incident counts are not reliably available from reachable public endpoints, the pipeline keeps those counts as `Unknown.` and stores the source caveat explicitly.

## How geocoding works

Each property is geocoded conservatively.

Rules:
- no invented coordinates
- failed rows stay in the dataset
- approximate matches are labeled low confidence
- tract and block group are only attached when the geocoder actually returns them

## How crime risk is calculated

This iteration does **not** treat citywide crime pages as parcel-specific proof.

The crime layer stores:
- crime source
- source date label
- incident counts when available
- area-level notes
- confidence level
- risk score and risk category

When only NeighborhoodScout or similar city-level context is available, the pipeline marks the result as low-confidence proxy data.

## How economic strength is calculated

Economic strength is a screening score, not a market valuation.

The score uses available ACS signals such as:
- household income
- poverty rate
- unemployment rate
- vacancy rate
- owner occupancy
- median home value

Tract-level data carries stronger confidence than ZIP-level data.
Missing or low-confidence area coverage lowers the score.

## How AI uses the enriched data

The AI review consumes the crime and economic columns directly.

The prompt requires the model or fallback reviewer to reference:
- bid cost
- parcel or address
- crime risk level
- at least one economic field or an explicit statement that economic data is unknown
- confidence or data-confidence context

If the model is unavailable or returns a weak response, the pipeline falls back to a rule-based record and logs the fallback.

## Output files

### Main workbook
- `output_excel/top_50_properties_1000_to_1500_crime_economic_ai.xlsx`
- final ranked shortlist, up to 50 rows

### Full ranked workbook
- `output_excel/full_ranked_properties_1000_to_1500_crime_economic_ai.xlsx`
- all qualifying rows in the bid range with ranking fields

### High-risk workbook
- `output_excel/high_risk_removed_properties_1000_to_1500.xlsx`
- risky or avoid-oriented rows that did not survive the shortlist cut, or a fallback bottom slice when needed

## Limitations

- This run may still contain fewer than 50 properties if the source range itself contains fewer than 50 rows.
- Crime context may be low-confidence and area-level only.
- Economic context is tract or ZIP level, not parcel-level proof.
- Geocoding can fail or land at approximate road-level matches for weak addresses.
- This workflow does not verify assessor detail pages, title, liens, zoning, physical condition, occupancy, flood risk, code issues, or parcel usability.

## Due diligence warning

This tool is a screening system only. It does not verify title, liens, code violations, zoning, flood zone, property condition, occupancy, structure quality, ARV, rehab cost, rentability, legal ownership, or whether the parcel is practically usable. Crime and economic data are area-level screening signals, not guarantees. Before bidding, manually verify through Tulsa County Assessor, Tulsa County Treasurer, title/lien research, code violation checks, zoning records, Google Street View, drive-by inspection, and nearby sold comps.
