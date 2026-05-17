from __future__ import annotations

from pathlib import Path

import pandas as pd

ITERATION_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
LOG_DIR = ITERATION_ROOT / 'logs'

BASE_CSV = CLEANED_DIR / 'final_property_base.csv'
MATCH_CSV = CLEANED_DIR / 'final_property_development_matches.csv'
GEOCODE_CSV = CLEANED_DIR / 'final_geocoding_results.csv'
OUT_CSV = CLEANED_DIR / 'final_rule_based_scores.csv'
LOG_FILE = LOG_DIR / 'rule_based_ranking_log.txt'


def clean_text(value) -> str:
    if value is None:
        return 'Unknown'
    text = str(value).strip()
    return text if text else 'Unknown'


def usable_address(address: str) -> bool:
    text = clean_text(address).upper()
    return text not in {'UNKNOWN', 'ADDRESS UNKNOWN'} and text[:1].isdigit()


def bid_signal(bid: float) -> tuple[str, int]:
    if pd.isna(bid):
        return 'Missing', 1
    if bid <= 4000:
        return 'Strong', 9
    if bid <= 5500:
        return 'Moderate', 7
    if bid <= 6500:
        return 'Borderline', 5
    return 'Weak', 3


def address_signal(address: str) -> tuple[str, int]:
    if usable_address(address):
        return 'Complete', 9
    if clean_text(address) not in {'Unknown', 'ADDRESS UNKNOWN'}:
        return 'Partial', 5
    return 'Missing', 1


def clarity_signal(parcel_id: str, address: str, legal_description: str) -> tuple[str, int]:
    score = 0
    if clean_text(parcel_id) != 'Unknown':
        score += 1
    if usable_address(address):
        score += 1
    if clean_text(legal_description) != 'Unknown':
        score += 1
    if score == 3:
        return 'Strong', 9
    if score == 2:
        return 'Moderate', 6
    return 'Weak', 2


def development_signal(row: pd.Series) -> tuple[str, int]:
    strength = clean_text(row['corrected_development_match_strength'])
    basis = clean_text(row['final_match_basis'])
    inv_strength = clean_text(row['final_matched_investment_signal_strength'])
    distance_verified = bool(row['distance_verified_match'])
    weak_removed = bool(row['weak_match_removed_flag'])
    if weak_removed:
        return 'Low', 1
    if strength == 'Strong Match' and distance_verified and inv_strength == 'High':
        return 'High', 9
    if strength == 'Strong Match' and basis in {'named_area', 'named_area_plus_zip'}:
        return 'High', 8
    if strength == 'Strong Match':
        return 'Medium', 7
    if strength == 'Possible Match' and inv_strength in {'High', 'Medium'}:
        return 'Medium', 5
    if strength == 'Possible Match':
        return 'Low', 4
    return 'Low', 2


def surrounding_signal(row: pd.Series, verified_dev_signal: str) -> tuple[str, int]:
    strength = clean_text(row['corrected_development_match_strength'])
    inv_strength = clean_text(row['final_matched_investment_signal_strength'])
    if strength == 'Strong Match' and verified_dev_signal == 'High' and inv_strength == 'High':
        return 'Positive', 8
    if strength in {'Strong Match', 'Possible Match'} and inv_strength in {'High', 'Medium'}:
        return 'Possible Upside', 6
    return 'Unknown', 4


def crime_signal(row: pd.Series) -> tuple[str, int]:
    return ('Unknown', 5) if usable_address(row['property_address']) else ('Unknown', 4)


def data_confidence(row: pd.Series, addr_signal: str, clarity: str) -> tuple[str, int]:
    extraction = clean_text(row['extraction_confidence'])
    geo = clean_text(row['geocode_confidence'])
    if extraction == 'High' and addr_signal == 'Complete' and clarity == 'Strong' and geo in {'High', 'Medium'}:
        return 'High', 9
    if extraction in {'High', 'Medium'} and clarity in {'Strong', 'Moderate'}:
        return 'Medium', 6
    return 'Low', 3


def category_for_row(row: pd.Series, score: float, bid_sig: str, addr_sig: str, clarity_sig: str, dev_sig: str, data_conf: str) -> tuple[str, bool]:
    previous_cat = clean_text(row['previous_investment_category'])
    corrected_strength = clean_text(row['corrected_development_match_strength'])
    raw_text = clean_text(row['raw_text']).upper()
    major_red_flag = any(flag in raw_text for flag in ['LANDLOCKED', 'VACANT ONLY']) or pd.isna(row['bid_cost'])
    weak_identity = clean_text(row['parcel_id']) == 'Unknown' or addr_sig == 'Missing'
    downgraded_previous_good = previous_cat == 'Good Investment' and (corrected_strength in {'No Clear Match', 'Unknown'} or data_conf == 'Low' or clarity_sig == 'Weak')

    if weak_identity or major_red_flag or (data_conf == 'Low' and row['bid_cost'] >= 6500) or (corrected_strength in {'No Clear Match', 'Unknown'} and data_conf == 'Low'):
        return 'Bad Investment', downgraded_previous_good

    good_requires = all([
        bid_sig in {'Strong', 'Moderate'},
        addr_sig == 'Complete',
        clarity_sig == 'Strong',
        data_conf in {'Medium', 'High'},
        corrected_strength == 'Strong Match',
        dev_sig in {'High', 'Medium'},
        not bool(row['weak_match_removed_flag']),
        score >= 7.4,
    ])
    if good_requires and (bool(row['distance_verified_match']) or clean_text(row['final_match_basis']) in {'named_area', 'named_area_plus_zip'}):
        return 'Good Investment', downgraded_previous_good

    if downgraded_previous_good:
        return ('Strong Manual Review Candidate' if score >= 6.0 else 'Mid Investment'), True

    if addr_sig != 'Missing' and clarity_sig in {'Strong', 'Moderate'} and data_conf in {'Medium', 'High'} and (bid_sig in {'Strong', 'Moderate', 'Borderline'} or dev_sig in {'High', 'Medium'}):
        return 'Strong Manual Review Candidate', False

    if addr_sig != 'Missing' and clarity_sig != 'Weak':
        return 'Mid Investment', False

    return 'Bad Investment', False


