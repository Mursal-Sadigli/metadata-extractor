"""
Language Analyzer

langdetect vasitəsilə verilmiş mətndən dil aşkarlayır.
"""

from langdetect import detect, detect_langs, DetectorFactory

# Deterministik nəticə üçün seed təyin edirik
DetectorFactory.seed = 0

LANGUAGE_NAMES = {
    'az': 'Azerbaijani', 'en': 'English', 'tr': 'Turkish', 'ru': 'Russian',
    'de': 'German', 'fr': 'French', 'es': 'Spanish', 'ar': 'Arabic',
    'zh-cn': 'Chinese (Simplified)', 'zh-tw': 'Chinese (Traditional)', 
    'ja': 'Japanese', 'ko': 'Korean', 'it': 'Italian', 'pt': 'Portuguese', 
    'nl': 'Dutch', 'pl': 'Polish', 'uk': 'Ukrainian', 'fa': 'Persian'
}

def analyze_language(text):
    """
    Mətndəki dili aşkar et.
    """
    try:
        code = detect(text)
        langs = detect_langs(text)
        confidence = 0.0
        if langs:
            confidence = langs[0].prob
            
        return {
            'language': code,
            'confidence': round(confidence, 4),
            'language_name': LANGUAGE_NAMES.get(code, code)
        }
    except Exception as e:
        print(f"  [!] Dil analizi xətası: {e}", file=sys.stderr)
        return None

def analyze_multiple_texts(texts_dict):
    """
    Birdən çox mənbədən gələn mətnləri analiz et.
    """
    results = {}
    for source, text in texts_dict.items():
        if not text or not isinstance(text, str): 
            continue
        if len(text.strip()) < 3: 
            continue
            
        res = analyze_language(text)
        if res:
            results[source] = res
            
    return results if results else None
