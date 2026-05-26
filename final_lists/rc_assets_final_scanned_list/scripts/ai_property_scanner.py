from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_CSV = BASE_DIR / "cleaned_data" / "rc_assets_final_cleaned_list.csv"
CRIME_CSV = BASE_DIR / "cleaned_data" / "crime_scan_results.csv"
ECON_CSV = BASE_DIR / "cleaned_data" / "economic_scan_results.csv"
OUTPUT_CSV = BASE_DIR / "cleaned_data" / "ai_scanner_results.csv"
LOG_FILE = BASE_DIR / "logs" / "ai_scan_log.txt"
REPO_ENV = BASE_DIR.parents[2] / ".env"

ALLOWED_CATEGORY = {"Top Candidate", "Strong Candidate", "Watchlist", "High Risk", "Remove"}
ALLOWED_PRIORITY = {"Priority 1", "Priority 2", "Priority 3", "Do Not Bid", "Unknown"}
ALLOWED_CONFIDENCE = {"High", "Medium", "Low"}

SYSTEM_PROMPT = "You are a grounded real-estate tax-auction screening assistant. Return valid JSON only. Use only the provided property data, crime scan result, and economic scan result. Do not invent facts."


def clean_number(value):
    if pd.isna(value):
        return None
    try:
        return float(value)
    except Exception:
        return None


def rule_based_result(row: pd.Series) -> dict:
    score = 50
    color = str(row.get("Color", "")).strip()
    opening_bid = clean_number(row.get("Opening Bid"))
    max_bid = clean_number(row.get("Max Bid"))
    crime = str(row.get("crime_risk_level", "Unknown"))
    econ = str(row.get("economic_signal_level", "Unknown"))
    match = str(row.get("development_match_strength", "Unknown"))

    if color.lower() == "green":
        score += 12
    elif color.lower() == "purple":
        score += 10
    elif color.lower() == "blue":
        score += 4
    elif color.lower() == "red":
        score -= 20

    if opening_bid is not None and opening_bid < 2000:
        score += 8
    elif opening_bid is not None and opening_bid > 6000:
        score -= 5

    if max_bid is None:
        score -= 4
    else:
        spread = max_bid - opening_bid if opening_bid is not None else 0
        if spread > 0:
            score += 3

    if crime == "High":
        score -= 18
    elif crime == "Medium":
        score -= 8

    if econ == "Positive":
        score += 6
    elif econ == "Negative":
        score -= 6

    if match == "Strong Match":
        score += 8
    elif match == "Possible Match":
        score += 3

    score = max(0, min(100, int(score)))
    if score >= 78:
        category, priority = "Top Candidate", "Priority 1"
    elif score >= 68:
        category, priority = "Strong Candidate", "Priority 2"
    elif score >= 52:
        category, priority = "Watchlist", "Priority 3"
    elif score >= 35:
        category, priority = "High Risk", "Do Not Bid"
    else:
        category, priority = "Remove", "Do Not Bid"

    confidence = "Medium"
    if crime == "Unknown" or econ == "Unknown" or pd.isna(row.get("Max Bid")):
        confidence = "Low"

    summary = (
        f"Parcel {row.get('Parcel ID')} at {row.get('Address')} has opening bid {row.get('Opening Bid')}, "
        f"max bid {row.get('Max Bid')}, color {row.get('Color')}, crime risk {crime}, and economic signal {econ}."
    )
    risks = []
    if crime in {"High", "Medium", "Unknown"}:
        risks.append(f"crime context {crime}")
    if econ in {"Unknown", "Negative"}:
        risks.append(f"economic signal {econ}")
    if pd.isna(row.get("Max Bid")):
        risks.append("blank max bid")
    if not risks:
        risks.append("standard tax-sale due diligence still required")
    return {
        "ai_final_score": score,
        "ai_final_category": category,
        "ai_bid_priority": priority,
        "ai_summary": summary,
        "ai_key_risks": ", ".join(risks),
        "ai_due_diligence_next_step": "Verify title, liens, occupancy, and auction-order assumptions before bidding.",
        "ai_confidence": confidence,
    }


