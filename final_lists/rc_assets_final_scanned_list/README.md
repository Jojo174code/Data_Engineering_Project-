# Final RC Assets scanned bid list

This folder contains the final RC Assets auction workbook pipeline for the file `rc_assets_final_bid_list_original.xlsx`.

## What it does

- Backs up the original workbook into `input/`
- Removes only rows that are both red and clearly crossed out / strikethrough
- Preserves the original columns, including Color, grade/final-decision context, Max Bid, and Notes
- Produces cleaned CSV outputs, scanner CSV outputs, and a final multi-sheet workbook

## Cleaning rule

Rows are removed only when both conditions are true:

1. The row has a red indicator, typically the `Color` column saying `Red`
2. The row is crossed out, strikethrough, or clearly marked removed

Red rows without a crossed-out indicator stay in the active list.
Non-red rows stay in the active list.

## Sorting

The main workbook sheet is sorted by auction-list order, using the best available source-order column.
A second sheet sorts the same active list by cheapest opening bid first.

## Crime scanner

The crime scanner adds conservative public-source safety context.
It does not invent exact address-level crime statistics.
If only neighborhood or corridor context is available, the granularity and confidence are marked accordingly.

## Economic scanner

The economic scanner looks for conservative development and investment context using named corridors or district clues.
It rejects weak generic Tulsa-only matches.

## AI scanner

The AI scanner adds a grounded screening layer using only:

- spreadsheet fields already present
- color / grade context
- opening bid / max bid
- crime scan result
- economic scan result

If AI output is weak or fails validation, the script falls back to a rule-based summary.

## Workbook sheets

- `Final List - Auction Order`: main active list in auction order
- `Final List - Cheapest First`: same list sorted by opening bid ascending
- `Top Candidates`: Top Candidate / Strong Candidate / Priority 1 / Priority 2 rows
- `Removed Red Crossed Out`: rows removed by the cleaning rule
- `Crime Scan`: crime scanner output
- `Economic Scan`: economic scanner output
- `Summary`: counts and totals

## Limitations

- Public data coverage may be neighborhood-level rather than address-level
- Economic matching is conservative and may leave many rows as unknown
- This is a screening tool, not a title, condition, or legal review

## Manual due diligence warning

Always verify title, liens, legal description, occupancy, property condition, zoning, auction terms, and final bid discipline before bidding.
