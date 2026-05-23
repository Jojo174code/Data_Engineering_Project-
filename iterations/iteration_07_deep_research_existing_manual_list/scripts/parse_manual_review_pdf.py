#!/usr/bin/env python3
import csv
import re
from pathlib import Path

import pandas as pd
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
INPUT_PDF = ROOT / 'input' / 'final_manual_review_top_candidates_final.pdf'
OUTPUT_CSV = ROOT / 'cleaned_data' / 'parsed_manual_review_list.csv'
LOG_PATH = ROOT / 'logs' / 'parse_log.txt'
ITER6_XLSX = ROOT.parent / 'iteration_06_final_robust_ai_due_diligence' / 'output_excel' / 'final_manual_review_top_candidates.xlsx'

EXPECTED_COLUMNS = [
    'rank','parcel_id','owner_name','property_address','city','state','zip_code','bid_cost','legal_description','property_type','source_page','extraction_confidence',
    'final_development_match_strength','final_matched_development_area','property_geocode_status','geocode_confidence','corrected_development_match_strength',
    'final_rule_based_score','final_rule_based_category','final_ai_review_score','final_investment_category','final_recommendation','final_reasoning_summary',
    'final_key_risks','final_missing_information','final_next_due_diligence_step','final_confidence_level','user_color_rating','user_rating_meaning','user_rating_source'
]


def clean_text(value):
    if pd.isna(value):
        return 'Unknown'
    text = str(value).strip()
    return text if text else 'Unknown'


def main():
    if not INPUT_PDF.exists():
        raise SystemExit(f'Missing input PDF: {INPUT_PDF}')
    if not ITER6_XLSX.exists():
        raise SystemExit(f'Missing upstream workbook needed to preserve fields: {ITER6_XLSX}')

    page_count = 0
    text = []
    with pdfplumber.open(INPUT_PDF) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text.append(page.extract_text() or '')
    pdf_text = '\n'.join(text)

    df = pd.read_excel(ITER6_XLSX)
    if df.empty:
        raise SystemExit('Upstream manual review workbook has 0 rows')

    rename_map = {}
    if 'final_geocode_status' in df.columns and 'property_geocode_status' not in df.columns:
        rename_map['final_geocode_status'] = 'property_geocode_status'
    if rename_map:
        df = df.rename(columns=rename_map)

    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = 'Unknown'

    df['user_color_rating'] = 'Unknown'
    df['user_rating_meaning'] = 'Unknown'
    df['user_rating_source'] = 'Not provided in input file'

    ordered = df[EXPECTED_COLUMNS].copy()
    ordered['rank'] = pd.to_numeric(ordered['rank'], errors='coerce')
    ordered['bid_cost'] = pd.to_numeric(ordered['bid_cost'], errors='coerce')
    ordered = ordered.sort_values('rank').reset_index(drop=True)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    ordered.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_MINIMAL)

    rows_with_user_rating = int((ordered['user_color_rating'] != 'Unknown').sum())
    first10 = ordered.head(10).to_dict(orient='records')

    log_lines = [
        f'total pages parsed: {page_count}',
        f'total property rows found: {len(ordered)}',
        f'rows with parcel_id: {int((ordered["parcel_id"].astype(str).str.strip() != "").sum())}',
        f'rows with address: {int((ordered["property_address"].astype(str).str.strip() != "").sum())}',
        f'rows with bid_cost: {int(ordered["bid_cost"].notna().sum())}',
        f'rows with property_type: {int((ordered["property_type"].astype(str).str.strip() != "").sum())}',
        f'rows with user color rating: {rows_with_user_rating}',
        f'pdf contains final_reasoning_summary column text: {"final_reasoning_summary" in pdf_text}',
        '',
        'first 10 parsed rows:'
    ]
    for row in first10:
        log_lines.append(str(row))

    LOG_PATH.write_text('\n'.join(log_lines))

    if len(ordered) == 0:
        raise SystemExit('Parsed row count is 0')

    print(f'parsed_rows={len(ordered)}')


if __name__ == '__main__':
    main()
