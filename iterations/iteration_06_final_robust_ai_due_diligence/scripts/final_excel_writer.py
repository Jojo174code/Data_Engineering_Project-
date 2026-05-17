from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ITERATION_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
OUTPUT_DIR = ITERATION_ROOT / 'output_excel'

PREV_UTILS_DIR = ITERATION_ROOT.parents[0] / 'iteration_05_strict_development_matching' / 'scripts'
if str(PREV_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(PREV_UTILS_DIR))

from common_iter_utils import validate_workbook, write_dataframe_to_excel  # noqa: E402

BASE_CSV = CLEANED_DIR / 'final_property_base.csv'
MATCH_CSV = CLEANED_DIR / 'final_property_development_matches.csv'
GEOCODE_CSV = CLEANED_DIR / 'final_geocoding_results.csv'
SCORES_CSV = CLEANED_DIR / 'final_rule_based_scores.csv'
AI_CSV = CLEANED_DIR / 'final_ai_property_reviews.csv'

FINAL_INVESTMENT_XLSX = OUTPUT_DIR / 'final_investment_ranked_properties.xlsx'
FINAL_MANUAL_XLSX = OUTPUT_DIR / 'final_manual_review_top_candidates.xlsx'
FINAL_DEV_XLSX = OUTPUT_DIR / 'final_development_opportunity_properties.xlsx'
FINAL_GOOD_XLSX = OUTPUT_DIR / 'final_good_investment_candidates.xlsx'
FINAL_BAD_XLSX = OUTPUT_DIR / 'final_bad_high_risk_properties.xlsx'

CATEGORY_PRIORITY = {'Good Investment': 0, 'Strong Manual Review Candidate': 1, 'Mid Investment': 2, 'Bad Investment': 3}
CONF_PRIORITY = {'High': 0, 'Medium': 1, 'Low': 2}
MATCH_PRIORITY = {'Strong Match': 0, 'Possible Match': 1, 'No Clear Match': 2, 'Unknown': 3}

FINAL_COLUMNS = [
    'parcel_id', 'owner_name', 'property_address', 'city', 'state', 'zip_code', 'bid_cost', 'legal_description', 'property_type',
    'source_page', 'extraction_confidence', 'final_development_match_strength', 'final_matched_development_area',
    'final_matched_project_or_area_name', 'final_development_source_title', 'final_development_source_url',
    'final_development_match_reason', 'final_development_warning', 'property_geocode_status', 'development_geocode_status',
    'estimated_distance_miles', 'geocode_confidence', 'distance_verified_match', 'corrected_development_match_strength',
    'final_rule_based_score', 'final_rule_based_category', 'final_ai_review_score', 'final_investment_category',
    'final_manual_review_flag', 'final_recommendation', 'final_development_opportunity_flag', 'final_development_opportunity_reason',
    'final_reasoning_summary', 'final_key_risks', 'final_missing_information', 'final_next_due_diligence_step',
    'final_confidence_level', 'raw_text'
]


