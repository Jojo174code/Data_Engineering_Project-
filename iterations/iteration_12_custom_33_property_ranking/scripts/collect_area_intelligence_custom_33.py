#!/usr/bin/env python3
from __future__ import annotations

import re

import pandas as pd
import requests

from common_custom_33 import CLEANED_DIR, LOG_DIR, clean_text, ensure_dirs, safe_float, write_log

IN_CSV = CLEANED_DIR / 'custom_33_geocoded.csv'
OUT_CSV = CLEANED_DIR / 'custom_33_area_intelligence.csv'
LOG_FILE = LOG_DIR / 'area_intelligence_log.txt'
TABLE_IDS = 'B19013,B17001,B23025,B25077,B25064,B25002,B25003,B01003'
API_URL = 'https://api.censusreporter.org/1.0/data/show/latest'
HEADERS = {'User-Agent': 'OpenClawIteration12/1.0 (custom 33 area intelligence)'}
CITY_SLUGS = {'Tulsa': 'tulsa', 'Sand Springs': 'sand-springs', 'Bixby': 'bixby', 'Broken Arrow': 'broken-arrow'}


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
    if tract.isdigit() and len(tract) == 11:
        return f'14000US{tract}', 'Tract'
    return None, None


def zip_geo_id(row: pd.Series):
    zip_code = ''.join(ch for ch in clean_text(row.get('confirmed_zip_code')) if ch.isdigit())
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


def compute_economic_strength(metrics: dict, confidence: str):
    scores = []
    income = metrics['median_household_income']
    if income is not None:
        scores.append(10.0 if income >= 80000 else 8.5 if income >= 65000 else 7.0 if income >= 50000 else 5.5 if income >= 40000 else 3.5)
    if metrics['poverty_rate'] is not None:
        scores.append(percent_to_score(metrics['poverty_rate'], 10, 18, 25))
    if metrics['unemployment_rate'] is not None:
        scores.append(percent_to_score(metrics['unemployment_rate'], 4.5, 6.5, 9.0))
    if metrics['vacancy_rate'] is not None:
        scores.append(percent_to_score(metrics['vacancy_rate'], 8.0, 12.0, 18.0))
    owner_occ = metrics['owner_occupied_rate']
    if owner_occ is not None:
        pct = owner_occ * 100
        scores.append(10.0 if pct >= 70 else 8.5 if pct >= 58 else 7.0 if pct >= 45 else 5.5 if pct >= 35 else 3.0)
    home_value = metrics['median_home_value']
    if home_value is not None:
        scores.append(8.0 if home_value >= 300000 else 7.5 if home_value >= 175000 else 6.5 if home_value >= 100000 else 5.0 if home_value >= 70000 else 3.5)
    scores = [s for s in scores if s is not None]
    if not scores:
        return None
    base = sum(scores) / len(scores)
    if confidence == 'Medium':
        base -= 0.5
    if confidence == 'Low':
        base -= 1.0
    return round(max(1.0, min(10.0, base)), 2)


def economic_level(score):
    if score is None:
        return 'Unknown'
    if score >= 7.0:
        return 'Low'
    if score >= 5.0:
        return 'Medium'
    return 'High'


def infer_city(row: pd.Series) -> str:
    text = ' '.join([clean_text(row.get('city')), clean_text(row.get('geocode_display_name')), clean_text(row.get('neighborhood_or_area'))]).upper()
    if 'BIXBY' in text:
        return 'Bixby'
    if 'SAND SPRINGS' in text:
        return 'Sand Springs'
    if 'BROKEN ARROW' in text:
        return 'Broken Arrow'
    return 'Tulsa' if 'TULSA' in text or text else 'Unknown'


