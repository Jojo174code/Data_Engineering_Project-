from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common_iter_utils import ALLOWED_MATCH_STRENGTH, CLEANED_DIR, LOG_DIR, clean_text, parse_zip_list, tokenize_street_text, write_log

PROPERTIES_CSV = CLEANED_DIR / 'filtered_properties_3000_to_8000.csv'
DEV_CSV = CLEANED_DIR / 'tulsa_development_intelligence.csv'
OUT_CSV = CLEANED_DIR / 'property_development_matches.csv'
LOG_FILE = LOG_DIR / 'property_matching_log.txt'


def score_match(prop_row, dev_row):
    address_tokens = tokenize_street_text(prop_row['property_address'])
    legal_tokens = tokenize_street_text(prop_row['legal_description'])
    corridor_tokens = tokenize_street_text(dev_row['corridor']) | tokenize_street_text(dev_row['relevant_streets']) | tokenize_street_text(dev_row['area_name']) | tokenize_street_text(dev_row['neighborhood']) | tokenize_street_text(dev_row['project_or_area_name'])
    street_overlap = sorted((address_tokens | legal_tokens) & corridor_tokens)
    prop_zip = parse_zip_list(prop_row['zip_code'])
    dev_zips = parse_zip_list(dev_row['relevant_zip_codes'])
    zip_overlap = sorted(prop_zip & dev_zips) if prop_zip and dev_zips else []

    if street_overlap:
        return 'Strong Match', f"Street/corridor token overlap: {', '.join(street_overlap[:5])}", 3
    if zip_overlap:
        return 'Possible Match', f"ZIP overlap: {', '.join(zip_overlap)}", 2
    if clean_text(prop_row['zip_code']) in {'', 'Unknown'} and clean_text(prop_row['property_address']) in {'', 'Unknown', 'ADDRESS UNKNOWN'}:
        return 'Unknown', 'Insufficient overlap data', 0
    return 'No Clear Match', 'No street, corridor, neighborhood, or ZIP overlap found', 1


def main():
    props = pd.read_csv(PROPERTIES_CSV)
    dev = pd.read_csv(DEV_CSV)
    records = []
    area_counts = {}

    for _, prop_row in props.iterrows():
        best = None
        best_rank = -1
        best_reason = 'Insufficient overlap data'
        best_strength = 'Unknown'
        for _, dev_row in dev.iterrows():
            strength, reason, rank = score_match(prop_row, dev_row)
            if rank > best_rank or (rank == best_rank and strength == 'Strong Match' and best_strength != 'Strong Match'):
                best_rank = rank
                best = dev_row
                best_reason = reason
                best_strength = strength
        if best is None:
            best_strength = 'Unknown'
            row = {
                'parcel_id': prop_row['parcel_id'],
                'development_match_strength': 'Unknown',
                'matched_development_area': 'Unknown',
                'matched_project_or_area_name': 'Unknown',
                'matched_project_type': 'Unknown',
                'matched_investment_signal_strength': 'Unknown',
                'development_source_url': 'Unknown',
                'development_source_title': 'Unknown',
                'development_summary': 'Unknown',
                'development_match_reason': 'No development data available',
                'development_confidence': 'Low',
            }
        else:
            row = {
                'parcel_id': prop_row['parcel_id'],
                'development_match_strength': best_strength,
                'matched_development_area': best['area_name'],
                'matched_project_or_area_name': best['project_or_area_name'],
                'matched_project_type': best['project_type'],
                'matched_investment_signal_strength': best['investment_signal_strength'],
                'development_source_url': best['source_url'],
                'development_source_title': best['source_title'],
                'development_summary': best['summary'],
                'development_match_reason': best_reason,
                'development_confidence': best['confidence_level'] if best_strength != 'Unknown' else 'Low',
            }
            area_counts[row['matched_development_area']] = area_counts.get(row['matched_development_area'], 0) + 1
        records.append(row)

    out_df = pd.DataFrame(records)
    out_df.to_csv(OUT_CSV, index=False)

    strong = int((out_df['development_match_strength'] == 'Strong Match').sum())
    possible = int((out_df['development_match_strength'] == 'Possible Match').sum())
    no_clear = int((out_df['development_match_strength'] == 'No Clear Match').sum())
    unknown = int((out_df['development_match_strength'] == 'Unknown').sum())
    top_areas = sorted(area_counts.items(), key=lambda x: (-x[1], x[0]))[:10]

    log_lines = [
        f'total filtered properties: {len(props)}',
        f'properties with Strong Match: {strong}',
        f'properties with Possible Match: {possible}',
        f'properties with No Clear Match: {no_clear}',
        f'properties with Unknown: {unknown}',
        'top matched development areas:',
    ]
    log_lines.extend(f'{area}: {count}' for area, count in top_areas)
    for line in log_lines:
        print(line)
    write_log(LOG_FILE, log_lines)


if __name__ == '__main__':
    main()
