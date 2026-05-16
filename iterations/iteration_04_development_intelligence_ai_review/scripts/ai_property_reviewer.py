from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common_iter_utils import ALLOWED_CATEGORIES, ALLOWED_CONFIDENCE, ALLOWED_RECOMMENDATIONS, CLEANED_DIR, ITERATION_ROOT, LOG_DIR, clean_text, write_log

IN_CSV = CLEANED_DIR / 'filtered_properties_3000_to_8000.csv'
OUT_CSV = CLEANED_DIR / 'ai_property_reviews.csv'
LOG_FILE = LOG_DIR / 'ai_review_log.txt'

SYSTEM_MSG = 'You are a grounded real-estate auction screening assistant. Return valid JSON only. Use only the provided property data and cited development intelligence. Do not invent facts. Do not provide generic real estate advice.'

PROMPT_TEMPLATE = """Review this Tulsa County tax auction property for preliminary investment screening.

This is not final investment advice.
Your job is to decide whether the property deserves manual review and whether nearby public/private investment activity improves its priority.

Use only the data provided below.

Property Data:
Parcel ID: {parcel_id}
Owner Name: {owner_name}
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

Development Intelligence:
Development Match Strength: {development_match_strength}
Matched Development Area: {matched_development_area}
Matched Project or Area Name: {matched_project_or_area_name}
Matched Project Type: {matched_project_type}
Matched Investment Signal Strength: {matched_investment_signal_strength}
Development Source Title: {development_source_title}
Development Source URL: {development_source_url}
Development Summary: {development_summary}
Development Match Reason: {development_match_reason}
Development Confidence: {development_confidence}

Rule-Based Signals:
Rule-Based Score: {rule_based_score}
Rule-Based Category: {rule_based_category}
Bid Price Signal: {bid_price_signal}
Address Quality Signal: {address_quality_signal}
Property Clarity Signal: {property_clarity_signal}
Development Signal: {development_signal}
Surrounding Value Signal: {surrounding_value_signal}
Crime Risk Estimate: {crime_risk_estimate}
Data Confidence: {data_confidence}
Rule-Based Reasoning: {rule_based_reasoning}
Key Rule-Based Risks: {key_rule_based_risks}

Return JSON only using this exact schema:

{{
 "parcel_id": "",
 "ai_review_score": 0,
 "investment_category": "",
 "manual_review_flag": true,
 "recommendation": "",
 "development_opportunity_flag": true,
 "development_opportunity_reason": "",
 "reasoning_summary": "",
 "key_risks": "",
 "missing_information": "",
 "next_due_diligence_step": "",
 "confidence_level": ""
}}

Rules:
1. Do not classify as Good Investment unless data quality and development/surrounding value signals support it.
2. Use Strong Manual Review Candidate when bid is low, parcel/address data is usable, and/or development intelligence makes the property worth deeper review.
3. Use Mid Investment when some upside exists but important information is missing.
4. Use Bad Investment when data quality is poor, bid is high relative to uncertainty, or the property appears unclear/unusable.
5. Set development_opportunity_flag=true only if there is Strong Match or Possible Match to a cited development item.
6. Be specific. Mention bid cost, address/parcel quality, and development signal if present.
7. Do not invent external facts.
8. Return JSON only.
"""


def load_client():
    load_dotenv(ITERATION_ROOT.parents[1] / '.env')
    api_key = os.getenv('OPENAI_API_KEY')
    base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    model = os.getenv('OPENAI_MODEL')
    missing = [k for k, v in [('OPENAI_API_KEY', api_key), ('OPENAI_MODEL', model)] if not v]
    if missing:
        raise RuntimeError('Missing OpenAI env vars: ' + ', '.join(missing))
    return OpenAI(api_key=api_key, base_url=base_url), model, base_url


def parse_json_text(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end+1])
        raise


def grounded_enough(reasoning: str, row: pd.Series) -> bool:
    text = clean_text(reasoning).lower()
    candidates = [
        str(row['parcel_id']).lower(),
        clean_text(row['property_address']).lower(),
        str(row['bid_cost']).lower(),
        clean_text(row['development_match_strength']).lower(),
        clean_text(row['matched_development_area']).lower(),
        clean_text(row['matched_project_or_area_name']).lower(),
        clean_text(row['matched_investment_signal_strength']).lower(),
        clean_text(row['data_confidence']).lower(),
    ]
    hits = sum(1 for candidate in candidates if candidate and candidate != 'unknown' and candidate in text)
    dev_needed = clean_text(row['development_match_strength']) in {'Strong Match', 'Possible Match'}
    has_dev_ref = any(clean_text(row[field]).lower() in text for field in ['development_match_strength', 'matched_development_area', 'matched_project_or_area_name', 'matched_investment_signal_strength'] if clean_text(row[field]))
    return hits >= 3 and ((not dev_needed) or has_dev_ref)