def prompt_for_row(row: pd.Series) -> str:
    return f'''Review this RC Assets and Development final auction property.\n\nThis is a screening tool, not final investment advice.\n\nUse only the data provided below.\n\nProperty Data:\nColor: {row.get("Color", "")}\nSource: {row.get("Source", "")}\nGrade: {row.get("Final Decision", "")}\nParcel ID: {row.get("Parcel ID", "")}\nAddress: {row.get("Address", "")}\nOpening Bid: {row.get("Opening Bid", "")}\nMax Bid: {row.get("Max Bid", "")}\nBid Spread: {row.get("Bid Spread", "")}\nExisting Notes: {row.get("Notes", "")}\nAuction/List Order: {row.get("#", row.get("Original Rank", row.get("source_excel_row", "")))}\n\nCrime Scan:\nCrime Risk Level: {row.get("crime_risk_level", "")}\nCrime Context Summary: {row.get("crime_context_summary", "")}\nCrime Data Granularity: {row.get("crime_data_granularity", "")}\nCrime Source URL: {row.get("crime_source_url", "")}\nCrime Data Confidence: {row.get("crime_data_confidence", "")}\n\nEconomic Scan:\nEconomic Signal Level: {row.get("economic_signal_level", "")}\nDevelopment Match Strength: {row.get("development_match_strength", "")}\nMatched Development Area: {row.get("matched_development_area", "")}\nMatched Project or Investment: {row.get("matched_project_or_investment", "")}\nDevelopment Source URL: {row.get("development_source_url", "")}\nDevelopment Summary: {row.get("development_summary", "")}\nDevelopment Match Reason: {row.get("development_match_reason", "")}\nEconomic Data Confidence: {row.get("economic_data_confidence", "")}\n\nReturn JSON only:\n\n{{\n \"ai_final_score\": 0,\n \"ai_final_category\": \"\",\n \"ai_bid_priority\": \"\",\n \"ai_summary\": \"\",\n \"ai_key_risks\": \"\",\n \"ai_due_diligence_next_step\": \"\",\n \"ai_confidence\": \"\"\n}}'''


def valid_result(result: dict) -> bool:
    if result.get("ai_final_category") not in ALLOWED_CATEGORY:
        return False
    if result.get("ai_bid_priority") not in ALLOWED_PRIORITY:
        return False
    if result.get("ai_confidence") not in ALLOWED_CONFIDENCE:
        return False
    summary = str(result.get("ai_summary", ""))
    concrete_hits = 0
    for token in ["Parcel", "bid", "color", "crime", "economic", "address", "grade", "max bid"]:
        if token.lower() in summary.lower():
            concrete_hits += 1
    return concrete_hits >= 3


def call_ai(client: OpenAI, model: str, row: pd.Series) -> dict | None:
    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_for_row(row)},
        ],
    )
    text = response.choices[0].message.content
    return json.loads(text)


def main() -> int:
    load_dotenv(REPO_ENV)
    base_url = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")

    properties = pd.read_csv(INPUT_CSV)
    crime = pd.read_csv(CRIME_CSV)
    econ = pd.read_csv(ECON_CSV)
    merged = properties.merge(crime, on=["Parcel ID", "Address"], how="left").merge(econ, on=["Parcel ID", "Address"], how="left")

    client = None
    if OpenAI and api_key and model:
        client = OpenAI(api_key=api_key, base_url=base_url)

    results = []
    used_fallback = 0
    for _, row in merged.iterrows():
        result = None
        if client is not None:
            try:
                result = call_ai(client, model, row)
                if not valid_result(result):
                    result = call_ai(client, model, row)
                    if not valid_result(result):
                        result = None
            except Exception:
                result = None
        if result is None:
            result = rule_based_result(row)
            used_fallback += 1
        if not valid_result(result):
            result = rule_based_result(row)
            used_fallback += 1
        results.append({"Parcel ID": row.get("Parcel ID"), "Address": row.get("Address"), **result})

    out = pd.DataFrame(results)
    out.to_csv(OUTPUT_CSV, index=False)
    LOG_FILE.write_text(
        "ai_scan_completed=yes\n"
        f"rows_scanned={len(out)}\n"
        f"fallback_rows={used_fallback}\n",
        encoding="utf-8",
    )
    print(f"rows_scanned={len(out)} fallback_rows={used_fallback}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
