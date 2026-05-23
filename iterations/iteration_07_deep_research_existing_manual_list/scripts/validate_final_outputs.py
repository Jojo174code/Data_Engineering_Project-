#!/usr/bin/env python3
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / 'cleaned_data'
OUT = ROOT / 'output_excel'
LOG = ROOT / 'logs' / 'validation_report.txt'
REQUIRED_FILES = [
    CLEAN / 'parsed_manual_review_list.csv',
    CLEAN / 'assessor_property_results.csv',
    CLEAN / 'neighborhoodscout_results.csv',
    CLEAN / 'map_location_intelligence.csv',
    CLEAN / 'final_combined_research.csv',
    CLEAN / 'ai_deep_property_reviews.csv',
]
EXCEL_FILES = [
    OUT / 'final_deep_property_rankings.xlsx',
    OUT / 'top_ai_upgrade_candidates.xlsx',
    OUT / 'top_ai_downgrade_candidates.xlsx',
    OUT / 'final_purple_green_watchlist.xlsx',
    OUT / 'final_yellow_mid_watchlist.xlsx',
    OUT / 'final_red_avoid_or_high_risk_list.xlsx',
]
REQ_COLS = [
    'rank','parcel_id','property_address','bid_cost','property_type','user_color_rating','user_rating_meaning','previous_final_investment_category','previous_ai_review_score',
    'deep_rule_score_1_to_10','deep_rule_color_rating','ai_score_1_to_10','ai_color_rating','ai_category','rating_change_from_previous','agree_with_user_rating','assessor_market_value',
    'assessor_total_assessed_value','assessor_land_value','assessor_improvement_value','bid_to_assessor_market_value_ratio','value_spread_estimate','assessor_property_type','assessor_year_built',
    'assessor_square_feet','crime_risk_rating','real_estate_trend_direction','location_strength_rating','nearby_schools','nearby_major_employers','nearby_hospitals','nearby_universities',
    'nearby_retail_or_grocery','nearby_highways_or_major_roads','negative_location_flags','investment_summary','key_positive_signals','key_risks','missing_information','next_due_diligence_step',
    'confidence_level','assessor_source_url','neighborhoodscout_source_url'
]


def fail(msg):
    raise SystemExit(msg)


def main():
    for path in REQUIRED_FILES + EXCEL_FILES:
        if not path.exists():
            fail(f'Missing required file: {path}')

    for path in REQUIRED_FILES:
        df = pd.read_csv(path)
        if df.empty:
            fail(f'CSV has no rows: {path}')

    main_df = pd.read_excel(OUT / 'final_deep_property_rankings.xlsx')
    missing = [c for c in REQ_COLS if c not in main_df.columns]
    if missing:
        fail(f'Main workbook missing columns: {missing}')

    for path in EXCEL_FILES:
        wb = load_workbook(path)
        ws = wb.active
        if ws.max_row <= 1:
            fail(f'Excel workbook has no data rows: {path}')

    ai = pd.read_csv(CLEAN / 'ai_deep_property_reviews.csv')
    if not set(ai['ai_color_rating']).issubset({'Purple','Green','Yellow','Red'}):
        fail('Invalid ai_color_rating values present')
    if not set(ai['ai_category']).issubset({'Amazing','Great','Mid','Avoid'}):
        fail('Invalid ai_category values present')
    if not set(ai['confidence_level']).issubset({'High','Medium','Low'}):
        fail('Invalid confidence_level values present')

    assessor = pd.read_csv(CLEAN / 'assessor_property_results.csv')
    ns = pd.read_csv(CLEAN / 'neighborhoodscout_results.csv')
    maps = pd.read_csv(CLEAN / 'map_location_intelligence.csv')

    git_status = Path('.git')
    staged_env = False
    staged_venv = False
    try:
        import subprocess
        out = subprocess.check_output(['git','status','--short'], text=True)
        staged_env = '.env' in out
        staged_venv = '.venv' in out
    except Exception:
        pass
    if staged_env or staged_venv:
        fail('Validation failed because .env or .venv appears in git status output')

    report = [
        f'total properties reviewed: {len(ai)}',
        f"AI Red count: {(ai['ai_color_rating'] == 'Red').sum()}",
        f"AI Yellow count: {(ai['ai_color_rating'] == 'Yellow').sum()}",
        f"AI Green count: {(ai['ai_color_rating'] == 'Green').sum()}",
        f"AI Purple count: {(ai['ai_color_rating'] == 'Purple').sum()}",
        f"upgrades count: {(ai['rating_change_from_previous'] == 'Upgrade').sum()}",
        f"downgrades count: {(ai['rating_change_from_previous'] == 'Downgrade').sum()}",
        f"same rating count: {(ai['rating_change_from_previous'] == 'Same').sum()}",
        f"assessor matches: {assessor['assessor_match_status'].astype(str).str.contains('Search Reachable|Address Fallback', regex=True).sum()}",
        f"assessor failed matches: {assessor['assessor_match_status'].isin(['No Match','Blocked']).sum()}",
        f"NeighborhoodScout successful matches: {len(ns)}",
        f"NeighborhoodScout unavailable count: {ns['neighborhoodscout_match_status'].isin(['Unavailable','Blocked']).sum()}",
        f"geocoding success count: {(maps['geocode_status'] == 'Success').sum()}",
        'validation PASS'
    ]
    LOG.write_text('\n'.join(report))
    print('PASS')


if __name__ == '__main__':
    main()
