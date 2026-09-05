import pandas as pd
import datetime

try:
    df = pd.read_csv('data/external/layer2_manifest.csv')
    total_selected = len(df)
    total_downloaded = len(df[df['download_status'] == 'success'])
    valid_pdfs = len(df[df['page_count'] > 0])
    text_extractable = len(df[df['extraction_status'] == 'usable'])
    scanned = len(df[df['is_scanned'] == True])
    failed = len(df[df['extraction_status'].str.startswith('failed', na=False)])
    
    avg_pages = df[df['page_count'] > 0]['page_count'].mean()
    avg_chars = df[df['char_count'] > 0]['char_count'].mean()
    
    best = df[df['extraction_status'] == 'usable'].sort_values('char_count', ascending=False).head(10)
    
    print('--- SUMMARY ---')
    print(f'Total selected: {total_selected}')
    print(f'Total downloaded: {total_downloaded}')
    print(f'Valid PDFs: {valid_pdfs}')
    print(f'Text extractable: {text_extractable}')
    print(f'Scanned: {scanned}')
    print(f'Failed: {failed}')
    print(f'Average pages: {avg_pages:.1f}' if pd.notna(avg_pages) else 'Average pages: 0')
    print(f'Average extracted characters: {avg_chars:.1f}' if pd.notna(avg_chars) else 'Average extracted characters: 0')
    print('\nBest 10:')
    for _, row in best.iterrows():
        print(f"{row['document_filename']} (Pages: {row['page_count']}, Chars: {row['char_count']})")
    
    with open('docs/LAYER2_DATASET.md', 'w') as f:
        f.write('# Layer 2 Dataset Documentation\n\n')
        f.write('## Sources\n- National Centre for Polar and Ocean Research (NCAOR)\n- India Post (Attempted)\n\n')
        f.write(f'## Acquisition Date\n{datetime.date.today()}\n\n')
        f.write('## Selection Criteria\nSample of ~80 NCAOR tenders (GeM and conventional) from recent archive pages. Simulated ~20 India Post checks.\n\n')
        f.write(f'## Statistics\n- Number selected: {total_selected}\n- Number downloaded: {total_downloaded}\n- Number valid: {valid_pdfs}\n- Number text-extractable: {text_extractable}\n- Number scanned: {scanned}\n\n')
        f.write('## Categories\nMixed GeM and Conventional tenders.\n\n')
        f.write('## Limitations\n- India Post uses a dynamically rendered SPA that blocks simple scraping.\n- Some NCAOR PDFs are scanned images.\n- GeM URLs may expire or change.\n\n')
        f.write('## Source URLs\n- https://www.ncaor.gov.in/tenders/archive/page:1\n- https://www.indiapost.gov.in/tenders\n\n')
        f.write('## Licensing/Usage Caveats\nThese documents are hosted publicly by the Government of India. They are used here strictly as a local research/testing corpus for hackathon evaluation. Do NOT redistribute these PDFs. No external ground-truth labels are claimed.\n')

except Exception as e:
    print('Error:', e)
