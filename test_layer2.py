import urllib.request
import json
import ssl
import time
import urllib.error

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request('https://datasets-server.huggingface.co/rows?dataset=rumourscape/tenders&config=default&split=train&offset=0&length=100')
req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
resp = urllib.request.urlopen(req, context=ctx)
data = json.loads(resp.read().decode('utf-8'))

rows = [r['row'] for r in data['rows']]
with open('data/external/indian_tenders/sample/sample_100.json', 'w', encoding='utf-8') as f:
    json.dump(rows, f, indent=2)

print(f'Sample size: {len(rows)}')
fields = ['tender_id', 'organisation_name', 'title', 'tender_description', 'tender_type', 'tender_document_url']
for field in fields:
    present = sum(1 for r in rows if r.get(field))
    print(f'Field {field}: {present}/{len(rows)}')

urls = [r['tender_document_url'] for r in rows if r.get('tender_document_url')]
print(f'URLs present: {len(urls)}')

reachable = 0
is_pdf = 0
for url in urls[:20]:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=10, context=ctx)
        if res.status == 200:
            reachable += 1
            header = res.read(10)
            if header.startswith(b'%PDF'):
                is_pdf += 1
        time.sleep(0.5)
    except Exception as e:
        print(f'Failed {url}: {e}')

print(f'URLs reachable (out of {min(20, len(urls))}): {reachable}')
print(f'Actual PDFs: {is_pdf}')

