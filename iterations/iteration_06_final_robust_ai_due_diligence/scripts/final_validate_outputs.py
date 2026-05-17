from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

ITERATION_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
OUTPUT_DIR = ITERATION_ROOT / 'output_excel'
LOG_DIR = ITERATION_ROOT / 'logs'

PREV_UTILS_DIR = ITERATION_ROOT.parents[0] / 'iteration_05_strict_development_matching' / 'scripts'
if str(PREV_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(PREV_UTILS_DIR))

from common_iter_utils import validate_workbook  # noqa: E402

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
LOG_FILE = LOG_DIR / 'final_validation_report.txt'

ALLOWED_CATEGORIES = {'Good Investment', 'Strong Manual Review Candidate', 'Mid Investment', 'Bad Investment'}
ALLOWED_RECOMMENDATIONS = {'Bid Candidate', 'Research First', 'Drive By', 'Watch', 'Avoid'}
ALLOWED_CONFIDENCE = {'High', 'Medium', 'Low'}
EXPECTED_COLUMNS = {
    'parcel_id', 'owner_name', 'property_address', 'city', 'state', 'zip_code', 'bid_cost', 'legal_description', 'property_type',
    'source_page', 'extraction_confidence', 'final_development_match_strength', 'final_matched_development_area',
    'final_matched_project_or_area_name', 'final_development_source_title', 'final_development_source_url',
    'final_development_match_reason', 'final_development_warning', 'property_geocode_status', 'development_geocode_status',
    'estimated_distance_miles', 'geocode_confidence', 'distance_verified_match', 'corrected_development_match_strength',
    'final_rule_based_score', 'final_rule_based_category', 'final_ai_review_score', 'final_investment_category',
    'final_manual_review_flag', 'final_recommendation', 'final_development_opportunity_flag', 'final_development_opportunity_reason',
    'final_reasoning_summary', 'final_key_risks', 'final_missing_information', 'final_next_due_diligence_step',
    'final_confidence_level', 'raw_text'
}