def parse_neighborhoodscout(city: str):
    slug = CITY_SLUGS.get(city)
    if not slug:
        return None
    url = f'https://www.neighborhoodscout.com/ok/{slug}/crime'
    response = requests.get(url, headers=HEADERS, timeout=45)
    response.raise_for_status()
    html = response.text
    safer_match = re.search(r'Safer than\s*<[^>]*>\s*([0-9]+)%', html, re.I | re.S)
    crime_rate_match = re.search(r'With a crime rate of ([0-9.]+) per one thousand residents', html, re.I)
    year_match = re.search(r'Most accurate\s+([0-9]{4})\s+crime rates', html, re.I)
    violent_match = re.search(r'violent crime .*? one in ([0-9,]+)', html, re.I)
    property_match = re.search(r'property crime .*? one in ([0-9,]+)', html, re.I)
    safer_pct = int(safer_match.group(1)) if safer_match else None
    overall_rate = float(crime_rate_match.group(1)) if crime_rate_match else None
    year = year_match.group(1) if year_match else 'Unknown'
    violent_ratio = violent_match.group(1).replace(',', '') if violent_match else None
    property_ratio = property_match.group(1).replace(',', '') if property_match else None
    if safer_pct is None and overall_rate is None:
        return None
    score = round(max(1.0, min(10.0, 1.5 + (safer_pct / 10.0))), 2) if safer_pct is not None else 'Unknown'
    level = 'Low' if safer_pct is not None and safer_pct >= 55 else 'Medium' if safer_pct is not None and safer_pct >= 20 else 'High' if safer_pct is not None else 'Unknown'
    notes = [
        f'City-level proxy for {city}, not parcel-specific and not a 0.5-mile incident count.',
        'Official parcel-level incident counts were not reliably queryable from the public endpoints used in this run.',
    ]
    if violent_ratio:
        notes.append(f'NeighborhoodScout reported violent-crime victimization odds of about 1 in {violent_ratio}.')
    if property_ratio:
        notes.append(f'Property-crime victimization odds were about 1 in {property_ratio}.')
    if overall_rate is not None:
        notes.append(f'Overall city-level crime rate text reported {overall_rate} per 1,000 residents.')
    return {
        'crime_source': 'NeighborhoodScout city-level crime page (low-confidence proxy)',
        'crime_data_date_range': f'{year} city-level page' if year != 'Unknown' else 'Unknown',
        'crime_incident_count_0_5mi': 'Unknown',
        'violent_crime_count_0_5mi': 'Unknown',
        'property_crime_count_0_5mi': 'Unknown',
        'crime_risk_score': score,
        'crime_risk_level': level,
        'crime_confidence': 'Low',
        'crime_notes': ' '.join(notes),
    }


