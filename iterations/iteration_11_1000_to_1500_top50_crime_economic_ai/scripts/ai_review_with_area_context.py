#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

ITERATION_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ITERATION_ROOT.parents[1]
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
LOG_DIR = ITERATION_ROOT / 'logs'
IN_CSV = CLEANED_DIR / 'crime_economic_ranked_properties.csv'
OUT_CSV = CLEANED_DIR / 'ai_reviews_crime_economic.csv'
LOG_FILE = LOG_DIR / 'ai_review_log.txt'

ALLOWED_CATEGORIES = {'Top Candidate', 'Manual Review Candidate', 'Risky / Needs Verification', 'Avoid'}
ALLOWED_RECOMMENDATIONS = {'Research First', 'Drive By', 'Watch', 'Avoid'}
ALLOWED_CONFIDENCE = {'High', 'Medium', 'Low'}

SYSTEM_MSG = 'You are a grounded tax-auction property screening assistant. Return valid JSON only. Use only the provided property, crime, and economic data. Do not invent facts.'
PROMPT_TEMPLATE = """Review this Tulsa County auction property in the $1,000-$1,500 range.

This is not final investment advice.
Your job is to help rank whether the property deserves to be in the final Top 50 list.

Use only the provided data.

Property Data:
Parcel ID: {parcel_id}
Owner Name: {owner_name}
Address: {property_address}
City: {city}
State: {state}
ZIP: {zip_code}
Confirmed ZIP: {confirmed_zip_code}
Bid Cost: {bid_cost}
Legal Description: {legal_description}
Property Type: {property_type}
Extraction Confidence: {extraction_confidence}

Geocoding:
Geocode Status: {geocode_status}
Geocode Confidence: {geocode_confidence}
Latitude: {latitude}
Longitude: {longitude}
Neighborhood/Area: {neighborhood_or_area}

Crime Context:
Crime Source: {crime_source}
Crime Date Range: {crime_data_date_range}
Crime Incident Count 0.5mi: {crime_incident_count_0_5mi}
Violent Crime Count 0.5mi: {violent_crime_count_0_5mi}
Property Crime Count 0.5mi: {property_crime_count_0_5mi}
Crime Risk Score: {crime_risk_score}
Crime Risk Level: {crime_risk_level}
Crime Confidence: {crime_confidence}
Crime Notes: {crime_notes}

Economic Context:
Median Household Income: {median_household_income}
Poverty Rate: {poverty_rate}
Unemployment Rate: {unemployment_rate}
Median Home Value: {median_home_value}
Median Gross Rent: {median_gross_rent}
Vacancy Rate: {vacancy_rate}
Owner Occupied Rate: {owner_occupied_rate}
Economic Risk Level: {economic_risk_level}
Economic Confidence: {economic_confidence}
Economic Source: {economic_source}

Rule-Based Area Ranking:
Pre-AI Final Score: {pre_ai_final_score}
Pre-AI Category: {pre_ai_category}
Property Clarity Score: {property_clarity_score}
Geocoding Score: {geocoding_score}
Residential Likelihood Score: {residential_likelihood_score}
Crime Score: {crime_score}
Economic Strength Score: {economic_strength_score}
Area Ranking Reason: {area_ranking_reason}
Area Key Risks: {area_key_risks}

Return JSON only:

{{
 "parcel_id": "",
 "ai_area_adjusted_score": 0,
 "ai_area_adjusted_category": "",
 "recommendation": "",
 "reasoning_summary": "",
 "crime_economic_summary": "",
 "key_risks": "",
 "missing_information": "",
 "next_due_diligence_step": "",
 "confidence_level": ""
}}

Rules:
- Top Candidate requires usable property data and acceptable area signals.
- Manual Review Candidate means worth checking manually, not automatically worth bidding.
- Risky / Needs Verification means possible opportunity but the area/property uncertainty is high.
- Avoid means the known risk is too high or the property data is too weak.
- Unknown crime/economic data should lower confidence.
- Mention bid cost, address or parcel ID, crime risk, and economic data status.
- Return JSON only.
"""


def clean_text(value, default='Unknown.'):
    if value is None:
        return default
    if pd.isna(value):
        return default
    text = str(value).strip()
    if not text or text.lower() == 'nan':
        return default
    return text


def numeric(value, fallback=None):
    try:
        return float(value)
    except Exception:
        return fallback


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


def reasoning_valid(payload: dict, row: pd.Series) -> bool:
    reasoning = clean_text(payload.get('reasoning_summary')).lower()
    bid_variants = [str(row['bid_cost']).lower()]
    try:
        bid_variants.append(f"{float(row['bid_cost']):.2f}".lower())
    except Exception:
        pass
    has_bid = any(b and b in reasoning for b in bid_variants)
    has_property = clean_text(row['parcel_id']).lower() in reasoning or clean_text(row['property_address']).lower() in reasoning
    has_crime = clean_text(row['crime_risk_level']).lower() in reasoning
    econ_field = any(token in reasoning for token in ['income', 'poverty', 'unemployment', 'economic data is unknown', 'economic confidence', 'median household income'])
    conf = clean_text(payload.get('confidence_level')).lower() in reasoning or clean_text(row['data_confidence']).lower() in reasoning or 'confidence' in reasoning
    generic = len(reasoning.split()) < 18
    return has_bid and has_property and has_crime and econ_field and conf and not generic


