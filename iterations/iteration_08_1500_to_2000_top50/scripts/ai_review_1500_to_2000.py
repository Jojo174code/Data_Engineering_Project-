#!/usr/bin/env python3
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'cleaned_data' / 'ranked_properties_1500_to_2000.csv'
OUT = ROOT / 'cleaned_data' / 'ai_reviews_1500_to_2000.csv'
LOG = ROOT / 'logs' / 'ai_review_log.txt'

ALLOWED_CATEGORIES = ['Top Candidate', 'Manual Review Candidate', 'Risky / Needs Verification', 'Avoid']
ALLOWED_RECS = ['Research First', 'Drive By', 'Watch', 'Avoid']
ALLOWED_CONF = ['High', 'Medium', 'Low']


def ai_category(rank_score):
    if rank_score >= 8.4:
        return 'Top Candidate'
    if rank_score >= 7.0:
        return 'Manual Review Candidate'
    if rank_score >= 5.2:
        return 'Risky / Needs Verification'
    return 'Avoid'


def recommendation(cat):
    return {
        'Top Candidate': 'Research First',
        'Manual Review Candidate': 'Drive By',
        'Risky / Needs Verification': 'Watch',
        'Avoid': 'Avoid',
    }[cat]


def confidence(row):
    if row['data_confidence'] == 'High' and row['residential_likelihood'] == 'High':
        return 'High'
    if row['data_confidence'] in ['High', 'Medium']:
        return 'Medium'
    return 'Low'


def main():
    df = pd.read_csv(INPUT)
    review_df = df.head(50).copy() if len(df) > 50 else df.copy()
    rows = []
    logs = []
    for _, row in review_df.iterrows():
        cat = ai_category(float(row['rank_score']))
        rec = recommendation(cat)
        conf = confidence(row)
        ai_score = round(float(row['rank_score']), 2)
        reason = f"Bid cost {row['bid_cost']:.2f}, property type {row.get('property_type','Unknown')}, address {row.get('property_address','Unknown')}, and residential likelihood {row.get('residential_likelihood','Unknown')} drive this screen."
        risks = row.get('obvious_red_flags', 'None observed')
        missing = []
        for field in ['zip_code', 'owner_name', 'property_type', 'raw_text']:
            val = str(row.get(field, 'Unknown'))
            if val in {'Unknown', '', 'nan'}:
                missing.append(field)
        next_step = 'Verify title/liens, inspect the parcel visually, and confirm assessor and map details before bidding.'
        out = {
            'parcel_id': row['parcel_id'],
            'ai_score': ai_score,
            'ai_category': cat,
            'recommendation': rec,
            'reasoning_summary': reason,
            'key_risks': risks,
            'missing_information': '; '.join(missing) if missing else 'No major missing fields in source row.',
            'next_due_diligence_step': next_step,
            'confidence_level': conf,
        }
        rows.append(out)
        logs.append(json.dumps(out, ensure_ascii=False))
    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT, index=False)
    LOG.write_text('\n'.join(logs))
    print(f'ai_reviewed_rows={len(out_df)}')


if __name__ == '__main__':
    main()
