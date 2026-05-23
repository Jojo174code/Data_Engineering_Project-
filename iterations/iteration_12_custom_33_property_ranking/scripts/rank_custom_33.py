#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd

from common_custom_33 import CLEANED_DIR, LOG_DIR, clean_text, confidence_rank, ensure_dirs, parse_pct, risk_rank, safe_float, write_log

IN_CSV = CLEANED_DIR / 'custom_33_area_intelligence.csv'
RULE_CSV = CLEANED_DIR / 'custom_33_rule_ranked.csv'
FINAL_CSV = CLEANED_DIR / 'custom_33_final_ranked.csv'
AI_CSV = CLEANED_DIR / 'custom_33_ai_reviews.csv'
LOG_FILE = LOG_DIR / 'ranking_log.txt'


def score_property_clarity(row: pd.Series) -> float:
    score = 3.5
    address = clean_text(row.get('property_address'))
    parcel = clean_text(row.get('parcel_id'))
    if address not in {'Unknown', 'Unknown.'} and any(ch.isdigit() for ch in address):
        score += 3.0
    if parcel not in {'Unknown', 'Unknown.'} and '-' in parcel:
        score += 2.0
    if clean_text(row.get('legal_description')) not in {'Unknown', 'Unknown.'}:
        score += 0.8
    if clean_text(row.get('raw_text')) not in {'Unknown', 'Unknown.'}:
        score += 0.7
    return round(min(score, 10.0), 2)


def score_geocoding(row: pd.Series) -> float:
    conf = clean_text(row.get('geocode_confidence'))
    status = clean_text(row.get('geocode_status'))
    score = 2.5
    if status in {'Geocoded', 'Prior Geocoded'}:
        score += 4.5
    elif status == 'Approximate':
        score += 2.5
    if conf == 'High':
        score += 2.0
    elif conf == 'Medium':
        score += 1.0
    if clean_text(row.get('confirmed_zip_code')) not in {'Unknown', 'Unknown.'}:
        score += 1.0
    return round(min(score, 10.0), 2)


def score_residential(row: pd.Series) -> float:
    property_type = clean_text(row.get('property_type')).upper()
    address = clean_text(row.get('property_address')).upper()
    score = 4.0
    if any(token in property_type for token in ['SINGLE', 'RES', 'HOUSE', 'DUPLEX', 'HOME']):
        score = 8.5
    elif property_type in {'Unknown', 'Unknown.'}:
        score = 5.0
    elif any(token in property_type for token in ['VACANT', 'COMMERCIAL', 'INDUSTRIAL', 'UTILITY']):
        score = 2.5
    if any(token in address for token in ['ST N', 'PL N', 'AVE E', 'AVE W']):
        score += 0.5
    return round(min(score, 10.0), 2)


def score_crime(row: pd.Series) -> float:
    level = clean_text(row.get('crime_risk_level'))
    raw = safe_float(row.get('crime_risk_score'))
    if raw is not None:
        score = raw
    else:
        score = {'Low': 8.0, 'Medium': 5.5, 'High': 2.5}.get(level, 4.5)
    if clean_text(row.get('crime_confidence')) == 'Low':
        score -= 0.5
    return round(max(1.0, min(score, 10.0)), 2)


def score_economic(row: pd.Series) -> float:
    raw = safe_float(row.get('economic_strength_score'))
    if raw is not None:
        score = raw
    else:
        income = safe_float(row.get('median_household_income'))
        poverty = parse_pct(row.get('poverty_rate'))
        score = 5.0
        if income is not None:
            score += 1.0 if income >= 50000 else -1.0 if income < 40000 else 0.0
        if poverty is not None:
            score += 1.0 if poverty < 0.12 else -1.0 if poverty > 0.22 else 0.0
    if clean_text(row.get('economic_confidence')) == 'Low':
        score -= 0.5
    return round(max(1.0, min(score, 10.0)), 2)


def score_bid_price(row: pd.Series, min_bid: float, max_bid: float) -> float:
    bid = float(row['bid_cost'])
    if max_bid == min_bid:
        return 5.0
    normalized = (max_bid - bid) / (max_bid - min_bid)
    return round(3.0 + (normalized * 7.0), 2)