def main() -> None:
    ensure_dirs()
    df = pd.read_csv(IN_CSV)
    econ_cache = {}
    crime_cache = {}
    out_rows = []
    econ_coverage = 0
    crime_coverage = 0
    log_lines = [f'input row count: {len(df)}']

    for _, row in df.iterrows():
        result = row.to_dict()
        geo_id, geo_type = tract_geo_id(row)
        econ_conf = 'High'
        if not geo_id:
            geo_id, geo_type = zip_geo_id(row)
            econ_conf = 'Medium' if geo_id else 'Low'
        if clean_text(row.get('geocode_confidence')) == 'Low' and econ_conf == 'High':
            econ_conf = 'Medium'

        metrics = {
            'median_household_income': None,
            'poverty_rate': None,
            'unemployment_rate': None,
            'median_home_value': None,
            'median_gross_rent': None,
            'vacancy_rate': None,
            'owner_occupied_rate': None,
        }
        release_name = 'Unknown'

        if geo_id:
            try:
                if geo_id not in econ_cache:
                    econ_cache[geo_id] = fetch_census_reporter(geo_id)
                payload = econ_cache[geo_id]
                release_name = clean_text(payload.get('release', {}).get('name'))
                metrics['median_household_income'] = estimate(payload, geo_id, 'B19013', 'B19013001')
                metrics['poverty_rate'] = safe_ratio(estimate(payload, geo_id, 'B17001', 'B17001002'), estimate(payload, geo_id, 'B17001', 'B17001001'))
                metrics['unemployment_rate'] = safe_ratio(estimate(payload, geo_id, 'B23025', 'B23025005'), estimate(payload, geo_id, 'B23025', 'B23025003'))
                metrics['median_home_value'] = estimate(payload, geo_id, 'B25077', 'B25077001')
                metrics['median_gross_rent'] = estimate(payload, geo_id, 'B25064', 'B25064001')
                metrics['vacancy_rate'] = safe_ratio(estimate(payload, geo_id, 'B25002', 'B25002003'), estimate(payload, geo_id, 'B25002', 'B25002001'))
                metrics['owner_occupied_rate'] = safe_ratio(estimate(payload, geo_id, 'B25003', 'B25003002'), estimate(payload, geo_id, 'B25003', 'B25003001'))
            except Exception:
                geo_id = None
                geo_type = None
                econ_conf = 'Low'

        econ_score = compute_economic_strength(metrics, econ_conf)
        econ_level = economic_level(econ_score)
        result.update({
            'median_household_income': round(metrics['median_household_income'], 2) if metrics['median_household_income'] is not None else 'Unknown',
            'poverty_rate': round(metrics['poverty_rate'], 4) if metrics['poverty_rate'] is not None else 'Unknown',
            'unemployment_rate': round(metrics['unemployment_rate'], 4) if metrics['unemployment_rate'] is not None else 'Unknown',
            'median_home_value': round(metrics['median_home_value'], 2) if metrics['median_home_value'] is not None else 'Unknown',
            'median_gross_rent': round(metrics['median_gross_rent'], 2) if metrics['median_gross_rent'] is not None else 'Unknown',
            'vacancy_rate': round(metrics['vacancy_rate'], 4) if metrics['vacancy_rate'] is not None else 'Unknown',
            'owner_occupied_rate': round(metrics['owner_occupied_rate'], 4) if metrics['owner_occupied_rate'] is not None else 'Unknown',
            'economic_source': f'{release_name} via Census Reporter API ({geo_type}-level)' if geo_id else 'Unknown',
            'economic_confidence': econ_conf if geo_id else 'Low',
            'economic_strength_score': econ_score if econ_score is not None else 'Unknown',
            'economic_risk_level': econ_level if geo_id else 'Unknown',
        })
        if result['economic_source'] != 'Unknown':
            econ_coverage += 1

        prior_crime_level = clean_text(row.get('prior_crime_risk_level'))
        prior_crime_score = safe_float(row.get('prior_crime_score'))
        city = infer_city(row)
        if city not in crime_cache:
            try:
                crime_cache[city] = parse_neighborhoodscout(city) if city != 'Unknown' else None
            except Exception:
                crime_cache[city] = None
        if prior_crime_level not in {'Unknown', 'Unknown.'} or prior_crime_score is not None:
            result.update({
                'crime_source': 'Prior iteration area context',
                'crime_data_date_range': 'Prior iteration dataset',
                'crime_incident_count_0_5mi': 'Unknown',
                'violent_crime_count_0_5mi': 'Unknown',
                'property_crime_count_0_5mi': 'Unknown',
                'crime_risk_score': round(prior_crime_score, 2) if prior_crime_score is not None else 'Unknown',
                'crime_risk_level': prior_crime_level if prior_crime_level not in {'Unknown', 'Unknown.'} else 'Unknown',
                'crime_confidence': 'Medium',
                'crime_notes': 'Merged from prior iteration screening data; area-level signal only.',
            })
        elif crime_cache.get(city):
            result.update(crime_cache[city])
        else:
            result.update({
                'crime_source': 'Unknown',
                'crime_data_date_range': 'Unknown',
                'crime_incident_count_0_5mi': 'Unknown',
                'violent_crime_count_0_5mi': 'Unknown',
                'property_crime_count_0_5mi': 'Unknown',
                'crime_risk_score': 'Unknown',
                'crime_risk_level': 'Unknown',
                'crime_confidence': 'Low',
                'crime_notes': 'No usable crime data source was attached for this row. Treat crime risk as unknown.',
            })
        if result['crime_source'] != 'Unknown':
            crime_coverage += 1

        out_rows.append(result)
        log_lines.append(
            f"{result['parcel_id']} | geocode={result['geocode_status']} | crime={result['crime_risk_level']} ({result['crime_confidence']}) | economic={result['economic_risk_level']} ({result['economic_confidence']})"
        )

    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(OUT_CSV, index=False)
    log_lines.insert(1, f'crime data coverage count: {crime_coverage}')
    log_lines.insert(2, f'economic data coverage count: {econ_coverage}')
    write_log(LOG_FILE, log_lines)
    print(f'crime_coverage={crime_coverage}/{len(out_df)} economic_coverage={econ_coverage}/{len(out_df)}')


if __name__ == '__main__':
    main()