def normalize_category(value: str, row: pd.Series) -> str:
    text = clean_text(value)
    if text in ALLOWED_CATEGORIES:
        out = text
    else:
        out = clean_text(row['pre_ai_category']) if clean_text(row['pre_ai_category']) in ALLOWED_CATEGORIES else 'Risky / Needs Verification'
    if clean_text(row['crime_risk_level']) == 'High' and out == 'Top Candidate':
        return 'Manual Review Candidate'
    if clean_text(row['economic_risk_level']) == 'High' and out == 'Top Candidate':
        return 'Manual Review Candidate'
    return out


def normalize_recommendation(value: str, category: str) -> str:
    text = clean_text(value)
    if text in ALLOWED_RECOMMENDATIONS:
        return text
    return {
        'Top Candidate': 'Research First',
        'Manual Review Candidate': 'Drive By',
        'Risky / Needs Verification': 'Watch',
        'Avoid': 'Avoid',
    }[category]


def normalize_confidence(value: str, row: pd.Series) -> str:
    text = clean_text(value)
    if text in ALLOWED_CONFIDENCE:
        return text
    data_conf = clean_text(row['data_confidence'])
    return data_conf if data_conf in ALLOWED_CONFIDENCE else 'Medium'


def fallback_record(row: pd.Series, reason: str) -> dict:
    pre_score = numeric(row['pre_ai_final_score'], 5.0)
    category = normalize_category(clean_text(row['pre_ai_category']), row)
    confidence = normalize_confidence('', row)
    econ_phrase = 'economic data is Unknown' if clean_text(row['median_household_income']) in {'Unknown.', 'Unknown'} else f"median household income {row['median_household_income']}"
    reasoning = (
        f"Bid cost {float(row['bid_cost']):.2f} for parcel {row['parcel_id']} at {row['property_address']} stays in {category} because crime risk is "
        f"{row['crime_risk_level']} and {econ_phrase}; fallback confidence is {confidence}."
    )
    summary = (
        f"Crime signal is {row['crime_risk_level']} with {row['crime_confidence']} confidence. "
        f"Economic risk is {row['economic_risk_level']} with {row['economic_confidence']} confidence."
    )
    return {
        'parcel_id': row['parcel_id'],
        'ai_area_adjusted_score': round(pre_score, 2),
        'ai_area_adjusted_category': category,
        'recommendation': normalize_recommendation('', category),
        'reasoning_summary': reasoning,
        'crime_economic_summary': summary,
        'key_risks': clean_text(row['area_key_risks']),
        'missing_information': clean_text(reason),
        'next_due_diligence_step': 'Verify assessor details, title/liens, street-level condition, and whether the parcel is practically usable before bidding.',
        'confidence_level': confidence,
    }


def normalize_record(payload: dict, row: pd.Series) -> dict:
    pre_score = numeric(row['pre_ai_final_score'], 5.0)
    ai_score = numeric(payload.get('ai_area_adjusted_score'), pre_score)
    ai_score = max(pre_score - 1.5, min(pre_score + 1.25, ai_score))
    ai_score = round(max(1.0, min(10.0, ai_score)), 2)
    category = normalize_category(payload.get('ai_area_adjusted_category', row['pre_ai_category']), row)
    rec = normalize_recommendation(payload.get('recommendation', ''), category)
    conf = normalize_confidence(payload.get('confidence_level', ''), row)
    out = {
        'parcel_id': row['parcel_id'],
        'ai_area_adjusted_score': ai_score,
        'ai_area_adjusted_category': category,
        'recommendation': rec,
        'reasoning_summary': clean_text(payload.get('reasoning_summary')),
        'crime_economic_summary': clean_text(payload.get('crime_economic_summary')),
        'key_risks': clean_text(payload.get('key_risks', row['area_key_risks'])),
        'missing_information': clean_text(payload.get('missing_information')),
        'next_due_diligence_step': clean_text(payload.get('next_due_diligence_step', 'Verify assessor details, title/liens, and parcel usability before bidding.')),
        'confidence_level': conf,
    }
    if not reasoning_valid(out, row):
        raise ValueError('Reasoning summary missing required concrete fields.')
    return out


def review_with_model(client: OpenAI, model: str, row: pd.Series):
    row_dict = {k: clean_text(v) for k, v in row.to_dict().items()}
    row_dict['bid_cost'] = f"{float(row['bid_cost']):.2f}"
    prompt = PROMPT_TEMPLATE.format(**row_dict)
    retry_prompt = prompt + '\nYour previous response was too generic or missed required references. Mention the bid cost, parcel or address, crime risk level, at least one economic field or explicitly say economic data is Unknown, and confidence.'
    last_error = 'Unknown model error'
    for attempt, content in enumerate([prompt, retry_prompt], start=1):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.1,
                timeout=45.0,
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


def main():
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(IN_CSV)
    try:
        client, model = load_client()
        ai_ready = True
        startup_note = f'OpenAI ready with configured model {model}.'
    except Exception as exc:
        client = None
        model = None
        ai_ready = False
        startup_note = f'OpenAI unavailable, rule-based fallback will be used. Reason: {exc}'

    rows = []
    logs = [startup_note]
    total = len(df)
    for idx, (_, row) in enumerate(df.iterrows(), start=1):
        try:
            if ai_ready:
                record, mode = review_with_model(client, model, row)
            else:
                raise RuntimeError('Fallback forced because OpenAI configuration was unavailable.')
        except Exception as exc:
            record = fallback_record(row, f'Fallback used: {exc}')
            mode = 'rule_based_fallback'
        rows.append(record)
        logs.append(json.dumps({'mode': mode, **record}, ensure_ascii=False))
        if idx % 5 == 0 or idx == total:
            print(f'ai_progress={idx}/{total}')

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT_CSV, index=False)
    LOG_FILE.write_text('\n'.join(logs))
    print(f'ai_review_rows={len(out_df)}')


if __name__ == '__main__':
    main()
