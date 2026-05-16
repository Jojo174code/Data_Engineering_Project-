from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common_utils import ROOT, clean_text, looks_residential_address, validate_workbook, write_dataframe_to_excel

FILTERED_XLSX = ROOT / 'output_excel' / 'filtered_properties_3000_to_8000.xlsx'
AI_REVIEW_CSV = ROOT / 'cleaned_data' / 'ai_property_reviews.csv'
RANKED_XLSX = ROOT / 'output_excel' / 'investment_ranked_properties.xlsx'
MANUAL_REVIEW_XLSX = ROOT / 'output_excel' / 'manual_review_top_candidates.xlsx'

CATEGORY_PRIORITY = {
    'Good Investment': 0,
    'Strong Manual Review Candidate': 1,
    'Mid Investment': 2,
    'Bad Investment': 3,
}
CONF_PRIORITY = {'High': 0, 'Medium': 1, 'Low': 2}
ZIP_CRIME = {
    '74106': 'High', '74110': 'High', '74112': 'Medium', '74114': 'Medium', '74115': 'High', '74126': 'High',
    '74127': 'High', '74128': 'High', '74129': 'High', '74133': 'Low', '74134': 'Low', '74135': 'Medium',
    '74136': 'Low', '74137': 'Low'
}
ZIP_VALUES = {
    '74106': 'Low', '74110': 'Low', '74112': 'Moderate', '74114': 'Positive', '74115': 'Low', '74126': 'Low',
    '74127': 'Low', '74128': 'Low', '74129': 'Moderate', '74133': 'Positive', '74134': 'Positive', '74135': 'Moderate',
    '74136': 'Positive', '74137': 'Positive'
}
ZIP_GROWTH = {
    '74106': 'Unknown', '74110': 'Unknown', '74112': 'Moderate', '74114': 'Positive', '74115': 'Unknown', '74126': 'Unknown',
    '74127': 'Unknown', '74128': 'Unknown', '74129': 'Unknown', '74133': 'Positive', '74134': 'Positive', '74135': 'Moderate',
    '74136': 'Positive', '74137': 'Positive'
}


def bid_price_signal(bid: float) -> tuple[str, int]:
    if bid <= 4500:
        return 'Strong', 9
    if bid <= 6500:
        return 'Moderate', 6
    return 'Weak', 3


def address_quality_signal(address: str) -> tuple[str, int]:
    address = clean_text(address)
    if looks_residential_address(address):
        return 'Complete', 9
    if address and address.upper() != 'ADDRESS UNKNOWN':
        return 'Partial', 5
    return 'Missing', 1


def property_clarity_signal(parcel_id: str, address: str, legal_description: str) -> tuple[str, int]:
    score = 0
    if clean_text(parcel_id):
        score += 1
    if looks_residential_address(address):
        score += 1
    if clean_text(legal_description):
        score += 1
    if score == 3:
        return 'Strong', 9
    if score == 2:
        return 'Moderate', 6
    return 'Weak', 2


def data_confidence(extraction_confidence: str, zip_code: str, clarity_signal: str) -> str:
    if extraction_confidence == 'High' and zip_code != 'Unknown' and clarity_signal == 'Strong':
        return 'High'
    if extraction_confidence in {'High', 'Medium'} and clarity_signal in {'Strong', 'Moderate'}:
        return 'Medium'
    return 'Low'


