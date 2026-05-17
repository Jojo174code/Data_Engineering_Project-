from __future__ import annotations

from pathlib import Path

import pandas as pd

ITERATION_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ITERATION_ROOT / 'input'
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
LOG_DIR = ITERATION_ROOT / 'logs'

STRICT_XLSX = INPUT_DIR / 'investment_ranked_properties_strict.xlsx'
MANUAL_XLSX = INPUT_DIR / 'manual_review_top_candidates_strict.xlsx'
DEV_SOURCE_CSV = INPUT_DIR / 'development_intelligence_source_data.csv'

OUT_BASE_CSV = CLEANED_DIR / 'final_property_base.csv'
OUT_DEV_CSV = CLEANED_DIR / 'final_development_intelligence.csv'
LOG_FILE = LOG_DIR / 'prepare_base_log.txt'


def clean_text(value) -> str:
    if value is None:
        return 'Unknown'
    text = str(value).strip()
    return text if text else 'Unknown'


def write_log(lines: list[str]):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)

    strict_df = pd.read_excel(STRICT_XLSX)
    manual_df = pd.read_excel(MANUAL_XLSX)
    dev_df = pd.read_csv(DEV_SOURCE_CSV)

    if strict_df.empty:
        raise SystemExit('Strict investment workbook loaded 0 rows')

    strict_df['parcel_id'] = strict_df['parcel_id'].astype(str).str.strip()
    manual_df['parcel_id'] = manual_df['parcel_id'].astype(str).str.strip()

    manual_rank_map = {}
    if 'rank' in manual_df.columns:
        manual_rank_map = manual_df.set_index('parcel_id')['rank'].to_dict()

    base_df = strict_df.copy()
    base_df['previous_investment_category'] = base_df.get('investment_category', 'Unknown')
    base_df['previous_ai_review_score'] = base_df.get('ai_review_score', pd.NA)
    base_df['previous_development_match_strength'] = base_df.get('development_match_strength', 'Unknown')
    base_df['previous_matched_development_area'] = base_df.get('matched_development_area', 'Unknown')
    base_df['previous_development_source_url'] = base_df.get('development_source_url', 'Unknown')
    base_df['previous_reasoning_summary'] = base_df.get('reasoning_summary', 'Unknown')
    base_df['previous_development_match_quality'] = base_df.get('development_match_quality', 'Unknown')
    base_df['previous_development_match_reason'] = base_df.get('development_match_reason', 'Unknown')
    base_df['manual_review_source_rank'] = base_df['parcel_id'].map(manual_rank_map)

    for col in ['parcel_id', 'owner_name', 'property_address', 'city', 'state', 'zip_code', 'legal_description', 'property_type', 'raw_text', 'extraction_confidence']:
        if col in base_df.columns:
            base_df[col] = base_df[col].map(clean_text)

    if 'bid_cost' in base_df.columns:
        base_df['bid_cost'] = pd.to_numeric(base_df['bid_cost'], errors='coerce')

    dev_out = dev_df.copy()
    dev_out['development_geocode_query'] = dev_out['project_or_area_name'].fillna('').astype(str)
    broad_mask = dev_out['development_geocode_query'].str.strip().eq('')
    dev_out.loc[broad_mask, 'development_geocode_query'] = dev_out.loc[broad_mask, 'area_name'].fillna('').astype(str)
    dev_out['development_geocode_query'] = dev_out['development_geocode_query'].str.strip() + ', Tulsa, Oklahoma'

    base_df.to_csv(OUT_BASE_CSV, index=False)
    dev_out.to_csv(OUT_DEV_CSV, index=False)

    duplicate_parcels = int(base_df['parcel_id'].duplicated().sum())
    missing_addresses = int(base_df['property_address'].isin(['Unknown', 'ADDRESS UNKNOWN']).sum())
    missing_parcels = int(base_df['parcel_id'].isin(['Unknown', 'nan']).sum())
    missing_bids = int(base_df['bid_cost'].isna().sum())

    lines = [
        f'total strict properties loaded: {len(strict_df)}',
        f'total manual-review candidates loaded: {len(manual_df)}',
        f'duplicate parcel IDs: {duplicate_parcels}',
        f'missing addresses: {missing_addresses}',
        f'missing parcel IDs: {missing_parcels}',
        f'missing bid costs: {missing_bids}',
        f'final_property_base rows: {len(base_df)}',
        f'final_development_intelligence rows: {len(dev_out)}',
    ]
    for line in lines:
        print(line)
    write_log(lines)

    if len(base_df) == 0:
        raise SystemExit('final_property_base.csv has 0 rows')


if __name__ == '__main__':
    main()
