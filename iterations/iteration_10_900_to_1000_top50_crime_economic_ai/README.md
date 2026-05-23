# Iteration 10, $900-$1,000 top 50 with crime and economic area intelligence

## Purpose

This iteration rebuilds the Tulsa-area $900-$1,000 auction screen with area intelligence baked directly into the ranking instead of treating crime and economic context as a disconnected side sheet.

The goal is to prioritize very cheap auction properties only when the property record looks usable enough and the surrounding area signals are not obviously weak.

## Why crime and economic data are baked into the ranking

At this price range, cheap alone is not enough.

A property can look attractive on bid cost while still being weak because of:
- unclear or weak location data
- non-residential or unclear property type
- high area crime risk
- weak local economic conditions
- low-confidence geocoding or area coverage

This iteration pushes those signals into both the pre-AI score and the final AI-adjusted score.

## Data sources used

### Base property source

The preferred iteration 09 source was not available in this repo during the run.

The usable fallback source was:
- `iterations/iteration_04_development_intelligence_ai_review/cleaned_data/cleaned_auction_properties.csv`

That broader auction file was filtered again for:
- `bid_cost >= 900`
- `bid_cost <= 1000`

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

The pipeline tried to keep crime context grounded and conservative.

Preferred order was:
1. official Tulsa Police / Tulsa open-data incident source if queryable
2. other already-available public source
3. NeighborhoodScout city-level crime page as a low-confidence area proxy
4. Unknown if no usable source was available

For this run, exact 0.5-mile incident counts were not reliably available from the public sources that were reachable in automation, so the pipeline used low-confidence city-level proxy context where available and left parcel-radius incident counts as `Unknown.`.

## How crime risk is calculated

This iteration does **not** pretend citywide crime pages are parcel-specific.

The crime layer stores:
- crime source
- source date label
- area-level risk notes
- low-confidence proxy score when only city-level context is available

When NeighborhoodScout is used, the crime score is derived from the page's city-level safety percentile and is explicitly marked low-confidence in the output.

## How economic strength is calculated

Economic strength is a screening score, not a market valuation.

The score uses available ACS signals such as:
- household income
- poverty rate
- unemployment rate
- vacancy rate
- owner occupancy
- median home value

Tract-level data gets higher confidence than ZIP-level data.
Missing or low-confidence area coverage reduces the score.

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
- `output_excel/top_50_properties_900_to_1000_crime_economic_ai.xlsx`
- final ranked shortlist, up to 50 rows

### Full ranked workbook
- `output_excel/full_ranked_properties_900_to_1000_crime_economic_ai.xlsx`
- all qualifying rows in the bid range with ranking fields

### High-risk workbook
- `output_excel/high_risk_removed_properties_900_to_1000.xlsx`
- risky or avoid-oriented rows, or a fallback bottom slice when fewer than 50 rows exist

## Limitations

- This run may contain fewer than 50 properties if the source range itself contains fewer than 50 rows.
- Crime context may be low-confidence and area-level only.
- Economic context is tract or ZIP level, not parcel-level proof.
- Geocoding can fail or land at approximate road-level matches for weak addresses.
- This workflow does not verify assessor detail pages, title, liens, zoning, physical condition, occupancy, flood risk, code issues, or parcel usability.

## Due diligence warning

This tool is a screening system only. It does not verify title, liens, code violations, zoning, flood zone, property condition, occupancy, structure quality, ARV, rehab cost, rentability, legal ownership, or whether the parcel is practically usable. Crime and economic data are area-level screening signals, not guarantees. Before bidding, manually verify through Tulsa County Assessor, Tulsa County Treasurer, title/lien research, code violation checks, zoning records, Google Street View, drive-by inspection, and nearby sold comps.
