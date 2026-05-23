#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import requests

ITERATION_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
LOG_DIR = ITERATION_ROOT / 'logs'
IN_CSV = CLEANED_DIR / 'property_area_intelligence.csv'
OUT_CSV = CLEANED_DIR / 'property_area_intelligence.csv'
LOG_FILE = LOG_DIR / 'crime_data_log.txt'
HEADERS = {'User-Agent': 'OpenClawIteration10/1.0 (crime context collector)'}

CITY_SLUGS = {
    'Tulsa': 'tulsa',
    'Sand Springs': 'sand-springs',
    'Bixby': 'bixby',
    'Broken Arrow': 'broken-arrow',
}


def clean_text(value, default='Unknown.'):
    if pd.isna(value):
        return default
    text = str(value).strip()
    if not text or text.lower() == 'nan':
        return default
    return text


def infer_city(row: pd.Series) -> str:
    candidates = [
        clean_text(row.get('city')),
        clean_text(row.get('geocode_display_name')),
        clean_text(row.get('neighborhood_or_area')),
    ]
    for value in candidates:
        upper = value.upper()
        if 'BIXBY' in upper:
            return 'Bixby'
        if 'SAND SPRINGS' in upper:
            return 'Sand Springs'
        if 'BROKEN ARROW' in upper:
            return 'Broken Arrow'
        if 'TULSA' in upper:
            return 'Tulsa'
    return 'Unknown'


def parse_neighborhoodscout(city: str):
    slug = CITY_SLUGS.get(city)
    if not slug:
        return None
    url = f'https://www.neighborhoodscout.com/ok/{slug}/crime'
    response = requests.get(url, headers=HEADERS, timeout=45)
    response.raise_for_status()
    html = response.text

    meta_match = re.search(r'<meta name="description" content="([^"]+)"', html, re.I)
    safer_match = re.search(r'Safer than\s*<[^>]*>\s*([0-9]+)%', html, re.I | re.S)
    crime_rate_match = re.search(r'With a crime rate of ([0-9.]+) per one thousand residents', html, re.I)
    year_match = re.search(r'Most accurate\s+([0-9]{4})\s+crime rates', html, re.I)
    violent_match = re.search(r'violent crime .*? one in ([0-9,]+)', html, re.I)
    property_match = re.search(r'property crime .*? one in ([0-9,]+)', html, re.I)

    safer_pct = int(safer_match.group(1)) if safer_match else None
    violent_ratio = violent_match.group(1).replace(',', '') if violent_match else None
    property_ratio = property_match.group(1).replace(',', '') if property_match else None
    overall_rate = float(crime_rate_match.group(1)) if crime_rate_match else None
    year = year_match.group(1) if year_match else 'Unknown.'
    meta = meta_match.group(1) if meta_match else 'Unknown.'

    if safer_pct is None and overall_rate is None and not meta_match:
        return None

    if safer_pct is None:
        score = None
    else:
        score = round(max(1.0, min(10.0, 1.5 + (safer_pct / 10.0))), 2)

    if safer_pct is None:
        level = 'Unknown'
    elif safer_pct >= 55:
        level = 'Low'
    elif safer_pct >= 20:
        level = 'Medium'
    else:
        level = 'High'

    notes = [
        f'City-level proxy for {city}, not parcel-specific and not a 0.5-mile incident count.',
        'Official Tulsa parcel-level incident counts were not reliably queryable from the available public endpoints during this pipeline run.',
    ]
    if violent_ratio:
        notes.append(f'NeighborhoodScout reported violent-crime victimization odds of about 1 in {violent_ratio}.')
    if property_ratio:
        notes.append(f'Property-crime victimization odds were about 1 in {property_ratio}.')
    if safer_pct is not None:
        notes.append(f'The city page said {city} is safer than {safer_pct}% of U.S. cities.')
    if overall_rate is not None:
        notes.append(f'City-level overall crime rate text reported {overall_rate} per 1,000 residents.')

    return {
        'crime_source': 'NeighborhoodScout city-level crime page (low-confidence proxy)',
        'crime_data_date_range': f'{year} city-level page' if year != 'Unknown.' else 'Unknown.',
        'crime_incident_count_0_5mi': 'Unknown.',
        'violent_crime_count_0_5mi': 'Unknown.',
        'property_crime_count_0_5mi': 'Unknown.',
        'burglary_count_0_5mi': 'Unknown.',
        'theft_count_0_5mi': 'Unknown.',
        'assault_count_0_5mi': 'Unknown.',
        'crime_risk_score': score if score is not None else 'Unknown.',
        'crime_risk_level': level,
        'crime_confidence': 'Low',
        'crime_notes': ' '.join(notes),
        '_meta_summary': meta,
    }


def main():
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(IN_CSV)
    city_cache = {}
    out_rows = []
    logs = []

    for _, row in df.iterrows():
        city = infer_city(row)
        if city not in city_cache:
            try:
                city_cache[city] = parse_neighborhoodscout(city) if city != 'Unknown' else None
            except Exception:
                city_cache[city] = None
        result = row.to_dict()
        crime = city_cache.get(city)
        if crime:
            result.update({k: v for k, v in crime.items() if not k.startswith('_')})
        else:
            result.update({
                'crime_source': 'Unknown.',
                'crime_data_date_range': 'Unknown.',
                'crime_incident_count_0_5mi': 'Unknown.',
                'violent_crime_count_0_5mi': 'Unknown.',
                'property_crime_count_0_5mi': 'Unknown.',
                'burglary_count_0_5mi': 'Unknown.',
                'theft_count_0_5mi': 'Unknown.',
                'assault_count_0_5mi': 'Unknown.',
                'crime_risk_score': 'Unknown.',
                'crime_risk_level': 'Unknown',
                'crime_confidence': 'Unknown',
                'crime_notes': 'No usable official or area-level crime source was attached for this row. Treat crime risk as unknown and do not assume the area is safe.',
            })

        out_rows.append(result)
        logs.append(json.dumps({
            'parcel_id': result['parcel_id'],
            'city_used_for_crime_proxy': city,
            'crime_source': result['crime_source'],
            'crime_data_date_range': result['crime_data_date_range'],
            'crime_risk_score': result['crime_risk_score'],
            'crime_risk_level': result['crime_risk_level'],
            'crime_confidence': result['crime_confidence'],
            'crime_notes': result['crime_notes'],
        }, ensure_ascii=False))

    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(OUT_CSV, index=False)
    coverage = int((out_df['crime_source'] != 'Unknown.').sum())
    LOG_FILE.write_text('\n'.join([
        f'input row count: {len(df)}',
        f'crime coverage count: {coverage}',
        'crime counts within 0.5 miles were not available from the chosen public source and remain Unknown.',
        *logs,
    ]))
    print(f'crime_coverage={coverage}/{len(df)}')


if __name__ == '__main__':
    main()
