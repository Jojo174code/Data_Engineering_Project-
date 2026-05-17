from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ITERATION_ROOT = Path(__file__).resolve().parents[1]
CLEANED_DIR = ITERATION_ROOT / 'cleaned_data'
LOG_DIR = ITERATION_ROOT / 'logs'

BASE_CSV = CLEANED_DIR / 'final_property_base.csv'
DEV_CSV = CLEANED_DIR / 'final_development_intelligence.csv'
OUT_CSV = CLEANED_DIR / 'final_property_development_matches.csv'
LOG_FILE = LOG_DIR / 'development_verification_log.txt'

WEAK_WARNING = 'Weak match removed; previous match was based on generic or insufficient location wording.'
LEGAL_NOISE = {'LOT', 'LT', 'LTS', 'BLK', 'BLOCK', 'ADDN', 'ADDITION', 'SUB', 'SUBD', 'RESUB', 'SEC', 'ACS', 'AC', 'R', 'W', 'RR'}
BANNED_WEAK_TERMS = {
    'TULSA', 'OKLAHOMA', 'COUNTY', 'CITY', 'NORTH', 'SOUTH', 'EAST', 'WEST', 'N', 'S', 'E', 'W',
    'STREET', 'AVENUE', 'ROAD', 'BOULEVARD', 'DRIVE', 'PLACE', 'COURT', 'ST', 'AVE', 'RD', 'BLVD', 'DR', 'PL', 'CT',
    'DISTRICT', 'AREA', 'PROJECT', 'DEVELOPMENT', 'REDEVELOPMENT', 'CENTER', 'CENTRE', 'HUB', 'CORRIDOR',
    'CITYWIDE', 'REGIONAL', 'METRO', 'MULTIPLE', 'URBAN', 'CORE', 'COMMERCIAL', 'RETAIL'
}
BROAD_LABELS = {'MULTIPLE NEIGHBORHOODS', 'CITYWIDE', 'URBAN CORE', 'TULSA METRO', 'REGIONAL TRANSPORTATION NETWORK', 'TULSA COMMERCIAL CORRIDORS', 'TULSA REDEVELOPMENT SITES'}
TOKEN_RE = re.compile(r'[^A-Z0-9]+')


def clean_text(value) -> str:
    if value is None:
        return 'Unknown'
    text = str(value).strip()
    return text if text else 'Unknown'


def tokenize(value, *, remove_banned=True, keep_numbers=False) -> set[str]:
    text = clean_text(value).upper()
    if text == 'UNKNOWN':
        return set()
    tokens = set()
    for part in TOKEN_RE.split(text):
        if not part:
            continue
        if not keep_numbers and part.isdigit() and part != '66':
            continue
        if len(part) <= 1 and part != '66':
            continue
        if part in LEGAL_NOISE:
            continue
        if remove_banned and part in BANNED_WEAK_TERMS:
            continue
        tokens.add(part)
    return tokens


def parse_zips(value) -> set[str]:
    text = clean_text(value)
    return set(re.findall(r'\b\d{5}\b', text))


def is_usable_address(address: str) -> bool:
    text = clean_text(address).upper()
    return text not in {'UNKNOWN', 'ADDRESS UNKNOWN'} and bool(re.match(r'^\d+\s+.+', text))


def is_broad_development(dev_row: pd.Series) -> bool:
    labels = {
        clean_text(dev_row.get('area_name')).upper(),
        clean_text(dev_row.get('neighborhood')).upper(),
        clean_text(dev_row.get('corridor')).upper(),
        clean_text(dev_row.get('project_or_area_name')).upper(),
    }
    return any(label in BROAD_LABELS for label in labels)


def source_confidence_value(dev_row: pd.Series) -> int:
    value = clean_text(dev_row.get('confidence_level'))
    return {'High': 3, 'Medium': 2, 'Low': 1}.get(value, 1)


def investment_value(dev_row: pd.Series) -> int:
    value = clean_text(dev_row.get('investment_signal_strength'))
    return {'High': 3, 'Medium': 2, 'Low': 1}.get(value, 1)


