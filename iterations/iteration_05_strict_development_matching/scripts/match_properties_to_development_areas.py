from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common_iter_utils import CLEANED_DIR, LOG_DIR, clean_text, parse_zip_list, tokenize_street_text, write_log

PROPERTIES_CSV = CLEANED_DIR / 'filtered_properties_3000_to_8000.csv'
DEV_CSV = CLEANED_DIR / 'tulsa_development_intelligence.csv'
OUT_CSV = CLEANED_DIR / 'property_development_matches.csv'
LOG_FILE = LOG_DIR / 'property_matching_log.txt'
PREV_MATCH_CSV = Path(__file__).resolve().parents[2] / 'iteration_04_development_intelligence_ai_review' / 'cleaned_data' / 'property_development_matches.csv'
WEAK_WARNING = 'Weak match removed; previous match was based on generic location wording.'


def strict_match(prop_row, dev_row):
    address_strict = tokenize_street_text(prop_row['property_address'])
    legal_strict = tokenize_street_text(prop_row['legal_description'])
    prop_tokens = address_strict | legal_strict
    address_raw = tokenize_street_text(prop_row['property_address'], remove_weak=False)
    legal_raw = tokenize_street_text(prop_row['legal_description'], remove_weak=False)

    dev_corridor_strict = tokenize_street_text(dev_row['relevant_streets']) | tokenize_street_text(dev_row['corridor'])
    dev_neighborhood_strict = tokenize_street_text(dev_row['neighborhood'])
    dev_area_strict = tokenize_street_text(dev_row['area_name']) | tokenize_street_text(dev_row['project_or_area_name'])
    dev_corridor_raw = tokenize_street_text(dev_row['relevant_streets'], remove_weak=False) | tokenize_street_text(dev_row['corridor'], remove_weak=False)
    dev_neighborhood_raw = tokenize_street_text(dev_row['neighborhood'], remove_weak=False)
    dev_area_raw = tokenize_street_text(dev_row['area_name'], remove_weak=False) | tokenize_street_text(dev_row['project_or_area_name'], remove_weak=False)

    street_overlap = sorted(address_strict & dev_corridor_strict)
    corridor_overlap = sorted(prop_tokens & dev_corridor_strict)
    neighborhood_overlap = sorted(prop_tokens & dev_neighborhood_strict)
    area_overlap = sorted(prop_tokens & dev_area_strict)
    raw_overlap = sorted((address_raw | legal_raw) & (dev_corridor_raw | dev_neighborhood_raw | dev_area_raw))
    prop_zip = parse_zip_list(prop_row['zip_code'])
    dev_zips = parse_zip_list(dev_row['relevant_zip_codes'])
    zip_overlap = sorted(prop_zip & dev_zips) if prop_zip and dev_zips else []
    weak_only = bool(raw_overlap) and not street_overlap and not corridor_overlap and not neighborhood_overlap and not area_overlap and not zip_overlap

    if street_overlap:
        return {
            'strength': 'Strong Match',
            'quality': 'High',
            'warning': '',
            'reason': f"Specific street/corridor overlap: {', '.join(street_overlap[:5])}",
            'rank': 50,
        }
    if neighborhood_overlap:
        return {
            'strength': 'Strong Match',
            'quality': 'High',
            'warning': '',
            'reason': f"Same neighborhood name evidence: {', '.join(neighborhood_overlap[:5])}",
            'rank': 45,
        }
    if zip_overlap and (corridor_overlap or neighborhood_overlap or area_overlap):
        matched = corridor_overlap or neighborhood_overlap or area_overlap
        return {
            'strength': 'Strong Match',
            'quality': 'High',
            'warning': '',
            'reason': f"ZIP plus corridor/neighborhood evidence: {', '.join(matched[:5])}; ZIP {', '.join(zip_overlap)}",
            'rank': 40,
        }
    if corridor_overlap:
        return {
            'strength': 'Possible Match',
            'quality': 'Medium',
            'warning': '',
            'reason': f"Nearby named corridor overlap: {', '.join(corridor_overlap[:5])}",
            'rank': 30,
        }
    if area_overlap:
        return {
            'strength': 'Possible Match',
            'quality': 'Medium',
            'warning': '',
            'reason': f"Partial neighborhood/project-area overlap: {', '.join(area_overlap[:5])}",
            'rank': 25,
        }
    if zip_overlap:
        return {
            'strength': 'Possible Match',
            'quality': 'Low',
            'warning': '',
            'reason': f"ZIP overlap only: {', '.join(zip_overlap)}",
            'rank': 20,
        }
    if weak_only:
        return {
            'strength': 'No Clear Match',
            'quality': 'Invalid Weak Match',
            'warning': WEAK_WARNING,
            'reason': f"Weak generic overlap only: {', '.join(raw_overlap[:5])}",
            'rank': 5,
        }
    if clean_text(prop_row['zip_code']) in {'', 'Unknown'} and clean_text(prop_row['property_address']) in {'', 'Unknown', 'ADDRESS UNKNOWN'}:
        return {
            'strength': 'Unknown',
            'quality': 'Low',
            'warning': '',
            'reason': 'Insufficient overlap data',
            'rank': 0,
        }
    return {
        'strength': 'No Clear Match',
        'quality': 'Low',
        'warning': '',
        'reason': 'No specific street, corridor, neighborhood, or ZIP overlap found',
        'rank': 10,
    }


