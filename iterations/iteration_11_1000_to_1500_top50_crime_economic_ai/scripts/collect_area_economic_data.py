#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import requests

ITERATION_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
LOG_DIR = ITERATION_ROOT / 'logs'
IN_CSV = CLEANED_DIR / 'geocoded_properties.csv'
OUT_CSV = CLEANED_DIR / 'property_area_intelligence.csv'
LOG_FILE = LOG_DIR / 'economic_data_log.txt'

TABLE_IDS = 'B19013,B17001,B23025,B25077,B25064,B25002,B25003,B01003'
API_URL = 'https://api.censusreporter.org/1.0/data/show/latest'
HEADERS = {'User-Agent': 'OpenClawIteration10/1.0 (economic intelligence)'}


def clean_text(value, default='Unknown.'):
    if pd.isna(value):
        return default
    text = str(value).strip()
    if not text or text.lower() == 'nan':
        return default
    return text


def numeric(value):
    try:
        return float(value)
    except Exception:
        return None


def safe_ratio(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def tract_geo_id(row: pd.Series):
    tract = clean_text(row.get('census_tract'))
    if tract not in {'Unknown.', 'Unknown'} and tract.isdigit() and len(tract) == 11:
        return f'14000US{tract}', 'Tract'
    return None, None


def zip_geo_id(row: pd.Series):
    for field in ['confirmed_zip_code', 'zip_code']:
        zip_code = ''.join(ch for ch in clean_text(row.get(field)) if ch.isdigit())
        if len(zip_code) == 5:
            return f'86000US{zip_code}', 'ZIP'
    return None, None


def fetch_census_reporter(geo_id: str):
    response = requests.get(API_URL, params={'table_ids': TABLE_IDS, 'geo_ids': geo_id}, headers=HEADERS, timeout=60)
    response.raise_for_status()
    return response.json()


def estimate(data: dict, geo_key: str, table: str, code: str):
    try:
        return numeric(data['data'][geo_key][table]['estimate'][code])
    except Exception:
        return None


def percent_to_score(value, low_good, med_good, high_good):
    if value is None:
        return None
    pct = value * 100
    if pct <= low_good:
        return 10.0
    if pct <= med_good:
        return 8.0
    if pct <= high_good:
        return 6.0
    if pct <= high_good + 10:
        return 4.0
    return 2.0


def level_from_score(score, confidence):
    if score is None:
        return 'Unknown'
    if confidence == 'Low' and score < 5.5:
        return 'High'
    if score >= 7.0:
        return 'Low'
    if score >= 5.0:
        return 'Medium'
    return 'High'


def compute_economic_strength(metrics: dict, confidence: str):
    scores = []

    income = metrics['median_household_income']
    if income is not None:
        if income >= 80000:
            scores.append(10.0)
        elif income >= 65000:
            scores.append(8.5)
        elif income >= 50000:
            scores.append(7.0)
        elif income >= 40000:
            scores.append(5.5)
        else:
            scores.append(3.5)

    scores.append(percent_to_score(metrics['poverty_rate'], 10, 18, 25)) if metrics['poverty_rate'] is not None else None
    scores.append(percent_to_score(metrics['unemployment_rate'], 4.5, 6.5, 9.0)) if metrics['unemployment_rate'] is not None else None
    scores.append(percent_to_score(metrics['vacancy_rate'], 8.0, 12.0, 18.0)) if metrics['vacancy_rate'] is not None else None

    owner_occ = metrics['owner_occupied_rate']
    if owner_occ is not None:
        pct = owner_occ * 100
        if pct >= 70:
            scores.append(10.0)
        elif pct >= 58:
            scores.append(8.5)
        elif pct >= 45:
            scores.append(7.0)
        elif pct >= 35:
            scores.append(5.5)
        else:
            scores.append(3.0)

    home_value = metrics['median_home_value']
    if home_value is not None:
        if home_value >= 300000:
            scores.append(8.0)
        elif home_value >= 175000:
            scores.append(7.5)
        elif home_value >= 100000:
            scores.append(6.5)
        elif home_value >= 70000:
            scores.append(5.0)
        else:
            scores.append(3.5)

    usable_scores = [s for s in scores if s is not None]
    if not usable_scores:
        return None
    base = sum(usable_scores) / len(usable_scores)
    if confidence == 'Medium':
        base -= 0.5
    if confidence == 'Low':
        base -= 1.0
    return round(max(1.0, min(10.0, base)), 2)


def main():
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(IN_CSV)
    cache = {}
    out_rows = []
    logs = []

    for _, row in df.iterrows():
        geo_id, geo_type = tract_geo_id(row)
        confidence = 'High'
        if not geo_id:
            geo_id, geo_type = zip_geo_id(row)
            confidence = 'Medium' if geo_id else 'Unknown'
        if clean_text(row.get('geocode_confidence')) == 'Low' and confidence == 'High':
            confidence = 'Medium'

        result = row.to_dict()
        metrics = {
            'median_household_income': None,
            'poverty_rate': None,
            'unemployment_rate': None,
            'median_home_value': None,
            'median_gross_rent': None,
            'vacancy_rate': None,
            'owner_occupied_rate': None,
            'population_estimate': None,
        }
        release_name = 'Unknown.'
        release_year = 'Unknown.'

        if geo_id:
            try:
                if geo_id not in cache:
                    cache[geo_id] = fetch_census_reporter(geo_id)
                payload = cache[geo_id]
                release_name = clean_text(payload.get('release', {}).get('name'))
                release_year = clean_text(payload.get('release', {}).get('years'))
                metrics['median_household_income'] = estimate(payload, geo_id, 'B19013', 'B19013001')
                poverty_total = estimate(payload, geo_id, 'B17001', 'B17001001')
                poverty_below = estimate(payload, geo_id, 'B17001', 'B17001002')
                metrics['poverty_rate'] = safe_ratio(poverty_below, poverty_total)
                labor_force = estimate(payload, geo_id, 'B23025', 'B23025003')
                unemployed = estimate(payload, geo_id, 'B23025', 'B23025005')
                metrics['unemployment_rate'] = safe_ratio(unemployed, labor_force)
                metrics['median_home_value'] = estimate(payload, geo_id, 'B25077', 'B25077001')
                metrics['median_gross_rent'] = estimate(payload, geo_id, 'B25064', 'B25064001')
                housing_units = estimate(payload, geo_id, 'B25002', 'B25002001')
                vacant_units = estimate(payload, geo_id, 'B25002', 'B25002003')
                metrics['vacancy_rate'] = safe_ratio(vacant_units, housing_units)
                occupied_units = estimate(payload, geo_id, 'B25003', 'B25003001')
                owner_units = estimate(payload, geo_id, 'B25003', 'B25003002')
                metrics['owner_occupied_rate'] = safe_ratio(owner_units, occupied_units)
                metrics['population_estimate'] = estimate(payload, geo_id, 'B01003', 'B01003001')
            except Exception:
                geo_id = None
                geo_type = None
                confidence = 'Unknown'

        economic_score = compute_economic_strength(metrics, confidence if confidence != 'Unknown' else 'Low')
        economic_risk_level = level_from_score(economic_score, confidence) if geo_id else 'Unknown'
        economic_source = f'{release_name} via Census Reporter API ({geo_type}-level)' if geo_id else 'Unknown.'

        result.update({
            'median_household_income': round(metrics['median_household_income'], 2) if metrics['median_household_income'] is not None else 'Unknown.',
            'poverty_rate': round(metrics['poverty_rate'], 4) if metrics['poverty_rate'] is not None else 'Unknown.',
            'unemployment_rate': round(metrics['unemployment_rate'], 4) if metrics['unemployment_rate'] is not None else 'Unknown.',
            'median_home_value': round(metrics['median_home_value'], 2) if metrics['median_home_value'] is not None else 'Unknown.',
            'median_gross_rent': round(metrics['median_gross_rent'], 2) if metrics['median_gross_rent'] is not None else 'Unknown.',
            'vacancy_rate': round(metrics['vacancy_rate'], 4) if metrics['vacancy_rate'] is not None else 'Unknown.',
            'owner_occupied_rate': round(metrics['owner_occupied_rate'], 4) if metrics['owner_occupied_rate'] is not None else 'Unknown.',
            'population_estimate': round(metrics['population_estimate'], 0) if metrics['population_estimate'] is not None else 'Unknown.',
            'economic_data_year': release_year,
            'economic_source': economic_source,
            'economic_confidence': confidence,
            'economic_strength_score': economic_score if economic_score is not None else 'Unknown.',
            'economic_risk_level': economic_risk_level,
        })
        out_rows.append(result)
        logs.append(json.dumps({
            'parcel_id': result['parcel_id'],
            'geo_basis': geo_id or 'Unknown.',
            'economic_source': economic_source,
            'economic_confidence': confidence,
            'median_household_income': result['median_household_income'],
            'poverty_rate': result['poverty_rate'],
            'unemployment_rate': result['unemployment_rate'],
            'median_home_value': result['median_home_value'],
            'vacancy_rate': result['vacancy_rate'],
            'owner_occupied_rate': result['owner_occupied_rate'],
            'economic_strength_score': result['economic_strength_score'],
            'economic_risk_level': result['economic_risk_level'],
        }, ensure_ascii=False))

    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(OUT_CSV, index=False)
    coverage = int((out_df['economic_source'] != 'Unknown.').sum())
    LOG_FILE.write_text('\n'.join([
        f'input row count: {len(df)}',
        f'economic coverage count: {coverage}',
        *logs,
    ]))
    print(f'economic_coverage={coverage}/{len(df)}')


if __name__ == '__main__':
    main()