def evaluate_match(prop_row: pd.Series, dev_row: pd.Series) -> dict:
    address_tokens = tokenize(prop_row['property_address'], keep_numbers=True)
    legal_tokens = tokenize(prop_row['legal_description'])
    prop_tokens = address_tokens | legal_tokens
    non_numeric_prop_tokens = {token for token in prop_tokens if not token.isdigit() and token != '66'}

    raw_prop = tokenize(prop_row['property_address'], remove_banned=False, keep_numbers=True) | tokenize(prop_row['legal_description'], remove_banned=False)
    project_tokens = {token for token in tokenize(dev_row['project_or_area_name']) if not token.isdigit() and token != '66'}
    area_tokens = {token for token in tokenize(dev_row['area_name']) if not token.isdigit() and token != '66'}
    neighborhood_tokens = {token for token in tokenize(dev_row['neighborhood']) if not token.isdigit() and token != '66'}
    corridor_tokens = tokenize(dev_row['relevant_streets'], keep_numbers=True) | tokenize(dev_row['corridor'], keep_numbers=True)
    raw_dev = tokenize(dev_row['project_or_area_name'], remove_banned=False, keep_numbers=True) | tokenize(dev_row['area_name'], remove_banned=False, keep_numbers=True) | tokenize(dev_row['neighborhood'], remove_banned=False, keep_numbers=True) | tokenize(dev_row['relevant_streets'], remove_banned=False, keep_numbers=True) | tokenize(dev_row['corridor'], remove_banned=False, keep_numbers=True)

    project_overlap = sorted(non_numeric_prop_tokens & project_tokens)
    area_overlap = sorted(non_numeric_prop_tokens & area_tokens)
    neighborhood_overlap = sorted(non_numeric_prop_tokens & neighborhood_tokens)
    corridor_overlap = sorted(address_tokens & corridor_tokens)
    raw_overlap = sorted(raw_prop & raw_dev)

    prop_zips = parse_zips(prop_row['zip_code'])
    dev_zips = parse_zips(dev_row['relevant_zip_codes'])
    zip_overlap = sorted(prop_zips & dev_zips) if prop_zips and dev_zips else []

    broad_dev = is_broad_development(dev_row)
    exact_named_overlap = neighborhood_overlap or project_overlap or area_overlap
    weak_only = bool(raw_overlap) and not exact_named_overlap and not corridor_overlap and not zip_overlap

    if not is_usable_address(prop_row['property_address']) and not prop_zips and not legal_tokens:
        return {
            'rank': 0,
            'strength': 'Unknown',
            'quality': 'Low',
            'confidence': 'Low',
            'warning': '',
            'reason': 'Missing or unusable address and no useful ZIP or legal-description location evidence',
            'basis': 'unknown',
            'removed_weak': False,
        }

    if exact_named_overlap and not broad_dev:
        reason_tokens = neighborhood_overlap or project_overlap or area_overlap
        if zip_overlap:
            return {
                'rank': 95,
                'strength': 'Strong Match',
                'quality': 'High',
                'confidence': 'High',
                'warning': '',
                'reason': f"Same named district/neighborhood plus ZIP support: {', '.join(reason_tokens[:5])}; ZIP {', '.join(zip_overlap)}",
                'basis': 'named_area_plus_zip',
                'removed_weak': False,
            }
        return {
            'rank': 80,
            'strength': 'Strong Match',
            'quality': 'High',
            'confidence': 'Medium' if source_confidence_value(dev_row) >= 2 else 'Low',
            'warning': '',
            'reason': f"Same named district or neighborhood with source support: {', '.join(reason_tokens[:5])}",
            'basis': 'named_area',
            'removed_weak': False,
        }

    if zip_overlap and corridor_overlap and not broad_dev:
        return {
            'rank': 74,
            'strength': 'Strong Match',
            'quality': 'High',
            'confidence': 'Medium',
            'warning': '',
            'reason': f"Same ZIP plus stronger corridor evidence: {', '.join(corridor_overlap[:5])}; ZIP {', '.join(zip_overlap)}",
            'basis': 'zip_plus_corridor',
            'removed_weak': False,
        }

    if corridor_overlap and not broad_dev:
        return {
            'rank': 55,
            'strength': 'Possible Match',
            'quality': 'Medium',
            'confidence': 'Medium',
            'warning': '',
            'reason': f"Partial named corridor overlap without verified proximity: {', '.join(corridor_overlap[:5])}",
            'basis': 'corridor_only',
            'removed_weak': False,
        }

    if zip_overlap and not broad_dev:
        return {
            'rank': 45,
            'strength': 'Possible Match',
            'quality': 'Low',
            'confidence': 'Low',
            'warning': '',
            'reason': f"ZIP overlap with sourced development area but limited stronger evidence: {', '.join(zip_overlap)}",
            'basis': 'zip_only',
            'removed_weak': False,
        }

    if weak_only or broad_dev:
        return {
            'rank': 10,
            'strength': 'No Clear Match',
            'quality': 'Invalid Weak Match' if raw_overlap else 'Low',
            'confidence': 'Low',
            'warning': WEAK_WARNING if raw_overlap else '',
            'reason': f"Weak or overly broad overlap only: {', '.join(raw_overlap[:5])}" if raw_overlap else 'Development area is too broad to connect credibly to the property',
            'basis': 'weak_or_broad',
            'removed_weak': bool(raw_overlap),
        }

    return {
        'rank': 20,
        'strength': 'No Clear Match',
        'quality': 'Low',
        'confidence': 'Low',
        'warning': '',
        'reason': 'Property is not clearly near or tied to the development area based on available address, ZIP, and named-location evidence',
        'basis': 'no_clear_match',
        'removed_weak': False,
    }


