from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from pypdf import PdfReader

REPO_DIR = Path(__file__).resolve().parents[3]
BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_WORKBOOK = BASE_DIR / "output_excel" / "rc_assets_final_scanned_bid_list.xlsx"
AUCTION_PDF = REPO_DIR / "2026 auction.pdf"
CORRECTED_WORKBOOK = BASE_DIR / "output_excel" / "rc_assets_final_scanned_bid_list_CORRECTED.xlsx"
CORRECTED_ACTIVE_CSV = BASE_DIR / "cleaned_data" / "rc_assets_final_cleaned_list_CORRECTED.csv"
DELETED_CSV = BASE_DIR / "cleaned_data" / "deleted_properties.csv"
REPORT = BASE_DIR / "logs" / "validation_report_CORRECTED.txt"

DELETE_IDS = {
    "44675-92-08-04460",
    "24925-02-36-17420",
    "05400-02-25-04330",
    "44675-92-08-04450",
    "34300-03-32-15230",
    "34750-02-26-08160",
    "07600-02-24-01200",
    "46465-92-11-31880",
    "00575-93-06-01170",
}
MANUAL_AUCTION_OVERRIDES = {
    "53775-02-02-00220": (967, 143, 967),
    "53825-02-02-01690": (971, 144, 971),
    "90306-03-06-24020": (1249, 184, 1249),
    "96203-62-03-50220": (1303, 193, 1303),
}
ACTIVE_SHEETS = ["Final List - Auction Order", "Cheapest First", "Top Candidates", "Crime Scan", "Economic Scan"]
EXPECTED_SHEETS = ACTIVE_SHEETS + ["Deleted Properties", "Summary"]
COLOR_EXPECTATIONS = {"Green": {"00E2F0D9", "00000000"}, "Blue": {"00DDEBF7"}, "Purple": {"00E4DFEC"}}


def extract_auction_map(pdf_path: Path) -> dict[str, tuple[int, int, int]]:
    reader = PdfReader(str(pdf_path))
    pattern = re.compile(r"\b(\d{1,4})\s+\n\s*(\d{5}-\d{2}-\d{2}-\d{5})\b", re.M)
    order_map: dict[str, tuple[int, int, int]] = {}
    sequence = 0
    for page_no, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for match in pattern.finditer(text):
            prop_no = int(match.group(1))
            parcel = match.group(2)
            if parcel not in order_map:
                sequence += 1
                order_map[parcel] = (prop_no, page_no, sequence)
    order_map.update(MANUAL_AUCTION_OVERRIDES)
    return order_map


def staged_paths() -> list[str]:
    proc = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=REPO_DIR, capture_output=True, text=True, check=False)
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def parcel_list(df: pd.DataFrame) -> list[str]:
    return df["Parcel ID"].astype(str).str.strip().tolist() if "Parcel ID" in df.columns else []


def check_main_auction_sort(df: pd.DataFrame, auction_map: dict[str, tuple[int, int, int]]) -> bool:
    keys = []
    for _, row in df.iterrows():
        parcel = str(row["Parcel ID"]).strip()
        match = auction_map.get(parcel)
        if match:
            prop_no, page_no, sequence = match
            keys.append((0, prop_no, page_no, sequence, float(row.get("source_excel_row", 0) or 0)))
        else:
            fallback = pd.to_numeric(pd.Series([row.get("Original Rank", row.get("source_excel_row"))]), errors="coerce").iloc[0]
            fallback = float(fallback) if pd.notna(fallback) else 999999.0
            keys.append((1, 999999, 999999, 999999, fallback))
    return keys == sorted(keys)


def check_not_price_sorted(df: pd.DataFrame) -> bool:
    current = parcel_list(df)
    by_price = df.assign(_bid=pd.to_numeric(df["Opening Bid"], errors="coerce")).sort_values(["_bid", "source_excel_row"], kind="stable")
    return current != parcel_list(by_price)


def color_fill_ok(workbook_path: Path, sheet_name: str) -> bool:
    wb = load_workbook(workbook_path)
    ws = wb[sheet_name]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    color_col = headers.index("Color") + 1
    max_bid_col = headers.index("Max Bid") + 1
    saw_non_green_fill = False
    saw_max_bid_fill = False
    for r in range(2, ws.max_row + 1):
        color_value = str(ws.cell(r, color_col).value).strip()
        row_fill = str(ws.cell(r, 1).fill.fgColor.rgb or "")
        max_bid_fill = str(ws.cell(r, max_bid_col).fill.fgColor.rgb or "")
        if max_bid_fill and max_bid_fill != "00000000":
            saw_max_bid_fill = True
        if color_value in {"Blue", "Purple"} and row_fill in COLOR_EXPECTATIONS[color_value]:
            saw_non_green_fill = True
    return saw_non_green_fill and saw_max_bid_fill


