#!/usr/bin/env python3
import json
import re
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / 'cleaned_data' / 'parsed_manual_review_list.csv'
OUTPUT_CSV = ROOT / 'cleaned_data' / 'assessor_property_results.csv'
LOG_PATH = ROOT / 'logs' / 'assessor_lookup_log.txt'
SEARCH_URL = 'https://assessor.tulsacounty.org/Property/Search'
FIELDS = [
    'parcel_id','assessor_match_status','assessor_property_address','assessor_owner_name','assessor_property_type','assessor_land_value','assessor_improvement_value',
    'assessor_total_assessed_value','assessor_market_value','assessor_taxable_value','assessor_year_built','assessor_square_feet','assessor_lot_size','assessor_bedrooms',
    'assessor_bathrooms','assessor_last_sale_date','assessor_last_sale_price','assessor_neighborhood','assessor_school_district','assessor_source_url','manual_lookup_url',
    'assessor_notes','assessor_confidence'
]


def normalize_parcel(parcel_id: str) -> str:
    return re.sub(r'[^0-9]', '', str(parcel_id or ''))


def check_search_reachable(session):
    r = session.get(SEARCH_URL, timeout=30)
    r.raise_for_status()
    return 'Tulsa County Assessor - Property Search' in r.text


def build_record(row, search_reachable):
    parcel_id = str(row.get('parcel_id', '')).strip()
    address = str(row.get('property_address', '')).strip()
    city = str(row.get('city', '')).strip()
    state = str(row.get('state', '')).strip()
    parcel_numeric = normalize_parcel(parcel_id)
    address_query = ', '.join(x for x in [address, city, state] if x and x != 'Unknown')
    filter_tag = 'AccountNo' if parcel_numeric else 'FullPropertyAddress'
    search_term = parcel_numeric or address_query
    manual_lookup_url = f"{SEARCH_URL}?terms={quote_plus(search_term)}&filterTag={filter_tag}"
    status = 'Search Reachable, Detail Unavailable' if search_reachable else 'Blocked'
    notes = 'Assessor search endpoint was reachable, but this automation path did not have reliable access to parcel-level valuation cards. Manual lookup link provided.' if search_reachable else 'Assessor search endpoint could not be verified during this run. Manual lookup link provided.'
    return {
        'parcel_id': parcel_id,
        'assessor_match_status': status,
        'assessor_property_address': 'Unavailable',
        'assessor_owner_name': 'Unavailable',
        'assessor_property_type': 'Unavailable',
        'assessor_land_value': 'Unavailable',
        'assessor_improvement_value': 'Unavailable',
        'assessor_total_assessed_value': 'Unavailable',
        'assessor_market_value': 'Unavailable',
        'assessor_taxable_value': 'Unavailable',
        'assessor_year_built': 'Unavailable',
        'assessor_square_feet': 'Unavailable',
        'assessor_lot_size': 'Unavailable',
        'assessor_bedrooms': 'Unavailable',
        'assessor_bathrooms': 'Unavailable',
        'assessor_last_sale_date': 'Unavailable',
        'assessor_last_sale_price': 'Unavailable',
        'assessor_neighborhood': 'Unavailable',
        'assessor_school_district': 'Unavailable',
        'assessor_source_url': SEARCH_URL,
        'manual_lookup_url': manual_lookup_url,
        'assessor_notes': notes,
        'assessor_confidence': 'Low',
    }


def main():
    df = pd.read_csv(INPUT_CSV)
    session = requests.Session()
    session.headers.update({'User-Agent': 'OpenClawResearch/1.0'})
    try:
        search_reachable = check_search_reachable(session)
    except Exception:
        search_reachable = False

    rows = [build_record(row, search_reachable) for _, row in df.iterrows()]
    out = pd.DataFrame(rows, columns=FIELDS)
    out.to_csv(OUTPUT_CSV, index=False)

    successful = int((out['assessor_match_status'] == 'Search Reachable, Detail Unavailable').sum())
    blocked = int((out['assessor_match_status'] == 'Blocked').sum())
    log_lines = [
        f'total properties attempted: {len(df)}',
        f'successful parcel matches: {successful}',
        'address fallback matches: 0',
        'failed matches: 0',
        f'blocked/errors: {blocked}',
        '',
        'first 10 assessor results:'
    ]
    for row in out.head(10).to_dict(orient='records'):
        log_lines.append(json.dumps(row, ensure_ascii=False))
    LOG_PATH.write_text('\n'.join(log_lines))
    print(f'assessor_rows={len(out)}')


if __name__ == '__main__':
    main()