def main():
    base = pd.read_csv(BASE_CSV)
    matches = pd.read_csv(MATCH_CSV)
    geo = pd.read_csv(GEOCODE_CSV)
    scores = pd.read_csv(SCORES_CSV)
    ai = pd.read_csv(AI_CSV)
    investment = pd.read_excel(FINAL_INVESTMENT_XLSX)
    manual = pd.read_excel(FINAL_MANUAL_XLSX)
    dev = pd.read_excel(FINAL_DEV_XLSX)
    good = pd.read_excel(FINAL_GOOD_XLSX)
    bad = pd.read_excel(FINAL_BAD_XLSX)

    merged = base[['parcel_id', 'previous_investment_category']].merge(matches[['parcel_id', 'final_development_match_strength', 'weak_match_removed_flag']], on='parcel_id', how='left')
    merged = merged.merge(geo[['parcel_id', 'property_geocode_status', 'corrected_development_match_strength']], on='parcel_id', how='left')
    merged = merged.merge(ai, on='parcel_id', how='left')

    workbooks = {
        'final_investment_ranked_properties.xlsx': validate_workbook(FINAL_INVESTMENT_XLSX),
        'final_manual_review_top_candidates.xlsx': validate_workbook(FINAL_MANUAL_XLSX),
        'final_development_opportunity_properties.xlsx': validate_workbook(FINAL_DEV_XLSX),
        'final_good_investment_candidates.xlsx': validate_workbook(FINAL_GOOD_XLSX),
        'final_bad_high_risk_properties.xlsx': validate_workbook(FINAL_BAD_XLSX),
    }

    missing_columns = sorted(EXPECTED_COLUMNS - set(investment.columns))
    invalid_categories = int((~investment['final_investment_category'].isin(ALLOWED_CATEGORIES)).sum())
    invalid_recs = int((~investment['final_recommendation'].isin(ALLOWED_RECOMMENDATIONS)).sum())
    invalid_conf = int((~investment['final_confidence_level'].isin(ALLOWED_CONFIDENCE)).sum())
    missing_dev_reason = int(((investment['final_development_opportunity_flag'] == True) & investment['final_development_opportunity_reason'].fillna('').astype(str).str.strip().eq('')).sum())
    bad_good_conf = int(((investment['final_investment_category'] == 'Good Investment') & (~investment['final_confidence_level'].isin(['High', 'Medium']))).sum())
    bad_good_match = int(((investment['final_investment_category'] == 'Good Investment') & (investment['corrected_development_match_strength'].isin(['No Clear Match', 'Unknown']))).sum())

    git_status = subprocess.run(['git', 'status', '--short'], cwd=ITERATION_ROOT.parents[1], capture_output=True, text=True)
    staged_env = any(line.strip().endswith('.env') or '.venv' in line for line in git_status.stdout.splitlines())

    geocode_success = int((geo['property_geocode_status'] == 'Success').sum())
    geocode_failure = int((geo['property_geocode_status'] != 'Success').sum())
    final_strong = int((geo['corrected_development_match_strength'] == 'Strong Match').sum())
    final_possible = int((geo['corrected_development_match_strength'] == 'Possible Match').sum())
    final_no_clear = int((geo['corrected_development_match_strength'] == 'No Clear Match').sum())
    final_unknown = int((geo['corrected_development_match_strength'] == 'Unknown').sum())
    downgraded_previous_good = int(((merged['previous_investment_category'] == 'Good Investment') & (merged['final_investment_category'] != 'Good Investment')).sum())
    weak_removed = int(matches['weak_match_removed_flag'].fillna(False).astype(bool).sum())

    passed = all([
        len(base) > 0,
        len(matches) > 0,
        len(geo) > 0,
        len(scores) > 0,
        len(ai) > 0,
        all(card['max_row'] > 1 and card['max_column'] > 1 for card in workbooks.values()),
        not missing_columns,
        invalid_categories == 0,
        invalid_recs == 0,
        invalid_conf == 0,
        missing_dev_reason == 0,
        bad_good_conf == 0,
        bad_good_match == 0,
        not staged_env,
    ])

    lines = [
        f'total final properties: {len(investment)}',
        f'final manual review candidate count: {int((investment["final_manual_review_flag"] == True).sum())}',
        f'final development opportunity count: {int((investment["final_development_opportunity_flag"] == True).sum())}',
        f'final Good Investment count: {(investment["final_investment_category"] == "Good Investment").sum()}',
        f'final Strong Manual Review Candidate count: {(investment["final_investment_category"] == "Strong Manual Review Candidate").sum()}',
        f'final Mid Investment count: {(investment["final_investment_category"] == "Mid Investment").sum()}',
        f'final Bad Investment count: {(investment["final_investment_category"] == "Bad Investment").sum()}',
        f'number geocoded successfully: {geocode_success}',
        f'number geocoding failed: {geocode_failure}',
        f'final Strong Match count: {final_strong}',
        f'final Possible Match count: {final_possible}',
        f'final No Clear Match count: {final_no_clear}',
        f'final Unknown match count: {final_unknown}',
        f'number of weak matches removed: {weak_removed}',
        f'number of properties downgraded from previous Good: {downgraded_previous_good}',
        f'invalid category count: {invalid_categories}',
        f'invalid recommendation count: {invalid_recs}',
        f'invalid confidence count: {invalid_conf}',
        f'missing development opportunity reason count: {missing_dev_reason}',
        f'Good rows with invalid confidence count: {bad_good_conf}',
        f'Good rows relying on No Clear/Unknown development count: {bad_good_match}',
        f'missing expected output columns: {missing_columns}',
        f'.env or .venv staged: {staged_env}',
        f'validation {"PASS" if passed else "FAIL"}',
    ]

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for line in lines:
        print(line)
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
