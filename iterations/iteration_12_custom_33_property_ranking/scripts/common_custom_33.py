#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import pandas as pd

ITERATION_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ITERATION_ROOT.parents[1]
INPUT_DIR = ITERATION_ROOT / 'input'
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
OUTPUT_DIR = ITERATION_ROOT / 'output_excel'
SCRIPTS_DIR = ITERATION_ROOT / 'scripts'
LOG_DIR = ITERATION_ROOT / 'logs'

ALLOWED_TIERS = [
    'Tier 1 Priority',
    'Tier 2 Strong Review',
    'Tier 3 Watch',
    'Tier 4 High Risk',
]
ALLOWED_RECOMMENDATIONS = [
    'Bid Candidate',
    'Research First',
    'Drive By',
    'Watch',
    'Avoid',
]
ALLOWED_CONFIDENCE = ['High', 'Medium', 'Low']

CUSTOM_PROPERTIES = [
    {'source_list': 'Manual Review', 'original_rank': 1, 'parcel_id': '00575-93-06-01170', 'property_address': '511 S VICTOR AV E', 'bid_cost': 3910.27},
    {'source_list': 'Manual Review', 'original_rank': 2, 'parcel_id': '34300-03-32-15230', 'property_address': '135 N COLUMBIA AV E', 'bid_cost': 3005.69},
    {'source_list': 'Manual Review', 'original_rank': 8, 'parcel_id': '44200-02-11-04390', 'property_address': '4696 N BOULDER AV W', 'bid_cost': 3075.02},
    {'source_list': 'Manual Review', 'original_rank': 9, 'parcel_id': '34750-02-26-08160', 'property_address': '2507 N MAIN ST E TULSA', 'bid_cost': 3097.02},
    {'source_list': 'Manual Review', 'original_rank': 11, 'parcel_id': '23175-03-30-13610', 'property_address': '2526 N QUAKER AV E', 'bid_cost': 3115.02},
    {'source_list': 'Manual Review', 'original_rank': 15, 'parcel_id': '53775-02-02-00220', 'property_address': '6105 N MAIN ST E TULSA', 'bid_cost': 3140.32},
    {'source_list': 'Manual Review', 'original_rank': 17, 'parcel_id': '07600-02-24-01200', 'property_address': '820 E 36 ST N', 'bid_cost': 3152.35},
    {'source_list': 'Manual Review', 'original_rank': 21, 'parcel_id': '44200-02-14-06630', 'property_address': '18 E 44 PL N', 'bid_cost': 3183.01},
    {'source_list': 'Manual Review', 'original_rank': 26, 'parcel_id': '07675-02-13-01140', 'property_address': '4018 N GARRISON AV E', 'bid_cost': 3245.67},
    {'source_list': 'Manual Review', 'original_rank': 34, 'parcel_id': '17675-02-24-07570', 'property_address': '750 E 32 PL N', 'bid_cost': 3310.33},
    {'source_list': 'Manual Review', 'original_rank': 35, 'parcel_id': '25500-03-29-06060', 'property_address': '2625 E TECUMSEH ST N', 'bid_cost': 3310.33},
    {'source_list': 'Manual Review', 'original_rank': 36, 'parcel_id': '44200-02-11-03380', 'property_address': '4627 N BOSTON AV E', 'bid_cost': 3311.0},
    {'source_list': 'Manual Review', 'original_rank': 38, 'parcel_id': '25375-03-29-05240', 'property_address': '3215 E XYLER ST N', 'bid_cost': 3313.8},
    {'source_list': 'Manual Review', 'original_rank': 40, 'parcel_id': '44250-02-12-15190', 'property_address': '549 E 54 PL N', 'bid_cost': 3327.0},
    {'source_list': 'Manual Review', 'original_rank': 43, 'parcel_id': '46465-92-11-31880', 'property_address': '2034 S PHOENIX AV W', 'bid_cost': 3329.0},
    {'source_list': '$1,500-$2,000', 'original_rank': 2, 'parcel_id': '47175-03-29-18430', 'property_address': '1903 N FLORENCE PL E', 'bid_cost': 1549.17},
    {'source_list': '$1,500-$2,000', 'original_rank': 7, 'parcel_id': '38675-93-10-06110', 'property_address': '1321 S DARLINGTON AV E', 'bid_cost': 1603.63},
    {'source_list': '$1,500-$2,000', 'original_rank': 12, 'parcel_id': '40250-03-31-14910', 'property_address': '1945 E NEWTON ST N', 'bid_cost': 1613.17},
    {'source_list': '$1,500-$2,000', 'original_rank': 28, 'parcel_id': '40825-02-13-08310', 'property_address': '4337 N GARRISON AV E', 'bid_cost': 1697.16},
    {'source_list': '$1,500-$2,000', 'original_rank': 31, 'parcel_id': '24675-03-31-13270', 'property_address': '1404 N ST LOUIS AV E', 'bid_cost': 1697.83},
    {'source_list': '$1,500-$2,000', 'original_rank': 43, 'parcel_id': '40850-02-12-07900', 'property_address': '517 E 47 PL N', 'bid_cost': 1771.82},
    {'source_list': '$1,500-$2,000', 'original_rank': 44, 'parcel_id': '40250-03-31-15190', 'property_address': '2143 E NEWTON ST N', 'bid_cost': 1778.61},
    {'source_list': '$1,500-$2,000', 'original_rank': 46, 'parcel_id': '44675-92-08-04450', 'property_address': '5128 W CHARLES PAGE', 'bid_cost': 1783.15},
    {'source_list': '$1,000-$1,500', 'original_rank': 5, 'parcel_id': '24925-02-36-17420', 'property_address': '1084 N NORFOLK AV E', 'bid_cost': 1199.79},
    {'source_list': '$1,000-$1,500', 'original_rank': 13, 'parcel_id': '40875-02-13-11530', 'property_address': '210 E 44 ST N', 'bid_cost': 1184.93},
    {'source_list': '$1,000-$1,500', 'original_rank': 16, 'parcel_id': '26725-02-25-16640', 'property_address': '515 E UTE ST N', 'bid_cost': 1216.55},
    {'source_list': '$1,000-$1,500', 'original_rank': 21, 'parcel_id': '05400-02-25-04330', 'property_address': '524 E YOUNG ST N', 'bid_cost': 1418.58},
    {'source_list': '$1,000-$1,500', 'original_rank': 32, 'parcel_id': '41025-02-01-04710', 'property_address': '5901 N GARRISON PL E', 'bid_cost': 1273.2},
    {'source_list': '$1,000-$1,500', 'original_rank': 33, 'parcel_id': '41025-02-01-05430', 'property_address': '522 E 59 ST N', 'bid_cost': 1273.2},
    {'source_list': '$1,000-$1,500', 'original_rank': 36, 'parcel_id': '43300-03-29-09940', 'property_address': '2311 N ATLANTA AV E', 'bid_cost': 1179.88},
    {'source_list': '$1,000-$1,500', 'original_rank': 38, 'parcel_id': '05850-03-30-04070', 'property_address': '1844 N TRENTON AV E', 'bid_cost': 1297.53},
    {'source_list': '$900-$1,000', 'original_rank': 1, 'parcel_id': '01875-03-19-00200', 'property_address': '2612 N TRENTON AV E', 'bid_cost': 962.57},
    {'source_list': '$900-$1,000', 'original_rank': 7, 'parcel_id': '44675-92-08-04460', 'property_address': '5134 W CHARLES PAGE', 'bid_cost': 907.78},
]


