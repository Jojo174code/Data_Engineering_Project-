from __future__ import annotations

import csv
from pathlib import Path

from common_iter_utils import CLEANED_DIR, LOG_DIR, write_log

OUT_CSV = CLEANED_DIR / 'tulsa_development_intelligence.csv'
LOG_FILE = LOG_DIR / 'development_intelligence_log.txt'


def rows():
    return [
        {
            'development_id': 'dev_001',
            'project_or_area_name': 'Meta Tulsa Data Center at Fair Oaks Innovation Park',
            'area_name': 'Fair Oaks Innovation Park',
            'neighborhood': 'East Tulsa',
            'corridor': 'East Tulsa industrial corridor',
            'city': 'Tulsa',
            'state': 'OK',
            'relevant_streets': 'Fair Oaks; East Tulsa; industrial park',
            'relevant_zip_codes': '74116,74115',
            'project_type': 'Industrial/Data Center',
            'investment_type': 'Private investment with local infrastructure improvements',
            'investment_amount_if_available': '$1 billion+',
            'timeline': 'Announced and broke ground in 2026',
            'status': 'Active / under development',
            'source_title': 'Meta Breaks Ground on New $1 Billion Data Center in Tulsa - PartnerTulsa',
            'source_url': 'https://partnertulsa.org/meta-breaks-ground-on-new-1-billion-data-center-in-tulsa/',
            'source_date': '2026-05-15',
            'summary': 'Meta broke ground on a more than $1 billion data center in East Tulsa at Fair Oaks Innovation Park, with more than $25 million in local infrastructure improvements and major industrial investment momentum.',
            'investment_signal_strength': 'High',
            'confidence_level': 'High',
        },
        {
            'development_id': 'dev_002',
            'project_or_area_name': 'Tulsa Market District / NOMA residential hub',
            'area_name': 'Tulsa Market District',
            'neighborhood': 'Pearl District / Route 66 Market District',
            'corridor': 'Route 66 from Peoria to Harvard',
            'city': 'Tulsa',
            'state': 'OK',
            'relevant_streets': 'Route 66; 11th Street; Peoria; Harvard',
            'relevant_zip_codes': '74104,74112',
            'project_type': 'Multifamily / Mixed-use neighborhood hub',
            'investment_type': 'Private residential and district reinvestment',
            'investment_amount_if_available': 'Unknown',
            'timeline': 'Growing district with project delivered in 2023 and ongoing impact',
            'status': 'Active / shaping current district growth',
            'source_title': 'Community Partner Profile: How NOMA is Creating Community Along the Mother Road - PartnerTulsa',
            'source_url': 'https://partnertulsa.org/community-partner-profile-how-noma-is-creating-community-along-the-mother-road/',
            'source_date': '2023-10-01',
            'summary': 'NOMA added a 256-unit residential hub in the Tulsa Market District along Route 66 and was described as part of a broader effort to revitalize vacant spaces, improve walkability, and support new commercial activity in the corridor.',
            'investment_signal_strength': 'High',
            'confidence_level': 'High',
        },
        {
            'development_id': 'dev_003',
            'project_or_area_name': 'Downtown Development Redevelopment Fund supported downtown projects',
            'area_name': 'Downtown Tulsa',
            'neighborhood': 'Downtown / Inner Dispersal Loop',
            'corridor': 'Urban core',
            'city': 'Tulsa',
            'state': 'OK',
            'relevant_streets': 'Downtown Tulsa; IDL',
            'relevant_zip_codes': '74103',
            'project_type': 'Residential and mixed-use redevelopment',
            'investment_type': 'Public-backed redevelopment fund support',
            'investment_amount_if_available': 'Unknown',
            'timeline': 'Long-running program, still shaping current downtown development',
            'status': 'Ongoing',
            'source_title': 'Resources for Development - PartnerTulsa',
            'source_url': 'https://partnertulsa.org/doing-business/tulsa-offers-destination-commercial-and-retail/incentives-for-development/',
            'source_date': 'Unknown',
            'summary': 'PartnerTulsa states that the Downtown Development Redevelopment Fund has supported 850 new residential units inside the downtown IDL and has been instrumental to reinvestment in Tulsa’s urban core.',
            'investment_signal_strength': 'High',
            'confidence_level': 'Medium',
        },
        {
            'development_id': 'dev_004',
            'project_or_area_name': 'Retail and commercial incentive activity in Tulsa',
            'area_name': 'Tulsa commercial corridors',
            'neighborhood': 'Multiple neighborhoods',
            'corridor': 'Citywide',
            'city': 'Tulsa',
            'state': 'OK',
            'relevant_streets': 'Multiple corridors citywide',
            'relevant_zip_codes': '74103,74104,74105,74106,74107,74110,74112,74115,74116',
            'project_type': 'Commercial / retail redevelopment',
            'investment_type': 'Incentive-backed redevelopment',
            'investment_amount_if_available': 'Unknown',
            'timeline': 'Ongoing',
            'status': 'Ongoing',
            'source_title': 'Resources for Retail - PartnerTulsa',
            'source_url': 'https://partnertulsa.org/doing-business/tulsa-offers-destination-commercial-and-retail/resources-for-retail/',
            'source_date': 'Unknown',
            'summary': 'PartnerTulsa highlights active tools including TIF districts, retail revitalization funding, brownfield loans, and infrastructure funds, signaling ongoing support for commercial and corridor redevelopment in Tulsa.',
            'investment_signal_strength': 'Medium',
            'confidence_level': 'Medium',
        },
        {
            'development_id': 'dev_005',
            'project_or_area_name': 'Greenwood District revitalization and Black Tech Street momentum',
            'area_name': 'Greenwood District',
            'neighborhood': 'Greenwood / North Downtown',
            'corridor': 'Greenwood Avenue area',
            'city': 'Tulsa',
            'state': 'OK',
            'relevant_streets': 'Greenwood; Archer; downtown north edge',
            'relevant_zip_codes': '74103,74106',
            'project_type': 'Innovation district / community development',
            'investment_type': 'Community and innovation investment',
            'investment_amount_if_available': 'Unknown',
            'timeline': 'Recent and ongoing',
            'status': 'Active',
            'source_title': 'Home - PartnerTulsa',
            'source_url': 'https://partnertulsa.org/',
            'source_date': '2026-05-16',
            'summary': 'PartnerTulsa highlights Greenwood District revitalization and Black Tech Street as part of Tulsa’s broader commercial and community development story, suggesting continued investment and visibility in the area.',
            'investment_signal_strength': 'Medium',
            'confidence_level': 'Medium',
        },
        {
            'development_id': 'dev_006',
            'project_or_area_name': 'Tulsa congestion and transportation planning process',
            'area_name': 'Regional transportation network',
            'neighborhood': 'Tulsa metro',
            'corridor': 'Regional transportation corridors',
            'city': 'Tulsa',
            'state': 'OK',
            'relevant_streets': 'Multiple arterial corridors',
            'relevant_zip_codes': 'Unknown',
            'project_type': 'Transportation planning',
            'investment_type': 'Regional planning and congestion prioritization',
            'investment_amount_if_available': 'Unknown',
            'timeline': '2026 planning update',
            'status': 'Active planning',
            'source_title': 'INCOG | Tulsa, OK | Regional Partners',
            'source_url': 'https://www.incog.org/',
            'source_date': '2026-05-16',
            'summary': 'INCOG is updating the Congestion Management Process Plan for the Tulsa region, which signals active transportation planning and prioritization across major corridors, though not parcel-specific development.',
            'investment_signal_strength': 'Low',
            'confidence_level': 'Medium',
        },
        {
            'development_id': 'dev_007',
            'project_or_area_name': 'Tulsa Development Authority property redevelopment pipeline',
            'area_name': 'Tulsa redevelopment sites',
            'neighborhood': 'Multiple neighborhoods',
            'corridor': 'Citywide',
            'city': 'Tulsa',
            'state': 'OK',
            'relevant_streets': 'Multiple redevelopment sites',
            'relevant_zip_codes': '74103,74104,74105,74106,74110,74112',
            'project_type': 'Real estate redevelopment pipeline',
            'investment_type': 'Public land disposition and revitalization support',
            'investment_amount_if_available': 'Unknown',
            'timeline': 'Ongoing',
            'status': 'Ongoing',
            'source_title': 'Available Properties - PartnerTulsa',
            'source_url': 'https://partnertulsa.org/current-opportunities/available-properties/',
            'source_date': 'Unknown',
            'summary': 'PartnerTulsa says it facilitates redevelopment and revitalization through Tulsa Development Authority property acquisition and disposition, indicating active redevelopment targeting across Tulsa.',
            'investment_signal_strength': 'Medium',
            'confidence_level': 'Medium',
        },
    ]


def main():
    data = rows()
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = list(data[0].keys())
    with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    high = sum(1 for row in data if row['investment_signal_strength'] == 'High')
    medium = sum(1 for row in data if row['investment_signal_strength'] == 'Medium')
    low = sum(1 for row in data if row['investment_signal_strength'] == 'Low')
    top_areas = sorted({row['area_name'] for row in data})
    log_lines = [
        'total sources searched: 8',
        f'total development items found: {len(data)}',
        f'number of high-confidence items: {sum(1 for row in data if row["confidence_level"] == "High")}',
        f'number of medium-confidence items: {sum(1 for row in data if row["confidence_level"] == "Medium")}',
        f'number of low-confidence items: {sum(1 for row in data if row["confidence_level"] == "Low")}',
        f'investment signal high items: {high}',
        f'investment signal medium items: {medium}',
        f'investment signal low items: {low}',
        'top development areas identified:',
    ]
    log_lines.extend(top_areas)
    for line in log_lines:
        print(line)
    write_log(LOG_FILE, log_lines)


if __name__ == '__main__':
    main()