def build_row(prop_row: pd.Series, dev_row: pd.Series | None, evaluation: dict, prev_strong: str) -> dict:
    match_strength = evaluation['strength']
    matched = dev_row is not None and match_strength in {'Strong Match', 'Possible Match'}
    warning = evaluation['warning']
    if not warning and prev_strong in {'Strong Match', 'Possible Match'} and match_strength in {'No Clear Match', 'Unknown'} and evaluation['basis'] in {'weak_or_broad', 'no_clear_match'}:
        warning = WEAK_WARNING
    return {
        'parcel_id': prop_row['parcel_id'],
        'property_address': prop_row['property_address'],
        'city': prop_row['city'],
        'state': prop_row['state'],
        'zip_code': prop_row['zip_code'],
        'legal_description': prop_row['legal_description'],
        'bid_cost': prop_row['bid_cost'],
        'previous_investment_category': prop_row.get('previous_investment_category', 'Unknown'),
        'previous_development_match_strength': prev_strong,
        'previous_development_match_quality': prop_row.get('previous_development_match_quality', 'Unknown'),
        'final_development_match_strength': match_strength,
        'final_matched_development_area': dev_row['area_name'] if matched else 'Unknown',
        'final_matched_project_or_area_name': dev_row['project_or_area_name'] if matched else 'Unknown',
        'final_matched_project_type': dev_row['project_type'] if matched else 'Unknown',
        'final_matched_investment_signal_strength': dev_row['investment_signal_strength'] if matched else 'Unknown',
        'final_development_source_title': dev_row['source_title'] if matched else 'Unknown',
        'final_development_source_url': dev_row['source_url'] if matched else 'Unknown',
        'final_development_summary': dev_row['summary'] if matched else 'Unknown',
        'final_development_corridor': dev_row['corridor'] if matched else 'Unknown',
        'final_development_relevant_streets': dev_row['relevant_streets'] if matched else 'Unknown',
        'final_development_match_reason': evaluation['reason'],
        'final_development_match_quality': evaluation['quality'],
        'final_development_warning': warning,
        'final_development_confidence': evaluation['confidence'] if not matched else dev_row['confidence_level'],
        'final_match_basis': evaluation['basis'],
        'final_development_geocode_query': dev_row['development_geocode_query'] if matched else 'Unknown',
        'weak_match_removed_flag': bool(warning == WEAK_WARNING or evaluation['removed_weak']),
    }


def main():
    props = pd.read_csv(BASE_CSV)
    dev = pd.read_csv(DEV_CSV)

    records = []
    weak_removed = 0
    previous_strong = int(props['previous_development_match_strength'].isin(['Strong Match']).sum()) if 'previous_development_match_strength' in props.columns else 0

    for _, prop_row in props.iterrows():
        best_dev = None
        best_eval = {'rank': -1, 'strength': 'Unknown', 'quality': 'Low', 'confidence': 'Low', 'warning': '', 'reason': 'No evaluation', 'basis': 'unknown', 'removed_weak': False}
        for _, dev_row in dev.iterrows():
            evaluation = evaluate_match(prop_row, dev_row)
            tie_break = (evaluation['rank'], source_confidence_value(dev_row), investment_value(dev_row))
            best_tie = (best_eval['rank'], source_confidence_value(best_dev) if best_dev is not None else 0, investment_value(best_dev) if best_dev is not None else 0)
            if tie_break > best_tie:
                best_dev = dev_row
                best_eval = evaluation

        prev_strength = clean_text(prop_row.get('previous_development_match_strength', 'Unknown'))
        row = build_row(prop_row, best_dev, best_eval, prev_strength)
        weak_removed += int(row['weak_match_removed_flag'])
        records.append(row)

    out_df = pd.DataFrame(records)
    out_df.to_csv(OUT_CSV, index=False)

    final_strong = int((out_df['final_development_match_strength'] == 'Strong Match').sum())
    final_possible = int((out_df['final_development_match_strength'] == 'Possible Match').sum())
    final_no_clear = int((out_df['final_development_match_strength'] == 'No Clear Match').sum())
    final_unknown = int((out_df['final_development_match_strength'] == 'Unknown').sum())

    lines = [
        f'previous Strong Matches: {previous_strong}',
        f'final Strong Matches: {final_strong}',
        f'weak matches removed: {weak_removed}',
        f'Possible Matches: {final_possible}',
        f'No Clear Matches: {final_no_clear}',
        f'Unknown matches: {final_unknown}',
    ]
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for line in lines:
        print(line)


if __name__ == '__main__':
    main()
