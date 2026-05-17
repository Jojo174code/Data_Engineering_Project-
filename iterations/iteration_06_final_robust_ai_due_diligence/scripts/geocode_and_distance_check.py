from __future__ import annotations

import math
import time
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import requests

ITERATION_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
LOG_DIR = ITERATION_ROOT / 'logs'

MATCH_CSV = CLEANED_DIR / 'final_property_development_matches.csv'
OUT_CSV = CLEANED_DIR / 'final_geocoding_results.csv'
LOG_FILE = LOG_DIR / 'geocoding_log.txt'

CENSUS_URL = 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress'
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'OpenClaw-Context-Iteration06/1.0 (research use)'})


def clean_text(value) -> str:
    if value is None:
        return 'Unknown'
    text = str(value).strip()
    return text if text else 'Unknown'


def is_usable_address(address: str) -> bool:
    text = clean_text(address).upper()
    return text not in {'UNKNOWN', 'ADDRESS UNKNOWN'} and text[:1].isdigit()


def is_broad_query(query: str) -> bool:
    upper = clean_text(query).upper()
    return any(term in upper for term in ['CITYWIDE', 'MULTIPLE NEIGHBORHOODS', 'REGIONAL', 'METRO', 'TRANSPORTATION NETWORK'])


def haversine_miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


def census_geocode(query: str):
    params = {'address': query, 'benchmark': 'Public_AR_Current', 'format': 'json'}
    try:
        response = SESSION.get(CENSUS_URL, params=params, timeout=20)
        response.raise_for_status()
        matches = response.json().get('result', {}).get('addressMatches', [])
        if not matches:
            return None
        best = matches[0]
        coords = best.get('coordinates', {})
        return {
            'lat': coords.get('y'),
            'lon': coords.get('x'),
            'match_type': clean_text(best.get('matchType')),
            'matched_address': clean_text(best.get('matchedAddress')),
        }
    except Exception:
        return None


def nominatim_geocode(query: str):
    try:
        response = SESSION.get(f'{NOMINATIM_URL}?q={quote_plus(query)}&format=jsonv2&limit=1', timeout=30)
        response.raise_for_status()
        rows = response.json()
        if not rows:
            return None
        best = rows[0]
        return {
            'lat': float(best['lat']),
            'lon': float(best['lon']),
            'display_name': clean_text(best.get('display_name')),
            'type': clean_text(best.get('type')),
        }
    except Exception:
        return None


def development_queries(row: pd.Series) -> list[str]:
    queries: list[str] = []
    rel = clean_text(row.get('final_development_relevant_streets', 'Unknown'))
    corridor = clean_text(row.get('final_development_corridor', 'Unknown'))
    project = clean_text(row.get('final_matched_project_or_area_name', 'Unknown'))
    area = clean_text(row.get('final_matched_development_area', 'Unknown'))

    street_parts = [part.strip() for part in rel.split(';') if part.strip()]
    street_parts = [part for part in street_parts if part.upper() not in {'UNKNOWN', 'EAST TULSA', 'INDUSTRIAL PARK', 'DOWNTOWN TULSA', 'IDL', 'DOWNTOWN NORTH EDGE'}]
    if len(street_parts) >= 2:
        queries.append(f'{street_parts[0]} and {street_parts[1]}, Tulsa, Oklahoma')
    if len(street_parts) >= 3:
        queries.append(f'{street_parts[1]} and {street_parts[2]}, Tulsa, Oklahoma')
    if corridor != 'Unknown':
        queries.append(f'{corridor}, Tulsa, Oklahoma')
    if project != 'Unknown':
        queries.append(f'{project}, Tulsa, Oklahoma')
    if area != 'Unknown':
        queries.append(f'{area}, Tulsa, Oklahoma')
    deduped = []
    for query in queries:
        if query not in deduped:
            deduped.append(query)
    return deduped


def property_query(row: pd.Series) -> str:
    address = clean_text(row['property_address'])
    city = clean_text(row['city'])
    state = clean_text(row['state'])
    zip_code = clean_text(row['zip_code'])
    if city == 'Unknown':
        city = 'Tulsa'
    parts = [address, city, state if state != 'Unknown' else 'OK']
    if zip_code != 'Unknown':
        parts.append(zip_code)
    return ', '.join(parts)


def corrected_strength(row: pd.Series, distance: float | None) -> tuple[str, bool, str]:
    base_strength = clean_text(row['final_development_match_strength'])
    basis = clean_text(row['final_match_basis'])

    if base_strength == 'Unknown':
        return 'Unknown', False, 'Base match was Unknown'
    if base_strength == 'No Clear Match':
        return 'No Clear Match', False, 'Base match was already No Clear Match'

    if distance is not None:
        if distance <= 1.0:
            return 'Strong Match', True, f'Geocoding verified close proximity ({distance} miles)'
        if distance <= 2.5:
            return 'Possible Match', False, f'Geocoding shows limited but still plausible proximity ({distance} miles)'
        return 'No Clear Match', False, f'Geocoding shows the property is not meaningfully close ({distance} miles)'

    if basis in {'named_area', 'named_area_plus_zip'}:
        return 'Strong Match', False, 'Named district or neighborhood evidence remains credible without precise coordinates'
    if basis in {'zip_plus_corridor', 'corridor_only', 'zip_only'}:
        return 'Possible Match', False, 'Match remains plausible but not distance-verified'
    return 'No Clear Match', False, 'Insufficient geocoding support to keep the match strong'


