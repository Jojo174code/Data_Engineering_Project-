from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common_iter_utils import CLEANED_DIR, clean_text, looks_residential_address

FILTERED_CSV = CLEANED_DIR / 'filtered_properties_3000_to_8000.csv'
MATCH_CSV = CLEANED_DIR / 'property_development_matches.csv'
OUT_CSV = CLEANED_DIR / 'filtered_properties_3000_to_8000.csv'


def bid_price_signal(bid: float) -> tuple[str, int]:
    if bid <= 4500:
        return 'Strong', 9
    if bid <= 6500:
        return 'Moderate', 6
    return 'Weak', 3


def address_quality_signal(address: str) -> tuple[str, int]:
    if looks_residential_address(address):
        return 'Complete', 9
    if clean_text(address) and clean_text(address) != 'Unknown':
        return 'Partial', 5
    return 'Missing', 1


def property_clarity_signal(parcel_id: str, address: str, legal_description: str) -> tuple[str, int]:
    score = 0
    if clean_text(parcel_id) and clean_text(parcel_id) != 'Unknown':
        score += 1
    if looks_residential_address(address):
        score += 1
    if clean_text(legal_description) and clean_text(legal_description) != 'Unknown':
        score += 1
    if score == 3:
        return 'Strong', 9
    if score == 2:
        return 'Moderate', 6
    return 'Weak', 2


def development_signal(match_strength: str, inv_strength: str) -> tuple[str, int]:
    if match_strength == 'Strong Match' and inv_strength == 'High':
        return 'High', 9
    if match_strength == 'Strong Match' and inv_strength in {'Medium', 'Low'}:
        return 'Medium', 7
    if match_strength == 'Possible Match' and inv_strength in {'High', 'Medium'}:
        return 'Medium', 6
    if match_strength == 'Possible Match':
        return 'Low', 4
    return 'Low', 3


def surrounding_value_signal(dev_signal: str) -> tuple[str, int]:
    if dev_signal == 'High':
        return 'Positive', 8
    if dev_signal == 'Medium':
        return 'Possible Upside', 6
    return 'Unknown', 4


def crime_risk_estimate(address: str) -> tuple[str, int]:
    if looks_residential_address(address):
        return 'Unknown', 5
    return 'Unknown', 4


def main():
    filtered = pd.read_csv(FILTERED_CSV)
    matches = pd.read_csv(MATCH_CSV)
    stale_cols = [
        'development_match_strength', 'matched_development_area', 'matched_project_or_area_name', 'matched_project_type',
        'matched_investment_signal_strength', 'development_source_url', 'development_source_title', 'development_summary',
        'development_match_reason', 'development_confidence', 'rule_based_score', 'rule_based_category', 'bid_price_signal',
        'address_quality_signal', 'property_clarity_signal', 'development_signal', 'surrounding_value_signal',
        'crime_risk_estimate', 'data_confidence', 'rule_based_reasoning', 'key_rule_based_risks'
    ]
    filtered = filtered.drop(columns=[col for col in stale_cols if col in filtered.columns], errors='ignore')
    df = filtered.merge(matches, on='parcel_id', how='left')

    def score_row(row):
        bid = float(row['bid_cost'])
        bid_signal, bid_score = bid_price_signal(bid)
        addr_signal, addr_score = address_quality_signal(row['property_address'])
        clarity_signal, clarity_score = property_clarity_signal(row['parcel_id'], row['property_address'], row['legal_description'])
        dev_signal, dev_score = development_signal(clean_text(row['development_match_strength']), clean_text(row['matched_investment_signal_strength']))
        surround_signal, surround_score = surrounding_value_signal(dev_signal)
        crime_signal, crime_score = crime_risk_estimate(row['property_address'])
        data_confidence = 'High' if row['extraction_confidence'] == 'High' and clarity_signal == 'Strong' else 'Medium' if clarity_signal in {'Strong', 'Moderate'} else 'Low'
        data_score = {'High': 9, 'Medium': 6, 'Low': 3}[data_confidence]
        score = round(
            bid_score * 0.20 +
            addr_score * 0.15 +
            clarity_score * 0.15 +
            dev_score * 0.20 +
            surround_score * 0.15 +
            crime_score * 0.05 +
            data_score * 0.10,
            1,
        )
        raw_upper = clean_text(row['raw_text']).upper()
        red_flag = any(flag in raw_upper for flag in ['COMMERCIAL', 'INDUSTRIAL', 'LANDLOCKED', 'VACANT ONLY'])

        if addr_signal == 'Missing' or clean_text(row['parcel_id']) == 'Unknown' or (bid >= 6500 and data_confidence == 'Low') or red_flag or (dev_signal == 'Low' and data_confidence == 'Low'):
            category = 'Bad Investment'
        elif bid_signal == 'Strong' and addr_signal == 'Complete' and clarity_signal == 'Strong' and data_confidence in {'Medium', 'High'} and (dev_signal == 'High' or surround_signal == 'Positive') and not red_flag:
            category = 'Good Investment'
        elif ((3000 <= bid <= 5500 and addr_signal != 'Missing' and clean_text(row['parcel_id']) != 'Unknown' and data_confidence in {'Medium', 'High'} and not red_flag) or (dev_signal in {'High', 'Medium'} and bid <= 6500 and data_confidence in {'Medium', 'High'})):
            category = 'Strong Manual Review Candidate'
        else:
            category = 'Mid Investment'

        reasoning = (
            f"Bid cost {bid:.2f}, parcel_id {row['parcel_id']}, address quality {addr_signal}, property clarity {clarity_signal}, "
            f"development match {row['development_match_strength']} to {row['matched_development_area']}, development signal {dev_signal}, data confidence {data_confidence}."
        )
        risks = []
        if clean_text(row['zip_code']) == 'Unknown':
            risks.append('ZIP unknown')
        if dev_signal == 'Low':
            risks.append('development upside not clearly supported')
        if clean_text(row['development_match_strength']) in {'Unknown', 'No Clear Match'}:
            risks.append('no clear development overlap')
        if addr_signal != 'Complete':
            risks.append('address not fully verified')
        if not risks:
            risks.append('normal auction diligence still required')

        return pd.Series({
            'rule_based_score': score,
            'rule_based_category': category,
            'bid_price_signal': bid_signal,
            'address_quality_signal': addr_signal,
            'property_clarity_signal': clarity_signal,
            'development_signal': dev_signal,
            'surrounding_value_signal': surround_signal,
            'crime_risk_estimate': crime_signal,
            'data_confidence': data_confidence,
            'rule_based_reasoning': reasoning,
            'key_rule_based_risks': '; '.join(risks),
        })

    scored = df.apply(score_row, axis=1)
    out_df = pd.concat([df, scored], axis=1)
    out_df.to_csv(OUT_CSV, index=False)
    print(f'Rule-based ranking rows: {len(out_df)}')
    print(out_df.head(10).to_dict('records'))


if __name__ == '__main__':
    main()
