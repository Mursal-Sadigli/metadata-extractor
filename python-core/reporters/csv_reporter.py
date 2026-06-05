"""
CSV Reporter

Nəticələri Excel və Google Sheets üçün CSV formatında çıxarır.
"""
import pandas as pd
import os
from datetime import datetime

def save_csv_report(results, output_path=None):
    """Bütün analiz nəticələrini tək bir CSV faylında yadda saxla."""
    if not output_path:
        os.makedirs('results', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join('results', f"report_{timestamp}.csv")
        
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    
    rows = []
    for r in results:
        row = {}
        row['Filename'] = r['file_info']['filename']
        row['Type'] = r['type']
        
        # EXIF Dataları
        if r.get('exif'):
            if r['exif'].get('camera'):
                row['Camera Make'] = r['exif']['camera'].get('make', '')
                row['Camera Model'] = r['exif']['camera'].get('model', '')
            if r['exif'].get('settings'):
                row['ISO'] = r['exif']['settings'].get('iso', '')
                row['Aperture'] = r['exif']['settings'].get('aperture', '')
            if r['exif'].get('datetime'):
                row['Date'] = r['exif']['datetime'].get('original', '')
                
        # Lokasiya (GPS)
        if r.get('location'):
            row['Latitude'] = r['location'].get('latitude', '')
            row['Longitude'] = r['location'].get('longitude', '')
            if r['location'].get('address'):
                row['City'] = r['location']['address'].get('city', '')
                row['Country'] = r['location']['address'].get('country_code', '')
                
        # AI Nəticələri
        if r.get('ai'):
            if r['ai'].get('extracted_text'):
                row['Extracted Text'] = " | ".join(r['ai']['extracted_text'])[:200]
                
        # Dil
        if r.get('language'):
            langs = []
            for src, lang_data in r['language'].items():
                name = lang_data.get('language_name', '')
                langs.append(name)
            row['Language'] = ", ".join(langs)
                
        rows.append(row)
        
    df = pd.DataFrame(rows)
    # Excel-də problem olmaması üçün utf-8-sig
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    return output_path
