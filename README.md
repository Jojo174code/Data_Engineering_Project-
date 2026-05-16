# Tulsa 2026 Auction Property Analysis

This repository stores a structured screening pass for the **2026 Tulsa County June resale auction land/property list**.

## What this project does

- Stores the original auction list PDF
- Extracts auction rows into a cleaned CSV
- Filters residential-looking properties with minimum bids between **$3,000 and $8,000**
- Produces Excel outputs for review
- Applies a cautious investment screen using available public context and clearly-labeled heuristics where exact public property-level data could not be verified cleanly

## Auction list analyzed

- Source file: `auction_lists/2026_tulsa_auction_list.pdf`
- Original report title in PDF: **Land List for 2026 June Resale Auction**
- Jurisdiction: Tulsa County, Oklahoma

## Folder structure

```text
OpenClaw_Context/
├── auction_lists/
│   └── 2026_tulsa_auction_list.pdf
├── cleaned_data/
│   └── cleaned_auction_properties.csv
├── output_excel/
│   ├── filtered_properties_3000_to_8000.xlsx
│   └── investment_ranked_properties.xlsx
├── scripts/
│   ├── extract_auction_properties.py
│   ├── filter_properties.py
│   └── investment_ranker.py
└── README.md
```

## Filtering rules used

Included only rows that met all of these:

- Minimum bid **>= $3,000**
- Minimum bid **<= $8,000**
- Excluded **$100 bids**
- Excluded rows with unreadable or missing bid values
- Excluded duplicate parcel IDs
- Excluded rows that did not look residential from the auction-list property-type field
- Rows with incomplete addresses were retained only if they still passed the extraction rules, but they are flagged with lower confidence in downstream scoring

## Generated files

### 1) `cleaned_data/cleaned_auction_properties.csv`
A cleaned intermediate extraction from the PDF with key fields such as parcel ID, legal description, address, city, property type, minimum bid, fees, and source page.

### 2) `output_excel/filtered_properties_3000_to_8000.xlsx`
Contains the filtered property list sorted by bid cost ascending.

### 3) `output_excel/investment_ranked_properties.xlsx`
Contains the filtered list with an investment screen including:

- estimated surrounding value band
- crime-risk estimate
- neighborhood investment potential estimate
- overall investment score (1 to 10)
- category: Good / Mid / Bad
- color status: Green / Yellow / Red
- explanation, risks, confidence, and recommendation

## How investment ratings were calculated

The ranking uses this weighted model:

- **Bid price attractiveness:** 20%
- **Surrounding property values / comps:** 25%
- **Crime / safety:** 20%
- **Neighborhood investment / growth potential:** 25%
- **Data confidence / property clarity:** 10%

### Rating bands

- **Good Investment (Green):** score 8 to 10
- **Mid Investment (Yellow):** score 5 to 7
- **Bad Investment (Red):** score 1 to 4

## Public data sources used

This screening used the following source types:

- Tulsa County auction PDF itself
- Tulsa citywide public crime summary context (NeighborhoodScout Tulsa crime page)
- ZIP / neighborhood-level heuristic scoring for likely crime pressure, demand, and value bands when exact parcel-level public data could not be verified reliably in an automated way

## Important limitations

- The source PDF did **not** expose owner names in the extracted table, so owner names are recorded as `Unknown` unless independently verified later.
- Exact parcel-level public comps, assessor values, or address-level crime stats were **not consistently available through clean unauthenticated public endpoints** during this automated pass.
- Some ZIP codes were missing from the extracted rows, which lowers confidence.
- Some rows marked residential in the auction list may still be vacant lots or otherwise require further verification.
- The investment ranking workbook is a **screening tool**, not a substitute for parcel-by-parcel diligence.

## Warning

**Final purchase decisions require title research, physical inspection, county assessor review, lien review, zoning review, code violation review, and legal due diligence. This analysis is only a screening tool and should not be treated as final investment advice.**
