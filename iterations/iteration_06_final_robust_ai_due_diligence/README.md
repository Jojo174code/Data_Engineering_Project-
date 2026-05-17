# Iteration 06, Final Robust AI Due Diligence

## Purpose

Iteration 06 is the final conservative screening pass for the 2026 Tulsa tax-auction list. It starts from the strict iteration 05 spreadsheet, re-checks development matches, adds geocoding and distance review where possible, recalculates a more conservative rule-based score, and then runs a grounded OpenAI review using only row-level evidence already present in the pipeline.

## Why this iteration was needed

Earlier iterations could still over-credit broad development language. A property could look stronger than it really was if a weak corridor or generic location phrase created a development match. Iteration 06 is designed to stop that.

## What changed

### 1. Strict development verification
- Uses the strict iteration 05 workbook as the starting point.
- Removes generic location words as matching evidence.
- Requires stronger named district, corridor, ZIP, or source-supported evidence before keeping a development match.
- Preserves warnings when an earlier development signal was too weak.

### 2. Geocoding and distance checks
- Attempts public geocoding for property addresses.
- Attempts development-area geocoding using corridor/intersection-style queries when possible.
- Downgrades location confidence when coordinates cannot be verified.
- Prevents vague city-level overlap from being treated as verified development upside.

### 3. Conservative rule-based scoring
Scoring weights:
- Bid price attractiveness: 20%
- Address quality: 15%
- Property clarity: 15%
- Verified development signal: 20%
- Surrounding value signal: 10%
- Crime/safety estimate: 5%
- Data confidence: 15%

Good ratings are intentionally hard to earn. Cheap bid price alone is not enough.

### 4. Grounded OpenAI review
- Uses only the row data produced by the pipeline.
- Does not invent ARV, rehab, rent, title status, crime stats, or condition.
- Treats development as a positive only when the final verified match remains Strong Match or Possible Match.
- Falls back safely to rule-based logic if the API fails.

## Files

### Inputs
- `input/investment_ranked_properties_strict.xlsx`
- `input/manual_review_top_candidates_strict.xlsx`
- `input/development_intelligence_source_data.csv`

### Cleaned data
- `cleaned_data/final_property_base.csv`
- `cleaned_data/final_development_intelligence.csv`
- `cleaned_data/final_property_development_matches.csv`
- `cleaned_data/final_geocoding_results.csv`
- `cleaned_data/final_rule_based_scores.csv`
- `cleaned_data/final_ai_property_reviews.csv`

### Final Excel outputs
- `output_excel/final_investment_ranked_properties.xlsx`, all screened properties
- `output_excel/final_manual_review_top_candidates.xlsx`, top 50 manual-review priorities
- `output_excel/final_development_opportunity_properties.xlsx`, only final Strong/Possible development opportunities
- `output_excel/final_good_investment_candidates.xlsx`, final Good candidates or a no-clearance note
- `output_excel/final_bad_high_risk_properties.xlsx`, bad and higher-risk cases

## Output meaning

- **Good Investment**: strong enough to stand out even after conservative screening
- **Strong Manual Review Candidate**: interesting, but still needs human verification
- **Mid Investment**: some upside, but too much uncertainty remains
- **Bad Investment**: weak or risky based on currently available evidence

## Current final outcome

The final run is intentionally conservative:
- 0 final Good Investments
- 3 final development-opportunity rows
- most properties remain manual-review or mid-tier candidates rather than automatic bids

That is expected. The goal is to avoid false confidence.

## Limitations

This system does **not** verify:
- title or liens
- code violations
- zoning or land-use restrictions
- flood risk
- occupancy
- structure condition
- ARV or rehab cost
- rentability
- legal ownership status
- true parcel boundaries beyond what public geocoding can support

## Due diligence warning

This tool is a screening system only. It does not verify title, liens, code violations, zoning, flood zone, property condition, occupancy, structure quality, ARV, rehab cost, rentability, or legal ownership. Before bidding, manually verify through Tulsa County Assessor, Tulsa County Treasurer, title/lien research, code violation checks, zoning records, Google Street View, drive-by inspection, and nearby sold comps.
