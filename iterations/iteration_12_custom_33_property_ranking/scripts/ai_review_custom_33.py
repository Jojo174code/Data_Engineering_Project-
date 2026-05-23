#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

from common_custom_33 import ALLOWED_CONFIDENCE, ALLOWED_RECOMMENDATIONS, ALLOWED_TIERS, CLEANED_DIR, LOG_DIR, REPO_ROOT, clean_text, ensure_dirs, safe_float, write_log

IN_CSV = CLEANED_DIR / 'custom_33_rule_ranked.csv'
OUT_CSV = CLEANED_DIR / 'custom_33_ai_reviews.csv'
LOG_FILE = LOG_DIR / 'ai_review_log.txt'

SYSTEM_MSG = 'You are a grounded tax-auction property screening assistant. Return valid JSON only. Use only the provided property, crime, economic, geocoding, and prior-ranking data. Do not invent facts.'
PROMPT_TEMPLATE = """Review this specific Tulsa auction property from my custom 33-property shortlist.

This is not final investment advice.
Your job is to rank it against the other custom candidates and explain whether it deserves priority before the auction.

Property Data:
Source List: {source_list}
Original Rank: {original_rank}
Parcel ID: {parcel_id}
Address: {property_address}
City: {city}
State: {state}
Bid Cost: {bid_cost}
Legal Description: {legal_description}
Property Type: {property_type}
Extraction Confidence: {extraction_confidence}

Geocoding:
Geocode Status: {geocode_status}
Geocode Confidence: {geocode_confidence}
Neighborhood/Area: {neighborhood_or_area}
Confirmed ZIP: {confirmed_zip_code}
Latitude: {latitude}
Longitude: {longitude}

Crime Context:
Crime Risk Level: {crime_risk_level}
Crime Risk Score: {crime_risk_score}
Crime Confidence: {crime_confidence}
Crime Notes: {crime_notes}

Economic Context:
Median Household Income: {median_household_income}
Poverty Rate: {poverty_rate}
Unemployment Rate: {unemployment_rate}
Median Home Value: {median_home_value}
Vacancy Rate: {vacancy_rate}
Economic Risk Level: {economic_risk_level}
Economic Strength Score: {economic_strength_score}
Economic Confidence: {economic_confidence}

Prior Signals:
Previous Category: {previous_category}
Previous AI Score: {previous_ai_score}
Previous Recommendation: {previous_recommendation}
Previous Reasoning: {previous_reasoning_summary}

Rule Ranking:
Rule Score: {rule_score}
Rule Category: {rule_category}
Property Clarity Score: {property_clarity_score}
Geocoding Score: {geocoding_score}
Residential Likelihood Score: {residential_likelihood_score}
Crime Score: {crime_score}
Economic Score: {economic_score}
Bid Price Score: {bid_price_score}
Rule Reasoning: {rule_reasoning}
Rule Key Risks: {rule_key_risks}

Return JSON only:

{{
 "parcel_id": "",
 "ai_score": 0,
 "ai_tier": "",
 "recommendation": "",
 "bid_strategy_note": "",
 "reasoning_summary": "",
 "crime_economic_summary": "",
 "key_risks": "",
 "missing_information": "",
 "next_due_diligence_step": "",
 "confidence_level": ""
}}

Rules:
- Tier 1 Priority means this should be one of the strongest targets to manually verify and possibly bid on.
- Tier 2 Strong Review means worth checking seriously, but not automatically a bid.
- Tier 3 Watch means track it, but only bid if manual checks are good and price stays low.
- Tier 4 High Risk means avoid unless manual research reveals something unusually good.
- Do not overrate cheap properties.
- Mention bid cost, address/parcel, crime/economic signal, and confidence.
- Return JSON only.
"""


def load_client():
    load_dotenv(REPO_ROOT / '.env')
    api_key = os.getenv('OPENAI_API_KEY')
    model = os.getenv('OPENAI_MODEL')
    base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    if not api_key or not model:
        raise RuntimeError('Missing OpenAI configuration.')
    return OpenAI(api_key=api_key, base_url=base_url), model


