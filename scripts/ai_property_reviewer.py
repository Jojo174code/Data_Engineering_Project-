from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common_utils import ROOT, clean_text

FILTERED_XLSX = ROOT / 'output_excel' / 'filtered_properties_3000_to_8000.xlsx'
RANKED_XLSX = ROOT / 'output_excel' / 'investment_ranked_properties.xlsx'
OUT_CSV = ROOT / 'cleaned_data' / 'ai_property_reviews.csv'

ALLOWED_CATEGORIES = {'Good Investment', 'Strong Manual Review Candidate', 'Mid Investment', 'Bad Investment'}
ALLOWED_RECOMMENDATIONS = {'Bid Candidate', 'Research First', 'Drive By', 'Watch', 'Avoid'}
ALLOWED_CONFIDENCE = {'High', 'Medium', 'Low'}

PROMPT_TEMPLATE = """You are reviewing a Tulsa County tax auction property for preliminary investment screening.

You are not making final investment advice.
You are only helping rank which properties deserve manual research.

Use only the data provided below.
Do not invent missing facts.
Do not give generic real estate advice.
Be specific and grounded.
Return valid JSON only.

Property data:

Parcel ID: {parcel_id}
Address: {property_address}
City: {city}
State: {state}
ZIP: {zip_code}
Bid Cost: {bid_cost}
Legal Description: {legal_description}
Property Type: {property_type}
Source Page: {source_page}
Raw Auction Text: {raw_text}
Extraction Confidence: {extraction_confidence}

Rule-Based Signals:

Bid Price Signal: {bid_price_signal}
Address Quality Signal: {address_quality_signal}
Property Clarity Signal: {property_clarity_signal}
Neighborhood/Location Signal: {neighborhood_growth_signal}
Surrounding Value Signal: {surrounding_value_signal}
Crime Risk Estimate: {crime_risk_estimate}
Data Confidence: {data_confidence}
Rule-Based Score: {rule_based_score}
Rule-Based Category: {rule_based_category}

Task:

Return a JSON object with:

- parcel_id
- ai_review_score from 1 to 10
- investment_category
- manual_review_flag
- recommendation
- reasoning_summary
- key_risks
- missing_information
- next_due_diligence_step
- confidence_level

Rules:

1. Do not classify as \"Good Investment\" unless the data is strong enough.
2. Use \"Strong Manual Review Candidate\" when the property looks promising but still needs manual verification.
3. If address, parcel ID, or legal description is missing, lower confidence.
4. If bid cost is low and the parcel/address data is clean, consider Strong Manual Review Candidate.
5. If data is too incomplete, classify as Mid or Bad depending on risk.
6. Be specific. Mention the actual bid cost, parcel/address quality, and missing data.
7. Do not write generic statements.
8. Return JSON only.
"""


def load_env():
    load_dotenv(ROOT / '.env')
    required = ['LITELLM_API_KEY', 'LITELLM_BASE_URL', 'LITELLM_MODEL']
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print('Missing LiteLLM environment variables:', ', '.join(missing))
        return None
    return {
        'api_key': os.getenv('LITELLM_API_KEY'),
        'base_url': os.getenv('LITELLM_BASE_URL').rstrip('/'),
        'model': os.getenv('LITELLM_MODEL'),
    }


def is_grounded_enough(reasoning: str, row: pd.Series) -> bool:
    text = clean_text(reasoning).lower()
    hits = 0
    for candidate in [str(row['parcel_id']), clean_text(row['property_address']), str(row['bid_cost']), clean_text(row['legal_description'])[:20], clean_text(row['zip_code'])]:
        if candidate and candidate.lower() in text:
            hits += 1
    return hits >= 2


def parse_json_response(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end+1])
        raise


