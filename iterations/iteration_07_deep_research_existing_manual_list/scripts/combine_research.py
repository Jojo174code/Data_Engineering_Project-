#!/usr/bin/env python3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PARSED = ROOT / 'cleaned_data' / 'parsed_manual_review_list.csv'
ASSESSOR = ROOT / 'cleaned_data' / 'assessor_property_results.csv'
NS = ROOT / 'cleaned_data' / 'neighborhoodscout_results.csv'
MAP = ROOT / 'cleaned_data' / 'map_location_intelligence.csv'
OUTPUT = ROOT / 'cleaned_data' / 'final_combined_research.csv'


def to_num(v):
    if pd.isna(v):
        return np.nan
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace('$', '').replace(',', '').strip()
    if s in {'', 'Unknown', 'Unavailable', 'nan'}:
        return np.nan
    try:
        return float(s)
    except Exception:
        return np.nan


def score_location(rating):
    return {'Strong': 8.5, 'Moderate': 6.5, 'Weak': 3.5, 'Unknown': 5.0}.get(str(rating), 5.0)


def score_crime(rating):
    return {'Low': 8.0, 'Medium': 5.5, 'High': 2.5, 'Unknown': 5.0}.get(str(rating), 5.0)


def score_trend(direction):
    return {'Increasing': 8.0, 'Stable': 6.0, 'Decreasing': 3.0, 'Unknown': 5.0}.get(str(direction), 5.0)


def score_assessor(row):
    market = to_num(row.get('assessor_market_value'))
    assessed = to_num(row.get('assessor_total_assessed_value'))
    bid = to_num(row.get('bid_cost'))
    improv = to_num(row.get('assessor_improvement_value'))
    base_value = market if not np.isnan(market) else assessed
    if np.isnan(base_value) or np.isnan(bid) or bid <= 0:
        return 5.0
    ratio = bid / base_value if base_value else np.nan
    score = 8.5 if ratio < 0.15 else 7.5 if ratio < 0.30 else 6.0 if ratio < 0.50 else 4.0 if ratio < 1.0 else 2.5
    if not np.isnan(improv) and improv > 0:
        score += 0.5
    return min(10.0, max(1.0, score))


def data_quality(row):
    pts = 0
    if str(row.get('assessor_match_status')) not in {'No Match', 'Blocked'}:
        pts += 3
    if str(row.get('geocode_status')) == 'Success':
        pts += 3
    if str(row.get('neighborhoodscout_match_status')).startswith('Area-Level'):
        pts += 2
    if str(row.get('property_address')) not in {'Unknown', ''}:
        pts += 2
    return min(10, pts)


def source_verification(row):
    pts = 0
    if str(row.get('assessor_source_url')) not in {'Unavailable', '', 'nan'}:
        pts += 3
    if str(row.get('neighborhoodscout_source_url')) not in {'Unavailable', '', 'nan'}:
        pts += 2
    if str(row.get('geocode_status')) == 'Success':
        pts += 3
    if str(row.get('location_confidence')) == 'Medium':
        pts += 2
    return min(10, pts)


def previous_rank_score(rank, prev_ai):
    rank = to_num(rank)
    prev_ai = to_num(prev_ai)
    rank_score = 10 - min(9, (rank - 1) / 6) if not np.isnan(rank) else 5
    ai_score = prev_ai if not np.isnan(prev_ai) else 5
    return max(1, min(10, (rank_score * 0.4) + (ai_score * 0.6)))


def color_and_category(score):
    if score >= 8.5:
        return 'Purple', 'Amazing'
    if score >= 7.0:
        return 'Green', 'Great'
    if score >= 5.0:
        return 'Yellow', 'Mid'
    return 'Red', 'Avoid'


def user_numeric(color):
    return {'Red': 1, 'Yellow': 2, 'Green': 3, 'Purple': 4}.get(str(color), np.nan)


