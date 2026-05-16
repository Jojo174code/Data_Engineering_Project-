import csv, zipfile, re
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
IN_CSV = ROOT / 'cleaned_data' / 'cleaned_auction_properties.csv'
OUT_XLSX = ROOT / 'output_excel' / 'investment_ranked_properties.xlsx'

MIN_BID = 3000
MAX_BID = 8000

ZIP_SAFETY = {
    '74106': ('High', 2, 'North Tulsa area has historically elevated crime risk compared with metro averages.'),
    '74110': ('High', 2, 'North Tulsa area has historically elevated crime risk compared with metro averages.'),
    '74112': ('Medium', 5, 'Midtown/east Tulsa has mixed block-by-block risk.'),
    '74114': ('Medium', 6, 'Established midtown area, generally better than citywide average but mixed by corridor.'),
    '74115': ('High', 3, 'Airport and north-central Tulsa areas are generally higher risk.'),
    '74126': ('High', 2, 'Far north Tulsa generally screens as higher risk.'),
    '74127': ('High', 3, 'West/northwest Tulsa often has elevated risk.'),
    '74128': ('High', 3, 'East Tulsa has many higher-risk pockets.'),
    '74129': ('High', 3, 'East Tulsa has many higher-risk pockets.'),
    '74133': ('Low', 7, 'South Tulsa is generally lower crime than citywide average.'),
    '74134': ('Low', 7, 'Far southeast Tulsa is generally lower crime than citywide average.'),
    '74135': ('Medium', 6, 'Central/south Tulsa is mixed but often more stable than city average.'),
    '74136': ('Low', 7, 'South Tulsa tends to screen better on stability and crime.'),
    '74137': ('Low', 8, 'Far south Tulsa tends to screen better on stability and crime.'),
}
ZIP_VALUES = {
    '74106': ('$40k-$90k estimate', 2), '74110': ('$45k-$95k estimate', 3), '74112': ('$90k-$170k estimate', 5),
    '74114': ('$140k-$300k+ estimate', 8), '74115': ('$55k-$110k estimate', 3), '74126': ('$40k-$90k estimate', 2),
    '74127': ('$55k-$130k estimate', 4), '74128': ('$60k-$130k estimate', 3), '74129': ('$65k-$140k estimate', 4),
    '74133': ('$180k-$350k+ estimate', 8), '74134': ('$180k-$325k+ estimate', 8), '74135': ('$120k-$240k estimate', 6),
    '74136': ('$180k-$350k+ estimate', 8), '74137': ('$220k-$450k+ estimate', 9),
}
ZIP_GROWTH = {
    '74106': ('Medium', 5, 'Some long-horizon redevelopment potential, but uneven execution risk.'),
    '74110': ('Medium', 5, 'Some reinvestment potential, but neighborhood risk remains meaningful.'),
    '74112': ('Medium', 6, 'Infill and midtown proximity help, but results vary a lot by street.'),
    '74114': ('High', 8, 'Midtown location and established demand support long-run desirability.'),
    '74115': ('Low', 3, 'Weaker screening signal for stable appreciation.'),
    '74126': ('Low', 2, 'Limited evidence of near-term broad-based uplift.'),
    '74127': ('Low', 3, 'Patchy upside, weaker broad investment signal.'),
    '74128': ('Low', 3, 'Patchy upside and more operational risk.'),
    '74129': ('Low', 3, 'Patchy upside and more operational risk.'),
    '74133': ('High', 8, 'South Tulsa submarket generally benefits from stronger buyer and renter demand.'),
    '74134': ('High', 8, 'South/east Tulsa generally benefits from stronger buyer and renter demand.'),
    '74135': ('Medium', 6, 'Established neighborhoods and central access support moderate upside.'),
    '74136': ('High', 8, 'South Tulsa market generally shows stronger stability and resale demand.'),
    '74137': ('High', 9, 'Far south Tulsa typically screens well for stability and demand.'),
}
CITY_CRIME_NOTE = 'Tulsa citywide public crime summaries indicate above-average crime versus many U.S. cities, so ZIP-level estimates matter.'
SOURCE_SET = 'Auction PDF; Tulsa citywide crime summary (NeighborhoodScout Tulsa crime page); ZIP/neighborhood heuristic estimates due limited property-level public access.'

def money_to_float(v):
    try:
        return float(v.replace(',', '').strip())
    except Exception:
        return None

def xml_col(n):
    s=''
    while n:
        n, rem = divmod(n-1, 26)
        s = chr(65+rem) + s
    return s

def shared_strings(values):
    unique=[]; index={}
    for v in values:
        if v not in index:
            index[v]=len(unique); unique.append(v)
    parts=['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="%d" uniqueCount="%d">' % (len(values), len(unique))]
    for s in unique:
        parts.append('<si><t xml:space="preserve">%s</t></si>' % escape(str(s)))
    parts.append('</sst>')
    return '\n'.join(parts), index

