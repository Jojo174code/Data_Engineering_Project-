from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

ITERATION_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
LOG_DIR = ITERATION_ROOT / 'logs'

IN_CSV = CLEANED_DIR / 'final_rule_based_scores.csv'
BASE_CSV = CLEANED_DIR / 'final_property_base.csv'
MATCH_CSV = CLEANED_DIR / 'final_property_development_matches.csv'
GEO_CSV = CLEANED_DIR / 'final_geocoding_results.csv'
OUT_CSV = CLEANED_DIR / 'final_ai_property_reviews.csv'
LOG_FILE = LOG_DIR / 'ai_review_log.txt'

ALLOWED_CATEGORIES = {'Good Investment', 'Strong Manual Review Candidate', 'Mid Investment', 'Bad Investment'}
ALLOWED_RECOMMENDATIONS = {'Bid Candidate', 'Research First', 'Drive By', 'Watch', 'Avoid'}
ALLOWED_CONFIDENCE = {'High', 'Medium', 'Low'}

SYSTEM_MSG = 'You are a grounded real-estate tax-auction screening assistant. Return valid JSON only. Use only the provided property data, development-match data, and scoring signals. Do not invent facts. Do not write generic real estate advice.'
PROMPT_TEMPLATE = """Review this Tulsa County tax auction property for preliminary investment screening.

This is not final investment advice.
Your job is to classify whether this property deserves manual review and whether any verified development signal improves its priority.

Use only the data below.

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
Extraction Confidence: {extraction_confidence}

Development Verification:
Final Development Match Strength: {final_development_match_strength}
Final Matched Development Area: {final_matched_development_area}
Final Matched Project/Area Name: {final_matched_project_or_area_name}
Final Development Source Title: {final_development_source_title}
Final Development Source URL: {final_development_source_url}
Final Development Match Reason: {final_development_match_reason}
Final Development Warning: {final_development_warning}
Final Development Confidence: {final_development_confidence}

Geocoding/Distance:
Property Geocode Status: {property_geocode_status}
Development Geocode Status: {development_geocode_status}
Estimated Distance Miles: {estimated_distance_miles}
Geocode Confidence: {geocode_confidence}
Distance Verified Match: {distance_verified_match}
Corrected Development Match Strength: {corrected_development_match_strength}

Rule-Based Signals:
Final Rule-Based Score: {final_rule_based_score}
Final Rule-Based Category: {final_rule_based_category}
Final Bid Price Signal: {final_bid_price_signal}
Final Address Quality Signal: {final_address_quality_signal}
Final Property Clarity Signal: {final_property_clarity_signal}
Final Verified Development Signal: {final_verified_development_signal}
Final Surrounding Value Signal: {final_surrounding_value_signal}
Final Crime Risk Estimate: {final_crime_risk_estimate}
Final Data Confidence: {final_data_confidence}
Final Rule-Based Reasoning: {final_rule_based_reasoning}
Final Key Risks: {final_key_risks}

Return JSON only using this exact schema:

{{
 "parcel_id": "",
 "final_ai_review_score": 0,
 "final_investment_category": "",
 "final_manual_review_flag": true,
 "final_recommendation": "",
 "final_development_opportunity_flag": true,
 "final_development_opportunity_reason": "",
 "final_reasoning_summary": "",
 "final_key_risks": "",
 "final_missing_information": "",
 "final_next_due_diligence_step": "",
 "final_confidence_level": ""
}}

Rules:
- Good Investment requires strong property data and verified upside.
- Strong Manual Review Candidate means the property deserves deeper manual research, not that it is automatically a buy.
- Mid Investment means possible upside but significant uncertainty.
- Bad Investment means risk or missing data is too high.
- If the development match is No Clear Match or Unknown, do not treat development as a positive signal.
- Be specific and concise.
- Mention bid cost, parcel/address, development match status, and data confidence.
- Do not invent external facts.
"""


def clean_text(value) -> str:
    if value is None:
        return 'Unknown'
    text = str(value).strip()
    return text if text else 'Unknown'


def load_client():
    load_dotenv(ITERATION_ROOT.parents[1] / '.env')
    api_key = os.getenv('OPENAI_API_KEY')
    base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    model = os.getenv('OPENAI_MODEL')
    if not api_key or not model:
        raise RuntimeError('Missing OpenAI env vars')
    return OpenAI(api_key=api_key, base_url=base_url), model, base_url


