import re, zlib, csv
from pathlib import Path
from collections import OrderedDict

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / 'auction_lists' / '2026_tulsa_auction_list.pdf'
OUT = ROOT / 'cleaned_data' / 'cleaned_auction_properties.csv'

HEADER_SKIP = {
    'Page','Report generated as of','TR01033','Data created as of 4/27/2026 2:09:04 PM',
    'Land List for 2026 June Resale Auction','Bids will be accepted in minimum increments of $25.',
    'Tulsa County Treasurer','Land','List','Prop.','No.','Parcel','Status','Parcel Number',
    'Legal Description','Subdivision','Property Address','and City','Approx','Square','Footage',
    'C=Commercial','R=Residential','B=Both Comm / Res','A=Agricultural','MH=Mobile Home',
    'HS=Homestead','IMP=Improvements','Minimum','Bid','Approximate','Resale','Costs & Fees',
    'Must Be Paid','In Addition To','Successful Bid','*','Successful','Amount','Notations'
}
parcel_re = re.compile(r'^\d{5}-\d{2}-\d{2}-\d{5}$')
money_re = re.compile(r'^\d{1,3}(?:,\d{3})*\.\d{2}$|^\d+\.\d{2}$')
city_re = re.compile(r'^(CITY OF|TOWN OF|UNINCORPORATED|BROKEN ARROW|SAND SPRINGS|OWASSO|BIXBY|JENKS|SAPULPA|COLLINSVILLE|SKIATOOK)')
zip_re = re.compile(r'\b(74\d{3})\b')

def decode_pdf_string(bs: bytes) -> str:
    out=[]; i=0
    while i < len(bs):
        c=bs[i]
        if c==92:
            i += 1
            if i >= len(bs): break
            c=bs[i]
            mapping={ord('n'):'\n',ord('r'):'\r',ord('t'):'\t',ord('b'):'\b',ord('f'):'\f',ord('('):'(',ord(')'):')',ord('\\'):'\\'}
            if c in mapping:
                out.append(mapping[c])
            elif 48 <= c <= 55:
                octal=bytes([c])
                for _ in range(2):
                    if i+1 < len(bs) and 48 <= bs[i+1] <= 55:
                        i += 1; octal += bytes([bs[i]])
                    else:
                        break
                out.append(chr(int(octal,8)))
            else:
                out.append(chr(c))
        else:
            out.append(chr(c))
        i += 1
    return ''.join(out)

def extract_pages(pdf_bytes: bytes):
    pages=[]
    for m in re.finditer(rb'stream\r?\n', pdf_bytes):
        start=m.end(); end=pdf_bytes.find(b'endstream', start)
        if end == -1:
            continue
        chunk=pdf_bytes[start:end].rstrip(b'\r\n')
        try:
            data=zlib.decompress(chunk)
        except Exception:
            continue
        if b'Land List for 2026 June Resale Auction' not in data and b'Property Address' not in data:
            continue
        texts=[decode_pdf_string(s.group(1)).strip() for s in re.finditer(rb'\((.*?)\)\s*Tj', data, re.S)]
        pages.append(texts)
    return pages

def parse_pages(pages):
    rows=[]
    for page_no, texts in enumerate(pages, start=1):
        lines=[t for t in texts if t and t not in HEADER_SKIP]
        i=0
        while i < len(lines):
            if not lines[i].isdigit() or i+1 >= len(lines) or not parcel_re.match(lines[i+1]):
                i += 1
                continue
            prop_no=lines[i]
            parcel=lines[i+1]
            found=None
            for k in range(i+4, min(len(lines)-4, i+20)):
                if city_re.match(lines[k]) and re.match(r'^[\d,]+$', lines[k+1]) and money_re.match(lines[k+3]) and money_re.match(lines[k+4]):
                    found=k
                    break
            if found is None:
                i += 1
                continue
            middle=lines[i+2:found]
            if len(middle) < 3:
                i += 1
                continue
            legal=' '.join(middle[:-2]).strip()
            subdivision=middle[-2]
            address=middle[-1]
            city=lines[found]
            rows.append({
                'prop_no': prop_no,
                'parcel_id': parcel,
                'owner_name': 'Unknown',
                'legal_description': legal,
                'subdivision': subdivision,
                'address': address,
                'city': city,
                'zip_code': zip_re.search(address + ' ' + city).group(1) if zip_re.search(address + ' ' + city) else '',
                'land_sqft': lines[found+1],
                'property_type': ' '.join(lines[found+2].split()),
                'minimum_bid': lines[found+3],
                'resale_costs_fees': lines[found+4],
                'notes': '',
                'page_number': page_no,
                'source_notes': f'PDF page {page_no}, property #{prop_no}',
            })
            i = found + 5
    uniq=OrderedDict()
    for r in rows:
        uniq.setdefault(r['parcel_id'], r)
    return list(uniq.values())

def main():
    pages = extract_pages(PDF.read_bytes())
    rows = parse_pages(pages)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f'extracted {len(rows)} rows from {len(pages)} pages into {OUT}')

if __name__ == '__main__':
    main()