def main():
    base = pd.read_csv(PARSED)
    assessor = pd.read_csv(ASSESSOR)
    ns = pd.read_csv(NS)
    mp = pd.read_csv(MAP)

    df = base.merge(assessor, on='parcel_id', how='left').merge(ns, on=['parcel_id','property_address'], how='left').merge(mp, on=['parcel_id','property_address'], how='left')

    df['bid_to_assessor_market_value_ratio'] = df.apply(lambda r: to_num(r['bid_cost']) / to_num(r['assessor_market_value']) if pd.notna(to_num(r['bid_cost'])) and pd.notna(to_num(r['assessor_market_value'])) and to_num(r['assessor_market_value']) else np.nan, axis=1)
    df['bid_to_assessed_value_ratio'] = df.apply(lambda r: to_num(r['bid_cost']) / to_num(r['assessor_total_assessed_value']) if pd.notna(to_num(r['bid_cost'])) and pd.notna(to_num(r['assessor_total_assessed_value'])) and to_num(r['assessor_total_assessed_value']) else np.nan, axis=1)
    df['value_spread_estimate'] = df.apply(lambda r: (to_num(r['assessor_market_value']) - to_num(r['bid_cost'])) if pd.notna(to_num(r['assessor_market_value'])) and pd.notna(to_num(r['bid_cost'])) else np.nan, axis=1)
    df['data_quality_score'] = df.apply(data_quality, axis=1)
    df['source_verification_score'] = df.apply(source_verification, axis=1)
    df['location_score'] = df['location_strength_rating'].map(score_location)
    df['assessor_value_score'] = df.apply(score_assessor, axis=1)
    df['neighborhood_trend_score'] = df['real_estate_trend_direction'].map(score_trend)
    df['crime_score'] = df['crime_risk_rating'].map(score_crime)
    df['previous_rank_score'] = df.apply(lambda r: previous_rank_score(r['rank'], r['final_ai_review_score']), axis=1)
    df['user_rating_numeric'] = df['user_color_rating'].map(user_numeric)

    df['deep_rule_score_1_to_10'] = (
        df['assessor_value_score'] * 0.35 +
        df['location_score'] * 0.20 +
        ((df['neighborhood_trend_score'] + df['crime_score']) / 2.0) * 0.20 +
        ((df['data_quality_score'] + df['source_verification_score']) / 2.0) * 0.15 +
        df['previous_rank_score'] * 0.10
    ).round(1)
    df[['deep_rule_color_rating','deep_rule_category']] = df['deep_rule_score_1_to_10'].apply(lambda s: pd.Series(color_and_category(s)))
    df['deep_rule_reasoning'] = df.apply(lambda r: f"Bid cost {r['bid_cost']} compared against assessor availability {r['assessor_match_status']}; location rated {r['location_strength_rating']}; area trend {r['real_estate_trend_direction']}; crime rating {r['crime_risk_rating']}; prior rank {r['rank']}.", axis=1)
    df['deep_rule_key_risks'] = df.apply(lambda r: '; '.join([x for x in [str(r.get('final_key_risks','')), str(r.get('negative_location_flags',''))] if x and x not in {'Unknown','nan'}]) or 'Unknown', axis=1)

    keep_cols = [
        'rank','parcel_id','property_address','city','state','zip_code','bid_cost','legal_description','property_type','final_rule_based_score','final_ai_review_score','final_investment_category',
        'final_recommendation','final_confidence_level','final_reasoning_summary','final_key_risks','final_missing_information','final_next_due_diligence_step','user_color_rating','user_rating_meaning',
        'user_rating_source','assessor_match_status','assessor_market_value','assessor_total_assessed_value','assessor_land_value','assessor_improvement_value','assessor_property_type','assessor_year_built',
        'assessor_square_feet','assessor_lot_size','assessor_source_url','assessor_confidence','manual_lookup_url','crime_risk_rating','crime_risk_summary','real_estate_trend_direction','real_estate_price_trend',
        'neighborhood_or_area_used','neighborhoodscout_source_url','neighborhoodscout_confidence','geocode_status','latitude','longitude','nearby_schools','nearby_major_employers','nearby_hospitals',
        'nearby_universities','nearby_retail_or_grocery','nearby_highways_or_major_roads','negative_location_flags','location_strength_rating','location_summary','location_confidence','bid_to_assessor_market_value_ratio',
        'bid_to_assessed_value_ratio','value_spread_estimate','data_quality_score','source_verification_score','location_score','assessor_value_score','neighborhood_trend_score','crime_score','previous_rank_score',
        'user_rating_numeric','deep_rule_score_1_to_10','deep_rule_color_rating','deep_rule_category','deep_rule_reasoning','deep_rule_key_risks'
    ]
    df[keep_cols].to_csv(OUTPUT, index=False)
    print(f'combined_rows={len(df)}')


if __name__ == '__main__':
    main()