def main():
    props = pd.read_csv(PROPERTIES_CSV)
    dev = pd.read_csv(DEV_CSV)
    prev = pd.read_csv(PREV_MATCH_CSV) if PREV_MATCH_CSV.exists() else pd.DataFrame()
    prev_map = prev.set_index('parcel_id').to_dict('index') if not prev.empty else {}

    records = []
    area_counts = {}
    removed_weak = 0

    for _, prop_row in props.iterrows():
        best_dev = None
        best_eval = {'rank': -1, 'strength': 'Unknown', 'quality': 'Low', 'warning': '', 'reason': 'Insufficient overlap data'}
        weak_hits = []
        for _, dev_row in dev.iterrows():
            evaluation = strict_match(prop_row, dev_row)
            if evaluation['quality'] == 'Invalid Weak Match':
                weak_hits.append((dev_row, evaluation))
            if evaluation['rank'] > best_eval['rank']:
                best_eval = evaluation
                best_dev = dev_row

        if best_eval['rank'] < 20 and weak_hits:
            best_dev, best_eval = weak_hits[0]

        prev_row = prev_map.get(prop_row['parcel_id'], {})
        prev_strength = clean_text(prev_row.get('development_match_strength', 'Unknown'))
        if best_eval['quality'] == 'Invalid Weak Match':
            removed_weak += 1
        if best_eval['strength'] in {'No Clear Match', 'Unknown'}:
            row = {
                'parcel_id': prop_row['parcel_id'],
                'development_match_strength': best_eval['strength'],
                'development_match_quality': best_eval['quality'],
                'development_match_warning': best_eval['warning'],
                'matched_development_area': 'Unknown',
                'matched_project_or_area_name': 'Unknown',
                'matched_project_type': 'Unknown',
                'matched_investment_signal_strength': 'Unknown',
                'development_source_url': 'Unknown',
                'development_source_title': 'Unknown',
                'development_summary': 'Unknown',
                'development_match_reason': best_eval['reason'],
                'development_confidence': 'Low' if best_eval['strength'] == 'Unknown' else 'Medium',
                'previous_development_match_strength': prev_strength or 'Unknown',
            }
        else:
            row = {
                'parcel_id': prop_row['parcel_id'],
                'development_match_strength': best_eval['strength'],
                'development_match_quality': best_eval['quality'],
                'development_match_warning': best_eval['warning'],
                'matched_development_area': best_dev['area_name'],
                'matched_project_or_area_name': best_dev['project_or_area_name'],
                'matched_project_type': best_dev['project_type'],
                'matched_investment_signal_strength': best_dev['investment_signal_strength'],
                'development_source_url': best_dev['source_url'],
                'development_source_title': best_dev['source_title'],
                'development_summary': best_dev['summary'],
                'development_match_reason': best_eval['reason'],
                'development_confidence': best_dev['confidence_level'],
                'previous_development_match_strength': prev_strength or 'Unknown',
            }
            area_counts[row['matched_development_area']] = area_counts.get(row['matched_development_area'], 0) + 1
        records.append(row)

    out_df = pd.DataFrame(records)
    out_df.to_csv(OUT_CSV, index=False)

    log_lines = [
        f'total filtered properties: {len(props)}',
        f'previous Strong Match count: {int((prev.get("development_match_strength", pd.Series(dtype=str)) == "Strong Match").sum()) if not prev.empty else 0}',
        f'corrected Strong Match count: {int((out_df["development_match_strength"] == "Strong Match").sum())}',
        f'properties with Possible Match: {int((out_df["development_match_strength"] == "Possible Match").sum())}',
        f'properties with No Clear Match: {int((out_df["development_match_strength"] == "No Clear Match").sum())}',
        f'properties with Unknown: {int((out_df["development_match_strength"] == "Unknown").sum())}',
        f'removed weak development matches: {removed_weak}',
        'top matched development areas:',
    ]
    log_lines.extend(f'{area}: {count}' for area, count in sorted(area_counts.items(), key=lambda x: (-x[1], x[0]))[:10])
    for line in log_lines:
        print(line)
    write_log(LOG_FILE, log_lines)


if __name__ == '__main__':
    main()
