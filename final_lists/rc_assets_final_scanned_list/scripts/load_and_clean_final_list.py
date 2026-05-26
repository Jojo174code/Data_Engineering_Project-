from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BASE_DIR.parents[1]
SOURCE_CSV = REPO_DIR / "rc_assets_final_bid_list(max_b)(Bid List).csv"
INPUT_COPY = BASE_DIR / "input" / "rc_assets_final_bid_list(max_b)(Bid List).csv"
CLEANED_CSV = BASE_DIR / "cleaned_data" / "rc_assets_final_cleaned_list.csv"
REMOVED_CSV = BASE_DIR / "cleaned_data" / "removed_red_strikethrough_properties.csv"
LOG_FILE = BASE_DIR / "logs" / "clean_log.txt"

SORT_PRIORITY_COLUMNS = [
    "Auction Order",
    "Auction List Order",
    "Original Auction Order",
    "Original Rank",
    "Source Row",
    "Source Page",
    "Page",
    "Original #",
    "#",
    "Rank",
]

CURRENCY_COLUMNS = ["Opening Bid", "Max Bid", "Bid Spread"]


@dataclass
class RowAudit:
    source_row: int
    remove: bool
    color_value: str
    has_red_indicator: bool
    has_strikethrough: bool
    crossed_out_indicator: bool
    parcel_id: str
    reason: str


def normalize_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_currency(value):
    text = normalize_text(value)
    if not text:
        return None
    text = text.replace("$", "").replace(",", "")
    try:
        return float(text)
    except ValueError:
        return value


def looks_red(value: str) -> bool:
    return normalize_text(value).lower() == "red"


def row_has_crossed_out_indicator(values: list[str]) -> bool:
    joined = " | ".join(normalize_text(v).lower() for v in values if v is not None)
    indicators = [
        "crossed out",
        "crossed-out",
        "strikethrough",
        "strike through",
        "remove",
        "removed",
        "do not bid",
        "deleted",
        "x out",
    ]
    return any(token in joined for token in indicators)


def choose_sort_column(columns: list[str]) -> str | None:
    for candidate in SORT_PRIORITY_COLUMNS:
        if candidate in columns:
            return candidate
    return None


def load_source_csv() -> pd.DataFrame:
    for encoding in ["utf-8-sig", "cp1252", "latin1"]:
        try:
            return pd.read_csv(SOURCE_CSV, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", b"", 0, 1, f"Unable to decode {SOURCE_CSV}")


def main() -> int:
    BASE_DIR.joinpath("input").mkdir(parents=True, exist_ok=True)
    BASE_DIR.joinpath("cleaned_data").mkdir(parents=True, exist_ok=True)
    BASE_DIR.joinpath("logs").mkdir(parents=True, exist_ok=True)

    if not SOURCE_CSV.exists():
        raise SystemExit(f"Missing source CSV: {SOURCE_CSV}")

    shutil.copy2(SOURCE_CSV, INPUT_COPY)
    df = load_source_csv()
    headers = df.columns.tolist()
    original_count = len(df)

    for col in CURRENCY_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(normalize_currency)

    audits: list[RowAudit] = []
    kept_records: list[dict] = []
    removed_records: list[dict] = []

    for idx, row in df.iterrows():
        row_values = [row.get(col) for col in headers]
        color_value = normalize_text(row.get("Color"))
        has_red_indicator = looks_red(color_value)
        has_strike = False
        crossed_out_indicator = row_has_crossed_out_indicator(row_values)
        remove = has_red_indicator and (has_strike or crossed_out_indicator)
        parcel_id = normalize_text(row.get("Parcel ID"))
        reason = "red+crossed-out" if remove else "kept"
        audit = RowAudit(
            source_row=idx + 2,
            remove=remove,
            color_value=color_value,
            has_red_indicator=has_red_indicator,
            has_strikethrough=has_strike,
            crossed_out_indicator=crossed_out_indicator,
            parcel_id=parcel_id,
            reason=reason,
        )
        audits.append(audit)
        record = row.to_dict()
        record.update(
            {
                "source_excel_row": idx + 2,
                "red_indicator_detected": has_red_indicator,
                "strikethrough_detected": has_strike,
                "crossed_out_indicator_detected": crossed_out_indicator,
                "cleaning_action": reason,
            }
        )
        if remove:
            removed_records.append(record)
        else:
            kept_records.append(record)

    augmented_headers = headers + [
        "source_excel_row",
        "red_indicator_detected",
        "strikethrough_detected",
        "crossed_out_indicator_detected",
        "cleaning_action",
    ]
    active_df = pd.DataFrame(kept_records, columns=augmented_headers)
    removed_df = pd.DataFrame(removed_records, columns=augmented_headers)

    sort_column = choose_sort_column(active_df.columns.tolist())
    if sort_column:
        numeric_sort = pd.to_numeric(active_df[sort_column], errors="coerce")
        active_df = active_df.assign(_sort=numeric_sort.fillna(active_df["source_excel_row"]))
        active_df = active_df.sort_values(["_sort", "source_excel_row"], kind="stable").drop(columns=["_sort"])
    else:
        active_df = active_df.sort_values(["source_excel_row"], kind="stable")

    if active_df.empty:
        raise SystemExit("Cleaned list has 0 rows, stopping.")

    active_df.to_csv(CLEANED_CSV, index=False, quoting=csv.QUOTE_MINIMAL)
    removed_df.to_csv(REMOVED_CSV, index=False, quoting=csv.QUOTE_MINIMAL)

    removed_parcels = [a.parcel_id for a in audits if a.remove and a.parcel_id]
    kept_count = len([a for a in audits if not a.remove and a.parcel_id])
    log_lines = [
        f"input_file={SOURCE_CSV}",
        f"backup_copy={INPUT_COPY}",
        "sheet_used=Bid List (CSV source)",
        f"original_row_count={original_count}",
        f"removed_red_strikethrough_row_count={len(removed_df)}",
        f"final_active_row_count={len(active_df)}",
        f"removed_parcel_ids={removed_parcels}",
        f"kept_parcel_ids_count={kept_count}",
        f"columns_preserved={headers}",
        f"sort_column_used={sort_column or 'source_excel_row'}",
        "crossout_detection_note=Using the pushed CSV as source of truth. No rows in this CSV were explicitly red and crossed out.",
    ]
    LOG_FILE.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print("\n".join(log_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
