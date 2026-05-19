#!/usr/bin/env python3
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / 'cleaned_data' / 'final_combined_research.csv'
OUTPUT_CSV = ROOT / 'cleaned_data' / 'ai_deep_property_reviews.csv'
LOG_PATH = ROOT / 'logs' / 'ai_review_log.txt'


def num(v):
    if pd.isna(v):
        return np.nan
    try:
        return float(v)
    except Exception:
        try:
            return float(str(v).replace('$', '').replace(',', ''))
        except Exception:
            return np.nan


def color_and_category(score):
    if score >= 8.5:
        return 'Purple', 'Amazing'
    if score >= 7.0:
        return 'Green', 'Great'
    if score >= 5.0:
        return 'Yellow', 'Mid'
    return 'Red', 'Avoid'


def prev_color(cat):
    return {'Amazing': 'Purple', 'Great': 'Green', 'Mid': 'Yellow', 'Avoid': 'Red'}.get(str(cat), 'Unknown')


def compare_change(new_color, previous_category):
    old = prev_color(previous_category)
    order = {'Red': 1, 'Yellow': 2, 'Green': 3, 'Purple': 4}
    if old == 'Unknown' or new_color not in order:
        return 'Unknown'
    if order[new_color] > order[old]:
        return 'Upgrade'
    if order[new_color] < order[old]:
        return 'Downgrade'
    return 'Same'


def agree_with_user(ai_color, user_color):
    if str(user_color) == 'Unknown':
        return 'No User Rating Provided'
    if ai_color == user_color:
        return 'Agree'
    order = {'Red': 1, 'Yellow': 2, 'Green': 3, 'Purple': 4}
    if abs(order.get(ai_color, 0) - order.get(str(user_color), 0)) == 1:
        return 'Partially Agree'
    return 'Disagree'


def confidence(row):
    good = 0
    if str(row.get('assessor_match_status')) == 'Search Reachable, Detail Unavailable':
        good += 1
    if str(row.get('geocode_status')) == 'Success':
        good += 1
    if str(row.get('neighborhoodscout_confidence')) in {'Medium', 'High', 'Low'}:
        good += 1
    if good >= 3:
        return 'Medium'
    if good == 2:
        return 'Low'
    return 'Low'


def main():
    df = pd.read_csv(INPUT_CSV)
    rows = []
    logs = []
    for _, row in df.iterrows():
        deep_score = num(row.get('deep_rule_score_1_to_10'))
        if np.isnan(deep_score):
            deep_score = 5.0
        score = round(deep_score, 1)
        ai_color, ai_category = color_and_category(score)
        conf = confidence(row)
        summary = (
            f"Bid cost {row.get('bid_cost')}; assessor data {row.get('assessor_match_status')} with market value {row.get('assessor_market_value')}; "
            f"location signal {row.get('location_strength_rating')} and geocode {row.get('geocode_status')}; "
            f"crime/trend signal {row.get('crime_risk_rating')}/{row.get('real_estate_trend_direction')}."
        )
        positives = []
        if score >= 7.0:
            positives.append(f"Deep rule score {score} supports a stronger screen")
        if str(row.get('property_type')) not in {'Unknown', 'nan'}:
            positives.append(f"Property type {row.get('property_type')} is identified")
        if str(row.get('geocode_status')) == 'Success':
            positives.append('Property geocoded successfully for map context')
        if str(row.get('real_estate_trend_direction')) in {'Stable', 'Increasing'}:
            positives.append(f"Area trend is {row.get('real_estate_trend_direction')}")
        if str(row.get('nearby_highways_or_major_roads')) not in {'Unknown', 'nan'}:
            positives.append(f"Map context shows {row.get('nearby_highways_or_major_roads')}")
        risks = []
        if str(row.get('assessor_market_value')) in {'Unavailable', 'Unknown', 'nan'}:
            risks.append('Assessor valuation fields were unavailable to automation')
        if str(row.get('crime_risk_rating')) == 'Unknown':
            risks.append('Crime rating is area-level or unavailable')
        if str(row.get('negative_location_flags')) not in {'Unknown', 'nan'}:
            risks.append(str(row.get('negative_location_flags')))
        if str(row.get('final_key_risks')) not in {'Unknown', 'nan'}:
            risks.append(str(row.get('final_key_risks')))
        missing = []
        for label, value in [
            ('assessor market value', row.get('assessor_market_value')),
            ('assessor assessed value', row.get('assessor_total_assessed_value')),
            ('crime context', row.get('crime_risk_summary')),
            ('property condition', row.get('final_missing_information')),
        ]:
            if str(value) in {'Unavailable', 'Unknown', 'nan'} or label == 'property condition':
                missing.append(label)
        next_step = 'Verify the Tulsa County Assessor property card manually, confirm structure condition and occupancy, and review nearby comps before bidding.'
        out = {
            'parcel_id': row.get('parcel_id', ''),
            'ai_score_1_to_10': score,
            'ai_color_rating': ai_color,
            'ai_category': ai_category,
            'agree_with_user_rating': agree_with_user(ai_color, row.get('user_color_rating')),
            'rating_change_from_previous': compare_change(ai_color, row.get('final_investment_category')),
            'investment_summary': summary,
            'key_positive_signals': '; '.join(positives[:5]) if positives else 'Low bid cost created the initial screen opportunity.',
            'key_risks': '; '.join(dict.fromkeys(risks)) if risks else 'Missing assessor and property-condition detail increases uncertainty.',
            'missing_information': '; '.join(dict.fromkeys(missing)) if missing else 'No major missing information noted.',
            'next_due_diligence_step': next_step,
            'confidence_level': conf,
        }
        rows.append(out)
        logs.append(json.dumps(out, ensure_ascii=False))
    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUTPUT_CSV, index=False)
    LOG_PATH.write_text('\n'.join(logs))
    print(f'ai_rows={len(out_df)}')


if __name__ == '__main__':
    main()