def parse_json_text(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def normalize_tier(value: str, row: pd.Series) -> str:
    tier = clean_text(value)
    if tier not in ALLOWED_TIERS:
        tier = clean_text(row['rule_category']) if clean_text(row['rule_category']) in ALLOWED_TIERS else 'Tier 3 Watch'
    return tier


def normalize_recommendation(value: str, tier: str) -> str:
    rec = clean_text(value)
    if rec in ALLOWED_RECOMMENDATIONS:
        return rec
    defaults = {
        'Tier 1 Priority': 'Bid Candidate',
        'Tier 2 Strong Review': 'Research First',
        'Tier 3 Watch': 'Drive By',
        'Tier 4 High Risk': 'Avoid',
    }
    return defaults[tier]


def normalize_confidence(value: str) -> str:
    conf = clean_text(value)
    if conf in ALLOWED_CONFIDENCE:
        return conf
    return 'Medium'


def reasoning_valid(payload: dict, row: pd.Series) -> bool:
    reasoning = clean_text(payload.get('reasoning_summary')).lower()
    has_bid = any(token in reasoning for token in [str(row['bid_cost']).lower(), f"{float(row['bid_cost']):.2f}".lower()])
    has_property = clean_text(row['parcel_id']).lower() in reasoning or clean_text(row['property_address']).lower() in reasoning
    has_crime = clean_text(row['crime_risk_level']).lower() in reasoning
    has_econ = clean_text(row['economic_risk_level']).lower() in reasoning or any(token in reasoning for token in ['median household income', 'poverty', 'unemployment', 'economic'])
    has_conf = clean_text(payload.get('confidence_level')).lower() in reasoning or 'confidence' in reasoning or 'missing' in reasoning
    return has_bid and has_property and has_crime and has_econ and has_conf and len(reasoning.split()) >= 18


def fallback_record(row: pd.Series, reason: str) -> dict:
    tier = normalize_tier(row['rule_category'], row)
    confidence = 'Low' if clean_text(row['geocode_confidence']) == 'Low' or clean_text(row['economic_confidence']) == 'Low' else 'Medium'
    ai_score = round(max(1.0, min(10.0, float(row['rule_score']) - (0.5 if confidence == 'Low' else 0.0))), 2)
    return {
        'parcel_id': row['parcel_id'],
        'ai_score': ai_score,
        'ai_tier': tier,
        'recommendation': normalize_recommendation('', tier),
        'bid_strategy_note': 'Use rule-based fallback and require extra manual verification before any bid.',
        'reasoning_summary': f"Bid cost {float(row['bid_cost']):.2f} for parcel {row['parcel_id']} at {row['property_address']} falls into {tier} because crime risk is {row['crime_risk_level']} and economic risk is {row['economic_risk_level']}; confidence level is {confidence} due to fallback or missing data.",
        'crime_economic_summary': f"Crime risk is {row['crime_risk_level']} with {row['crime_confidence']} confidence. Economic risk is {row['economic_risk_level']} with {row['economic_confidence']} confidence.",
        'key_risks': clean_text(row['rule_key_risks']),
        'missing_information': clean_text(reason),
        'next_due_diligence_step': clean_text(row['manual_due_diligence_priority']) + ' priority: verify title/liens, assessor details, parcel usability, and street-level condition.',
        'confidence_level': confidence,
    }


def normalize_record(payload: dict, row: pd.Series) -> dict:
    tier = normalize_tier(payload.get('ai_tier', ''), row)
    recommendation = normalize_recommendation(payload.get('recommendation', ''), tier)
    confidence = normalize_confidence(payload.get('confidence_level', ''))
    base_score = float(row['rule_score'])
    ai_score = safe_float(payload.get('ai_score'), base_score)
    ai_score = max(base_score - 1.5, min(base_score + 1.5, ai_score))
    record = {
        'parcel_id': row['parcel_id'],
        'ai_score': round(max(1.0, min(10.0, ai_score)), 2),
        'ai_tier': tier,
        'recommendation': recommendation,
        'bid_strategy_note': clean_text(payload.get('bid_strategy_note'), 'Bid only after manual checks confirm parcel usability and area fit.'),
        'reasoning_summary': clean_text(payload.get('reasoning_summary')),
        'crime_economic_summary': clean_text(payload.get('crime_economic_summary')),
        'key_risks': clean_text(payload.get('key_risks', row['rule_key_risks'])),
        'missing_information': clean_text(payload.get('missing_information')),
        'next_due_diligence_step': clean_text(payload.get('next_due_diligence_step')),
        'confidence_level': confidence,
    }
    if not reasoning_valid(record, row):
        raise ValueError('Generic or incomplete reasoning')
    return record


def review_with_model(client: OpenAI, model: str, row: pd.Series):
    row_dict = {k: clean_text(v) for k, v in row.to_dict().items()}
    row_dict['bid_cost'] = f"{float(row['bid_cost']):.2f}"
    prompt = PROMPT_TEMPLATE.format(**row_dict)
    retry = prompt + '\nYour previous response was too generic or missed required references. Mention the bid cost, parcel ID or address, crime risk level, economic risk level or one economic field, and confidence or missing data.'
    last_error = 'Unknown model error'
    for attempt, content in enumerate([prompt, retry], start=1):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.1,
                timeout=20.0,
                response_format={'type': 'json_object'},
                messages=[
                    {'role': 'system', 'content': SYSTEM_MSG},
                    {'role': 'user', 'content': content},
                ],
            )
            payload = parse_json_text(response.choices[0].message.content)
            return normalize_record(payload, row), f'ai_success_attempt_{attempt}'
        except Exception as exc:
            last_error = str(exc)
            time.sleep(1.0)
    raise RuntimeError(last_error)


def main() -> None:
    ensure_dirs()
    df = pd.read_csv(IN_CSV)
    force_fallback = os.getenv('CUSTOM33_FORCE_FALLBACK', '0') == '1'
    try:
        client, model = load_client()
        ai_ready = not force_fallback
        if force_fallback:
            log_lines = ['Fallback forced by CUSTOM33_FORCE_FALLBACK=1.']
        else:
            log_lines = [f'OpenAI ready with configured model {model}.']
    except Exception as exc:
        client = None
        model = None
        ai_ready = False
        log_lines = [f'OpenAI unavailable, rule-based fallback will be used. Reason: {exc}']

    rows = []
    total = len(df)
    for idx, (_, row) in enumerate(df.iterrows(), start=1):
        print(f'ai_start={idx}/{total} parcel={row["parcel_id"]}', flush=True)
        try:
            if ai_ready:
                record, mode = review_with_model(client, model, row)
            else:
                raise RuntimeError('Fallback forced because OpenAI configuration was unavailable.')
        except Exception as exc:
            record = fallback_record(row, f'Fallback used: {exc}')
            mode = 'rule_based_fallback'
        rows.append(record)
        log_lines.append(json.dumps({'mode': mode, **record}, ensure_ascii=False))
        print(f'ai_done={idx}/{total} mode={mode} parcel={row["parcel_id"]}', flush=True)

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT_CSV, index=False)
    write_log(LOG_FILE, log_lines)
    print(f'ai_review_rows={len(out_df)}')


if __name__ == '__main__':
    main()
