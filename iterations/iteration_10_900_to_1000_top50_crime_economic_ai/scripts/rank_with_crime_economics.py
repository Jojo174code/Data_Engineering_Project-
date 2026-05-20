#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ITERATION_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
LOG_DIR = ITERATION_ROOT / 'logs'
IN_CSV = CLEANED_DIR / 'property_area_intelligence.csv'
OUT_CSV = CLEANED_DIR / 'crime_economic_ranked_properties.csv'
LOG_FILE = LOG_DIR / 'ranking_log.txt'

ALLOWED_CATEGORIES = ['Top Candidate', 'Manual Review Candidate', 'Risky / Needs Verification', 'Avoid']


def clean_text(value, default='Unknown.'):
    if pd.isna(value):
        return default
    text = str(value).strip()
    if not text or text.lower() == 'nan':
        return default
    return text


def num(value):
    try:
        return float(value)
    except Exception:
        return None


def signal_text_confidence(value: str) -> float:
    mapping = {'High': 9.0, 'Medium': 6.5, 'Low': 3.5, 'Unknown': 2.5, 'Unknown.': 2.5}
    return mapping.get(clean_text(value), 2.5)


def property_clarity_score(row: pd.Series) -> float:
    score = 0.0
    if clean_text(row['parcel_id']) not in {'Unknown.', 'Unknown'}:
        score += 3.0
    if clean_text(row['legal_description']) not in {'Unknown.', 'Unknown'}:
        score += 2.5
    if clean_text(row['raw_text']) not in {'Unknown.', 'Unknown'}:
        score += 1.5
    if clean_text(row['property_address']) not in {'Unknown.', 'Unknown', 'ADDRESS UNKNOWN'}:
        score += 2.0
    if clean_text(row['source_page']) not in {'Unknown.', 'Unknown'}:
        score += 1.0
    score += 0.5 if clean_text(row['extraction_confidence']) == 'High' else 0.0
    return round(min(10.0, score), 2)


def geocoding_score(row: pd.Series) -> float:
    if clean_text(row['geocode_status']) == 'Failed':
        return 1.5
    return round({'High': 9.0, 'Medium': 6.5, 'Low': 4.0}.get(clean_text(row['geocode_confidence']), 3.0), 2)


def residential_likelihood_score(row: pd.Series) -> float:
    ptype = clean_text(row['property_type']).upper()
    if 'HS IMP' in ptype:
        return 9.0
    if ptype.startswith('R') and 'IMP' in ptype:
        return 8.5
    if ptype == 'R' or ptype.startswith('R '):
        return 6.5
    if ptype.startswith('C'):
        return 3.0
    return 5.0


def crime_score(row: pd.Series) -> float:
    risk = clean_text(row.get('crime_risk_level'))
    conf = clean_text(row.get('crime_confidence'))
    if risk == 'Low':
        base = 8.5
    elif risk == 'Medium':
        base = 6.0
    elif risk == 'High':
        base = 2.5
    else:
        base = 4.0
    if conf == 'Low':
        base -= 0.75
    elif conf in {'Unknown', 'Unknown.'}:
        base -= 1.0
    return round(max(1.0, min(10.0, base)), 2)


def bid_price_score(row: pd.Series) -> float:
    bid = num(row['bid_cost']) or 1000.0
    span = 1000.0 - 900.0
    score = 10.0 - ((bid - 900.0) / span) * 3.0
    return round(max(6.5, min(10.0, score)), 2)


def data_confidence_score(row: pd.Series) -> float:
    scores = [
        signal_text_confidence(row['extraction_confidence']),
        signal_text_confidence(row['geocode_confidence']),
        signal_text_confidence(row['crime_confidence']),
        signal_text_confidence(row['economic_confidence']),
    ]
    return round(sum(scores) / len(scores), 2)


def category_from_score(score: float, row: pd.Series) -> str:
    ptype = clean_text(row['property_type']).upper()
    if clean_text(row['property_address']) in {'Unknown.', 'Unknown', 'ADDRESS UNKNOWN'} and score < 5.8:
        return 'Avoid'
    if clean_text(row['crime_risk_level']) == 'High' and clean_text(row['economic_risk_level']) == 'High' and score < 6.0:
        return 'Avoid'
    if ptype.startswith('C') and score < 5.6:
        return 'Avoid'
    if score >= 7.6:
        return 'Top Candidate'
    if score >= 5.8:
        return 'Manual Review Candidate'
    if score >= 4.2:
        return 'Risky / Needs Verification'
    return 'Avoid'


