#!/usr/bin/env python3
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/ubuntu/OpenClaw_Context/iterations/iteration_04_development_intelligence_ai_review/cleaned_data/cleaned_auction_properties.csv')
OUT_CSV = ROOT / 'cleaned_data' / 'filtered_properties_1500_to_2000.csv'
OUT_XLSX = ROOT / 'output_excel' / 'filtered_properties_1500_to_2000.xlsx'
LOG = ROOT / 'logs' / 'filtering_log.txt'


def num(v):
    try:
        return float(str(v).replace('$','').replace(',','').strip())
    except Exception:
        return None


def residential_likelihood(row):
    ptype = str(row.get('property_type', '')).upper()
    addr = str(row.get('property_address', '')).upper()
    legal = str(row.get('legal_description', '')).upper()
    if any(x in ptype for x in ['R IMP', 'R HS IMP', 'A HS IMP']):
        return 'High'
    if any(x in ptype for x in ['C IMP', 'DUP', 'RES']):
        return 'Medium'
    if addr not in {'', 'UNKNOWN'} and any(ch.isdigit() for ch in addr):
        return 'Medium'
    if 'LT ' in legal or 'BLK' in legal:
        return 'Low'
    return 'Unknown'


def red_flags(row):
    ptype = str(row.get('property_type', '')).upper()
    raw = ' '.join([str(row.get('legal_description','')), str(row.get('raw_text',''))]).upper()
    flags = []
    if any(x in ptype for x in ['C VAC', 'VAC', 'IND', 'INDUST', 'COMM']) and 'R IMP' not in ptype and 'R HS IMP' not in ptype:
        flags.append('Non-residential or vacant-coded property type')
    if any(x in raw for x in ['JUNK', 'DUMP', 'LANDFILL']):
        flags.append('Possible unusable or nuisance context in raw text')
    if 'LANDLOCK' in raw:
        flags.append('Possible landlocked parcel')
    return '; '.join(flags) if flags else 'None observed'


def confidence(row):
    score = 0
    if str(row.get('extraction_confidence','')) == 'High':
        score += 2
    if str(row.get('parcel_id','')) not in {'', 'Unknown'}:
        score += 1
    if str(row.get('property_address','')) not in {'', 'Unknown'}:
        score += 1
    if str(row.get('legal_description','')) not in {'', 'Unknown'}:
        score += 1
    return 'High' if score >= 4 else 'Medium' if score >= 2 else 'Low'


def filter_reason(row):
    return f"Included because bid_cost {row['bid_cost']:.2f} is within 1500 to 2000 and residential_likelihood={row['residential_likelihood']}."


def main():
    df = pd.read_csv(SOURCE)
    original = len(df)
    df['bid_cost_num'] = df['bid_cost'].apply(num)
    valid_bid = df[df['bid_cost_num'].notna()].copy()
    valid_bid_count = len(valid_bid)
    ranged = valid_bid[(valid_bid['bid_cost_num'] >= 1500) & (valid_bid['bid_cost_num'] <= 2000)].copy()
    ranged_count = len(ranged)
    before_dupes = len(ranged)
    ranged = ranged.drop_duplicates(subset=['parcel_id'], keep='first').copy()
    dupes_removed = before_dupes - len(ranged)

    ranged['residential_likelihood'] = ranged.apply(residential_likelihood, axis=1)
    ranged['obvious_red_flags'] = ranged.apply(red_flags, axis=1)
    ranged['data_confidence'] = ranged.apply(confidence, axis=1)
    ranged = ranged[~ranged['property_address'].astype(str).str.contains('rank parcel_id', case=False, na=False)].copy()
    ranged = ranged[ranged['residential_likelihood'].isin(['High', 'Medium']) | ((ranged['residential_likelihood'] == 'Unknown') & ranged['property_address'].astype(str).str.contains(r'\d', na=False))].copy()
    ranged['filter_reason'] = ranged.apply(filter_reason, axis=1)
    ranged['bid_cost'] = ranged['bid_cost_num'].round(2)
    ranged = ranged.drop(columns=['bid_cost_num'])

    if ranged.empty:
        raise SystemExit('No properties remained after filtering')

    ranged.to_csv(OUT_CSV, index=False)
    ranged.to_excel(OUT_XLSX, index=False)

    log_lines = [
        f'source file used: {SOURCE}',
        f'original row count: {original}',
        f'valid bid-cost row count: {valid_bid_count}',
        f'rows between $1,500 and $2,000: {ranged_count}',
        f'duplicates removed: {dupes_removed}',
        f'final filtered row count: {len(ranged)}',
        '',
        'first 10 filtered rows:'
    ]
    for row in ranged.head(10).to_dict(orient='records'):
        log_lines.append(json.dumps(row, ensure_ascii=False))
    LOG.write_text('\n'.join(log_lines))
    print(f'filtered_rows={len(ranged)}')


if __name__ == '__main__':
    main()