def normalize_category(cat: str, row: pd.Series, score: float) -> str:
    cat = clean_text(cat)
    if cat in ALLOWED_CATEGORIES:
        return cat
    lowered = cat.lower()
    if lowered == 'needs_further_review':
        return 'Strong Manual Review Candidate' if score >= 5 and row['data_confidence'] in {'Medium', 'High'} else 'Mid Investment'
    if lowered == 'insufficient_information':
        return 'Mid Investment' if row['data_confidence'] != 'Low' else 'Bad Investment'
    if lowered == 'unknown':
        return row['rule_based_category']
    return row['rule_based_category']


def normalize_record(data: dict, row: pd.Series) -> dict:
    try:
        score = float(data.get('ai_review_score', row['rule_based_score']))
    except Exception:
        score = float(row['rule_based_score'])
    score = max(float(row['rule_based_score']) - 1.5, min(float(row['rule_based_score']) + 1.0, score))
    score = round(max(1.0, min(10.0, score)), 1)
    category = normalize_category(data.get('investment_category', row['rule_based_category']), row, score)
    recommendation = clean_text(data.get('recommendation', ''))
    if recommendation not in ALLOWED_RECOMMENDATIONS:
        recommendation = 'Research First' if category in {'Good Investment', 'Strong Manual Review Candidate', 'Mid Investment'} else 'Avoid'
    confidence = clean_text(data.get('confidence_level', row['data_confidence']))
    if confidence not in ALLOWED_CONFIDENCE:
        confidence = row['data_confidence']
    reasoning = clean_text(data.get('reasoning_summary', ''))
    if not grounded_enough(reasoning, row):
        raise ValueError('reasoning_summary not grounded enough')
    dev_flag = bool(data.get('development_opportunity_flag', clean_text(row['development_match_strength']) in {'Strong Match', 'Possible Match'}))
    dev_reason = clean_text(data.get('development_opportunity_reason', row['development_match_reason']))
    if dev_flag and not dev_reason:
        dev_reason = row['development_match_reason']
    return {
        'parcel_id': row['parcel_id'],
        'ai_review_score': score,
        'investment_category': category,
        'manual_review_flag': bool(data.get('manual_review_flag', True)),
        'recommendation': recommendation,
        'development_opportunity_flag': dev_flag,
        'development_opportunity_reason': dev_reason,
        'reasoning_summary': reasoning,
        'key_risks': clean_text(data.get('key_risks', row['key_rule_based_risks'])),
        'missing_information': clean_text(data.get('missing_information', 'Unknown')),
        'next_due_diligence_step': clean_text(data.get('next_due_diligence_step', 'Drive-by, title review, and neighborhood verification')),
        'confidence_level': confidence,
    }


def fallback_record(row: pd.Series, reason: str) -> dict:
    return {
        'parcel_id': row['parcel_id'],
        'ai_review_score': row['rule_based_score'],
        'investment_category': row['rule_based_category'],
        'manual_review_flag': True,
        'recommendation': 'Research First' if row['rule_based_category'] != 'Bad Investment' else 'Avoid',
        'development_opportunity_flag': clean_text(row['development_match_strength']) in {'Strong Match', 'Possible Match'},
        'development_opportunity_reason': row['development_match_reason'],
        'reasoning_summary': 'AI review failed validation; fallback rule-based review used.',
        'key_risks': row['key_rule_based_risks'],
        'missing_information': reason,
        'next_due_diligence_step': 'Drive-by, title review, and neighborhood verification',
        'confidence_level': row['data_confidence'],
    }


def main():
    client, model, base_url = load_client()
    df = pd.read_csv(IN_CSV)
    existing = pd.read_csv(OUT_CSV) if OUT_CSV.exists() else pd.DataFrame()
    done = set(existing['parcel_id'].astype(str)) if not existing.empty else set()
    records = existing.to_dict('records') if not existing.empty else []
    log_lines = [f'base_url={base_url}', f'model={model}', f'existing_reviews={len(records)}']

    for _, row in df.iterrows():
        parcel_id = str(row['parcel_id'])
        if parcel_id in done:
            continue
        prompt = PROMPT_TEMPLATE.format(**row.to_dict())
        last_error = 'Unknown error'
        record = None
        for attempt in range(2):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    temperature=0.2,
                    response_format={'type': 'json_object'},
                    messages=[
                        {'role': 'system', 'content': SYSTEM_MSG},
                        {'role': 'user', 'content': prompt},
                    ],
                )
                data = parse_json_text(resp.choices[0].message.content)
                record = normalize_record(data, row)
                break
            except Exception as exc:
                last_error = str(exc)
                time.sleep(2 * (attempt + 1))
        if record is None:
            record = fallback_record(row, last_error)
        records.append(record)
        pd.DataFrame(records).to_csv(OUT_CSV, index=False)
        msg = f'Reviewed {len(records)}/{len(df)} properties'
        print(msg)
        log_lines.append(msg)

    log_lines.append(f'final_ai_review_rows={len(records)}')
    write_log(LOG_FILE, log_lines)


if __name__ == '__main__':
    main()
