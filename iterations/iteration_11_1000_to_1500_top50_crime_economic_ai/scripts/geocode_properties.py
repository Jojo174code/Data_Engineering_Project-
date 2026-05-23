#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

ITERATION_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
LOG_DIR = ITERATION_ROOT / 'logs'
IN_CSV = CLEANED_DIR / 'base_1000_to_1500_properties.csv'
OUT_CSV = CLEANED_DIR / 'geocoded_properties.csv'
LOG_FILE = LOG_DIR / 'geocoding_log.txt'

USER_AGENT = 'OpenClawIteration10/1.0 (auction screening geocoder)'
HEADERS = {'User-Agent': USER_AGENT}


def clean_text(value, default='Unknown.'):
    if pd.isna(value):
        return default
    text = str(value).strip()
    if not text or text.lower() == 'nan':
        return default
    return text


def ordinalize(number_text: str) -> str:
    try:
        value = int(number_text)
    except Exception:
        return number_text
    if 10 <= value % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(value % 10, 'th')
    return f'{value}{suffix}'


def normalize_address(address: str) -> str:
    text = clean_text(address)
    if text in {'Unknown.', 'ADDRESS UNKNOWN'}:
        return text
    text = re.sub(r'\bBV\b', 'BLVD', text)
    text = re.sub(r'\bPL\b', 'PL', text)
    text = re.sub(r'\bAV\b\s+E\b', lambda m: 'AVE E', text)
    text = re.sub(r'\bAV\b\s+W\b', lambda m: 'AVE W', text)
    text = re.sub(r'\b(\d+)\s+AV\s+E\b', lambda m: f"{ordinalize(m.group(1))} EAST AVE", text)
    text = re.sub(r'\b(\d+)\s+AV\s+W\b', lambda m: f"{ordinalize(m.group(1))} WEST AVE", text)
    text = re.sub(r'\b(\d+)\s+ST\s+N\b', lambda m: f"{ordinalize(m.group(1))} ST N", text)
    text = re.sub(r'\b(\d+)\s+ST\s+S\b', lambda m: f"{ordinalize(m.group(1))} ST S", text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def build_queries(row: pd.Series) -> list[tuple[str, str]]:
    address = normalize_address(row['property_address'])
    city = clean_text(row['city'], default='Unknown.')
    state = clean_text(row['state'], default='OK')
    zip_code = clean_text(row['zip_code'], default='Unknown.')
    queries = []
    if address in {'Unknown.', 'ADDRESS UNKNOWN'}:
        return queries

    city_candidates = []
    if city not in {'Unknown.', 'Unknown'}:
        city_candidates.append(city)
    if 'CITY OF BIXBY' in city.upper():
        city_candidates.append('Bixby')
    if address.endswith(' W') and 'Sand Springs' not in city_candidates:
        city_candidates.append('Tulsa')
    if 'Unknown.' not in city_candidates and 'Tulsa' not in city_candidates:
        city_candidates.append('Tulsa')

    dedup = set()
    for city_name in city_candidates:
        base = f'{address}, {city_name}, {state}'
        if base not in dedup:
            queries.append(('census', base))
            dedup.add(base)
        if zip_code not in {'Unknown.', 'Unknown'}:
            zip_query = f'{address}, {city_name}, {state} {zip_code}'
            if zip_query not in dedup:
                queries.append(('census', zip_query))
                dedup.add(zip_query)

    for city_name in city_candidates:
        base = f'{address}, {city_name}, {state}'
        if base not in dedup:
            queries.append(('nominatim', base))
            dedup.add(base)

    return queries


def census_search(query: str):
    url = 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress'
    params = {'address': query, 'benchmark': 'Public_AR_Current', 'format': 'json'}
    response = requests.get(url, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    matches = response.json().get('result', {}).get('addressMatches', [])
    return matches[0] if matches else None


def census_geographies(lon: float, lat: float):
    url = 'https://geocoding.geo.census.gov/geocoder/geographies/coordinates'
    params = {
        'x': lon,
        'y': lat,
        'benchmark': 'Public_AR_Current',
        'vintage': 'Current_Current',
        'format': 'json',
    }
    response = requests.get(url, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    geos = response.json().get('result', {}).get('geographies', {})
    tract = (geos.get('Census Tracts') or [{}])[0]
    block = (geos.get('2020 Census Blocks') or [{}])[0]
    place = (geos.get('Incorporated Places') or [{}])[0]
    ccd = (geos.get('County Subdivisions') or [{}])[0]
    return tract, block, place, ccd


def nominatim_search(query: str):
    url = 'https://nominatim.openstreetmap.org/search'
    params = {'q': query, 'format': 'jsonv2', 'limit': 1, 'addressdetails': 1}
    response = requests.get(url, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    rows = response.json()
    return rows[0] if rows else None


def confidence_from_census(row: pd.Series, match: dict) -> str:
    source_addr = normalize_address(row['property_address']).upper().replace('.', '')
    matched = clean_text(match.get('matchedAddress')).upper().replace('.', '')
    zip_match = clean_text(match.get('addressComponents', {}).get('zip'))
    has_number = bool(re.search(r'\b\d+\b', matched))
    if has_number and zip_match not in {'Unknown.', 'Unknown'} and source_addr.split(',')[0][:6] in matched:
        return 'High'
    if has_number:
        return 'Medium'
    return 'Low'


def geocode_row(row: pd.Series) -> dict:
    out = row.to_dict()
    out.update({
        'latitude': 'Unknown.',
        'longitude': 'Unknown.',
        'geocode_status': 'Failed',
        'geocode_confidence': 'Low',
        'geocode_source': 'Unknown.',
        'geocode_display_name': 'Unknown.',
        'census_tract': 'Unknown.',
        'block_group': 'Unknown.',
        'confirmed_zip_code': clean_text(row.get('zip_code')),
        'neighborhood_or_area': 'Unknown.',
    })

    queries = build_queries(row)
    if not queries:
        out['geocode_status'] = 'Failed'
        out['geocode_confidence'] = 'Low'
        return out

    for source, query in queries:
        try:
            if source == 'census':
                match = census_search(query)
                time.sleep(0.25)
                if not match:
                    continue
                lon = float(match['coordinates']['x'])
                lat = float(match['coordinates']['y'])
                tract, block, place, ccd = census_geographies(lon, lat)
                tract_geoid = tract.get('GEOID', 'Unknown.')
                block_group = 'Unknown.'
                if tract_geoid not in {'', 'Unknown.'} and block.get('BLKGRP'):
                    block_group = f"{tract_geoid}{block.get('BLKGRP')}"
                place_name = clean_text(place.get('BASENAME') or ccd.get('BASENAME'))
                tract_label = tract.get('TRACT') or ''
                area_label = place_name
                if tract_label:
                    tract_clean = tract_label.lstrip('0') or tract_label
                    area_label = f'{place_name} Census Tract {tract_clean}' if place_name not in {'Unknown.', 'Unknown'} else f'Census Tract {tract_clean}'

                out.update({
                    'latitude': round(lat, 7),
                    'longitude': round(lon, 7),
                    'geocode_status': 'Geocoded',
                    'geocode_confidence': confidence_from_census(row, match),
                    'geocode_source': 'Census Geocoder',
                    'geocode_display_name': clean_text(match.get('matchedAddress')),
                    'census_tract': tract_geoid,
                    'block_group': block_group,
                    'confirmed_zip_code': clean_text(match.get('addressComponents', {}).get('zip')),
                    'neighborhood_or_area': area_label,
                })
                return out

            nomi = nominatim_search(query)
            time.sleep(1.0)
            if not nomi:
                continue
            addr_bits = nomi.get('address', {})
            neighborhood = addr_bits.get('suburb') or addr_bits.get('neighbourhood') or addr_bits.get('city_district') or addr_bits.get('city')
            out.update({
                'latitude': round(float(nomi['lat']), 7),
                'longitude': round(float(nomi['lon']), 7),
                'geocode_status': 'Approximate',
                'geocode_confidence': 'Low',
                'geocode_source': 'Nominatim',
                'geocode_display_name': clean_text(nomi.get('display_name')),
                'confirmed_zip_code': clean_text(addr_bits.get('postcode') or row.get('zip_code')),
                'neighborhood_or_area': clean_text(neighborhood),
            })
            return out
        except Exception:
            continue

    return out


def main():
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(IN_CSV)
    out_rows = []
    logs = []
    for _, row in df.iterrows():
        result = geocode_row(row)
        out_rows.append(result)
        logs.append(json.dumps({
            'parcel_id': result['parcel_id'],
            'property_address': result['property_address'],
            'geocode_status': result['geocode_status'],
            'geocode_confidence': result['geocode_confidence'],
            'geocode_source': result['geocode_source'],
            'geocode_display_name': result['geocode_display_name'],
            'census_tract': result['census_tract'],
            'block_group': result['block_group'],
            'confirmed_zip_code': result['confirmed_zip_code'],
            'neighborhood_or_area': result['neighborhood_or_area'],
        }, ensure_ascii=False))
    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(OUT_CSV, index=False)
    success_count = int((out_df['geocode_status'] != 'Failed').sum())
    LOG_FILE.write_text('\n'.join([
        f'input row count: {len(df)}',
        f'geocoding success count: {success_count}',
        *logs,
    ]))
    print(f'geocoded_rows={success_count}/{len(df)}')


if __name__ == '__main__':
    main()