def score_rule_based(row) -> dict:
    bid = float(row['bid_cost'])
    zip_code = clean_text(row['zip_code']) or 'Unknown'
    addr_signal, addr_score = address_quality_signal(row['property_address'])
    clarity_signal, clarity_score = property_clarity_signal(row['parcel_id'], row['property_address'], row['legal_description'])
    price_signal, price_score = bid_price_signal(bid)

    crime = ZIP_CRIME.get(zip_code, 'Unknown')
    crime_score = {'Low': 8, 'Medium': 5, 'High': 2, 'Unknown': 4}[crime]
    value_signal = ZIP_VALUES.get(zip_code, 'Unknown')
    value_score = {'Positive': 8, 'Moderate': 6, 'Low': 3, 'Unknown': 4}[value_signal]
    growth_signal = ZIP_GROWTH.get(zip_code, 'Unknown')
    growth_score = {'Positive': 8, 'Moderate': 6, 'Unknown': 4}[growth_signal]
    confidence = data_confidence(row['extraction_confidence'], zip_code, clarity_signal)
    confidence_score = {'High': 9, 'Medium': 6, 'Low': 3}[confidence]

    rule_score = round(
        price_score * 0.20 +
        addr_score * 0.15 +
        clarity_score * 0.15 +
        max(crime_score, growth_score) * 0.20 +
        value_score * 0.20 +
        confidence_score * 0.10,
        1,
    )

    property_type = clean_text(row['property_type']).upper()
    raw_text = clean_text(row.get('raw_text', ''))
    red_flag_terms = ['COMMERCIAL', 'INDUSTRIAL', 'VACANT ONLY', 'LANDLOCKED']
    red_flag = any(term in raw_text.upper() for term in red_flag_terms)
    strong_manual = (
        3000 <= bid <= 5500 and
        addr_signal == 'Complete' and
        clean_text(row['parcel_id']) and
        clean_text(row['legal_description']) and
        confidence in {'Medium', 'High'} and
        not red_flag and
        not property_type.startswith('C')
    )

    if (
        price_signal == 'Strong' and addr_signal == 'Complete' and clarity_signal == 'Strong' and
        value_signal == 'Positive' and growth_signal in {'Positive', 'Moderate'} and crime != 'High' and confidence in {'Medium', 'High'}
    ):
        category = 'Good Investment'
    elif strong_manual:
        category = 'Strong Manual Review Candidate'
    elif addr_signal == 'Missing' or not clean_text(row['parcel_id']) or (bid >= 6500 and confidence == 'Low') or red_flag:
        category = 'Bad Investment'
    else:
        category = 'Mid Investment'

    manual_review_flag = category in {'Good Investment', 'Strong Manual Review Candidate'} or confidence == 'Low'
    risks = []
    if crime == 'High':
        risks.append('High crime-risk estimate')
    if value_signal in {'Low', 'Unknown'}:
        risks.append('Weak or unverified surrounding value signal')
    if addr_signal != 'Complete':
        risks.append('Address quality issue')
    if confidence == 'Low':
        risks.append('Low data confidence')
    if property_type == 'R':
        risks.append('Could be lot-only or unimproved, verify improvements')
    if not risks:
        risks.append('Needs normal title/condition verification')

    next_step = 'Drive by and verify assessor/parcel details' if manual_review_flag else 'Verify title, liens, and parcel details before bidding'
    recommendation = 'Research First' if category in {'Good Investment', 'Strong Manual Review Candidate', 'Mid Investment'} else 'Avoid'
    if category == 'Good Investment':
        recommendation = 'Bid Candidate'
    elif category == 'Strong Manual Review Candidate':
        recommendation = 'Drive By'

    reasoning = (
        f"Bid {bid:,.2f}, address quality {addr_signal.lower()}, parcel/address clarity {clarity_signal.lower()}, "
        f"crime signal {crime.lower()}, surrounding value signal {value_signal.lower()}, growth signal {growth_signal.lower()}, "
        f"data confidence {confidence.lower()}."
    )

    return {
        'rule_based_score': rule_score,
        'rule_based_category': category,
        'manual_review_flag': manual_review_flag,
        'crime_risk_estimate': crime,
        'surrounding_value_signal': value_signal,
        'neighborhood_growth_signal': growth_signal,
        'bid_price_signal': price_signal,
        'address_quality_signal': addr_signal,
        'property_clarity_signal': clarity_signal,
        'data_confidence': confidence,
        'reasoning_summary': reasoning,
        'key_risks': '; '.join(risks),
        'next_due_diligence_step': next_step,
        'recommendation': recommendation,
    }