def build_xlsx(rows, headers, path):
    all_strings=[]
    for h in headers: all_strings.append(h)
    for row in rows:
        for h in headers:
            v=row.get(h, '')
            if not isinstance(v, (int,float)): all_strings.append(str(v))
    sst, sindex = shared_strings(all_strings)
    xml=['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
         '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
         '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>',
         '<sheetData>']
    xml.append('<row r="1">')
    for c,h in enumerate(headers, start=1):
        xml.append(f'<c r="{xml_col(c)}1" t="s" s="1"><v>{sindex[h]}</v></c>')
    xml.append('</row>')
    for r_idx,row in enumerate(rows, start=2):
        style = {'Good':'3','Mid':'4','Bad':'5'}.get(row['Investment category'], '0')
        xml.append(f'<row r="{r_idx}" s="{style}">')
        for c,h in enumerate(headers, start=1):
            ref=f'{xml_col(c)}{r_idx}'
            v=row.get(h, '')
            if isinstance(v, (int,float)):
                num_style = '2' if h == 'Bid cost' else style
                xml.append(f'<c r="{ref}" s="{num_style}"><v>{v}</v></c>')
            else:
                xml.append(f'<c r="{ref}" t="s" s="{style}"><v>{sindex[str(v)]}</v></c>')
        xml.append('</row>')
    xml.append('</sheetData>')
    end_col=xml_col(len(headers))
    xml.append(f'<autoFilter ref="A1:{end_col}{len(rows)+1}"/>')
    cols=''.join([f'<col min="{i}" max="{i}" width="20" customWidth="1"/>' for i in range(1, len(headers)+1)])
    xml.append(f'<cols>{cols}</cols>')
    xml.append('</worksheet>')
    sheet_xml='\n'.join(xml)
    styles='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="5"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFC6EFCE"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFEB9C"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFC7CE"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<numFmts count="1"><numFmt numFmtId="164" formatCode="$#,##0.00"/></numFmts>
<cellXfs count="6"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="0" fontId="0" fillId="2" borderId="0" xfId="0" applyFill="1"/><xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/><xf numFmtId="0" fontId="0" fillId="4" borderId="0" xfId="0" applyFill="1"/></cellXfs>
</styleSheet>'''
    content_types='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>'''
    rels='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>'''
    wb='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Investment Ranked" sheetId="1" r:id="rId1"/></sheets></workbook>'''
    wb_rels='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>'''
    core='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Investment Ranked Properties</dc:title></cp:coreProperties>'''
    app='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>OpenClaw</Application></Properties>'''
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', rels)
        z.writestr('xl/workbook.xml', wb)
        z.writestr('xl/_rels/workbook.xml.rels', wb_rels)
        z.writestr('xl/worksheets/sheet1.xml', sheet_xml)
        z.writestr('xl/styles.xml', styles)
        z.writestr('xl/sharedStrings.xml', sst)
        z.writestr('docProps/core.xml', core)
        z.writestr('docProps/app.xml', app)

def classify(row):
    bid = money_to_float(row['minimum_bid'])
    if bid is None or bid < MIN_BID or bid > MAX_BID or not 'R' == row['property_type'].strip().split()[0]:
        return None
    zip_code = row['zip_code'].strip()
    addr = row['address'].strip()
    low_conf = addr == 'ADDRESS UNKNOWN' or not zip_code
    crime_label, crime_score, crime_note = ZIP_SAFETY.get(zip_code, ('Unknown', 4, 'No ZIP-specific public estimate was verified.'))
    value_est, value_score = ZIP_VALUES.get(zip_code, ('Unknown', 4))
    growth_label, growth_score, growth_note = ZIP_GROWTH.get(zip_code, ('Unknown', 4, 'No ZIP-specific growth estimate was verified.'))
    price_score = 8 if bid <= 4000 else 7 if bid <= 5000 else 6 if bid <= 6500 else 5
    clarity_score = 3 if low_conf else 7 if zip_code else 5
    total = round(price_score*0.20 + value_score*0.25 + crime_score*0.20 + growth_score*0.25 + clarity_score*0.10)
    if total >= 8:
        cat, color, rec = 'Good', 'Green', 'Bid'
    elif total >= 5:
        cat, color, rec = 'Mid', 'Yellow', 'Watch'
    else:
        cat, color, rec = 'Bad', 'Red', 'Avoid'
    if low_conf and cat == 'Good':
        cat, color, rec, total = 'Mid', 'Yellow', 'Watch', min(total, 7)
    risks=[]
    if crime_label == 'High': risks.append('Higher crime-risk area estimate')
    if value_est in ('Unknown', '$40k-$90k estimate', '$45k-$95k estimate'): risks.append('Weak or low surrounding value signal')
    if low_conf: risks.append('Address incomplete or low-confidence match')
    if row['property_type'].strip() == 'R': risks.append('Could be vacant lot or unimproved parcel, verify improvements')
    confidence = 'Low' if low_conf or zip_code == '' else 'Medium'
    explanation = f"Bid of ${bid:,.2f} was screened against ZIP-level surrounding value estimates, Tulsa crime context, and neighborhood demand/growth heuristics. {crime_note} {growth_note}".strip()
    return {
        'Property ID / Parcel ID': row['parcel_id'],
        'Address': addr,
        'ZIP code': zip_code or 'Unknown',
        'Bid cost': bid,
        'Estimated surrounding property value': value_est,
        'Crime risk: Low / Medium / High': crime_label,
        'Neighborhood investment potential: Low / Medium / High': growth_label,
        'Investment score: 1–10': total,
        'Investment category': cat,
        'Color status': color,
        'Explanation of rating': explanation,
        'Key risks': '; '.join(risks) if risks else 'None identified from limited public screening data',
        'Data confidence: High / Medium / Low': confidence,
        'Sources used / links researched': SOURCE_SET,
        'Recommendation: Bid / Watch / Avoid': rec,
    }

def main():
    seen=set(); rows=[]
    with open(IN_CSV, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['parcel_id'] in seen:
                continue
            seen.add(row['parcel_id'])
            c = classify(row)
            if c:
                rows.append(c)
    order = {'Good':0,'Mid':1,'Bad':2}
    rows.sort(key=lambda r: (order[r['Investment category']], -r['Investment score: 1–10'], r['Bid cost']))
    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    build_xlsx(rows, list(rows[0].keys()), OUT_XLSX)
    print(f'wrote {len(rows)} ranked properties to {OUT_XLSX}')

if __name__ == '__main__':
    main()
