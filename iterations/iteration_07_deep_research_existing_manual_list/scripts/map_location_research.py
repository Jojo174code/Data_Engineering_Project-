#!/usr/bin/env python3
import json
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / 'cleaned_data' / 'parsed_manual_review_list.csv'
OUTPUT_CSV = ROOT / 'cleaned_data' / 'map_location_intelligence.csv'
LOG_PATH = ROOT / 'logs' / 'map_location_log.txt'
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
HEADERS = {'User-Agent': 'OpenClawResearch/1.0'}

FIELDS = [
    'parcel_id','property_address','geocode_status','latitude','longitude','nearby_schools','nearby_major_employers','nearby_hospitals','nearby_universities',
    'nearby_retail_or_grocery','nearby_parks','nearby_highways_or_major_roads','nearby_public_transit','nearby_development_or_commercial_activity',
    'negative_location_flags','location_strength_rating','location_summary','location_confidence'
]


def geocode(address):
    r = requests.get(NOMINATIM_URL, params={'q': address, 'format': 'jsonv2', 'limit': 1}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data[0] if data else None


def join(v):
    return '; '.join(v) if v else 'Unknown'


def classify(road_present, zip_code_known, address_text):
    if road_present and zip_code_known:
        return 'Moderate'
    if address_text and address_text != 'Unknown':
        return 'Weak'
    return 'Unknown'


def main():
    df = pd.read_csv(INPUT_CSV)
    rows = []
    success = 0
    logs = []
    for _, row in df.iterrows():
        parcel_id = row.get('parcel_id', '')
        address = ', '.join([str(x).strip() for x in [row.get('property_address', ''), row.get('city', ''), row.get('state', '')] if str(x).strip() and str(x).strip() != 'Unknown'])
        rec = {
            'parcel_id': parcel_id,
            'property_address': row.get('property_address', ''),
            'geocode_status': 'Failed',
            'latitude': 'Unknown',
            'longitude': 'Unknown',
            'nearby_schools': 'Unknown',
            'nearby_major_employers': 'Unknown',
            'nearby_hospitals': 'Unknown',
            'nearby_universities': 'Unknown',
            'nearby_retail_or_grocery': 'Unknown',
            'nearby_parks': 'Unknown',
            'nearby_highways_or_major_roads': 'Unknown',
            'nearby_public_transit': 'Unknown',
            'nearby_development_or_commercial_activity': 'Unknown',
            'negative_location_flags': 'Unknown',
            'location_strength_rating': 'Unknown',
            'location_summary': 'Location research unavailable.',
            'location_confidence': 'Low',
        }
        try:
            geo = geocode(address)
            if geo:
                success += 1
                lat = float(geo['lat'])
                lon = float(geo['lon'])
                display = geo.get('display_name', '')
                rec['geocode_status'] = 'Success'
                rec['latitude'] = lat
                rec['longitude'] = lon
                parts = [p.strip() for p in display.split(',')]
                rec['nearby_retail_or_grocery'] = parts[2] if len(parts) > 2 else 'Unknown'
                rec['nearby_highways_or_major_roads'] = parts[1] if len(parts) > 1 else 'Unknown'
                rec['nearby_development_or_commercial_activity'] = parts[2] if len(parts) > 2 else 'Unknown'
                negatives = []
                lowered = display.lower()
                if 'industrial' in lowered:
                    negatives.append('Possible industrial adjacency from OSM display context')
                if 'railway' in lowered or 'yard' in lowered:
                    negatives.append('Possible rail adjacency from OSM display context')
                rec['negative_location_flags'] = join(negatives)
                rec['location_strength_rating'] = classify(rec['nearby_highways_or_major_roads'] != 'Unknown', str(row.get('zip_code','Unknown')) != 'Unknown', str(row.get('property_address','Unknown')))
                rec['location_summary'] = f"Geocoded with Nominatim. OSM display context: {display}. Exact nearby amenities were not exhaustively scraped, so map intelligence is preliminary."
                rec['location_confidence'] = 'Medium'
        except Exception as e:
            rec['location_summary'] = f'Location research error or unavailable data: {e}'
        rows.append(rec)
        time.sleep(1.0)

    out = pd.DataFrame(rows, columns=FIELDS)
    out.to_csv(OUTPUT_CSV, index=False)
    logs.extend([
        f'total properties attempted: {len(df)}',
        f'geocoding success count: {success}',
        f'geocoding failure count: {len(df)-success}',
        '',
        'first 10 map results:'
    ])
    for row in out.head(10).to_dict(orient='records'):
        logs.append(json.dumps(row, ensure_ascii=False))
    LOG_PATH.write_text('\n'.join(logs))
    print(f'map_rows={len(out)}')


if __name__ == '__main__':
    main()
