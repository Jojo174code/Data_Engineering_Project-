import csv, zipfile, html, re
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
IN_CSV = ROOT / 'cleaned_data' / 'cleaned_auction_properties.csv'
OUT_XLSX = ROOT / 'output_excel' / 'filtered_properties_3000_to_8000.xlsx'

MIN_BID = 3000
MAX_BID = 8000

residential_ok = {'R', 'R IMP', 'R HS', 'R HS IMP', 'R IMP HS', 'R MH', 'R MH IMP'}

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
            index[v]=len(unique)
            unique.append(v)
    parts=['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="%d" uniqueCount="%d">' % (len(values), len(unique))]
    for s in unique:
        parts.append('<si><t xml:space="preserve">%s</t></si>' % escape(str(s)))
    parts.append('</sst>')
    return '\n'.join(parts), index

def make_sheet(rows, headers):
    all_strings=[]
    for h in headers:
        all_strings.append(h)
    for row in rows:
        for h in headers:
            v=row.get(h, '')
            if not isinstance(v, (int, float)):
                all_strings.append(str(v))
    sst, sindex = shared_strings(all_strings)
    xml=['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
         '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
         '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>',
         '<sheetData>']
    # header row
    xml.append('<row r="1">')
    for c,h in enumerate(headers, start=1):
        ref=f'{xml_col(c)}1'
        xml.append(f'<c r="{ref}" t="s" s="1"><v>{sindex[h]}</v></c>')
    xml.append('</row>')
    for r_idx,row in enumerate(rows, start=2):
        xml.append(f'<row r="{r_idx}">')
        for c,h in enumerate(headers, start=1):
            ref=f'{xml_col(c)}{r_idx}'
            v=row.get(h, '')
            if isinstance(v, (int,float)):
                style = '2' if 'Bid cost' in h else '0'
                xml.append(f'<c r="{ref}" s="{style}"><v>{v}</v></c>')
            else:
                xml.append(f'<c r="{ref}" t="s"><v>{sindex[str(v)]}</v></c>')
        xml.append('</row>')
    xml.append('</sheetData>')
    end_col=xml_col(len(headers))
    xml.append(f'<autoFilter ref="A1:{end_col}{len(rows)+1}"/>')
    cols=''.join([f'<col min="{i}" max="{i}" width="18" customWidth="1"/>' for i in range(1, len(headers)+1)])
    xml.append(f'<cols>{cols}</cols>')
    xml.append('</worksheet>')
    return '\n'.join(xml), sst

def write_xlsx(path, rows, headers):
    sheet_xml, sst_xml = make_sheet(rows, headers)
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''
    wb = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Filtered Properties" sheetId="1" r:id="rId1"/></sheets></workbook>'''
    wb_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>'''
    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>
<numFmts count="1"><numFmt numFmtId="164" formatCode="$#,##0.00"/></numFmts>
</styleSheet>'''
    core = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>Filtered Tulsa Auction Properties</dc:title></cp:coreProperties>'''
    app = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>OpenClaw</Application></Properties>'''
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', rels)
        z.writestr('xl/workbook.xml', wb)
        z.writestr('xl/_rels/workbook.xml.rels', wb_rels)
        z.writestr('xl/worksheets/sheet1.xml', sheet_xml)
        z.writestr('xl/styles.xml', styles)
        z.writestr('xl/sharedStrings.xml', sst_xml)
        z.writestr('docProps/core.xml', core)
        z.writestr('docProps/app.xml', app)

def main():
    rows=[]
    seen=set()
    with open(IN_CSV, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            bid = money_to_float(r['minimum_bid'])
            if bid is None or bid < MIN_BID or bid > MAX_BID or abs(bid - 100.0) < 0.001:
                continue
            ptype = ' '.join(r['property_type'].split())
            if not ptype.startswith('R'):
                continue
            if r['parcel_id'] in seen:
                continue
            seen.add(r['parcel_id'])
            rows.append({
                'Property ID / Parcel ID': r['parcel_id'],
                'Owner name': r['owner_name'] or 'Unknown',
                'Address': r['address'],
                'City': r['city'],
                'ZIP code': r['zip_code'],
                'Legal description': r['legal_description'],
                'Bid cost': bid,
                'Property type': ptype,
                'Source notes': r['source_notes'],
                'Auction list page/source location': f"PDF page {r['page_number']}"
            })
    rows.sort(key=lambda x: x['Bid cost'])
    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    write_xlsx(OUT_XLSX, rows, list(rows[0].keys()))
    print(f'wrote {len(rows)} filtered properties to {OUT_XLSX}')

if __name__ == '__main__':
    main()