def merge_ai_reviews(df: pd.DataFrame) -> tuple[pd.DataFrame, int, bool, str]:
    fallback_used = False
    failed_ai_reviews = 0
    model_used = 'Rule-based only'
    if AI_REVIEW_CSV.exists():
        ai_df = pd.read_csv(AI_REVIEW_CSV)
        if not ai_df.empty:
            model_used = ai_df['model_used'].dropna().iloc[0] if 'model_used' in ai_df.columns and ai_df['model_used'].dropna().any() else 'LiteLLM'
            df = df.merge(ai_df, on='parcel_id', how='left')
        else:
            fallback_used = True
    else:
        fallback_used = True

    ai_cols_defaults = {
        'ai_review_score': None,
        'investment_category': None,
        'recommendation_ai': None,
        'reasoning_summary_ai': None,
        'key_risks_ai': None,
        'missing_information': None,
        'next_due_diligence_step_ai': None,
        'confidence_level': None,
        'manual_review_flag_ai': None,
    }
    for col, default in ai_cols_defaults.items():
        if col not in df.columns:
            df[col] = default

    for idx, row in df.iterrows():
        if pd.isna(row['ai_review_score']):
            failed_ai_reviews += 1
            fallback_used = True
            df.at[idx, 'ai_review_score'] = row['rule_based_score']
            df.at[idx, 'investment_category'] = row['rule_based_category']
            df.at[idx, 'manual_review_flag_ai'] = row['manual_review_flag']
            df.at[idx, 'recommendation_ai'] = row['recommendation']
            df.at[idx, 'reasoning_summary_ai'] = 'AI review failed; fallback rule-based score used.'
            df.at[idx, 'key_risks_ai'] = row['key_risks']
            df.at[idx, 'missing_information'] = 'No AI review available.'
            df.at[idx, 'next_due_diligence_step_ai'] = row['next_due_diligence_step']
            df.at[idx, 'confidence_level'] = 'Low'

    df['manual_review_flag'] = df['manual_review_flag_ai'].fillna(df['manual_review_flag']).astype(bool)
    df['recommendation'] = df['recommendation_ai'].fillna(df['recommendation'])
    df['reasoning_summary'] = df['reasoning_summary_ai'].fillna(df['reasoning_summary'])
    df['key_risks'] = df['key_risks_ai'].fillna(df['key_risks'])
    df['next_due_diligence_step'] = df['next_due_diligence_step_ai'].fillna(df['next_due_diligence_step'])
    df['confidence_level'] = df['confidence_level'].fillna(df['data_confidence'])
    return df, failed_ai_reviews, fallback_used, model_used


def build_manual_review(df: pd.DataFrame) -> pd.DataFrame:
    review_df = df[df['manual_review_flag'] == True].copy()
    review_df['category_sort'] = review_df['investment_category'].map({'Strong Manual Review Candidate': 0, 'Good Investment': 1, 'Mid Investment': 2, 'Bad Investment': 3}).fillna(4)
    review_df['confidence_sort'] = review_df['confidence_level'].map(CONF_PRIORITY).fillna(3)
    review_df = review_df.sort_values(by=['category_sort', 'ai_review_score', 'bid_cost', 'confidence_sort'], ascending=[True, False, True, True]).head(50)
    review_df['rank'] = range(1, len(review_df) + 1)
    review_df['why_it_is_worth_reviewing'] = review_df['reasoning_summary']
    review_df['main_risk'] = review_df['key_risks']
    review_df = review_df[[
        'rank', 'parcel_id', 'property_address', 'city', 'zip_code', 'bid_cost', 'ai_review_score', 'investment_category',
        'why_it_is_worth_reviewing', 'main_risk', 'missing_information', 'next_due_diligence_step', 'recommendation', 'confidence_level'
    ]]
    return review_df