def main():
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(IN_CSV)

    df['property_clarity_score'] = df.apply(property_clarity_score, axis=1)
    df['geocoding_score'] = df.apply(geocoding_score, axis=1)
    df['residential_likelihood_score'] = df.apply(residential_likelihood_score, axis=1)
    df['crime_score'] = df.apply(crime_score, axis=1)
    df['economic_strength_score'] = df['economic_strength_score'].apply(lambda v: round(float(v), 2) if str(v).replace('.', '', 1).isdigit() else v)
    df['economic_strength_score_numeric'] = df['economic_strength_score'].apply(lambda v: num(v) if num(v) is not None else 3.5)
    df['bid_price_score'] = df.apply(bid_price_score, axis=1)
    df['data_confidence_score'] = df.apply(data_confidence_score, axis=1)
    df['area_intelligence_score'] = ((df['crime_score'] + df['economic_strength_score_numeric']) / 2.0).round(2)

    df['pre_ai_final_score'] = (
        df['property_clarity_score'] * 0.20 +
        df['geocoding_score'] * 0.15 +
        df['residential_likelihood_score'] * 0.15 +
        df['crime_score'] * 0.20 +
        df['economic_strength_score_numeric'] * 0.20 +
        df['bid_price_score'] * 0.05 +
        df['data_confidence_score'] * 0.05
    ).round(2)

    df['pre_ai_category'] = df.apply(lambda row: category_from_score(float(row['pre_ai_final_score']), row), axis=1)
    df['area_ranking_reason'] = df.apply(
        lambda r: (
            f"Parcel {r['parcel_id']} at bid cost {float(r['bid_cost']):.2f} scored {r['pre_ai_final_score']} before AI because "
            f"property clarity={r['property_clarity_score']}, geocoding={r['geocoding_score']}, residential likelihood={r['residential_likelihood_score']}, "
            f"crime score={r['crime_score']} ({r['crime_risk_level']} risk, {r['crime_confidence']} confidence), economic strength={r['economic_strength_score_numeric']} "
            f"({r['economic_risk_level']} risk, {r['economic_confidence']} confidence), and data confidence={r['data_confidence_score']}."
        ),
        axis=1,
    )

    def key_risks(row: pd.Series) -> str:
        risks = []
        if clean_text(row['property_address']) in {'Unknown.', 'Unknown', 'ADDRESS UNKNOWN'}:
            risks.append('Address is missing or unclear.')
        if clean_text(row['geocode_confidence']) == 'Low' or clean_text(row['geocode_status']) == 'Failed':
            risks.append('Geocoding confidence is weak.')
        if clean_text(row['crime_risk_level']) == 'High':
            risks.append('Area-level crime proxy is high risk.')
        if clean_text(row['economic_risk_level']) == 'High':
            risks.append('Economic context is weak.')
        if clean_text(row['crime_confidence']) == 'Low':
            risks.append('Crime context is low-confidence and city-level only.')
        if clean_text(row['economic_confidence']) in {'Low', 'Unknown', 'Unknown.'}:
            risks.append('Economic coverage is weak or incomplete.')
        if clean_text(row['property_type']).upper().startswith('C'):
            risks.append('Property type appears commercial or unclear for a residential auction screen.')
        return ' '.join(risks) if risks else 'No major pre-AI risk beyond normal tax-auction due diligence.'

    df['area_key_risks'] = df.apply(key_risks, axis=1)
    df['data_confidence'] = df['data_confidence_score'].apply(lambda s: 'High' if s >= 7.5 else 'Medium' if s >= 5.0 else 'Low')

    df = df.drop(columns=['economic_strength_score_numeric'])
    df = df.sort_values(
        by=['pre_ai_category', 'pre_ai_final_score', 'crime_score', 'economic_strength_score', 'bid_cost'],
        ascending=[True, False, False, False, True],
        key=lambda series: series.map({
            'Top Candidate': 0,
            'Manual Review Candidate': 1,
            'Risky / Needs Verification': 2,
            'Avoid': 3,
        }) if series.name == 'pre_ai_category' else series,
    ).reset_index(drop=True)

    df.to_csv(OUT_CSV, index=False)
    log_lines = [f'ranked row count: {len(df)}']
    for record in df.to_dict(orient='records'):
        log_lines.append(json.dumps({
            'parcel_id': record['parcel_id'],
            'pre_ai_final_score': record['pre_ai_final_score'],
            'pre_ai_category': record['pre_ai_category'],
            'area_ranking_reason': record['area_ranking_reason'],
            'area_key_risks': record['area_key_risks'],
        }, ensure_ascii=False))
    LOG_FILE.write_text('\n'.join(log_lines))
    print(f'ranked_rows={len(df)}')


if __name__ == '__main__':
    main()