def parse_json_text(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def reasoning_has_required_data(reasoning: str, row: pd.Series) -> bool:
    text = clean_text(reasoning).lower()
    bid_variants = {str(row['bid_cost']).lower(), f"{float(row['bid_cost']):.2f}".lower() if not pd.isna(row['bid_cost']) else ''}
    has_bid = any(v and v in text for v in bid_variants)
    has_property = clean_text(row['parcel_id']).lower() in text or clean_text(row['property_address']).lower() in text
    has_dev = clean_text(row['corrected_development_match_strength']).lower() in text or clean_text(row['final_development_match_strength']).lower() in text
    has_conf = clean_text(row['final_data_confidence']).lower() in text or clean_text(row['extraction_confidence']).lower() in text
    return has_bid and has_property and has_dev and has_conf


def normalize_category(category: str, row: pd.Series) -> str:
    category = clean_text(category)
    if category in ALLOWED_CATEGORIES:
        out = category
    else:
        lowered = category.lower()
        if lowered == 'needs_further_review':
            out = 'Strong Manual Review Candidate' if row['final_rule_based_score'] >= 6 else 'Mid Investment'
        elif lowered == 'insufficient_information':
            out = 'Mid Investment' if clean_text(row['final_data_confidence']) != 'Low' else 'Bad Investment'
        elif lowered == 'unknown':
            out = clean_text(row['final_rule_based_category'])
        else:
            out = clean_text(row['final_rule_based_category'])
    if clean_text(row['corrected_development_match_strength']) in {'No Clear Match', 'Unknown'} and out == 'Good Investment':
        return 'Strong Manual Review Candidate' if clean_text(row['final_rule_based_category']) != 'Bad Investment' else 'Mid Investment'
    if clean_text(row['final_data_confidence']) == 'Low' and out == 'Good Investment':
        return 'Strong Manual Review Candidate'
    return out


def normalize_recommendation(value: str, category: str) -> str:
    value = clean_text(value)
    if value in ALLOWED_RECOMMENDATIONS:
        return value
    if category == 'Good Investment':
        return 'Bid Candidate'
    if category == 'Strong Manual Review Candidate':
        return 'Research First'
    if category == 'Mid Investment':
        return 'Watch'
    return 'Avoid'


def normalize_confidence(value: str, row: pd.Series) -> str:
    value = clean_text(value)
    if value in ALLOWED_CONFIDENCE:
        return value
    return clean_text(row['final_data_confidence']) if clean_text(row['final_data_confidence']) in ALLOWED_CONFIDENCE else 'Medium'


def fallback_record(row: pd.Series, reason: str) -> dict:
    dev_ok = clean_text(row['corrected_development_match_strength']) in {'Strong Match', 'Possible Match'}
    reasoning = (
        f"Bid cost {float(row['bid_cost']):.2f}, parcel_id {row['parcel_id']}, corrected development match {row['corrected_development_match_strength']}, "
        f"and final data confidence {row['final_data_confidence']} support a rule-based fallback because AI review failed."
    )
    category = clean_text(row['final_rule_based_category'])
    return {
        'parcel_id': row['parcel_id'],
        'final_ai_review_score': float(row['final_rule_based_score']),
        'final_investment_category': category,
        'final_manual_review_flag': bool(row['final_manual_review_flag']),
        'final_recommendation': normalize_recommendation('', category),
        'final_development_opportunity_flag': dev_ok,
        'final_development_opportunity_reason': clean_text(row['final_development_match_reason']) if dev_ok else clean_text(row['final_development_warning'] or row['final_development_match_reason']),
        'final_reasoning_summary': reasoning,
        'final_key_risks': clean_text(row['final_key_risks']),
        'final_missing_information': clean_text(reason),
        'final_next_due_diligence_step': 'Verify assessor data, title issues, physical condition, and nearby comps before bidding.',
        'final_confidence_level': normalize_confidence('', row),
    }


def normalize_record(data: dict, row: pd.Series) -> dict:
    try:
        score = float(data.get('final_ai_review_score', row['final_rule_based_score']))
    except Exception:
        score = float(row['final_rule_based_score'])
    score = max(float(row['final_rule_based_score']) - 1.2, min(float(row['final_rule_based_score']) + 1.0, score))
    score = round(max(1.0, min(10.0, score)), 1)

    category = normalize_category(data.get('final_investment_category', row['final_rule_based_category']), row)
    recommendation = normalize_recommendation(data.get('final_recommendation', ''), category)
    confidence = normalize_confidence(data.get('final_confidence_level', ''), row)
    reasoning = clean_text(data.get('final_reasoning_summary', ''))
    if not reasoning_has_required_data(reasoning, row):
        raise ValueError('Reasoning summary missing required concrete data points')

    dev_ok = clean_text(row['corrected_development_match_strength']) in {'Strong Match', 'Possible Match'}
    dev_flag = bool(data.get('final_development_opportunity_flag', dev_ok)) and dev_ok
    dev_reason = clean_text(data.get('final_development_opportunity_reason', row['final_development_match_reason'])) if dev_flag else clean_text(row['final_development_warning'] or row['final_development_match_reason'])

    return {
        'parcel_id': row['parcel_id'],
        'final_ai_review_score': score,
        'final_investment_category': category,
        'final_manual_review_flag': bool(data.get('final_manual_review_flag', row['final_manual_review_flag'])),
        'final_recommendation': recommendation,
        'final_development_opportunity_flag': dev_flag,
        'final_development_opportunity_reason': dev_reason,
        'final_reasoning_summary': reasoning,
        'final_key_risks': clean_text(data.get('final_key_risks', row['final_key_risks'])),
        'final_missing_information': clean_text(data.get('final_missing_information', 'Unknown')),
        'final_next_due_diligence_step': clean_text(data.get('final_next_due_diligence_step', 'Verify assessor data, title issues, physical condition, and nearby comps before bidding.')),
        'final_confidence_level': confidence,
    }


def review_row(idx: int, row_dict: dict, client: OpenAI, model: str):
    row = pd.Series(row_dict)
    prompt = PROMPT_TEMPLATE.format(**row_dict)
    retry_prompt = prompt + '\n\nYour previous response was rejected. The final_reasoning_summary must explicitly mention bid cost, parcel ID or address, development match status, and data or extraction confidence.'
    last_error = 'Unknown error'
    for attempt, content in enumerate([prompt, retry_prompt], start=1):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.1,
                response_format={'type': 'json_object'},
                messages=[
                    {'role': 'system', 'content': SYSTEM_MSG},
                    {'role': 'user', 'content': content},
                ],
            )
            data = parse_json_text(response.choices[0].message.content)
            return idx, normalize_record(data, row), None
        except Exception as exc:
            last_error = str(exc)
            time.sleep(1.5 * attempt)
    return idx, fallback_record(row, last_error), last_error


