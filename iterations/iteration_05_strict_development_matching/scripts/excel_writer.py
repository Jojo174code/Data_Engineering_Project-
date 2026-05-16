from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common_iter_utils import OUTPUT_DIR, CLEANED_DIR, validate_workbook, write_dataframe_to_excel

FILTERED_CSV = CLEANED_DIR / 'filtered_properties_3000_to_8000.csv'
AI_CSV = CLEANED_DIR / 'ai_property_reviews.csv'
INVESTMENT_XLSX = OUTPUT_DIR / 'investment_ranked_properties_strict.xlsx'
MANUAL_XLSX = OUTPUT_DIR / 'manual_review_top_candidates_strict.xlsx'
DEV_OPP_XLSX = OUTPUT_DIR / 'development_opportunity_properties_strict.xlsx'

CATEGORY_PRIORITY = {'Good Investment': 0, 'Strong Manual Review Candidate': 1, 'Mid Investment': 2, 'Bad Investment': 3}
MATCH_PRIORITY = {'Strong Match': 0, 'Possible Match': 1, 'No Clear Match': 2, 'Unknown': 3}
QUALITY_PRIORITY = {'High': 0, 'Medium': 1, 'Low': 2, 'Invalid Weak Match': 3}
CONF_PRIORITY = {'High': 0, 'Medium': 1, 'Low': 2}


def main():
    filtered_df = pd.read_csv(FILTERED_CSV)
    ai_df = pd.read_csv(AI_CSV)
    stale_ai_cols = [
        'ai_review_score', 'investment_category', 'manual_review_flag', 'recommendation', 'development_opportunity_flag',
        'development_opportunity_reason', 'reasoning_summary', 'key_risks', 'missing_information', 'next_due_diligence_step', 'confidence_level'
    ]
    filtered_df = filtered_df.drop(columns=[col for col in stale_ai_cols if col in filtered_df.columns], errors='ignore')
    merged = filtered_df.merge(ai_df, on='parcel_id', how='left')

    merged['category_sort'] = merged['investment_category'].map(CATEGORY_PRIORITY).fillna(9)
    merged['dev_opp_sort'] = merged['development_opportunity_flag'].astype(str).map({'True': 0, 'False': 1}).fillna(1)
    merged['quality_sort'] = merged['development_match_quality'].map(QUALITY_PRIORITY).fillna(9)
    merged['conf_sort'] = merged['confidence_level'].map(CONF_PRIORITY).fillna(9)
    merged = merged.sort_values(by=['category_sort', 'dev_opp_sort', 'quality_sort', 'ai_review_score', 'bid_cost', 'conf_sort'], ascending=[True, True, True, False, True, True])

    investment_df = merged.copy()
    manual_df = investment_df[(investment_df['manual_review_flag'] == True) & (investment_df['investment_category'].isin(['Good Investment', 'Strong Manual Review Candidate', 'Mid Investment']))].copy()
    manual_df = manual_df.sort_values(by=['category_sort', 'dev_opp_sort', 'quality_sort', 'ai_review_score', 'bid_cost', 'conf_sort'], ascending=[True, True, True, False, True, True]).head(50)
    manual_df.insert(0, 'rank', range(1, len(manual_df) + 1))

    dev_opp_df = investment_df[investment_df['development_match_strength'].isin(['Strong Match', 'Possible Match'])].copy()
    dev_opp_df = dev_opp_df[dev_opp_df['development_match_quality'] != 'Invalid Weak Match'].copy()
    dev_opp_df['match_sort'] = dev_opp_df['development_match_strength'].map(MATCH_PRIORITY).fillna(9)
    dev_opp_df['quality_sort'] = dev_opp_df['development_match_quality'].map(QUALITY_PRIORITY).fillna(9)
    dev_opp_df = dev_opp_df.sort_values(by=['match_sort', 'quality_sort', 'ai_review_score', 'bid_cost'], ascending=[True, True, False, True])

    helper_cols = ['category_sort', 'dev_opp_sort', 'quality_sort', 'conf_sort', 'match_sort']
    investment_df = investment_df.drop(columns=[c for c in helper_cols if c in investment_df.columns], errors='ignore')
    manual_df = manual_df.drop(columns=[c for c in helper_cols if c in manual_df.columns], errors='ignore')
    dev_opp_df = dev_opp_df.drop(columns=[c for c in helper_cols if c in dev_opp_df.columns], errors='ignore')

    wrap_cols = {
        'legal_description', 'development_match_reason', 'development_match_warning', 'development_summary', 'development_opportunity_reason',
        'reasoning_summary', 'key_risks', 'missing_information', 'next_due_diligence_step', 'raw_text'
    }
    fills = {'Good Investment': 'C6EFCE', 'Strong Manual Review Candidate': 'D9EAF7', 'Mid Investment': 'FFEB9C', 'Bad Investment': 'FFC7CE'}

    write_dataframe_to_excel(investment_df, INVESTMENT_XLSX, 'Invest Ranked', {'bid_cost'}, wrap_cols, 'investment_category', fills, 'development_opportunity_flag', {'True'})
    write_dataframe_to_excel(manual_df, MANUAL_XLSX, 'Manual Review', {'bid_cost'}, wrap_cols, 'investment_category', fills, 'development_opportunity_flag', {'True'})
    if dev_opp_df.empty:
        dev_opp_df = investment_df.head(1).copy()
    write_dataframe_to_excel(dev_opp_df, DEV_OPP_XLSX, 'Dev Opportunities', {'bid_cost'}, wrap_cols, 'investment_category', fills, 'development_opportunity_flag', {'True'})

    for path in [INVESTMENT_XLSX, MANUAL_XLSX, DEV_OPP_XLSX]:
        print(path.name, validate_workbook(path))


if __name__ == '__main__':
    main()
