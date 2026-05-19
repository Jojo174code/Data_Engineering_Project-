#!/usr/bin/env python3
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'cleaned_data' / 'filtered_properties_1500_to_2000.csv'
OUT = ROOT / 'cleaned_data' / 'ranked_properties_1500_to_2000.csv'
LOG = ROOT / 'logs' / 'ranking_log.txt'
ITER6 = Path('/home/ubuntu/OpenClaw_Context/iterations/iteration_06_final_robust_ai_due_diligence/cleaned_data/final_property_base.csv')


def signal_bid(v):
    if v <= 1600:
        return 10
    if v <= 1700:
        return 8.5
    if v <= 1850:
        return 7
    return 5.5


def signal_address(addr):
    addr = str(addr)
    if addr not in {'', 'Unknown'} and any(ch.isdigit() for ch in addr):
        return 9
    if addr not in {'', 'Unknown'}:
        return 6
    return 2


def signal_clarity(row):
    score = 0
    if str(row.get('parcel_id','')) not in {'', 'Unknown'}:
        score += 4
    if str(row.get('legal_description','')) not in {'', 'Unknown'}:
        score += 3
    if str(row.get('source_page','')) not in {'', 'Unknown'}:
        score += 1
    if str(row.get('raw_text','')) not in {'', 'Unknown'}:
        score += 2
    return min(10, score)


def signal_residential(v):
    return {'High': 9, 'Medium': 6.5, 'Low': 3, 'Unknown': 4}.get(str(v), 4)


def signal_dev(parcel_id, iter6_lookup):
    row = iter6_lookup.get(parcel_id)
    if not row:
        return 4
    score = float(row.get('rule_based_score', 5)) if pd.notna(row.get('rule_based_score')) else 5
    return min(10, max(1, score))


def signal_confidence(v):
    return {'High': 9, 'Medium': 6.5, 'Low': 3}.get(str(v), 3)


def risk_penalty(row):
    flags = str(row.get('obvious_red_flags',''))
    ptype = str(row.get('property_type','')).upper()
    reasons = []
    penalty = 0
    if flags not in {'', 'None observed'}:
        penalty += 4
        reasons.append(flags)
    if any(x in ptype for x in ['C IMP', 'COMM', 'IND']) and 'R' not in ptype:
        penalty += 3
        reasons.append('Property type leans non-residential')
    if str(row.get('property_address','')) in {'', 'Unknown'}:
        penalty += 3
        reasons.append('Missing address')
    return min(10, penalty), '; '.join(reasons) if reasons else 'None significant'


def category(score):
    if score >= 8.4:
        return 'Top Candidate'
    if score >= 7.0:
        return 'Manual Review Candidate'
    if score >= 5.2:
        return 'Risky / Needs Verification'
    return 'Avoid'


def main():
    df = pd.read_csv(INPUT)
    try:
        iter6 = pd.read_csv(ITER6)
        iter6_lookup = {str(r['parcel_id']): r for _, r in iter6.iterrows()}
    except Exception:
        iter6_lookup = {}

    df['bid_price_signal'] = df['bid_cost'].apply(signal_bid)
    df['address_quality_signal'] = df['property_address'].apply(signal_address)
    df['property_clarity_signal'] = df.apply(signal_clarity, axis=1)
    df['residential_signal'] = df['residential_likelihood'].apply(signal_residential)
    df['development_or_location_signal'] = df['parcel_id'].astype(str).apply(lambda x: signal_dev(x, iter6_lookup))
    df['data_confidence_signal'] = df['data_confidence'].apply(signal_confidence)
    penalties = df.apply(risk_penalty, axis=1)
    df['risk_penalty'] = [p[0] for p in penalties]
    df['risk_penalty_reason'] = [p[1] for p in penalties]

    df['rank_score'] = (
        df['bid_price_signal'] * 0.20 +
        df['address_quality_signal'] * 0.15 +
        df['property_clarity_signal'] * 0.15 +
        df['residential_signal'] * 0.15 +
        df['development_or_location_signal'] * 0.15 +
        df['data_confidence_signal'] * 0.10 +
        (10 - df['risk_penalty']) * 0.10
    ).round(2)
    df['rank_category'] = df['rank_score'].apply(category)
    df['ranking_reason'] = df.apply(lambda r: f"Bid {r['bid_cost']}, address quality {r['address_quality_signal']}, property clarity {r['property_clarity_signal']}, residential signal {r['residential_signal']}, development/location signal {r['development_or_location_signal']}, risk penalty {r['risk_penalty']}.", axis=1)
    df['manual_review_flag'] = df['rank_category'].isin(['Top Candidate', 'Manual Review Candidate'])

    df = df.sort_values(['rank_score', 'bid_cost'], ascending=[False, True]).reset_index(drop=True)
    df.to_csv(OUT, index=False)

    log_lines = [f'ranked row count: {len(df)}', 'top 10 ranked rows:']
    for row in df.head(10).to_dict(orient='records'):
        log_lines.append(json.dumps(row, ensure_ascii=False))
    LOG.write_text('\n'.join(log_lines))
    print(f'ranked_rows={len(df)}')


if __name__ == '__main__':
    main()
