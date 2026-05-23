#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time

import pandas as pd
import requests

from common_custom_33 import CLEANED_DIR, LOG_DIR, clean_text, ensure_dirs, normalize_address, write_log

IN_CSV = CLEANED_DIR / 'custom_33_enriched_from_prior_iterations.csv'
OUT_CSV = CLEANED_DIR / 'custom_33_geocoded.csv'
LOG_FILE = LOG_DIR / 'geocoding_log.txt'
HEADERS = {'User-Agent': 'OpenClawIteration12/1.0 (custom 33 geocoder)'}


def ordinalize(num_text: str) -> str:
    try:
        value = int(num_text)
    except Exception:
        return num_text
    if 10 <= value % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(value % 10, 'th')
    return f'{value}{suffix}'


def normalize_for_query(address: str) -> str:
    text = normalize_address(address)
    text = re.sub(r'\b(\d+)\s+ST\s+N\b', lambda m: f"{ordinalize(m.group(1))} ST N", text)
    text = re.sub(r'\b(\d+)\s+ST\s+S\b', lambda m: f"{ordinalize(m.group(1))} ST S", text)
    text = re.sub(r'\bAVE\s+E\b', 'AVE E', text)
    text = re.sub(r'\bAVE\s+W\b', 'AVE W', text)
    return text


def build_queries(row: pd.Series) -> list[tuple[str, str]]:
    address = normalize_for_query(row['property_address'])
    city = clean_text(row.get('city'), 'Tulsa')
    state = clean_text(row.get('state'), 'OK')
    queries = []
    seen = set()
    for city_name in [city, 'Tulsa']:
        q = f'{address}, {city_name}, {state}'
        if q not in seen:
            queries.append(('census', q))
            seen.add(q)
    for city_name in [city, 'Tulsa']:
        q = f'{address}, {city_name}, {state}'
        if q not in seen:
            queries.append(('nominatim', q))
            seen.add(q)
    return queries


