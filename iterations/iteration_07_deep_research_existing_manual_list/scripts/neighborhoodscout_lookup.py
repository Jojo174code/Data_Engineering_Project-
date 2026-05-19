#!/usr/bin/env python3
import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / 'cleaned_data' / 'parsed_manual_review_list.csv'
OUTPUT_CSV = ROOT / 'cleaned_data' / 'neighborhoodscout_results.csv'
LOG_PATH = ROOT / 'logs' / 'neighborhoodscout_log.txt'
DEM_URL = 'https://www.neighborhoodscout.com/ok/tulsa/demographics'
RE_URL = 'https://www.neighborhoodscout.com/ok/tulsa/real-estate'
CRIME_URL = 'https://www.neighborhoodscout.com/ok/tulsa/crime'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; OpenClawResearch/1.0)'}

FIELDS = [
    'parcel_id','property_address','neighborhoodscout_match_status','neighborhood_or_area_used','zip_code_used','crime_risk_summary','crime_risk_rating',
    'real_estate_price_trend','real_estate_trend_direction','median_home_value_if_available','rent_level_if_available','income_or_economic_summary',
    'demographic_summary','neighborhoodscout_source_url','neighborhoodscout_confidence','neighborhoodscout_notes'
]


def normalize_ws(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def extract_money_after_label(html: str, label: str):
    idx = html.lower().find(label.lower())
    if idx == -1:
        return 'Unavailable'
    segment = normalize_ws(html[idx: idx + 2000])
    monies = re.findall(r'\$[\d,]+', segment)
    return monies[0] if monies else 'Unavailable'


def build_context():
    pages = {}
    for key, url in [('demographics', DEM_URL), ('real_estate', RE_URL), ('crime', CRIME_URL)]:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        pages[key] = resp.text
        time.sleep(0.5)

    dem = pages['demographics']
    re_page = pages['real_estate']
    crime = pages['crime']

    median_income = extract_money_after_label(dem, 'Median Household Income')
    per_capita_income = extract_money_after_label(dem, 'Per capita Income')
    median_home_value = extract_money_after_label(re_page, 'Median real estate price')
    average_rent = extract_money_after_label(re_page, 'Average rental price')

    trend_direction = 'Unknown'
    trend_summary = 'Area-level NeighborhoodScout real estate trend data could not be cleanly extracted.'
    lowered = re_page.lower()
    if 'appreciation' in lowered or 'price appreciation' in lowered:
        trend_summary = 'NeighborhoodScout real-estate page indicates area-level pricing/appreciation context is available, but exact parcel-level trend figures were not relied on.'
    if any(x in lowered for x in ['appreciation has been above', 'prices have risen', 'increase in home values']):
        trend_direction = 'Increasing'
    elif any(x in lowered for x in ['stable', 'little change']):
        trend_direction = 'Stable'
    elif any(x in lowered for x in ['decline', 'decrease', 'fallen']):
        trend_direction = 'Decreasing'

    crime_rating = 'Unknown'
    crime_summary = 'NeighborhoodScout crime page was available, but exact parcel-level or neighborhood-level crime statistics were not extracted.'
    crime_lower = crime.lower()
    if 'safer than' in crime_lower or 'crime index' in crime_lower:
        crime_summary = 'NeighborhoodScout crime context page was available for Tulsa, but it is area-level screening context only and exact numeric crime rates were not used.'

    return {
        'median_income': median_income,
        'per_capita_income': per_capita_income,
        'median_home_value': median_home_value,
        'average_rent': average_rent,
        'trend_direction': trend_direction,
        'trend_summary': trend_summary,
        'crime_rating': crime_rating,
        'crime_summary': crime_summary,
    }


def main():
    df = pd.read_csv(INPUT_CSV)
    context = build_context()
    rows = []
    for _, row in df.iterrows():
        zip_code = str(row.get('zip_code', 'Unknown')).strip()
        rows.append({
            'parcel_id': row.get('parcel_id', ''),
            'property_address': row.get('property_address', ''),
            'neighborhoodscout_match_status': 'Area-Level Tulsa Context Only',
            'neighborhood_or_area_used': 'Tulsa, OK',
            'zip_code_used': zip_code if zip_code and zip_code != 'Unknown' else 'Unknown',
            'crime_risk_summary': context['crime_summary'],
            'crime_risk_rating': context['crime_rating'],
            'real_estate_price_trend': context['trend_summary'],
            'real_estate_trend_direction': context['trend_direction'],
            'median_home_value_if_available': context['median_home_value'],
            'rent_level_if_available': context['average_rent'],
            'income_or_economic_summary': f"Tulsa area-level median household income: {context['median_income']}; per capita income: {context['per_capita_income']}.",
            'demographic_summary': 'Tulsa city-level NeighborhoodScout demographic page was used as area-level context only, not parcel-level proof.',
            'neighborhoodscout_source_url': '|'.join([DEM_URL, RE_URL, CRIME_URL]),
            'neighborhoodscout_confidence': 'Low',
            'neighborhoodscout_notes': 'NeighborhoodScout data was treated as area-level screening context only. If parcel/neighborhood-specific data is needed, manual review is required.'
        })

    out = pd.DataFrame(rows, columns=FIELDS)
    out.to_csv(OUTPUT_CSV, index=False)

    counts = out['real_estate_trend_direction'].value_counts(dropna=False).to_dict()
    log_lines = [
        f'total properties attempted: {len(df)}',
        f'successful area matches: {len(df)}',
        'failed matches: 0',
        'blocked/unavailable results: 0',
        f"number Increasing: {counts.get('Increasing', 0)}",
        f"number Stable: {counts.get('Stable', 0)}",
        f"number Decreasing: {counts.get('Decreasing', 0)}",
        f"number Unknown: {counts.get('Unknown', 0)}",
        '',
        'first 10 neighborhoodscout results:'
    ]
    for row in out.head(10).to_dict(orient='records'):
        log_lines.append(json.dumps(row, ensure_ascii=False))
    LOG_PATH.write_text('\n'.join(log_lines))
    print(f'neighborhood_rows={len(out)}')


if __name__ == '__main__':
    main()
