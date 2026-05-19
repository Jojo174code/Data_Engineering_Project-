# Iteration 08 - Top 50 Auction Candidates in the $1,500 to $2,000 Range

## Purpose
This iteration isolates the lower bid band between $1,500 and $2,000 and builds a separate screening list of the best 50 candidates from that range.

## Why this is separate
The earlier $3,000 to $8,000 work focused on a different pricing band and a different investment profile. Very cheap auction properties often have weaker records, higher uncertainty, and different risk characteristics, so they need a dedicated filter and ranking pass.

## Filter range
- Minimum bid: $1,500
- Maximum bid: $2,000

## How ranking works
The pipeline ranks filtered properties using bid attractiveness, address quality, parcel clarity, residential likelihood, prior location/development signal where available, data confidence, and risk penalties.

## How AI review works
The AI review stage is a grounded shortlist review that uses only row-level source data. It does not invent ARV, rents, rehab costs, crime stats, liens, or property condition.

## Excel outputs
- `filtered_properties_1500_to_2000.xlsx`: every filtered property in the target bid band
- `top_50_properties_1500_to_2000.xlsx`: the top-ranked shortlist, capped at 50 rows
- `high_risk_properties_1500_to_2000.xlsx`: weaker or riskier properties that were not preferred for the top shortlist

## Limitations
- This is still a screening pass, not final underwriting
- Missing ZIP, owner, or condition data reduces certainty
- Prior development/location signal may be unavailable for many rows
- No title, lien, zoning, flood, occupancy, or structure-condition verification is included here

## Due diligence warning
Before bidding, manually verify title, liens, taxes, code violations, zoning, access, flood exposure, actual structure condition, occupancy, and nearby comps.
