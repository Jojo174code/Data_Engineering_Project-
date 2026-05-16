# Iteration 04 - OpenAI review with Tulsa development intelligence

## What iteration 04 does

Iteration 04 rebuilds the Tulsa 2026 auction screening pipeline in a self-contained folder and adds a development intelligence layer on top of the auction extraction, bid filtering, rule-based scoring, and OpenAI review.

## Why it was created

This iteration was created to go beyond bid-only screening. The goal is to identify not just low-cost auction properties, but also properties that may sit in or near parts of Tulsa receiving credible public or private investment attention.

## How auction extraction works

The extractor reads the PDF with `pdfplumber`, detects auction entry rows, preserves `raw_text`, keeps imperfect rows instead of silently dropping them, and labels missing values as `Unknown`.

## How the $3,000 to $8,000 filter works

The filtering step keeps properties with numeric bid costs between $3,000 and $8,000, excludes $100 bids, removes duplicate parcel IDs, and avoids over-filtering on missing owner, ZIP, or uncertain property type when address data is still usable.

## How development intelligence is gathered

The development intelligence file is built from public-facing Tulsa development and planning sources, especially PartnerTulsa and regional planning references. It captures active or still-relevant development, infrastructure, corridor, downtown, industrial, retail, and neighborhood reinvestment signals with source URLs and confidence levels.

## How properties are matched to development areas

Properties are matched transparently using available address text, ZIP overlap, corridor keywords, and neighborhood/area references. This is not presented as precise geocoding. If only ZIP overlaps, the property is marked as a possible match. If street or corridor tokens overlap clearly, it is marked as a strong match.

## How rule-based scoring works

The rule-based scorer combines:

- bid price attractiveness
- address quality
- property clarity
- development signal
- surrounding value potential
- crime/safety estimate placeholder
- data confidence

It produces four categories:

- Good Investment
- Strong Manual Review Candidate
- Mid Investment
- Bad Investment

## How OpenAI review works

The OpenAI reviewer uses the local `.env` configuration and reviews each property using only the extracted row data, rule-based signals, and matched development context. It must return structured JSON, cannot invent unsupported facts, and its reasoning must mention concrete row fields. Invalid or generic responses are normalized or rejected.

## What each Excel file means

- `filtered_properties_3000_to_8000.xlsx`: filtered working set after bid filtering
- `investment_ranked_properties.xlsx`: final combined screening output with development context and AI review
- `manual_review_top_candidates.xlsx`: the most actionable properties for manual follow-up
- `development_opportunity_properties.xlsx`: properties with strong or possible development overlap

## Limitations

This system is still a screening workflow, not a final underwriting or title workflow. Matching to development areas is text-based unless precise geocoding is added later. Public development signals may be incomplete, stale, or corridor-wide rather than parcel-specific.

## Due diligence warning

This tool is a screening system only. It does not verify title, liens, code violations, zoning, flood zone, property condition, occupancy, structure quality, ARV, rehab cost, rentability, or legal ownership. Before bidding, manually verify through Tulsa County Assessor, Tulsa County Treasurer, title/lien research, code violation checks, zoning records, Google Street View, drive-by inspection, and nearby sold comps.
