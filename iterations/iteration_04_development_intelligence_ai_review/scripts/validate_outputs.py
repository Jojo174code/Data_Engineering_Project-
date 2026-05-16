from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common_iter_utils import ALLOWED_CATEGORIES, ALLOWED_CONFIDENCE, ALLOWED_RECOMMENDATIONS, CLEANED_DIR, LOG_DIR, OUTPUT_DIR, validate_workbook, write_log

CLEANED_CSV = CLEANED_DIR / 'cleaned_auction_properties.csv'
FILTERED_CSV = CLEANED_DIR / 'filtered_properties_3000_to_8000.csv'
DEV_CSV = CLEANED_DIR / 'tulsa_development_intelligence.csv'
MATCH_CSV = CLEANED_DIR / 'property_development_matches.csv'
AI_CSV = CLEANED_DIR / 'ai_property_reviews.csv'
FILTERED_XLSX = OUTPUT_DIR / 'filtered_properties_3000_to_8000.xlsx'
INVESTMENT_XLSX = OUTPUT_DIR / 'investment_ranked_properties.xlsx'
MANUAL_XLSX = OUTPUT_DIR / 'manual_review_top_candidates.xlsx'
DEV_OPP_XLSX = OUTPUT_DIR / 'development_opportunity_properties.xlsx'
LOG_FILE = LOG_DIR / 'validation_report.txt'


def main():
    cleaned = pd.read_csv(CLEANED_CSV)
    filtered = pd.read_csv(FILTERED_CSV)
    dev = pd.read_csv(DEV_CSV)
    matches = pd.read_csv(MATCH_CSV)
    ai = pd.read_csv(AI_CSV)
    investment = pd.read_excel(INVESTMENT_XLSX)
    manual = pd.read_excel(MANUAL_XLSX)
    dev_opp = pd.read_excel(DEV_OPP_XLSX)

    filtered_wb = validate_workbook(FILTERED_XLSX)
    investment_wb = validate_workbook(INVESTMENT_XLSX)
    manual_wb = validate_workbook(MANUAL_XLSX)
    dev_opp_wb = validate_workbook(DEV_OPP_XLSX)

    invalid_categories = int((~investment['investment_category'].isin(ALLOWED_CATEGORIES)).sum())
    invalid_recs = int((~investment['recommendation'].isin(ALLOWED_RECOMMENDATIONS)).sum())
    invalid_conf = int((~investment['confidence_level'].isin(ALLOWED_CONFIDENCE)).sum())
    missing_source_urls = int((dev['source_url'].fillna('').astype(str).str.strip() == '').sum())
    missing_dev_reason = int(((investment['development_opportunity_flag'] == True) & (investment['development_opportunity_reason'].fillna('').astype(str).str.strip() == '')).sum())

    git_status = subprocess.run(['git', 'status', '--short'], cwd=CLEANED_DIR.parents[2], capture_output=True, text=True)
    env_staged = any(line.strip().endswith('.env') or '.venv' in line for line in git_status.stdout.splitlines())

    passed = all([
        len(cleaned) > 0,
        len(filtered) > 0,
        len(dev) > 0,
        len(matches) > 0,
        len(ai) > 0,
        filtered_wb['max_row'] > 1,
        investment_wb['max_row'] > 1,
        manual_wb['max_row'] > 1,
        dev_opp_wb['max_row'] > 1,
        invalid_categories == 0,
        invalid_recs == 0,
        invalid_conf == 0,
        missing_source_urls == 0,
        missing_dev_reason == 0,
        not env_staged,
    ])

    lines = [
        f'cleaned CSV row count: {len(cleaned)}',
        f'filtered CSV row count: {len(filtered)}',
        f'development intelligence row count: {len(dev)}',
        f'property development match count: {len(matches)}',
        f'AI review row count: {len(ai)}',
        f'filtered Excel row count: {filtered_wb["max_row"]}',
        f'investment Excel row count: {investment_wb["max_row"]}',
        f'manual review Excel row count: {manual_wb["max_row"]}',
        f'development opportunity Excel row count: {dev_opp_wb["max_row"]}',
        f'Good Investment count: {(investment["investment_category"] == "Good Investment").sum()}',
        f'Strong Manual Review Candidate count: {(investment["investment_category"] == "Strong Manual Review Candidate").sum()}',
        f'Mid Investment count: {(investment["investment_category"] == "Mid Investment").sum()}',
        f'Bad Investment count: {(investment["investment_category"] == "Bad Investment").sum()}',
        f'development opportunity count: {(investment["development_opportunity_flag"] == True).sum()}',
        f'invalid category count: {invalid_categories}',
        f'invalid recommendation count: {invalid_recs}',
        f'invalid confidence count: {invalid_conf}',
        f'development items missing source_url: {missing_source_urls}',
        f'development opportunity rows missing reason: {missing_dev_reason}',
        f'.env or .venv staged: {env_staged}',
        f'validation {"PASS" if passed else "FAIL"}',
    ]
    for line in lines:
        print(line)
    write_log(LOG_FILE, lines)
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