def normalize_response(data: dict, row: pd.Series, model_used: str) -> dict:
    category = data.get('investment_category', row['rule_based_category'])
    if category not in ALLOWED_CATEGORIES:
        category = row['rule_based_category']
    recommendation = data.get('recommendation', row['recommendation'])
    if recommendation not in ALLOWED_RECOMMENDATIONS:
        recommendation = row['recommendation']
    confidence = data.get('confidence_level', row['data_confidence'])
    if confidence not in ALLOWED_CONFIDENCE:
        confidence = row['data_confidence']

    try:
        ai_score = float(data.get('ai_review_score', row['rule_based_score']))
    except Exception:
        ai_score = float(row['rule_based_score'])
    ai_score = max(row['rule_based_score'] - 1.5, min(row['rule_based_score'] + 1.0, ai_score))
    ai_score = round(max(1.0, min(10.0, ai_score)), 1)

    reasoning = clean_text(data.get('reasoning_summary', ''))
    if not is_grounded_enough(reasoning, row):
        raise ValueError('AI response was too generic / not grounded enough')

    return {
        'parcel_id': row['parcel_id'],
        'ai_review_score': ai_score,
        'investment_category': category,
        'manual_review_flag_ai': bool(data.get('manual_review_flag', row['manual_review_flag'])),
        'recommendation_ai': recommendation,
        'reasoning_summary_ai': reasoning,
        'key_risks_ai': clean_text(data.get('key_risks', row['key_risks'])),
        'missing_information': clean_text(data.get('missing_information', 'Unknown')),
        'next_due_diligence_step_ai': clean_text(data.get('next_due_diligence_step', row['next_due_diligence_step'])),
        'confidence_level': confidence,
        'model_used': model_used,
    }


def fallback_record(row: pd.Series, model_used: str, message: str) -> dict:
    return {
        'parcel_id': row['parcel_id'],
        'ai_review_score': row['rule_based_score'],
        'investment_category': row['rule_based_category'],
        'manual_review_flag_ai': bool(row['manual_review_flag']),
        'recommendation_ai': row['recommendation'],
        'reasoning_summary_ai': 'AI review failed; fallback rule-based score used.',
        'key_risks_ai': row['key_risks'],
        'missing_information': message,
        'next_due_diligence_step_ai': row['next_due_diligence_step'],
        'confidence_level': 'Low',
        'model_used': model_used,
    }


def review_row(row: pd.Series, env: dict) -> dict:
    prompt = PROMPT_TEMPLATE.format(**row.to_dict())
    payload = {
        'model': env['model'],
        'temperature': 0.2,
        'messages': [
            {'role': 'system', 'content': 'Return valid JSON only.'},
            {'role': 'user', 'content': prompt},
        ],
        'response_format': {'type': 'json_object'},
    }
    headers = {
        'Authorization': f"Bearer {env['api_key']}",
        'Content-Type': 'application/json',
    }
    url = f"{env['base_url']}/chat/completions"

    last_error = 'Unknown AI error'
    for attempt in range(2):
        resp = requests.post(url, json=payload, headers=headers, timeout=90)
        if resp.status_code == 429:
            wait_seconds = 5 * (attempt + 1)
            time.sleep(wait_seconds)
            last_error = f'Rate limited ({resp.status_code})'
            continue
        resp.raise_for_status()
        raw = resp.json()['choices'][0]['message']['content']
        try:
            data = parse_json_response(raw)
            return normalize_response(data, row, env['model'])
        except Exception as exc:
            last_error = str(exc)
            if attempt == 0:
                time.sleep(1)
                continue
    return fallback_record(row, env['model'], last_error)


def main():
    env = load_env()
    ranked_df = pd.read_excel(RANKED_XLSX)
    if env is None:
        records = [fallback_record(row, 'Rule-based only', 'Missing LiteLLM environment variables') for _, row in ranked_df.iterrows()]
        pd.DataFrame(records).to_csv(OUT_CSV, index=False)
        print('LiteLLM not configured, wrote fallback AI review CSV.')
        return

    existing = pd.read_csv(OUT_CSV) if OUT_CSV.exists() else pd.DataFrame()
    done = set(existing['parcel_id'].astype(str)) if not existing.empty else set()
    records = existing.to_dict('records') if not existing.empty else []

    for idx, row in ranked_df.iterrows():
        parcel_id = str(row['parcel_id'])
        if parcel_id in done:
            continue
        record = review_row(row, env)
        records.append(record)
        pd.DataFrame(records).to_csv(OUT_CSV, index=False)
        print(f"Reviewed {len(records)}/{len(ranked_df)} properties")

    print(f'AI review CSV written to {OUT_CSV}')


if __name__ == '__main__':
    main()