def main():
    client, model, base_url = load_client()
    base = pd.read_csv(BASE_CSV)
    matches = pd.read_csv(MATCH_CSV)
    geo = pd.read_csv(GEO_CSV)
    scores = pd.read_csv(IN_CSV)

    df = base.merge(matches.drop(columns=[c for c in ['property_address', 'city', 'state', 'zip_code', 'legal_description', 'bid_cost', 'previous_investment_category', 'previous_development_match_strength', 'previous_development_match_quality'] if c in matches.columns]), on='parcel_id', how='left')
    df = df.merge(geo, on='parcel_id', how='left')
    df = df.merge(scores, on='parcel_id', how='left')

    if OUT_CSV.exists():
        OUT_CSV.unlink()

    rows = list(df.to_dict('records'))
    results: list[dict | None] = [None] * len(rows)
    failures = 0
    log_lines = [f'base_url={base_url}', f'model={model}', 'existing_reviews=0']

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(review_row, idx, row_dict, client, model) for idx, row_dict in enumerate(rows)]
        completed = 0
        for future in as_completed(futures):
            idx, record, error = future.result()
            results[idx] = record
            completed += 1
            if error:
                failures += 1
            partial = [row for row in results if row is not None]
            pd.DataFrame(partial).to_csv(OUT_CSV, index=False)
            msg = f'Reviewed {completed}/{len(rows)} properties (failures={failures})'
            print(msg, flush=True)
            log_lines.append(msg)

    out_df = pd.DataFrame(results)
    out_df.to_csv(OUT_CSV, index=False)
    log_lines.append(f'final_ai_review_rows={len(out_df)}')
    log_lines.append(f'fallback_failures={failures}')
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text('\n'.join(log_lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
