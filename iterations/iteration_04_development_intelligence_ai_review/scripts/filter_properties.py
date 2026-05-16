from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common_iter_utils import CLEANED_DIR, LOG_DIR, OUTPUT_DIR, clean_text, looks_residential_address, parse_money, write_dataframe_to_excel, write_log

IN_CSV = CLEANED_DIR / 'cleaned_auction_properties.csv'
OUT_CSV = CLEANED_DIR / 'filtered_properties_3000_to_8000.csv'
OUT_XLSX = OUTPUT_DIR / 'filtered_properties_3000_to_8000.xlsx'
LOG_FILE = LOG_DIR / 'filtering_log.txt'
MIN_BID = 3000
MAX_BID = 8000
RESIDENTIAL_HINTS = {'R', 'R IMP', 'R HS', 'R HS IMP', 'R IMP HS', 'R MH', 'R MH IMP'}


def residential_likelihood(row) -> str:
    ptype = clean_text(row['property_type']).upper()
    if ptype in RESIDENTIAL_HINTS:
        return 'High'
    if looks_residential_address(row['property_address']):
        return 'Medium'
    return 'Low'


def main():
    df = pd.read_csv(IN_CSV)
    original_row_count = len(df)
    df['bid_cost'] = df['bid_cost'].apply(parse_money)
    valid_bid_df = df[df['bid_cost'].notna()].copy()
    rows_with_valid_bid = len(valid_bid_df)
    range_df = valid_bid_df[(valid_bid_df['bid_cost'] >= MIN_BID) & (valid_bid_df['bid_cost'] <= MAX_BID) & (valid_bid_df['bid_cost'] != 100)].copy()
    rows_in_range = len(range_df)

    range_df['residential_likelihood'] = range_df.apply(residential_likelihood, axis=1)
    range_df['filter_included'] = True
    range_df['duplicate_removed'] = False
    range_df['filter_reason'] = range_df.apply(
        lambda row: f"Included because bid_cost {row['bid_cost']:.2f} is within range and residential_likelihood={row['residential_likelihood']}",
        axis=1,
    )
    dup_mask = range_df.duplicated(subset=['parcel_id'], keep='first')
    duplicates_removed = int(dup_mask.sum())
    range_df.loc[dup_mask, 'duplicate_removed'] = True
    filtered_df = range_df[~dup_mask].copy().sort_values(by=['bid_cost', 'parcel_id'])

    if filtered_df.empty:
        raise ValueError('Final filtered row count is 0, stopping for debug.')

    filtered_df.to_csv(OUT_CSV, index=False)
    validation = write_dataframe_to_excel(
        filtered_df,
        OUT_XLSX,
        sheet_name='Filtered Properties',
        currency_columns={'bid_cost'},
        wrap_columns={'legal_description', 'raw_text', 'filter_reason', 'extraction_notes'}
    )

    log_lines = [
        f'original row count: {original_row_count}',
        f'rows with valid bid_cost: {rows_with_valid_bid}',
        f'rows between $3,000 and $8,000: {rows_in_range}',
        f'duplicates removed: {duplicates_removed}',
        f'final filtered row count: {len(filtered_df)}',
        'first 10 filtered rows:',
    ]
    log_lines.extend(str(row) for row in filtered_df.head(10).to_dict('records'))
    log_lines.append(f"excel validation: sheets={validation['sheet_names']} rows={validation['max_row']} cols={validation['max_column']}")

    for line in log_lines:
        print(line)
    write_log(LOG_FILE, log_lines)


if __name__ == '__main__':
    main()