def ensure_dirs() -> None:
    for path in [INPUT_DIR, CLEANED_DIR, OUTPUT_DIR, SCRIPTS_DIR, LOG_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def clean_text(value: Any, default: str = 'Unknown') -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    text = str(value).strip()
    if not text or text.lower() == 'nan':
        return default
    return text


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace('$', '').replace(',', '').strip()
        number = float(value)
        if math.isnan(number):
            return default
        return number
    except Exception:
        return default


def safe_int(value: Any, default: int | None = None) -> int | None:
    num = safe_float(value, None)
    if num is None:
        return default
    return int(round(num))


def normalize_address(address: Any) -> str:
    text = clean_text(address)
    text = text.upper()
    text = re.sub(r'\bTULSA\b', '', text)
    text = re.sub(r'\bOKLAHOMA\b', '', text)
    text = re.sub(r'\bOK\b', '', text)
    text = re.sub(r'\bAV\b', 'AVE', text)
    text = re.sub(r'\bPL\b', 'PL', text)
    text = re.sub(r'\bST\b', 'ST', text)
    text = re.sub(r'\bRD\b', 'RD', text)
    text = re.sub(r'\bDR\b', 'DR', text)
    text = re.sub(r'\bN\s+([A-Z])', r'N \1', text)
    text = re.sub(r'\s+', ' ', text).strip(' ,')
    return text


def parse_pct(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip().replace('%', '')
        if not text or text.lower() in {'unknown', 'unknown.'}:
            return None
        num = safe_float(text, None)
        if num is None:
            return None
        return num / 100.0 if num > 1 else num
    num = safe_float(value, None)
    if num is None:
        return None
    return num / 100.0 if num > 1 else num


def confidence_rank(value: Any) -> int:
    mapping = {'High': 3, 'Medium': 2, 'Low': 1, 'Unknown': 0, 'Unknown.': 0}
    return mapping.get(clean_text(value), 0)


def risk_rank(value: Any) -> int:
    mapping = {'Low': 0, 'Medium': 1, 'Unknown': 2, 'Unknown.': 2, 'High': 3}
    return mapping.get(clean_text(value), 2)


def write_log(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + ('\n' if lines else ''))


def json_line(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)