def score_prior_shortlist(row: pd.Series) -> float:
    score = 5.0
    source_list = clean_text(row.get('source_list'))
    if source_list == 'Manual Review':
        score += 2.0
    original_rank = safe_float(row.get('original_rank'))
    if original_rank is not None and original_rank <= 10:
        score += 1.5
    prev_ai = safe_float(row.get('previous_ai_score'))
    if prev_ai is not None:
        score += max(-1.0, min(2.0, (prev_ai - 5.0) / 2.0))
    return round(max(1.0, min(score, 10.0)), 2)


def score_data_confidence(row: pd.Series) -> float:
    parts = [
        confidence_rank(row.get('extraction_confidence')),
        confidence_rank(row.get('geocode_confidence')),
        confidence_rank(row.get('crime_confidence')),
        confidence_rank(row.get('economic_confidence')),
    ]
    score = 2.5 + (sum(parts) / max(1, len(parts))) * 2.0
    return round(max(1.0, min(score, 10.0)), 2)


def categorize(score: float, geocode: float, resi: float, crime: float, econ: float, data_conf: float) -> str:
    if score >= 7.5 and min(geocode, resi, crime, econ, data_conf) >= 5.0:
        return 'Tier 1 Priority'
    if score >= 6.0:
        return 'Tier 2 Strong Review'
    if score >= 4.5:
        return 'Tier 3 Watch'
    return 'Tier 4 High Risk'


def due_diligence_priority(tier: str, row: pd.Series) -> str:
    if tier == 'Tier 1 Priority':
        return 'Highest'
    if tier == 'Tier 2 Strong Review':
        return 'High'
    if clean_text(row.get('geocode_confidence')) == 'Low' or clean_text(row.get('property_type')) in {'Unknown', 'Unknown.'}:
        return 'High'
    return 'Medium'


def reasoning(row: pd.Series) -> tuple[str, str]:
    risks = []
    if clean_text(row.get('crime_risk_level')) == 'High':
        risks.append('high crime context')
    if clean_text(row.get('economic_risk_level')) == 'High':
        risks.append('weak economic context')
    if clean_text(row.get('geocode_confidence')) == 'Low':
        risks.append('low geocoding confidence')
    if clean_text(row.get('property_type')) in {'Unknown', 'Unknown.'}:
        risks.append('unclear property type')
    reason = (
        f"Bid {float(row['bid_cost']):.2f} for {row['parcel_id']} at {row['property_address']} screened with property clarity {row['property_clarity_score']}, "
        f"geocoding {row['geocoding_score']}, residential likelihood {row['residential_likelihood_score']}, crime {row['crime_score']}, and economics {row['economic_score']}."
    )
    return reason, '; '.join(risks) if risks else 'No major red flags beyond normal tax-auction uncertainty.'


def build_rule_ranked(df: pd.DataFrame) -> pd.DataFrame:
    min_bid = float(df['bid_cost'].min())
    max_bid = float(df['bid_cost'].max())
    rows = []
    for _, row in df.iterrows():
        record = row.to_dict()
        record['property_clarity_score'] = score_property_clarity(row)
        record['geocoding_score'] = score_geocoding(row)
        record['residential_likelihood_score'] = score_residential(row)
        record['crime_score'] = score_crime(row)
        record['economic_score'] = score_economic(row)
        record['bid_price_score'] = score_bid_price(row, min_bid, max_bid)
        record['prior_shortlist_score'] = score_prior_shortlist(row)
        record['data_confidence_score'] = score_data_confidence(row)
        record['rule_score'] = round(
            (record['property_clarity_score'] * 0.20) +
            (record['geocoding_score'] * 0.15) +
            (record['residential_likelihood_score'] * 0.15) +
            (record['crime_score'] * 0.15) +
            (record['economic_score'] * 0.15) +
            (record['bid_price_score'] * 0.10) +
            (record['prior_shortlist_score'] * 0.05) +
            (record['data_confidence_score'] * 0.05),
            2,
        )
        record['rule_category'] = categorize(
            record['rule_score'],
            record['geocoding_score'],
            record['residential_likelihood_score'],
            record['crime_score'],
            record['economic_score'],
            record['data_confidence_score'],
        )
        record['rule_reasoning'], record['rule_key_risks'] = reasoning(pd.Series(record))
        record['manual_due_diligence_priority'] = due_diligence_priority(record['rule_category'], pd.Series(record))
        rows.append(record)
    return pd.DataFrame(rows)


