#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import pandas as pd

from common_custom_33 import CLEANED_DIR, LOG_DIR, clean_text, ensure_dirs, json_line, normalize_address, write_log

BASE_CSV = CLEANED_DIR / 'custom_33_base.csv'
OUT_CSV = CLEANED_DIR / 'custom_33_enriched_from_prior_iterations.csv'
LOG_FILE = LOG_DIR / 'enrichment_log.txt'

SOURCE_FILES = [
    Path('iterations/iteration_07_deep_research_existing_manual_list/cleaned_data/final_combined_research.csv'),
    Path('iterations/iteration_06_final_robust_ai_due_diligence/cleaned_data/final_rule_based_scores.csv'),
    Path('iterations/iteration_06_final_robust_ai_due_diligence/cleaned_data/final_ai_property_reviews.csv'),
    Path('iterations/iteration_10_900_to_1000_top50_crime_economic_ai/cleaned_data/final_top50_crime_economic_ai.csv'),
    Path('iterations/iteration_11_1000_to_1500_top50_crime_economic_ai/cleaned_data/final_top50_crime_economic_ai.csv'),
    Path('iterations/iteration_08_1500_to_2000_top50/cleaned_data/ranked_properties_1500_to_2000.csv'),
]

TARGET_COLUMNS = [
    'legal_description', 'property_type', 'source_page', 'raw_text', 'extraction_confidence',
    'previous_ai_score', 'previous_category', 'previous_recommendation', 'previous_reasoning_summary',
    'previous_key_risks', 'previous_confidence_level', 'prior_geocode_status', 'prior_latitude',
    'prior_longitude', 'prior_neighborhood_or_area', 'prior_crime_risk_level', 'prior_crime_score',
    'prior_economic_risk_level', 'prior_economic_strength_score', 'prior_median_household_income',
    'prior_poverty_rate', 'prior_median_home_value', 'prior_vacancy_rate',
]


def pick(row: pd.Series, *names: str) -> str:
    for name in names:
        if name in row.index:
            value = clean_text(row.get(name))
            if value not in {'Unknown', 'Unknown.'}:
                return value
    return 'Unknown'


def standardize_source(df: pd.DataFrame, label: str) -> pd.DataFrame:
    data = pd.DataFrame()
    data['parcel_id'] = df['parcel_id'].astype(str).str.strip() if 'parcel_id' in df.columns else ''
    data['normalized_address'] = df['property_address'].apply(normalize_address) if 'property_address' in df.columns else 'Unknown'
    data['legal_description'] = df.apply(lambda r: pick(r, 'legal_description'), axis=1)
    data['property_type'] = df.apply(lambda r: pick(r, 'property_type', 'assessor_property_type'), axis=1)
    data['source_page'] = df.apply(lambda r: pick(r, 'source_page'), axis=1)
    data['raw_text'] = df.apply(lambda r: pick(r, 'raw_text'), axis=1)
    data['extraction_confidence'] = df.apply(lambda r: pick(r, 'extraction_confidence', 'data_confidence', 'final_confidence_level', 'confidence_level'), axis=1)
    data['previous_ai_score'] = df.apply(lambda r: pick(r, 'final_ai_review_score', 'ai_area_adjusted_score', 'previous_ai_score', 'final_score'), axis=1)
    data['previous_category'] = df.apply(lambda r: pick(r, 'final_investment_category', 'final_category', 'rank_category', 'deep_rule_category', 'final_rule_based_category'), axis=1)
    data['previous_recommendation'] = df.apply(lambda r: pick(r, 'final_recommendation', 'recommendation', 'manual_review_flag'), axis=1)
    data['previous_reasoning_summary'] = df.apply(lambda r: pick(r, 'final_reasoning_summary', 'reasoning_summary', 'ranking_reason', 'deep_rule_reasoning'), axis=1)
    data['previous_key_risks'] = df.apply(lambda r: pick(r, 'final_key_risks', 'key_risks', 'deep_rule_key_risks', 'obvious_red_flags'), axis=1)
    data['previous_confidence_level'] = df.apply(lambda r: pick(r, 'final_confidence_level', 'confidence_level', 'location_confidence', 'data_confidence'), axis=1)
    data['prior_geocode_status'] = df.apply(lambda r: pick(r, 'geocode_status'), axis=1)
    data['prior_latitude'] = df.apply(lambda r: pick(r, 'latitude'), axis=1)
    data['prior_longitude'] = df.apply(lambda r: pick(r, 'longitude'), axis=1)
    data['prior_neighborhood_or_area'] = df.apply(lambda r: pick(r, 'neighborhood_or_area', 'neighborhood_or_area_used'), axis=1)
    data['prior_crime_risk_level'] = df.apply(lambda r: pick(r, 'crime_risk_level', 'crime_risk_rating', 'final_crime_risk_estimate'), axis=1)
    data['prior_crime_score'] = df.apply(lambda r: pick(r, 'crime_risk_score', 'crime_score'), axis=1)
    data['prior_economic_risk_level'] = df.apply(lambda r: pick(r, 'economic_risk_level'), axis=1)
    data['prior_economic_strength_score'] = df.apply(lambda r: pick(r, 'economic_strength_score'), axis=1)
    data['prior_median_household_income'] = df.apply(lambda r: pick(r, 'median_household_income'), axis=1)
    data['prior_poverty_rate'] = df.apply(lambda r: pick(r, 'poverty_rate'), axis=1)
    data['prior_median_home_value'] = df.apply(lambda r: pick(r, 'median_home_value', 'assessor_market_value'), axis=1)
    data['prior_vacancy_rate'] = df.apply(lambda r: pick(r, 'vacancy_rate'), axis=1)
    data['match_source_file'] = label
    return data


