# Tulsa 2026 Auction Analysis Pipeline

This repository contains a rebuilt screening pipeline for the **2026 Tulsa County June resale auction list**.

## What this project does

- stores the source auction PDF
- extracts auction rows into a cleaned CSV
- filters properties with bid costs between **$3,000 and $8,000**
- rebuilds Excel outputs using **pandas + openpyxl only**
- applies a transparent rule-based investment screen
- optionally applies a grounded LiteLLM AI review layer from local `.env` credentials
- validates every output by reopening the generated workbooks before commit

## Auction list analyzed

- source file: `auction_lists/2026_tulsa_auction_list.pdf`
- PDF title: **Land List for 2026 June Resale Auction**
- jurisdiction: Tulsa County, Oklahoma

## What failed in the previous run

The previous run did extract rows, but the workbook generation used a handwritten XLSX writer instead of `openpyxl`. That created fragile/corrupt Excel files that could appear blank or open in repair mode even though the underlying XML contained rows. The earlier scoring was also too generic and too pessimistic, with no strong manual-review tier.

## How the extraction was fixed

- extraction now uses `pdfplumber`
- every detected auction row is preserved even if some fields are unknown
- owner names default to `Unknown` when absent
- ZIP codes default to `Unknown` when not detected
- bid costs are normalized to numeric values where possible
- `raw_text` is preserved for manual debugging
- `extraction_confidence` is written for every row
- illegal Excel control characters are stripped before output

## Filtering rules

- minimum bid: **$3,000**
- maximum bid: **$8,000**
- exclude **$100 bids**
- exclude duplicate parcel IDs
- prefer residential-looking rows, but do not over-filter aggressively
- if property type is unknown, keep the row if the address still looks usable/residential
- keep rows with missing ZIP, owner, or property type when the parcel/address data is still usable

## Files regenerated

- `cleaned_data/cleaned_auction_properties.csv`
- `cleaned_data/ai_property_reviews.csv`
- `output_excel/filtered_properties_3000_to_8000.xlsx`
- `output_excel/investment_ranked_properties.xlsx`
- `output_excel/manual_review_top_candidates.xlsx`
- `scripts/extract_auction_properties.py`
- `scripts/filter_properties.py`
- `scripts/investment_ranker.py`
- `scripts/ai_property_reviewer.py`
- `scripts/validate_outputs.py`

## How Excel outputs are validated

Each workbook is created with `pandas.ExcelWriter(..., engine="openpyxl")` and then reopened with `openpyxl` to confirm:

- workbook opens successfully
- worksheet exists
- worksheet row count is greater than 1
- worksheet column count is greater than 1
- headers are present

This prevents the earlier false-success case where a file existed on disk but was not a trustworthy workbook.

## Rule-based scoring model

The baseline scoring is deterministic before any AI review:

- **Bid price attractiveness:** 20%
- **Address quality:** 15%
- **Property clarity:** 15%
- **Neighborhood/location signal:** 20%
- **Surrounding value signal:** 20%
- **Data confidence:** 10%

### Categories

- **Good Investment**
  - stronger bid price
  - complete parcel/address data
  - positive surrounding value or neighborhood growth signal
  - crime risk not high
  - medium or high confidence

- **Strong Manual Review Candidate**
  - promising low-to-mid bid range
  - clean parcel/address data
  - worth deeper manual research
  - not automatically a buy

- **Mid Investment**
  - mixed signals
  - not enough evidence for Good
  - not weak enough to discard immediately

- **Bad Investment**
  - high data risk, missing address/parcel data, high crime concern, high price with weak clarity, or other obvious red flags

## LiteLLM grounded AI review

The AI layer reads credentials only from local `.env` values:

- `LITELLM_API_KEY`
- `LITELLM_BASE_URL`
- `LITELLM_MODEL`

The AI reviewer is a second-pass screen only. It uses:

1. extracted auction row data
2. rule-based signals
3. known missing information
4. verified public/heuristic context already present in the row set

It is instructed to avoid generic responses and must reference concrete row fields such as bid cost, parcel ID, address quality, legal description quality, or missing ZIP/address data. If the response is too generic or invalid JSON, the script retries once and then falls back to the rule-based result.

## Why `.env` is required

LiteLLM credentials must stay local and must **never** be committed. The repository uses `.gitignore` to exclude:

- `.env`
- `.env.local`
- `*.env`

The validation step also checks that `.env` is not tracked by git.

## Due diligence warning

**This is a screening tool, not final investment advice. Before bidding, verify the property through Tulsa County Assessor records, title/lien checks, code violation checks, zoning checks, physical inspection or drive-by, Google Street View, recent nearby sales, and estimated rehab costs.**

**The AI review is a screening layer only. It does not verify title, liens, code violations, structure condition, ARV, rehab cost, rentability, zoning, or legal ownership.**
