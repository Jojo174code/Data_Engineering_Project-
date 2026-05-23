#!/usr/bin/env python3
from __future__ import annotations

import sys

import pandas as pd

from common_custom_33 import CLEANED_DIR, CUSTOM_PROPERTIES, INPUT_DIR, LOG_DIR, ensure_dirs, write_log

INPUT_CSV = INPUT_DIR / 'custom_33_properties.csv'
BASE_CSV = CLEANED_DIR / 'custom_33_base.csv'
LOG_FILE = LOG_DIR / 'prepare_log.txt'


def main() -> int:
    ensure_dirs()
    df = pd.DataFrame(CUSTOM_PROPERTIES)
    df.insert(0, 'custom_id', [f'C33-{i:02d}' for i in range(1, len(df) + 1)])
    df['city'] = 'Tulsa'
    df['state'] = 'OK'
    df = df[['custom_id', 'source_list', 'original_rank', 'parcel_id', 'property_address', 'city', 'state', 'bid_cost']]

    duplicate_rows = df[df.duplicated(subset=['parcel_id'], keep=False)].copy()
    log_lines = [f'initial row count: {len(df)}']
    if not duplicate_rows.empty:
        exact_dupes = df[df.duplicated(keep=False)]
        if not exact_dupes.empty:
            df = df.drop_duplicates().copy()
            log_lines.append(f'exact duplicate rows removed: {len(exact_dupes) - len(exact_dupes.drop_duplicates())}')
        else:
            log_lines.append('duplicate parcel IDs detected but not removed because rows were not exact duplicates')
            write_log(LOG_FILE, log_lines)
            print('prepare_custom_33 failed: duplicate parcel IDs were not exact duplicates', file=sys.stderr)
            return 1
    else:
        log_lines.append('duplicate parcel IDs detected: 0')

    if len(df) != 33:
        log_lines.append(f'validation failed: expected 33 rows, found {len(df)}')
        write_log(LOG_FILE, log_lines)
        print(f'prepare_custom_33 failed: expected 33 rows, found {len(df)}', file=sys.stderr)
        return 1

    INPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    BASE_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(INPUT_CSV, index=False)
    df.to_csv(BASE_CSV, index=False)
    log_lines.extend([
        f'final row count: {len(df)}',
        f'input written: {INPUT_CSV}',
        f'base written: {BASE_CSV}',
        'validation passed: row count is exactly 33',
    ])
    write_log(LOG_FILE, log_lines)
    print(f'prepared_rows={len(df)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