def census_search(query: str):
    response = requests.get(
        'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress',
        params={'address': query, 'benchmark': 'Public_AR_Current', 'format': 'json'},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    matches = response.json().get('result', {}).get('addressMatches', [])
    return matches[0] if matches else None


def census_geographies(lon: float, lat: float):
    response = requests.get(
        'https://geocoding.geo.census.gov/geocoder/geographies/coordinates',
        params={'x': lon, 'y': lat, 'benchmark': 'Public_AR_Current', 'vintage': 'Current_Current', 'format': 'json'},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    geos = response.json().get('result', {}).get('geographies', {})
    tract = (geos.get('Census Tracts') or [{}])[0]
    block = (geos.get('2020 Census Blocks') or [{}])[0]
    place = (geos.get('Incorporated Places') or [{}])[0]
    ccd = (geos.get('County Subdivisions') or [{}])[0]
    return tract, block, place, ccd


def nominatim_search(query: str):
    response = requests.get(
        'https://nominatim.openstreetmap.org/search',
        params={'q': query, 'format': 'jsonv2', 'limit': 1, 'addressdetails': 1},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    rows = response.json()
    return rows[0] if rows else None


def confidence_from_census(row: pd.Series, match: dict) -> str:
    source = normalize_for_query(row['property_address'])
    matched = clean_text(match.get('matchedAddress')).upper()
    if source[:8] in matched and any(ch.isdigit() for ch in matched):
        return 'High'
    if any(ch.isdigit() for ch in matched):
        return 'Medium'
    return 'Low'


def geocode_row(row: pd.Series) -> dict:
    result = row.to_dict()
    prior_lat = clean_text(row.get('prior_latitude'))
    prior_lon = clean_text(row.get('prior_longitude'))
    prior_status = clean_text(row.get('prior_geocode_status'))
    prior_area = clean_text(row.get('prior_neighborhood_or_area'))
    if prior_lat not in {'Unknown', 'Unknown.'} and prior_lon not in {'Unknown', 'Unknown.'}:
        result.update({
            'latitude': float(prior_lat),
            'longitude': float(prior_lon),
            'geocode_status': prior_status if prior_status not in {'Unknown', 'Unknown.'} else 'Prior Geocoded',
            'geocode_confidence': 'High',
            'geocode_source': 'Prior Iteration Coordinates',
            'geocode_display_name': clean_text(row.get('property_address')),
            'confirmed_zip_code': 'Unknown',
            'neighborhood_or_area': prior_area,
            'census_tract': 'Unknown',
            'block_group': 'Unknown',
        })
        return result

    result.update({
        'latitude': 'Unknown',
        'longitude': 'Unknown',
        'geocode_status': 'Failed',
        'geocode_confidence': 'Low',
        'geocode_source': 'Unknown',
        'geocode_display_name': 'Unknown',
        'confirmed_zip_code': 'Unknown',
        'neighborhood_or_area': prior_area if prior_area not in {'Unknown', 'Unknown.'} else 'Unknown',
        'census_tract': 'Unknown',
        'block_group': 'Unknown',
    })

    for source, query in build_queries(row):
        try:
            if source == 'census':
                match = census_search(query)
                time.sleep(0.25)
                if not match:
                    continue
                lon = float(match['coordinates']['x'])
                lat = float(match['coordinates']['y'])
                tract, block, place, ccd = census_geographies(lon, lat)
                tract_id = clean_text(tract.get('GEOID'))
                block_group = 'Unknown'
                if tract_id not in {'Unknown', 'Unknown.'} and block.get('BLKGRP'):
                    block_group = f"{tract_id}{block.get('BLKGRP')}"
                area = clean_text(place.get('BASENAME') or ccd.get('BASENAME'))
                result.update({
                    'latitude': round(lat, 7),
                    'longitude': round(lon, 7),
                    'geocode_status': 'Geocoded',
                    'geocode_confidence': confidence_from_census(row, match),
                    'geocode_source': 'Census Geocoder',
                    'geocode_display_name': clean_text(match.get('matchedAddress')),
                    'confirmed_zip_code': clean_text(match.get('addressComponents', {}).get('zip')),
                    'neighborhood_or_area': area if area not in {'Unknown', 'Unknown.'} else result['neighborhood_or_area'],
                    'census_tract': tract_id,
                    'block_group': block_group,
                })
                return result
            nomi = nominatim_search(query)
            time.sleep(1.0)
            if not nomi:
                continue
            addr = nomi.get('address', {})
            result.update({
                'latitude': round(float(nomi['lat']), 7),
                'longitude': round(float(nomi['lon']), 7),
                'geocode_status': 'Approximate',
                'geocode_confidence': 'Low',
                'geocode_source': 'Nominatim',
                'geocode_display_name': clean_text(nomi.get('display_name')),
                'confirmed_zip_code': clean_text(addr.get('postcode')),
                'neighborhood_or_area': clean_text(addr.get('suburb') or addr.get('neighbourhood') or addr.get('city_district') or addr.get('city')),
            })
            return result
        except Exception:
            continue
    return result


def main() -> None:
    ensure_dirs()
    df = pd.read_csv(IN_CSV)
    out_rows = []
    log_lines = [f'input row count: {len(df)}']
    success_count = 0
    for _, row in df.iterrows():
        result = geocode_row(row)
        if clean_text(result['geocode_status']) != 'Failed':
            success_count += 1
        out_rows.append(result)
        log_lines.append(json.dumps({
            'parcel_id': result['parcel_id'],
            'status': result['geocode_status'],
            'confidence': result['geocode_confidence'],
            'source': result['geocode_source'],
            'display_name': result['geocode_display_name'],
            'census_tract': result['census_tract'],
            'block_group': result['block_group'],
        }, ensure_ascii=False))
    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(OUT_CSV, index=False)
    log_lines.insert(1, f'geocoding success count: {success_count}')
    write_log(LOG_FILE, log_lines)
    print(f'geocoded_rows={success_count}/{len(out_df)}')


if __name__ == '__main__':
    main()
