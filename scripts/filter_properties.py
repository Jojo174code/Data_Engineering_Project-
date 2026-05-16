from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common_utils import ROOT, clean_text, looks_residential_address, parse_money, validate_workbook, write_dataframe_to_excel

IN_CSV = ROOT / 'cleaned_data' / 'cleaned_auction_properties.csv'
OUT_XLSX = ROOT / 'output_excel' / 'filtered_properties_3000_to_8000.xlsx'
MIN_BID = 3000
MAX_BID = 8000

RESIDENTIAL_HINTS = {'R', 'R IMP', 'R HS', 'R HS IMP', 'R IMP HS', 'R MH', 'R MH IMP'}


def include_reason(row) -> str:
    parts = [f"Bid ${row['bid_cost']:,.2f} within ${MIN_BID:,}-${MAX_BID:,} range"]
    if row['property_type'] in RESIDENTIAL_HINTS:
        parts.append(f"property_type={row['property_type']}")
    elif row['property_type'] == 'Unknown' and looks_residential_address(row['property_address']):
        parts.append('unknown property_type but address looks residential')
    else:
        parts.append('kept due to non-aggressive screening with usable address/parcel data')
    if row['zip_code'] == 'Unknown':
        parts.append('ZIP missing but row retained')
    return '; '.join(parts)


def main():
    df = pd.read_csv(IN_CSV)
    original_row_count = len(df)
    df['bid_cost'] = df['bid_cost'].apply(parse_money)
    valid_bid_df = df[df['bid_cost'].notna()].copy()
    rows_with_valid_bid_cost = len(valid_bid_df)

    range_df = valid_bid_df[(valid_bid_df['bid_cost'] >= MIN_BID) & (valid_bid_df['bid_cost'] <= MAX_BID) & (valid_bid_df['bid_cost'] != 100)].copy()
    rows_in_range = len(range_df)

    def keep_row(row):
        ptype = clean_text(row['property_type']).upper()
        if ptype in RESIDENTIAL_HINTS:
            return True
        if ptype in {'C', 'A'} and not looks_residential_address(row['property_address']):
            return False
        if ptype == 'UNKNOWN' and looks_residential_address(row['property_address']):
            return True
        return bool(clean_text(row['parcel_id']) and clean_text(row['property_address']))

    screened_df = range_df[range_df.apply(keep_row, axis=1)].copy()
    deduped_df = screened_df.drop_duplicates(subset=['parcel_id'], keep='first').copy()
    rows_after_duplicate_removal = len(deduped_df)

    deduped_df['filter_reason'] = deduped_df.apply(include_reason, axis=1)
    deduped_df = deduped_df.sort_values(by=['bid_cost', 'parcel_id'], ascending=[True, True])

    final_columns = [
        'parcel_id', 'owner_name', 'property_address', 'city', 'state', 'zip_code', 'legal_description',
        'bid_cost', 'property_type', 'source_page', 'extraction_confidence', 'filter_reason', 'raw_text'
    ]
    output_df = deduped_df[final_columns].copy()

    print(f'Original row count: {original_row_count}')
    print(f'Rows with valid bid cost: {rows_with_valid_bid_cost}')
    print(f'Rows in $3,000-$8,000 range: {rows_in_range}')
    print(f'Rows after duplicate removal: {rows_after_duplicate_removal}')
    print(f'Final filtered row count: {len(output_df)}')

    if output_df.empty:
        raise ValueError('Final filtered row count is zero, stopping for debug.')

    write_dataframe_to_excel(
        output_df,
        OUT_XLSX,
        sheet_name='Filtered Properties',
        currency_columns={'bid_cost'},
        wrap_columns={'legal_description', 'filter_reason', 'raw_text'}
    )
    validation = validate_workbook(OUT_XLSX, min_rows=2, min_cols=2)
    print(f"Excel validation result: sheets={validation['sheet_names']}, max_row={validation['max_row']}, max_column={validation['max_column']}")
    print('First 5 rows:')
    for row in validation['first_rows']:
        print(row)


if __name__ == '__main__':
    main()