def main():
    df = pd.read_excel(FILTERED_XLSX)
    baseline = df.apply(score_rule_based, axis=1, result_type='expand')
    ranked_df = pd.concat([df, baseline], axis=1)
    ranked_df, failed_ai_reviews, fallback_used, model_used = merge_ai_reviews(ranked_df)

    ranked_df = ranked_df.rename(columns={'recommendation': 'recommendation'})
    ranked_df = ranked_df[[
        'parcel_id', 'property_address', 'city', 'state', 'zip_code', 'bid_cost', 'legal_description', 'property_type', 'source_page',
        'extraction_confidence', 'rule_based_score', 'rule_based_category', 'bid_price_signal', 'address_quality_signal',
        'property_clarity_signal', 'crime_risk_estimate', 'surrounding_value_signal', 'neighborhood_growth_signal', 'data_confidence',
        'ai_review_score', 'investment_category', 'manual_review_flag', 'recommendation', 'reasoning_summary', 'key_risks',
        'missing_information', 'next_due_diligence_step', 'confidence_level', 'filter_reason', 'raw_text'
    ]]

    ranked_df['category_sort'] = ranked_df['investment_category'].map(CATEGORY_PRIORITY).fillna(9)
    ranked_df['confidence_sort'] = ranked_df['confidence_level'].map(CONF_PRIORITY).fillna(9)
    ranked_df = ranked_df.sort_values(by=['category_sort', 'ai_review_score', 'bid_cost', 'confidence_sort'], ascending=[True, False, True, True])
    ranked_df = ranked_df.drop(columns=['category_sort', 'confidence_sort'])

    write_dataframe_to_excel(
        ranked_df,
        RANKED_XLSX,
        sheet_name='Investment Ranked',
        currency_columns={'bid_cost'},
        wrap_columns={'legal_description', 'reasoning_summary', 'key_risks', 'missing_information', 'next_due_diligence_step', 'filter_reason', 'raw_text'},
        category_fill_column='investment_category',
        category_fills={
            'Good Investment': 'C6EFCE',
            'Strong Manual Review Candidate': 'D9EAF7',
            'Mid Investment': 'FFEB9C',
            'Bad Investment': 'FFC7CE',
        }
    )

    manual_review_df = build_manual_review(ranked_df)
    if manual_review_df.empty:
        raise ValueError('manual_review_top_candidates.xlsx would be empty, stopping for debug.')

    write_dataframe_to_excel(
        manual_review_df,
        MANUAL_REVIEW_XLSX,
        sheet_name='Manual Review',
        currency_columns={'bid_cost'},
        wrap_columns={'why_it_is_worth_reviewing', 'main_risk', 'missing_information', 'next_due_diligence_step'},
        category_fill_column='investment_category',
        category_fills={
            'Good Investment': 'C6EFCE',
            'Strong Manual Review Candidate': 'D9EAF7',
            'Mid Investment': 'FFEB9C',
            'Bad Investment': 'FFC7CE',
        }
    )

    validation_ranked = validate_workbook(RANKED_XLSX, min_rows=2, min_cols=2)
    validation_manual = validate_workbook(MANUAL_REVIEW_XLSX, min_rows=2, min_cols=2)
    print(f"Investment workbook validation: sheets={validation_ranked['sheet_names']}, rows={validation_ranked['max_row']}, cols={validation_ranked['max_column']}")
    print(f"Manual review workbook validation: sheets={validation_manual['sheet_names']}, rows={validation_manual['max_row']}, cols={validation_manual['max_column']}")
    print(f'Failed AI reviews: {failed_ai_reviews}')
    print(f'Fallback rule-based scoring used: {fallback_used}')
    print(f'Model used: {model_used}')


if __name__ == '__main__':
    main()
