from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = BASE_DIR / "cleaned_data" / "rc_assets_final_cleaned_list.csv"
OUTPUT_CSV = BASE_DIR / "cleaned_data" / "economic_scan_results.csv"
LOG_FILE = BASE_DIR / "logs" / "economic_scan_log.txt"

AREA_RULES = [
    {
        "tokens": ["ADMIRAL"],
        "economic_signal_level": "Positive",
        "development_match_strength": "Possible Match",
        "matched_development_area": "Admiral corridor",
        "matched_project_or_investment": "corridor-level reinvestment context",
        "development_source_title": "City of Tulsa planning and corridor resources",
        "development_source_url": "https://www.cityoftulsa.org/",
        "development_summary": "Address appears on or near the Admiral corridor, where corridor-scale planning and reinvestment signals may matter.",
        "development_match_reason": "Street/corridor name overlap supports only a possible corridor match, not a district-level certainty.",
        "economic_data_confidence": "Low",
    },
    {
        "tokens": ["CHARLES PAGE"],
        "economic_signal_level": "Neutral",
        "development_match_strength": "No Clear Match",
        "matched_development_area": "West Tulsa / Charles Page corridor",
        "matched_project_or_investment": "no supported named project matched in this batch",
        "development_source_title": "INCOG planning resources",
        "development_source_url": "https://incog.org/",
        "development_summary": "No strong named district or project overlap was confirmed from the spreadsheet row alone.",
        "development_match_reason": "Only a corridor reference is visible, which is not enough for a strong development match.",
        "economic_data_confidence": "Low",
    },
    {
        "tokens": ["PEORIA", "GREENWOOD", "KENDALL", "WHITTIER", "ROUTE 66"],
        "economic_signal_level": "Positive",
        "development_match_strength": "Possible Match",
        "matched_development_area": "Named Tulsa corridor or district",
        "matched_project_or_investment": "district-level redevelopment context",
        "development_source_title": "PartnerTulsa development resources",
        "development_source_url": "https://www.partnertulsa.org/",
        "development_summary": "The address references a named corridor or district that can have active redevelopment context, but the exact overlap is not proven here.",
        "development_match_reason": "Named corridor overlap is more meaningful than generic city overlap, but still not enough for a strong match without boundary proof.",
        "economic_data_confidence": "Low",
    },
]


def classify(address: str) -> dict:
    upper = (address or "").upper()
    for rule in AREA_RULES:
        if any(token in upper for token in rule["tokens"]):
            return {k: v for k, v in rule.items() if k != "tokens"}
    return {
        "economic_signal_level": "Unknown",
        "development_match_strength": "Unknown",
        "matched_development_area": "",
        "matched_project_or_investment": "",
        "development_source_title": "City of Tulsa development resources",
        "development_source_url": "https://www.cityoftulsa.org/",
        "development_summary": "No credible project or district match was established from the available row data in this batch.",
        "development_match_reason": "Avoided generic city-level matching without clearer location evidence.",
        "economic_data_confidence": "Low",
    }


def main() -> int:
    df = pd.read_csv(INPUT_CSV)
    results = []
    for _, row in df.iterrows():
        results.append({
            "Parcel ID": row.get("Parcel ID"),
            "Address": row.get("Address"),
            **classify(str(row.get("Address", ""))),
        })
    out = pd.DataFrame(results)
    out.to_csv(OUTPUT_CSV, index=False)
    LOG_FILE.write_text(
        "economic_scan_completed=yes\n"
        f"rows_scanned={len(out)}\n"
        "method=conservative corridor/district matching, generic city overlap rejected\n",
        encoding="utf-8",
    )
    print(f"rows_scanned={len(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
