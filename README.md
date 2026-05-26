# Tulsa Auction Property Screening Repository

A working research repository for screening Tulsa-area tax auction properties with conservative data enrichment, rule-based ranking, and grounded AI-assisted review.

## What this repo is for

This project helps narrow large or messy auction property lists into smaller shortlists worth real manual due diligence.

The workflow is designed to:
- structure auction property data
- preserve parcel/address fidelity
- reuse trustworthy findings from earlier runs
- geocode properties and label confidence
- add area-level crime and economic context
- rank properties with transparent scoring logic
- generate spreadsheets for priority review, drive-bys, and watchlists

This is a screening system, not an auto-investment engine.

## What the project is doing

The repo documents an iterative process for improving auction screening quality over time.

In plain English, the goal is to answer:
- which properties are cheap **and** clear enough to identify
- which are more likely residential or improved
- which sit in less risky area context
- which deserve manual due-diligence time before the auction

If you want the short version of the project story, read:
- `PROJECT_OVERVIEW.md`

If you want the technical pipeline and AI architecture, read:
- `TECHNICAL_OVERVIEW.md`

## Current recommended starting point

If you are new to the repo, start here:
1. `PROJECT_OVERVIEW.md`
2. `TECHNICAL_OVERVIEW.md`
3. `README.md`
4. `iterations/iteration_12_custom_33_property_ranking/README.md`
5. the workbooks in `iterations/iteration_12_custom_33_property_ranking/output_excel/`

## Current iteration

| Iteration | Folder | Purpose | Status |
|---|---|---|---|
| Iteration 12 | `iterations/iteration_12_custom_33_property_ranking/` | Custom AI ranking of 33 hand-selected auction properties | Current |

## Iteration history

| Iteration | Folder | Purpose | Status |
|---|---|---|---|
| Iteration 03 | `iterations/iteration_03_openai_ai_review/` | Corrected pipeline with OpenAI review and validation | Archived baseline |
| Iteration 04 | `iterations/iteration_04_development_intelligence_ai_review/` | Corrected spreadsheet with OpenAI review and Tulsa development intelligence | Historical |
| Iteration 05 | `iterations/iteration_05_strict_development_matching/` | Strict development matching pass that removed weak generic location matches | Historical |
| Iteration 06 | `iterations/iteration_06_final_robust_ai_due_diligence/` | Conservative screening pipeline with strict development verification, geocoding checks, and AI review | Historical reference |
| Iteration 07 | `iterations/iteration_07_deep_research_existing_manual_list/` | Deep research pass on the existing manual-review shortlist | Historical reference |
| Iteration 08 | `iterations/iteration_08_1500_to_2000_top50/` | Top 50 properties in the $1,500-$2,000 bid range with AI review | Historical |
| Iteration 10 | `iterations/iteration_10_900_to_1000_top50_crime_economic_ai/` | Top 50 $900-$1,000 properties with crime and economic area intelligence baked into ranking | Historical |
| Iteration 11 | `iterations/iteration_11_1000_to_1500_top50_crime_economic_ai/` | Top 50 $1,000-$1,500 properties with crime and economic area intelligence baked into ranking | Historical |
| Iteration 12 | `iterations/iteration_12_custom_33_property_ranking/` | Custom AI ranking of 33 hand-selected auction properties | Current |

## Repository layout

- `auction_lists/`
  - source auction PDFs and source-list materials
- `iterations/`
  - self-contained research runs, each with scripts, cleaned data, logs, and output workbooks
- `PROJECT_OVERVIEW.md`
  - plain-language explanation of what the repo is doing
- `TECHNICAL_OVERVIEW.md`
  - technical explanation of the data engineering pipeline and AI integration design
- `REPO_CLEANUP_NOTES.md`
  - notes for future structural cleanup without losing research history

## How each iteration is usually structured

Most iterations follow a pattern like this:
- `input/`
- `cleaned_data/`
- `scripts/`
- `logs/`
- `output_excel/`
- `README.md`

That layout is intentional. It keeps each run reproducible and makes it easier to inspect how a shortlist was built.

## Methodology in one paragraph

Each iteration usually starts with a property list or shortlist, enriches the rows with prior findings and public geocoding, adds area-level context such as crime and economic signals when available, applies a transparent rule-based score, optionally adds grounded AI review constrained to the actual row data, and then exports ranked spreadsheets for manual next steps.

## Technical highlights

From a technical perspective, the repo is built as an iteration-based batch pipeline with:
- structured CSV intermediates at each major processing step
- cross-iteration parcel/address enrichment
- public geocoding with confidence labeling
- tract-first and ZIP-fallback area joins for economic data
- conservative crime-context attachment with explicit confidence caveats
- weighted deterministic scoring before AI is applied
- structured JSON AI outputs with validation and fallback behavior

For the full technical breakdown, see `TECHNICAL_OVERVIEW.md`.

## Important limitations

This repo does **not** prove title quality, lien status, zoning fit, flood risk, occupancy, property condition, ARV, rehab cost, rentability, legal ownership certainty, or whether a parcel is practically usable.

Area-level crime and economic data are screening signals only. They are not parcel-specific guarantees.

## Due diligence warning

This tool is a screening system only. It does not verify title, liens, code violations, zoning, flood zone, property condition, occupancy, structure quality, ARV, rehab cost, rentability, legal ownership, or whether the parcel is practically usable. Crime and economic data are area-level screening signals, not guarantees. Before bidding, manually verify through Tulsa County Assessor, Tulsa County Treasurer, title/lien research, code violation checks, zoning records, Google Street View, drive-by inspection, and nearby sold comps.

Final RC Assets bid list is on branch `Final_list` under:

`final_lists/rc_assets_final_scanned_list/`