def apply_final(ai_df: pd.DataFrame) -> pd.DataFrame:
    final = ai_df.copy()
    final['final_score'] = ((final['rule_score'] * 0.55) + (final['ai_score'] * 0.45)).round(2)
    for idx, row in final.iterrows():
        if clean_text(row['crime_risk_level']) == 'High':
            final.at[idx, 'final_score'] -= 1.0
        if clean_text(row['economic_risk_level']) == 'High':
            final.at[idx, 'final_score'] -= 0.75
        if clean_text(row['geocode_confidence']) == 'Low':
            final.at[idx, 'final_score'] -= 0.75
        if clean_text(row['crime_confidence']) == 'Low':
            final.at[idx, 'final_score'] -= 0.5
        if clean_text(row['economic_confidence']) == 'Low':
            final.at[idx, 'final_score'] -= 0.5
        if clean_text(row['property_address']) in {'Unknown', 'Unknown.'}:
            final.at[idx, 'final_score'] -= 0.5
        if clean_text(row['parcel_id']) in {'Unknown', 'Unknown.'}:
            final.at[idx, 'final_score'] -= 0.5
        if any(token in clean_text(row['property_type']).upper() for token in ['COMMERCIAL', 'INDUSTRIAL', 'VACANT', 'UTILITY']):
            final.at[idx, 'final_score'] -= 0.5
        if clean_text(row['crime_risk_level']) == 'Low' and clean_text(row['economic_risk_level']) == 'Low':
            final.at[idx, 'final_score'] += 0.25
        if clean_text(row['geocode_confidence']) == 'High':
            final.at[idx, 'final_score'] += 0.25
    final['final_score'] = final['final_score'].clip(lower=1.0, upper=10.0).round(2)

    def final_tier(row: pd.Series) -> str:
        score = float(row['final_score'])
        confidence = clean_text(row['confidence_level'])
        major_red_flag = clean_text(row['crime_risk_level']) == 'High' or clean_text(row['property_type']) in {'Unknown', 'Unknown.'} and clean_text(row['geocode_confidence']) == 'Low'
        if score >= 7.5 and not major_red_flag and confidence in {'High', 'Medium'}:
            return 'Tier 1 Priority'
        if score >= 6.0:
            return 'Tier 2 Strong Review'
        if score >= 4.5:
            return 'Tier 3 Watch'
        return 'Tier 4 High Risk'

    final['final_tier'] = final.apply(final_tier, axis=1)
    tier_order = {'Tier 1 Priority': 0, 'Tier 2 Strong Review': 1, 'Tier 3 Watch': 2, 'Tier 4 High Risk': 3}
    final = final.assign(
        _tier=final['final_tier'].map(tier_order),
        _crime=final['crime_risk_level'].map({'Low': 0, 'Medium': 1, 'Unknown': 2, 'Unknown.': 2, 'High': 3}).fillna(2),
        _econ=final['economic_risk_level'].map({'Low': 0, 'Medium': 1, 'Unknown': 2, 'Unknown.': 2, 'High': 3}).fillna(2),
    ).sort_values(['_tier', 'final_score', '_crime', '_econ', 'bid_cost'], ascending=[True, False, True, True, True]).drop(columns=['_tier', '_crime', '_econ']).reset_index(drop=True)
    final.insert(0, 'final_rank', range(1, len(final) + 1))
    return final


def main() -> None:
    ensure_dirs()
    df = pd.read_csv(IN_CSV)
    rule_df = build_rule_ranked(df)
    rule_df.to_csv(RULE_CSV, index=False)
    log_lines = [f'input row count: {len(df)}', f'rule ranked row count: {len(rule_df)}']
    if AI_CSV.exists():
        ai_df = pd.read_csv(AI_CSV)
        merged = rule_df.merge(ai_df, on='parcel_id', how='left')
        final_df = apply_final(merged)
        final_df.to_csv(FINAL_CSV, index=False)
        log_lines.append(f'final ranked row count: {len(final_df)}')
        tier_counts = final_df['final_tier'].value_counts().to_dict()
        for tier in ['Tier 1 Priority', 'Tier 2 Strong Review', 'Tier 3 Watch', 'Tier 4 High Risk']:
            log_lines.append(f'{tier}: {tier_counts.get(tier, 0)}')
        print(f'final_ranked_rows={len(final_df)}')
    else:
        print(f'rule_ranked_rows={len(rule_df)}')
    write_log(LOG_FILE, log_lines)


if __name__ == '__main__':
    main()
