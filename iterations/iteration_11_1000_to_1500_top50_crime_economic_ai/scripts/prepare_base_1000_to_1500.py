#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ITERATION_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
LOG_DIR = ITERATION_ROOT / 'logs'
OUT_CSV = CLEANED_DIR / 'base_1000_to_1500_properties.csv'
LOG_FILE = LOG_DIR / 'prepare_base_log.txt'

SOURCE_CANDIDATES = [
    Path('/home/ubuntu/OpenClaw_Context/iterations/iteration_06_final_robust_ai_due_diligence/cleaned_data/final_property_base.csv'),
    Path('/home/ubuntu/OpenClaw_Context/iterations/iteration_04_development_intelligence_ai_review/cleaned_data/cleaned_auction_properties.csv'),
    Path('/home/ubuntu/OpenClaw_Context/iterations/iteration_03_openai_ai_review/cleaned_data/cleaned_auction_properties.csv'),
]

REQUIRED_COLUMNS = [
    'parcel_id', 'owner_name', 'property_address', 'city', 'state', 'zip_code', 'bid_cost',
    'legal_description', 'property_type', 'source_page', 'raw_text', 'extraction_confidence'
]


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


def property_use_flag(property_type: str, legal_description: str, address: str) -> str:
    ptype = clean_scalar(property_type).upper()
    legal = clean_scalar(legal_description).upper()
    addr = clean_scalar(address).upper()
    flags = []
    if ptype.startswith('C'):
        flags.append('Commercial-looking')
    if 'IND' in ptype or 'INDUSTR' in legal:
        flags.append('Industrial-looking')
    if addr in {'UNKNOWN.', 'UNKNOWN', 'ADDRESS UNKNOWN'}:
        flags.append('Address unclear')
    if 'VAC' in ptype or 'VACANT' in legal:
        flags.append('Possibly vacant')
    if not flags and (ptype.startswith('R') or 'HS IMP' in ptype or 'IMP' in ptype):
        flags.append('Residential/improved-looking')
    return '; '.join(flags) if flags else 'Unclear use type'


def select_source() -> tuple[Path, pd.DataFrame, list[dict]]:
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
        filtered = df[df['bid_cost'].between(1000, 1500, inclusive='both')].copy()
        attempts.append({'path': str(path), 'status': 'checked', 'rows_in_range': int(len(filtered))})
        if len(filtered) > 0:
            return path, filtered, attempts
    raise SystemExit(json.dumps({'error': 'No usable source file with $1,000-$1,500 rows found.', 'attempts': attempts}, indent=2))


def main():
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    source_path, df, attempts = select_source()
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
        out = {col: clean_scalar(row[col]) if col in row.index else 'Unknown.' for col in REQUIRED_COLUMNS}
        bid_cost = normalize_bid_cost(row['bid_cost'] if 'bid_cost' in row.index else out['bid_cost'])
        if bid_cost is None:
            continue
        out['bid_cost'] = bid_cost
        out['state'] = clean_scalar(out['state'], default='OK')
        out['property_use_flag'] = property_use_flag(out['property_type'], out['legal_description'], out['property_address'])
        out_rows.append(out)

    out_df = pd.DataFrame(out_rows, columns=REQUIRED_COLUMNS + ['property_use_flag'])
    if len(out_df) == 0:
        raise SystemExit('No rows survived normalization. Stopping.')

    out_df = out_df.sort_values(['bid_cost', 'parcel_id'], ascending=[True, True]).reset_index(drop=True)
    out_df.to_csv(OUT_CSV, index=False)

    log_lines = [
        f'source file used: {source_path}',
        f'loaded rows in range before dedupe: {original_count}',
        f'duplicate parcel IDs removed: {dupes_removed}',
        f'final base row count: {len(out_df)}',
        'source attempts:',
    ]
    log_lines.extend(json.dumps(item, ensure_ascii=False) for item in attempts)
    log_lines.append('sample rows:')
    log_lines.extend(json.dumps(record, ensure_ascii=False) for record in out_df.head(10).to_dict(orient='records'))
    LOG_FILE.write_text('\n'.join(log_lines))
    print(f'base_rows={len(out_df)}')


if __name__ == '__main__':
    main()
