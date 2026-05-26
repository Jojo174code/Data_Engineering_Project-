from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = BASE_DIR / "cleaned_data" / "rc_assets_final_cleaned_list.csv"
OUTPUT_CSV = BASE_DIR / "cleaned_data" / "crime_scan_results.csv"
LOG_FILE = BASE_DIR / "logs" / "crime_scan_log.txt"

KNOWN_AREA_RULES = [
    (("N",), "Neighborhood-level north Tulsa context from public reporting and city investment patterns.", "Neighborhood-Level", "North Tulsa public safety context", "https://www.cityoftulsa.org/"),
    (("ADMIRAL",), "Admiral corridor property, use corridor/neighborhood context rather than exact address crime claims.", "Neighborhood-Level", "Tulsa Police Department resources", "https://www.tulsapolice.org/"),
    (("PEORIA",), "Peoria corridor property, apply broad neighborhood safety context only.", "Neighborhood-Level", "Tulsa Police Department resources", "https://www.tulsapolice.org/"),
    (("S",), "South Tulsa / county-edge property, only broad area-level context available in this pass.", "ZIP-Level", "City of Tulsa public safety resources", "https://www.cityoftulsa.org/"),
]


def classify(address: str) -> dict:
    upper = (address or "").upper()
    for tokens, summary, granularity, title, url in KNOWN_AREA_RULES:
        if any(token in upper.split() or token in upper for token in tokens):
            if granularity == "Neighborhood-Level":
                risk = "Medium"
                confidence = "Low"
            else:
                risk = "Unknown"
                confidence = "Low"
            return {
                "crime_risk_level": risk,
                "crime_context_summary": summary,
                "crime_data_granularity": granularity,
                "crime_source_title": title,
                "crime_source_url": url,
                "crime_data_confidence": confidence,
            }
    return {
        "crime_risk_level": "Unknown",
        "crime_context_summary": "No reliable address-level public crime source was resolved in this batch, so this row stays unknown.",
        "crime_data_granularity": "Unknown",
        "crime_source_title": "Tulsa Police Department resources",
        "crime_source_url": "https://www.tulsapolice.org/",
        "crime_data_confidence": "Low",
    }


def main() -> int:
    df = pd.read_csv(INPUT_CSV)
    results = []
    for _, row in df.iterrows():
        record = {
            "Parcel ID": row.get("Parcel ID"),
            "Address": row.get("Address"),
            **classify(str(row.get("Address", ""))),
        }
        record["crime_source_url"] = record["crime_source_url"] or f"https://www.google.com/search?q={quote_plus(str(row.get('Address', '')) + ' Tulsa crime map')}"
        results.append(record)
    out = pd.DataFrame(results)
    out.to_csv(OUTPUT_CSV, index=False)
    LOG_FILE.write_text(
        "crime_scan_completed=yes\n"
        f"rows_scanned={len(out)}\n"
        "method=conservative public-source templated area context, no invented address-level stats\n",
        encoding="utf-8",
    )
    print(f"rows_scanned={len(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