def main():
    df = pd.read_csv(MATCH_CSV)

    property_cache: dict[str, dict | None] = {}
    development_cache: dict[str, dict | None] = {}
    last_nominatim_call = 0.0

    records = []
    prop_success = 0
    prop_failure = 0
    dev_success = 0
    dev_failure = 0
    verified_distance = 0
    downgraded = 0

    for _, row in df.iterrows():
        address_status = 'Not Attempted'
        property_lat = None
        property_lon = None
        dev_status = 'Not Attempted'
        dev_lat = None
        dev_lon = None
        distance = None
        geocode_notes = []

        p_query = property_query(row)
        if is_usable_address(row['property_address']):
            if p_query not in property_cache:
                property_cache[p_query] = census_geocode(p_query)
                time.sleep(0.12)
            result = property_cache[p_query]
            if result and result.get('lat') is not None and result.get('lon') is not None:
                property_lat = float(result['lat'])
                property_lon = float(result['lon'])
                address_status = 'Success'
                prop_success += 1
                geocode_notes.append(f"Property geocoded via Census: {result.get('matched_address', 'Unknown')}")
            else:
                address_status = 'Failed'
                prop_failure += 1
                geocode_notes.append('Property geocoding failed via Census')
        else:
            address_status = 'Unusable Address'
            prop_failure += 1
            geocode_notes.append('Property address unusable for geocoding')

        dev_query = clean_text(row.get('final_development_geocode_query', 'Unknown'))
        if clean_text(row['final_development_match_strength']) in {'Strong Match', 'Possible Match'} and dev_query != 'Unknown' and not is_broad_query(dev_query):
            d_result = None
            for candidate_query in development_queries(row):
                if candidate_query not in development_cache:
                    development_cache[candidate_query] = census_geocode(candidate_query)
                    time.sleep(0.12)
                    if development_cache[candidate_query] is None:
                        sleep_for = max(0.0, 1.1 - (time.time() - last_nominatim_call))
                        if sleep_for > 0:
                            time.sleep(sleep_for)
                        development_cache[candidate_query] = nominatim_geocode(candidate_query)
                        last_nominatim_call = time.time()
                d_result = development_cache[candidate_query]
                if d_result and d_result.get('lat') is not None and d_result.get('lon') is not None:
                    geocode_notes.append(f'Development geocode query used: {candidate_query}')
                    break
            if d_result and d_result.get('lat') is not None and d_result.get('lon') is not None:
                dev_lat = float(d_result['lat'])
                dev_lon = float(d_result['lon'])
                dev_status = 'Success'
                dev_success += 1
                geocode_notes.append('Development geocoding succeeded')
            else:
                dev_status = 'Failed'
                dev_failure += 1
                geocode_notes.append('Development geocoding failed for all candidate queries')
        elif clean_text(row['final_development_match_strength']) in {'Strong Match', 'Possible Match'} and is_broad_query(dev_query):
            dev_status = 'Skipped Broad Area'
            dev_failure += 1
            geocode_notes.append('Development area too broad for precise geocoding')
        else:
            dev_status = 'Not Needed'

        if property_lat is not None and property_lon is not None and dev_lat is not None and dev_lon is not None:
            distance = haversine_miles(property_lat, property_lon, dev_lat, dev_lon)

        corrected, distance_flag, correction_note = corrected_strength(row, distance)
        if distance_flag:
            verified_distance += 1
        if clean_text(row['final_development_match_strength']) == 'Strong Match' and corrected != 'Strong Match':
            downgraded += 1
        geocode_notes.append(correction_note)

        geocode_confidence = 'Low'
        if address_status == 'Success' and dev_status == 'Success' and distance is not None:
            geocode_confidence = 'High'
        elif address_status == 'Success' or dev_status == 'Success':
            geocode_confidence = 'Medium'

        records.append({
            'parcel_id': row['parcel_id'],
            'property_geocode_status': address_status,
            'property_latitude': property_lat,
            'property_longitude': property_lon,
            'development_geocode_status': dev_status,
            'development_latitude': dev_lat,
            'development_longitude': dev_lon,
            'estimated_distance_miles': distance,
            'geocode_confidence': geocode_confidence,
            'distance_verified_match': bool(distance_flag),
            'corrected_development_match_strength': corrected,
            'geocode_notes': '; '.join(geocode_notes),
        })

    out_df = pd.DataFrame(records)
    out_df.to_csv(OUT_CSV, index=False)

    lines = [
        f'total properties attempted: {len(df)}',
        f'property geocoding successes: {prop_success}',
        f'property geocoding failures: {prop_failure}',
        f'development geocoding successes: {dev_success}',
        f'development geocoding failures: {dev_failure}',
        f'distance-verified matches: {verified_distance}',
        f'downgraded development matches: {downgraded}',
    ]
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for line in lines:
        print(line)


if __name__ == '__main__':
    main()