def main():
    base = pd.read_csv(BASE_CSV)
    matches = pd.read_csv(MATCH_CSV)
    geo = pd.read_csv(GEOCODE_CSV)
    scores = pd.read_csv(SCORES_CSV)
    ai = pd.read_csv(AI_CSV)

    matches_trim = matches.drop(columns=[c for c in ['property_address', 'city', 'state', 'zip_code', 'legal_description', 'bid_cost', 'previous_investment_category', 'previous_development_match_strength', 'previous_development_match_quality'] if c in matches.columns])
    scores_trim = scores.drop(columns=[c for c in ['final_manual_review_flag', 'final_key_risks'] if c in scores.columns], errors='ignore')
    df = base.merge(matches_trim, on='parcel_id', how='left')
    df = df.merge(geo, on='parcel_id', how='left')
    df = df.merge(scores_trim, on='parcel_id', how='left')
    df = df.merge(ai, on='parcel_id', how='left')

    df['category_sort'] = df['final_investment_category'].map(CATEGORY_PRIORITY).fillna(9)
    df['dev_sort'] = df['final_development_opportunity_flag'].astype(str).map({'True': 0, 'False': 1}).fillna(1)
    df['match_sort'] = df['corrected_development_match_strength'].map(MATCH_PRIORITY).fillna(9)
    df['conf_sort'] = df['final_confidence_level'].map(CONF_PRIORITY).fillna(9)
    df = df.sort_values(by=['category_sort', 'dev_sort', 'match_sort', 'final_ai_review_score', 'final_rule_based_score', 'bid_cost', 'conf_sort'], ascending=[True, True, True, False, False, True, True]).reset_index(drop=True)

    investment_df = df[FINAL_COLUMNS].copy()

    manual_mask = (
        investment_df['final_investment_category'].isin(['Good Investment', 'Strong Manual Review Candidate']) |
        ((investment_df['final_investment_category'] == 'Mid Investment') & (pd.to_numeric(investment_df['final_ai_review_score'], errors='coerce') >= 6.5))
    )
    manual_df = df[manual_mask].head(50).copy()
    manual_df.insert(0, 'rank', range(1, len(manual_df) + 1))
    manual_df = manual_df[['rank'] + FINAL_COLUMNS].copy()

    dev_df = df[df['corrected_development_match_strength'].isin(['Strong Match', 'Possible Match']) & df['final_development_source_url'].notna()].copy()
    dev_df = dev_df[dev_df['final_development_source_url'].astype(str).str.strip().ne('Unknown')]
    dev_df = dev_df[FINAL_COLUMNS].copy()

    good_df = df[df['final_investment_category'] == 'Good Investment'][FINAL_COLUMNS].copy()
    if good_df.empty:
        note_row = {col: '' for col in FINAL_COLUMNS}
        note_row['parcel_id'] = 'NO_GOOD_INVESTMENTS'
        note_row['final_investment_category'] = 'Bad Investment'
        note_row['final_reasoning_summary'] = 'No properties cleared the final Good threshold after strict verification, geocoding review, and conservative AI screening.'
        note_row['final_key_risks'] = 'All candidates still require deeper due diligence before bidding.'
        note_row['final_recommendation'] = 'Avoid'
        note_row['final_confidence_level'] = 'Low'
        good_df = pd.DataFrame([note_row])

    bad_mask = (
        (df['final_investment_category'] == 'Bad Investment') |
        ((df['final_investment_category'] == 'Mid Investment') & ((df['final_confidence_level'] == 'Low') | (pd.to_numeric(df['final_ai_review_score'], errors='coerce') <= 5.5)))
    )
    bad_df = df[bad_mask][FINAL_COLUMNS].copy()
    if bad_df.empty:
        note_row = {col: '' for col in FINAL_COLUMNS}
        note_row['parcel_id'] = 'NO_BAD_HIGH_RISK_ROWS'
        note_row['final_investment_category'] = 'Mid Investment'
        note_row['final_reasoning_summary'] = 'No rows met the final Bad or high-risk Mid filters.'
        note_row['final_recommendation'] = 'Watch'
        note_row['final_confidence_level'] = 'Low'
        bad_df = pd.DataFrame([note_row])

    fills = {
        'Good Investment': 'C6EFCE',
        'Strong Manual Review Candidate': 'D9EAF7',
        'Mid Investment': 'FFEB9C',
        'Bad Investment': 'FFC7CE',
    }
    wrap_cols = {
        'legal_description', 'final_development_match_reason', 'final_development_warning', 'final_development_opportunity_reason',
        'final_reasoning_summary', 'final_key_risks', 'final_missing_information', 'final_next_due_diligence_step', 'raw_text'
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_dataframe_to_excel(investment_df, FINAL_INVESTMENT_XLSX, 'Final Ranked', {'bid_cost'}, wrap_cols, 'final_investment_category', fills, 'final_development_opportunity_flag', {'True'})
    write_dataframe_to_excel(manual_df, FINAL_MANUAL_XLSX, 'Final Manual', {'bid_cost'}, wrap_cols, 'final_investment_category', fills, 'final_development_opportunity_flag', {'True'})
    write_dataframe_to_excel(dev_df if not dev_df.empty else investment_df.head(1), FINAL_DEV_XLSX, 'Final Dev Opps', {'bid_cost'}, wrap_cols, 'final_investment_category', fills, 'final_development_opportunity_flag', {'True'})
    write_dataframe_to_excel(good_df, FINAL_GOOD_XLSX, 'Final Good', {'bid_cost'}, wrap_cols, 'final_investment_category', fills, 'final_development_opportunity_flag', {'True'})
    write_dataframe_to_excel(bad_df, FINAL_BAD_XLSX, 'Final Bad Risk', {'bid_cost'}, wrap_cols, 'final_investment_category', fills, 'final_development_opportunity_flag', {'True'})

    for path in [FINAL_INVESTMENT_XLSX, FINAL_MANUAL_XLSX, FINAL_DEV_XLSX, FINAL_GOOD_XLSX, FINAL_BAD_XLSX]:
        result = validate_workbook(path)
        print(path.name, result)


if __name__ == '__main__':
    main()
