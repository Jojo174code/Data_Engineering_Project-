#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ITERATION_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
LOG_DIR = ITERATION_ROOT / 'logs'
OUT_CSV = CLEANED_DIR / 'base_900_to_1000_properties.csv'
LOG_FILE = LOG_DIR / 'prepare_base_log.txt'

SOURCE_CANDIDATES = [
    Path('/home/ubuntu/OpenClaw_Context/iterations/iteration_09_900_to_1000_ai_ranked/cleaned_data/final_ranked_properties_900_to_1000.csv'),
    Path('/home/ubuntu/OpenClaw_Context/iterations/iteration_09_900_to_1000_ai_ranked/cleaned_data/ranked_properties_900_to_1000.csv'),
    Path('/home/ubuntu/OpenClaw_Context/iterations/iteration_06_final_robust_ai_due_diligence/cleaned_data/final_property_base.csv'),
    Path('/home/ubuntu/OpenClaw_Context/iterations/iteration_04_development_intelligence_ai_review/cleaned_data/cleaned_auction_properties.csv'),
]

REQUIRED_COLUMNS = [
    'parcel_id', 'owner_name', 'property_address', 'city', 'state', 'zip_code', 'bid_cost',
    'legal_description', 'property_type', 'source_page', 'raw_text', 'extraction_confidence',
    'previous_rule_based_score', 'previous_ai_score', 'previous_final_score', 'previous_category',
    'previous_recommendation', 'previous_reasoning_summary', 'previous_key_risks'
]

COLUMN_ALIASES = {
    'previous_rule_based_score': ['previous_rule_based_score', 'rule_based_score', 'rank_score', 'pre_ai_final_score'],
    'previous_ai_score': ['previous_ai_score', 'ai_review_score', 'ai_score', 'ai_area_adjusted_score'],
    'previous_final_score': ['previous_final_score', 'final_score'],
    'previous_category': ['previous_category', 'investment_category', 'rank_category', 'pre_ai_category', 'final_category'],
    'previous_recommendation': ['previous_recommendation', 'recommendation'],
    'previous_reasoning_summary': ['previous_reasoning_summary', 'reasoning_summary', 'area_ranking_reason'],
    'previous_key_risks': ['previous_key_risks', 'key_risks', 'key_rule_based_risks', 'area_key_risks'],
}


def clean_scalar(value, default='Unknown.'):
    if pd.isna(value):
        return default
    text = str(value).strip()
    if not text or text.lower() == 'nan':
        return default
    return text


def normalize_bid_cost(value):
    try:
        return round(float(value), 2)
    except Exception:
        return None


def select_source() -> tuple[Path, pd.DataFrame]:
    attempts = []
    for path in SOURCE_CANDIDATES:
        if not path.exists():
            attempts.append({'path': str(path), 'status': 'missing'})
            continue
        df = pd.read_csv(path, low_memory=False)
        if 'bid_cost' not in df.columns:
            attempts.append({'path': str(path), 'status': 'missing_bid_cost'})
            continue
        df['bid_cost'] = pd.to_numeric(df['bid_cost'], errors='coerce')
        filtered = df[df['bid_cost'].between(900, 1000, inclusive='both')].copy()
        attempts.append({'path': str(path), 'status': 'checked', 'rows_in_range': int(len(filtered))})
        if len(filtered) > 0:
            return path, filtered
    raise SystemExit(json.dumps({'error': 'No usable source file with $900-$1,000 rows found.', 'attempts': attempts}, indent=2))


def pick_value(row: pd.Series, target_col: str):
    if target_col in row.index and pd.notna(row[target_col]):
        return row[target_col]
    for alias in COLUMN_ALIASES.get(target_col, []):
        if alias in row.index and pd.notna(row[alias]):
            return row[alias]
    return 'Unknown.'


def main():
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    source_path, df = select_source()
    original_count = len(df)
    if original_count == 0:
        raise SystemExit('Filtered row count is 0. Stopping.')

    df = df.copy()
    if 'parcel_id' in df.columns:
        df['parcel_id'] = df['parcel_id'].apply(clean_scalar)
    else:
        df['parcel_id'] = 'Unknown.'
    before_dupes = len(df)
    df = df.drop_duplicates(subset=['parcel_id'], keep='first').reset_index(drop=True)
    dupes_removed = before_dupes - len(df)

    out_rows = []
    for _, row in df.iterrows():
        out = {}
        for col in REQUIRED_COLUMNS:
            out[col] = pick_value(row, col)

        out['parcel_id'] = clean_scalar(out['parcel_id'])
        out['owner_name'] = clean_scalar(out['owner_name'])
        out['property_address'] = clean_scalar(out['property_address'])
        out['city'] = clean_scalar(out['city'])
        out['state'] = clean_scalar(out['state'], default='OK')
        out['zip_code'] = clean_scalar(out['zip_code'])
        out['legal_description'] = clean_scalar(out['legal_description'])
        out['property_type'] = clean_scalar(out['property_type'])
        out['source_page'] = clean_scalar(out['source_page'])
        out['raw_text'] = clean_scalar(out['raw_text'])
        out['extraction_confidence'] = clean_scalar(out['extraction_confidence'])
        out['previous_recommendation'] = clean_scalar(out['previous_recommendation'])
        out['previous_reasoning_summary'] = clean_scalar(out['previous_reasoning_summary'])
        out['previous_key_risks'] = clean_scalar(out['previous_key_risks'])

        bid_cost = normalize_bid_cost(out['bid_cost'])
        if bid_cost is None:
            continue
        out['bid_cost'] = bid_cost

        for numeric_col in ['previous_rule_based_score', 'previous_ai_score', 'previous_final_score']:
            try:
                out[numeric_col] = round(float(out[numeric_col]), 2)
            except Exception:
                out[numeric_col] = 'Unknown.'

        out['previous_category'] = clean_scalar(out['previous_category'])
        out_rows.append(out)

    out_df = pd.DataFrame(out_rows, columns=REQUIRED_COLUMNS)
    if len(out_df) == 0:
        raise SystemExit('No rows survived normalization. Stopping.')

    out_df = out_df.sort_values(['bid_cost', 'parcel_id'], ascending=[True, True]).reset_index(drop=True)
    out_df.to_csv(OUT_CSV, index=False)

    log_lines = [
        f'source file used: {source_path}',
        f'loaded rows in range before dedupe: {original_count}',
        f'duplicate parcel IDs removed: {dupes_removed}',
        f'final base row count: {len(out_df)}',
        'sample rows:'
    ]
    for record in out_df.head(10).to_dict(orient='records'):
        log_lines.append(json.dumps(record, ensure_ascii=False))
    LOG_FILE.write_text('\n'.join(log_lines))
    print(f'base_rows={len(out_df)}')


if __name__ == '__main__':
    main()