def main():
    base = pd.read_csv(BASE_CSV)
    matches = pd.read_csv(MATCH_CSV)
    geo = pd.read_csv(GEOCODE_CSV)

    df = base.merge(matches.drop(columns=[c for c in ['property_address', 'city', 'state', 'zip_code', 'legal_description', 'bid_cost', 'previous_investment_category', 'previous_development_match_strength', 'previous_development_match_quality'] if c in matches.columns]), on='parcel_id', how='left')
    df = df.merge(geo, on='parcel_id', how='left')

    rows = []
    downgraded_previous_good_count = 0
    for _, row in df.iterrows():
        bid_sig, bid_score = bid_signal(row['bid_cost'])
        addr_sig, addr_score = address_signal(row['property_address'])
        clarity_sig, clarity_score = clarity_signal(row['parcel_id'], row['property_address'], row['legal_description'])
        dev_sig, dev_score = development_signal(row)
        surround_sig, surround_score = surrounding_signal(row, dev_sig)
        crime_sig, crime_score = crime_signal(row)
        data_conf, data_score = data_confidence(row, addr_sig, clarity_sig)

        final_score = round(
            bid_score * 0.20 + addr_score * 0.15 + clarity_score * 0.15 + dev_score * 0.20 + surround_score * 0.10 + crime_score * 0.05 + data_score * 0.15,
            1,
        )

        category, downgraded_prev_good = category_for_row(row, final_score, bid_sig, addr_sig, clarity_sig, dev_sig, data_conf)
        downgraded_previous_good_count += int(downgraded_prev_good)
        manual_flag = category != 'Bad Investment'

        risks = []
        if clean_text(row['zip_code']) == 'Unknown':
            risks.append('ZIP unknown')
        if clean_text(row['corrected_development_match_strength']) in {'No Clear Match', 'Unknown'}:
            risks.append('development upside not verified')
        if clean_text(row['geocode_confidence']) == 'Low':
            risks.append('geocoding support weak or unavailable')
        if data_conf == 'Low':
            risks.append('data confidence low')
        if addr_sig != 'Complete':
            risks.append('address not fully verified')
        if not risks:
            risks.append('title, condition, liens, and comps still require manual verification')

        reasoning = (
            f"Bid cost {row['bid_cost']:.2f}, parcel_id {row['parcel_id']}, address quality {addr_sig}, property clarity {clarity_sig}, "
            f"corrected development match {row['corrected_development_match_strength']}, geocode confidence {row['geocode_confidence']}, and final data confidence {data_conf} produced a conservative score of {final_score}."
        )

        rows.append({
            'parcel_id': row['parcel_id'],
            'final_rule_based_score': final_score,
            'final_rule_based_category': category,
            'final_bid_price_signal': bid_sig,
            'final_address_quality_signal': addr_sig,
            'final_property_clarity_signal': clarity_sig,
            'final_verified_development_signal': dev_sig,
            'final_surrounding_value_signal': surround_sig,
            'final_crime_risk_estimate': crime_sig,
            'final_data_confidence': data_conf,
            'final_manual_review_flag': bool(manual_flag),
            'final_rule_based_reasoning': reasoning,
            'final_key_risks': '; '.join(risks),
            'downgraded_from_previous_good': bool(downgraded_prev_good),
        })

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT_CSV, index=False)

    merged = df[['parcel_id', 'previous_investment_category']].merge(out_df, on='parcel_id', how='left')
    lines = [
        f'final properties scored: {len(out_df)}',
        f'Good Investment count: {(out_df["final_rule_based_category"] == "Good Investment").sum()}',
        f'Strong Manual Review Candidate count: {(out_df["final_rule_based_category"] == "Strong Manual Review Candidate").sum()}',
        f'Mid Investment count: {(out_df["final_rule_based_category"] == "Mid Investment").sum()}',
        f'Bad Investment count: {(out_df["final_rule_based_category"] == "Bad Investment").sum()}',
        f'properties downgraded from previous Good: {downgraded_previous_good_count}',
    ]
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for line in lines:
        print(line)


if __name__ == '__main__':
    main()
