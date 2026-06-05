"""
JSON Reporter

Metadata nəticələrini JSON formatında layihə qovluğuna yazır.
"""

import json
import os
from datetime import datetime

def save_single_result(result, output_path=None):
    """
    Tək faylın analiz nəticəsini JSON olaraq saxla.
    """
    if not output_path:
        os.makedirs('results', exist_ok=True)
        filename = result['file_info']['filename']
        output_path = os.path.join('results', f"{filename}_metadata.json")
        
    # Qovluğun mövcud olduğundan əmin ol
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
    return output_path

def save_batch_results(results, output_path=None):
    """
    Çoxlu faylın analiz nəticəsini (batch) JSON olaraq saxla.
    """
    if not output_path:
        os.makedirs('results', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join('results', f"batch_report_{timestamp}.json")
        
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
    return output_path

def print_summary(result):
    """
    Terminala qısa xülasə yaz.
    """
    try:
        filename = result['file_info']['filename']
        file_type = result.get('type', 'unknown')
        print(f"  - {filename} (Tipi: {file_type})")
        
        if result.get('location'):
            address = result['location'].get('address', {})
            if address:
                city = address.get('city', '?')
                country = address.get('country_code', '?')
                print(f"    📍 {city}, {country}")
            else:
                lat = result['location'].get('latitude')
                lon = result['location'].get('longitude')
                print(f"    📍 {lat}, {lon}")
            
        if result.get('language'):
            for src, lang_data in result['language'].items():
                name = lang_data.get('language_name', '?')
                conf = lang_data.get('confidence', 0)
                print(f"    🌐 Dil [{src}]: {name} ({conf*100:.0f}%)")
    except Exception as e:
        pass
