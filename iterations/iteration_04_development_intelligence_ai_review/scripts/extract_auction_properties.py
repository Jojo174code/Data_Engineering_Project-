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

from common_iter_utils import CLEANED_DIR, INPUT_PDF, LOG_DIR, clean_text, infer_extraction_confidence, parse_money, split_legal_city, write_log

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
OUT_CSV = CLEANED_DIR / 'cleaned_auction_properties.csv'
LOG_FILE = LOG_DIR / 'extraction_log.txt'


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


def parse_page(lines: list[str], page_number: int) -> list[dict]:
    rows = []
    i = 0
    while i < len(lines):
        m = ENTRY_RE.match(lines[i])
        if not m:
            i += 1
            continue
        entry = m.groupdict()
        legal_line = clean_text(lines[i + 1]) if i + 1 < len(lines) else 'Unknown'
        subdivision = clean_text(lines[i + 2]) if i + 2 < len(lines) else 'Unknown'
        legal_description, city = split_legal_city(legal_line)
        bid_cost = parse_money(entry['bid_cost'])
        extraction_confidence, extraction_notes = infer_extraction_confidence(entry['parcel_id'], entry['property_address'], legal_description, bid_cost)
        rows.append({
            'parcel_id': clean_text(entry['parcel_id']) or 'Unknown',
            'owner_name': 'Unknown',
            'property_address': clean_text(entry['property_address']) or 'Unknown',
            'city': city or 'Unknown',
            'state': 'OK',
            'zip_code': 'Unknown',
            'legal_description': legal_description or 'Unknown',
            'bid_cost': bid_cost,
            'property_type': clean_text(entry['property_type'].upper()) or 'Unknown',
            'source_page': page_number,
            'raw_text': clean_text(' | '.join(filter(None, [lines[i], legal_line, subdivision]))),
            'extraction_confidence': extraction_confidence,
            'extraction_notes': extraction_notes or 'Unknown',
        })
        i += 3
    return rows


def main():
    if not INPUT_PDF.exists():
        raise FileNotFoundError(f'Missing required input PDF: {INPUT_PDF}')

    all_rows = []
    raw_candidates = 0
    log_lines = []
    with pdfplumber.open(INPUT_PDF) as pdf:
        total_pages = len(pdf.pages)
        for page_number, page in enumerate(pdf.pages, start=1):
            lines = page_lines(page)
            raw_candidates += sum(1 for line in lines if ENTRY_RE.match(line))
            all_rows.extend(parse_page(lines, page_number))
            if page_number % 25 == 0:
                msg = f'Processed {page_number}/{total_pages} pages...'
                print(msg, flush=True)
                log_lines.append(msg)

    deduped = OrderedDict()
    for idx, row in enumerate(all_rows):
        key = row['parcel_id'] if row['parcel_id'] != 'Unknown' else f'unknown-{idx}'
        if key not in deduped:
            deduped[key] = row
    rows = list(deduped.values())
    if not rows:
        raise ValueError('Extraction produced 0 rows, stopping for debug.')

    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        'parcel_id', 'owner_name', 'property_address', 'city', 'state', 'zip_code', 'legal_description', 'bid_cost',
        'property_type', 'source_page', 'raw_text', 'extraction_confidence', 'extraction_notes'
    ]
    with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    rows_with_parcel = sum(1 for r in rows if r['parcel_id'] != 'Unknown')
    rows_with_address = sum(1 for r in rows if r['property_address'] != 'Unknown')
    rows_with_bid = sum(1 for r in rows if r['bid_cost'] is not None)
    rows_missing_bid = len(rows) - rows_with_bid

    summary = [
        f'total PDF pages processed: {total_pages}',
        f'total raw candidate rows found: {raw_candidates}',
        f'total extracted rows: {len(rows)}',
        f'rows with parcel_id: {rows_with_parcel}',
        f'rows with address: {rows_with_address}',
        f'rows with bid_cost: {rows_with_bid}',
        f'rows missing bid_cost: {rows_missing_bid}',
        'first 10 extracted rows:',
    ]
    summary.extend(str(row) for row in rows[:10])
    for line in summary:
        print(line)
    write_log(LOG_FILE, log_lines + summary)


if __name__ == '__main__':
    main()