def main() -> int:
    checks: list[tuple[str, bool]] = []
    for path in [INPUT_WORKBOOK, AUCTION_PDF, CORRECTED_WORKBOOK, CORRECTED_ACTIVE_CSV, DELETED_CSV]:
        checks.append((f"exists:{path.name}", path.exists()))

    base_df = pd.read_excel(INPUT_WORKBOOK, sheet_name="Final List - Auction Order")
    corrected_df = pd.read_excel(CORRECTED_WORKBOOK, sheet_name="Final List - Auction Order")
    deleted_df = pd.read_excel(CORRECTED_WORKBOOK, sheet_name="Deleted Properties")
    corrected_csv_df = pd.read_csv(CORRECTED_ACTIVE_CSV)
    deleted_csv_df = pd.read_csv(DELETED_CSV)
    wb = load_workbook(CORRECTED_WORKBOOK)
    checks.append(("corrected_workbook_opens", True))
    checks.append(("required_sheets_exist", all(sheet in wb.sheetnames for sheet in EXPECTED_SHEETS)))

    all_original_cols = list(base_df.columns)
    checks.append(("all_original_columns_preserved", all(col in corrected_df.columns for col in all_original_cols)))
    checks.append(("grade_column_preserved", "Grade" in corrected_df.columns))
    checks.append(("max_bid_column_preserved", "Max Bid" in corrected_df.columns))

    active_ids = set(parcel_list(corrected_df))
    deleted_ids_sheet = set(parcel_list(deleted_df))
    deleted_ids_csv = set(parcel_list(deleted_csv_df))
    checks.append(("9_deleted_ids_not_in_active_sheet", DELETE_IDS.isdisjoint(active_ids)))
    checks.append(("9_deleted_ids_in_deleted_sheet", DELETE_IDS.issubset(deleted_ids_sheet)))
    checks.append(("9_deleted_ids_in_deleted_csv", DELETE_IDS.issubset(deleted_ids_csv)))
    checks.append(("active_count_previous_minus_9", len(corrected_df) == len(base_df) - 9))
    checks.append(("no_duplicate_active_parcel_ids", not corrected_df["Parcel ID"].astype(str).duplicated().any()))

    checks.append(("deleted_ids_not_elsewhere", True))
    for sheet in ACTIVE_SHEETS:
        df = pd.read_excel(CORRECTED_WORKBOOK, sheet_name=sheet)
        if "Parcel ID" in df.columns and not DELETE_IDS.isdisjoint(set(parcel_list(df))):
            checks[-1] = ("deleted_ids_not_elsewhere", False)
            break

    auction_map = extract_auction_map(AUCTION_PDF)
    checks.append(("main_sheet_sorted_by_land_list_appearance", check_main_auction_sort(corrected_df, auction_map)))
    checks.append(("all_active_rows_have_auction_list_no", corrected_df["Auction List No"].notna().all()))
    checks.append(("main_sheet_not_price_sorted", check_not_price_sorted(corrected_df)))
    checks.append(("colors_preserved_or_recreated", color_fill_ok(CORRECTED_WORKBOOK, "Final List - Auction Order")))
    checks.append(("corrected_csv_row_count_matches_sheet", len(corrected_csv_df) == len(corrected_df)))

    staged = staged_paths()
    checks.append(("env_not_staged", ".env" not in staged and not any(path.endswith("/.env") for path in staged)))
    checks.append(("venv_not_staged", ".venv" not in staged and not any(path.startswith(".venv/") or "/.venv/" in path for path in staged)))

    ok = all(flag for _, flag in checks)
    lines = [f"{name}={'PASS' if flag else 'FAIL'}" for name, flag in checks]
    lines.append(f"previous_active_property_count={len(base_df)}")
    lines.append(f"deleted_property_count={len(deleted_df)}")
    lines.append(f"final_active_property_count={len(corrected_df)}")
    lines.append(f"validation={'PASS' if ok else 'FAIL'}")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
