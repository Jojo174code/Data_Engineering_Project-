from __future__ import annotations

import csv
import re
import sys
from collections import OrderedDict
from pathlib import Path

import pdfplumber

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common_utils import ROOT, clean_text, infer_extraction_confidence, normalize_city, parse_money

PDF = ROOT / 'auction_lists' / '2026_tulsa_auction_list.pdf'
OUT = ROOT / 'cleaned_data' / 'cleaned_auction_properties.csv'

ENTRY_RE = re.compile(
    r'^(?P<prop_no>\d+)\s+'
    r'(?P<parcel_id>\d{5}-\d{2}-\d{2}-\d{5})\s+'
    r'(?P<property_address>.*?)\s+'
    r'(?P<land_sqft>\d{1,3}(?:,\d{3})*)\s+'
    r'(?P<property_type>(?:R|C|B|A|MH)(?:\s+(?:HS|IMP))*)\s+'
    r'(?P<bid_cost>\d{1,3}(?:,\d{3})*\.\d{2})'
    r'(?:\s+(?P<resale_costs_fees>\d{1,3}(?:,\d{3})*\.\d{2}))?'
    r'(?:\s+(?P<notes>.*))?$'
)
CITY_SUFFIX_RE = re.compile(r'\s+((?:CITY|TOWN) OF [A-Z ]+|UNINCORPORATED|BROKEN ARROW|SAND SPRINGS|OWASSO|BIXBY|JENKS|SAPULPA|COLLINSVILLE|SKIATOOK)$', re.IGNORECASE)
SKIP_PREFIXES = (
    'TR01033', 'Page ', 'Report generated as of', 'Land List for 2026 June Resale Auction',
    'Data created as of', 'Bids will be accepted in minimum increments',
)
SKIP_EXACT = {
    'Tulsa County Treasurer', 'Land', 'List', 'Prop.', 'No.', 'Parcel', 'Status', 'Parcel Number', 'Legal Description',
    'Property Address', 'Square', 'Footage', 'Subdivision', 'and City', 'Minimum', 'Bid', 'Amount', 'Notations',
    'Status Subdivision', 'No. and City Footage IMP=Improvements Bid * Amount Notations',
    'C=Commercial Approximate', 'R=Residential Resale', 'B=Both Comm / Res Costs & Fees',
    'Approx', 'A=Agricultural Must Be Paid', 'Successful', 'MH=Mobile Home In Addition To',
    'Parcel Legal Description', 'Prop. Bid', 'HS=Homestead Successful Bid',
    'Parcel Number A=Agricultural Must Be Paid', 'List Successful', 'Square Minimum'
}


def page_lines(page) -> list[str]:
    text = page.extract_text(x_tolerance=2, y_tolerance=2) or ''
    out = []
    for raw in text.splitlines():
        line = clean_text(raw)
        if not line:
            continue
        if line in SKIP_EXACT:
            continue
        if any(line.startswith(prefix) for prefix in SKIP_PREFIXES):
            continue
        out.append(line)
    return out


def split_legal_city(line: str):
    m = CITY_SUFFIX_RE.search(line)
    if not m:
        return clean_text(line), 'Unknown'
    city_raw = clean_text(m.group(1))
    legal = clean_text(line[:m.start()])
    return legal, normalize_city(city_raw)


def parse_page(lines: list[str], page_number: int) -> list[dict]:
    rows = []
    i = 0
    while i < len(lines):
        m = ENTRY_RE.match(lines[i])
        if not m:
            i += 1
            continue
        entry = m.groupdict()
        legal_line = clean_text(lines[i + 1]) if i + 1 < len(lines) else ''
        subdivision = clean_text(lines[i + 2]) if i + 2 < len(lines) else ''
        legal_description, city = split_legal_city(legal_line)
        if city == 'Unknown':
            i += 1
            continue

        bid_cost = parse_money(entry['bid_cost'])
        property_address = clean_text(entry['property_address']) or 'Unknown'
        extraction_confidence = infer_extraction_confidence(entry['parcel_id'], property_address, legal_description, bid_cost)
        if property_address.upper() == 'ADDRESS UNKNOWN':
            extraction_confidence = 'Low' if extraction_confidence == 'Medium' else extraction_confidence

        rows.append({
            'parcel_id': clean_text(entry['parcel_id']),
            'owner_name': 'Unknown',
            'property_address': property_address,
            'city': city,
            'state': 'OK',
            'zip_code': 'Unknown',
            'legal_description': legal_description,
            'bid_cost': bid_cost,
            'property_type': clean_text(entry['property_type'].upper()) or 'Unknown',
            'source_page': page_number,
            'raw_text': clean_text(' | '.join(filter(None, [lines[i], legal_line, subdivision]))),
            'extraction_confidence': extraction_confidence,
            'prop_no': clean_text(entry['prop_no']),
            'subdivision': subdivision,
            'land_sqft': clean_text(entry['land_sqft']),
            'resale_costs_fees': clean_text(entry.get('resale_costs_fees') or ''),
            'notes': clean_text(entry.get('notes') or ''),
        })
        i += 3
    return rows


def main():
    if not PDF.exists():
        raise FileNotFoundError(f'Missing required auction file: {PDF}')

    all_rows = []
    with pdfplumber.open(PDF) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            lines = page_lines(page)
            all_rows.extend(parse_page(lines, page_number))
            if page_number % 25 == 0:
                print(f'Processed {page_number}/{len(pdf.pages)} pages...', flush=True)

    deduped = OrderedDict()
    for idx, row in enumerate(all_rows):
        key = row['parcel_id'] or f'missing-{idx}'
        if key not in deduped:
            deduped[key] = row
    rows = list(deduped.values())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        'parcel_id', 'owner_name', 'property_address', 'city', 'state', 'zip_code', 'legal_description',
        'bid_cost', 'property_type', 'source_page', 'raw_text', 'extraction_confidence', 'prop_no', 'subdivision',
        'land_sqft', 'resale_costs_fees', 'notes'
    ]
    with OUT.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    rows_with_bid = sum(1 for r in rows if r['bid_cost'] is not None)
    rows_without_bid = len(rows) - rows_with_bid
    rows_with_address = sum(1 for r in rows if r['property_address'] and r['property_address'] != 'Unknown')
    rows_without_address = len(rows) - rows_with_address
    rows_with_parcel = sum(1 for r in rows if r['parcel_id'])

    print(f'Total extracted rows: {len(rows)}')
    print(f'Rows with bid cost: {rows_with_bid}')
    print(f'Rows without bid cost: {rows_without_bid}')
    print(f'Rows with address: {rows_with_address}')
    print(f'Rows without address: {rows_without_address}')
    print(f'Rows with parcel ID: {rows_with_parcel}')
    print(f'Wrote cleaned CSV: {OUT}')


if __name__ == '__main__':
    main()
