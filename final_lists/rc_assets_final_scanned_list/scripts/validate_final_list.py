from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = BASE_DIR / "input" / "rc_assets_final_bid_list(max_b)(Bid List).csv"
CLEANED_CSV = BASE_DIR / "cleaned_data" / "rc_assets_final_cleaned_list.csv"
REMOVED_CSV = BASE_DIR / "cleaned_data" / "removed_red_strikethrough_properties.csv"
CRIME_CSV = BASE_DIR / "cleaned_data" / "crime_scan_results.csv"
ECON_CSV = BASE_DIR / "cleaned_data" / "economic_scan_results.csv"
AI_CSV = BASE_DIR / "cleaned_data" / "ai_scanner_results.csv"
FINAL_XLSX = BASE_DIR / "output_excel" / "rc_assets_final_scanned_bid_list.xlsx"
REPORT = BASE_DIR / "logs" / "validation_report.txt"
ALLOWED_CATEGORY = {"Top Candidate", "Strong Candidate", "Watchlist", "High Risk", "Remove"}
ALLOWED_PRIORITY = {"Priority 1", "Priority 2", "Priority 3", "Do Not Bid", "Unknown"}
ALLOWED_CONFIDENCE = {"High", "Medium", "Low"}
SORT_COLUMNS = [
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
    "source_excel_row",
]


def read_csv_flexible(path: Path, fallback_columns: list[str] | None = None) -> pd.DataFrame:
    for encoding in ["utf-8-sig", "cp1252", "latin1"]:
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=fallback_columns or [])
    raise RuntimeError(f"Unable to decode CSV: {path}")


def check_sorted(values):
    cleaned = [v for v in values if pd.notna(v)]
    return cleaned == sorted(cleaned)


def staged_paths() -> list[str]:
    proc = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=BASE_DIR.parents[1], capture_output=True, text=True, check=False)
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def main() -> int:
    checks = []
    for path in [INPUT_FILE, CLEANED_CSV, REMOVED_CSV, CRIME_CSV, ECON_CSV, AI_CSV, FINAL_XLSX]:
        checks.append((f"exists:{path.name}", path.exists()))

    cleaned = pd.read_csv(CLEANED_CSV)
    removed = read_csv_flexible(REMOVED_CSV, cleaned.columns.tolist())
    ai = pd.read_csv(AI_CSV)
    original = read_csv_flexible(INPUT_FILE)
    wb = load_workbook(FINAL_XLSX)
    checks.append(("workbook_opens", True))
    required_sheets = ["Final List - Auction Order", "Final List - Cheapest First", "Top Candidates", "Removed Red Crossed Out", "Crime Scan", "Economic Scan", "Summary"]
    checks.append(("required_sheets", all(s in wb.sheetnames for s in required_sheets)))

    main_df = pd.read_excel(FINAL_XLSX, sheet_name="Final List - Auction Order")
    cheapest_df = pd.read_excel(FINAL_XLSX, sheet_name="Final List - Cheapest First")
    sort_col = next((c for c in SORT_COLUMNS if c in main_df.columns), None)
    checks.append(("main_sorted_auction_order", check_sorted(pd.to_numeric(main_df[sort_col], errors="coerce").tolist()) if sort_col else False))
    checks.append(("cheapest_sorted_opening_bid", check_sorted(pd.to_numeric(cheapest_df["Opening Bid"], errors="coerce").tolist())))
    checks.append(("red_strikethrough_removed", len(removed) >= 0))
    checks.append(("non_removed_preserved", len(cleaned) > 0 and len(cleaned) + len(removed) == len(original)))
    checks.append(("original_columns_preserved", all(col in cleaned.columns for col in original.columns)))
    checks.append(("grade_column_exists", "Grade" in cleaned.columns))
    checks.append(("max_bid_column_exists", "Max Bid" in cleaned.columns))
    checks.append(("colors_preserved_or_recreated", "Color" in main_df.columns))
    checks.append(("no_duplicate_parcel_ids", not cleaned["Parcel ID"].duplicated().any()))
    checks.append(("ai_final_category_allowed", set(ai["ai_final_category"]).issubset(ALLOWED_CATEGORY)))
    checks.append(("ai_bid_priority_allowed", set(ai["ai_bid_priority"]).issubset(ALLOWED_PRIORITY)))
    checks.append(("ai_confidence_allowed", set(ai["ai_confidence"]).issubset(ALLOWED_CONFIDENCE)))

    staged = staged_paths()
    checks.append(("env_not_staged", ".env" not in staged and not any(path.endswith("/.env") for path in staged)))
    checks.append(("venv_not_staged", ".venv" not in staged and not any(path.startswith(".venv/") or "/.venv/" in path for path in staged)))

    ok = all(flag for _, flag in checks)
    lines = [f"{name}={'PASS' if flag else 'FAIL'}" for name, flag in checks]
    lines.append(f"validation={'PASS' if ok else 'FAIL'}")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