def main() -> None:
    ensure_dirs()
    base = pd.read_csv(BASE_CSV)
    base['normalized_address'] = base['property_address'].apply(normalize_address)

    source_frames = []
    used_sources = []
    for path in SOURCE_FILES:
        if path.exists():
            df = pd.read_csv(path)
            source_frames.append(standardize_source(df, str(path)))
            used_sources.append(str(path))
    source_all = pd.concat(source_frames, ignore_index=True).fillna('Unknown') if source_frames else pd.DataFrame(columns=['parcel_id', 'normalized_address'] + TARGET_COLUMNS + ['match_source_file'])

    enriched_rows = []
    matched_parcel = 0
    matched_address = 0
    unmatched = 0
    logs = [f'total properties: {len(base)}']

    for _, row in base.iterrows():
        result = row.to_dict()
        matches = source_all[source_all['parcel_id'].astype(str).str.strip() == str(row['parcel_id']).strip()]
        match_method = 'unmatched'
        if not matches.empty:
            picked = matches.iloc[0]
            matched_parcel += 1
            match_method = 'parcel_id'
        else:
            addr_matches = source_all[source_all['normalized_address'] == row['normalized_address']]
            if not addr_matches.empty:
                picked = addr_matches.iloc[0]
                matched_address += 1
                match_method = 'address'
            else:
                picked = None
                unmatched += 1

        for col in TARGET_COLUMNS:
            result[col] = clean_text(picked[col]) if picked is not None and col in picked.index else 'Unknown'
        result['enrichment_match_method'] = match_method
        result['enrichment_source_file'] = clean_text(picked['match_source_file']) if picked is not None else 'Unknown'
        enriched_rows.append(result)
        logs.append(json_line({
            'parcel_id': row['parcel_id'],
            'property_address': row['property_address'],
            'match_method': match_method,
            'source_file': result['enrichment_source_file'],
        }))

    out_df = pd.DataFrame(enriched_rows)
    out_df.drop(columns=['normalized_address'], inplace=True, errors='ignore')
    out_df.to_csv(OUT_CSV, index=False)

    logs[0:1] = [
        f'total properties: {len(base)}',
        f'matched by parcel ID: {matched_parcel}',
        f'matched by address: {matched_address}',
        f'unmatched: {unmatched}',
        f'source files used: {"; ".join(used_sources)}',
    ]
    write_log(LOG_FILE, logs)
    print(f'enriched_rows={len(out_df)} parcel_matches={matched_parcel} address_matches={matched_address} unmatched={unmatched}')


if __name__ == '__main__':
    main()
