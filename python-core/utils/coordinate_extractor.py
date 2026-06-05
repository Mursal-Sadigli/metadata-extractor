"""
Mətn, URL və binary-dən koordinat, ünvan və yer adı çıxarışı.
"""

import re
from typing import List, Dict, Any, Optional, Tuple

# Decimal: 40.4093, 49.8672 | 40.4093 49.8672
DECIMAL_PAIR = re.compile(
    r'(-?\d{1,3}\.\d{4,})\s*[,;\s|]+\s*(-?\d{1,3}\.\d{4,})',
)
# DMS: 40°23'45" N
DMS_PATTERN = re.compile(
    r'(\d{1,3})\s*°\s*(\d{1,2})\s*[\'′]?\s*(\d{1,2}(?:\.\d+)?)\s*[\"″]?\s*([NSEWnsew])',
    re.I,
)
# DMS cüt: 40°23'45"N 49°50'12"E
DMS_PAIR = re.compile(
    r'(\d{1,3})\s*°\s*(\d{1,2})\s*[\'′]?\s*(\d{1,2}(?:\.\d+)?)\s*[\"″]?\s*([NS])\s*'
    r'[,;\s]+\s*'
    r'(\d{1,3})\s*°\s*(\d{1,2})\s*[\'′]?\s*(\d{1,2}(?:\.\d+)?)\s*[\"″]?\s*([EW])',
    re.I,
)
# Google / OSM / Apple map URL-ləri
MAP_URL_PATTERNS = [
    re.compile(r'[@=](-?\d+\.\d{4,})[,\s]+(-?\d+\.\d{4,})', re.I),
    re.compile(r'[?&]q=(-?\d+\.\d{4,})[,\s+]+(-?\d+\.\d{4,})', re.I),
    re.compile(r'[?&]ll=(-?\d+\.\d{4,})[,\s+]+(-?\d+\.\d{4,})', re.I),
    re.compile(r'geo:(-?\d+\.\d{4,})[,\s]*(-?\d+\.\d{4,})', re.I),
]
PLUS_CODE = re.compile(r'\b([23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,3})\b')
POSTAL_AZ = re.compile(r'\b(AZ\s*)?(\d{4})\b', re.I)

PLACE_HINT_WORDS = re.compile(
    r'\b(küçə|kucə|küçəsi|küç\.|street|st\.|avenue|ave\.|bulvar|prospekt|'
    r'mahalle|mahallesi|şəhər|seher|city|rayon|district|ünvan|unvan|address|'
    r'metro|m\.|məh\.|məhəllə|kənd|qəsəbə|vilayət|ilçe|ilçesi|oblast|'
    r'проспект|улица|ул\.|город|район|пер\.|переулок)\b',
    re.I,
)

try:
    from data.places_gazetteer import GAZETTEER
    KNOWN_PLACES = {k: (v[0], v[1], v[2]) for k, v in GAZETTEER.items()}
except ImportError:
    KNOWN_PLACES = {
        'bakı': (40.4093, 49.8672, 'Bakı, Azərbaycan'),
        'baku': (40.4093, 49.8672, 'Bakı, Azərbaycan'),
    }

PHONE_REGION = re.compile(r'(\+994|\+90|\+7|\+380|\+49|\+44|\+1)(\d{2,})')


def dms_to_decimal(deg: float, minutes: float, seconds: float, ref: str) -> Optional[float]:
    try:
        decimal = float(deg) + float(minutes) / 60.0 + float(seconds) / 3600.0
        if ref.upper() in ('S', 'W'):
            decimal = -decimal
        return round(decimal, 6)
    except (TypeError, ValueError):
        return None


def _valid_lat_lon(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180 and (abs(lat) > 0.0001 or abs(lon) > 0.0001)


def _coord_hit(lat: float, lon: float, fmt: str, raw: str, confidence: float = 0.65) -> Dict[str, Any]:
    return {
        'latitude': lat,
        'longitude': lon,
        'format': fmt,
        'raw': raw[:200],
        'confidence': confidence,
    }


def extract_coordinates_from_text(text: str) -> List[Dict[str, Any]]:
    """Mətndən bütün koordinat formatlarını çıxarır."""
    if not text or len(text.strip()) < 3:
        return []

    found: List[Dict[str, Any]] = []
    seen: set = set()

    def add(lat, lon, fmt, raw, conf=0.65):
        if lat is None or lon is None or not _valid_lat_lon(lat, lon):
            return
        key = (round(lat, 5), round(lon, 5), fmt)
        if key in seen:
            return
        seen.add(key)
        found.append(_coord_hit(lat, lon, fmt, raw, conf))

    for m in DMS_PAIR.finditer(text):
        lat = dms_to_decimal(m.group(1), m.group(2), m.group(3), m.group(4))
        lon = dms_to_decimal(m.group(5), m.group(6), m.group(7), m.group(8))
        add(lat, lon, 'dms_pair', m.group(0), 0.72)

    dms_parts = list(DMS_PATTERN.finditer(text))
    i = 0
    while i < len(dms_parts) - 1:
        m1, m2 = dms_parts[i], dms_parts[i + 1]
        if m1.group(4).upper() in ('N', 'S') and m2.group(4).upper() in ('E', 'W'):
            lat = dms_to_decimal(m1.group(1), m1.group(2), m1.group(3), m1.group(4))
            lon = dms_to_decimal(m2.group(1), m2.group(2), m2.group(3), m2.group(4))
            add(lat, lon, 'dms_sequential', f'{m1.group(0)} {m2.group(0)}', 0.7)
            i += 2
        else:
            i += 1

    for m in DECIMAL_PAIR.finditer(text):
        add(float(m.group(1)), float(m.group(2)), 'decimal', m.group(0), 0.68)

    for pat in MAP_URL_PATTERNS:
        for m in pat.finditer(text):
            add(float(m.group(1)), float(m.group(2)), 'map_url', m.group(0), 0.75)

    for m in PLUS_CODE.finditer(text):
        found.append({
            'format': 'plus_code',
            'raw': m.group(1),
            'latitude': None,
            'longitude': None,
            'confidence': 0.4,
            'note': 'Plus Code — geocoding üçün ayrıca sorğu lazımdır',
        })

    return found


def extract_address_queries(texts: List[str], max_queries: int = 15) -> List[Dict[str, Any]]:
    """Geocoding üçün ünvan/yer sorğuları."""
    queries = []
    seen = set()

    for text in texts:
        if not text or len(str(text).strip()) < 4:
            continue
        text = str(text).strip()

        for m in DECIMAL_PAIR.finditer(text):
            key = m.group(0)
            if key not in seen:
                seen.add(key)
                queries.append({
                    'type': 'coord_pair',
                    'query': key,
                    'latitude': float(m.group(1)),
                    'longitude': float(m.group(2)),
                })

        if PLACE_HINT_WORDS.search(text) or ',' in text or re.search(r'\d{1,4}\s*(?:küç|street|st\.|bulvar)', text, re.I):
            clean = re.sub(r'[^\w\s,.\-əğıöüşçƏĞİÖÜŞÇа-яА-ЯёЁ]', ' ', text)
            clean = re.sub(r'\s+', ' ', clean).strip()
            if len(clean) >= 5 and clean.lower() not in seen:
                seen.add(clean.lower())
                queries.append({'type': 'address', 'query': clean})

        for m in POSTAL_AZ.finditer(text):
            q = f'Azərbaycan {m.group(2)}'
            if q.lower() not in seen:
                seen.add(q.lower())
                queries.append({'type': 'postal', 'query': q})

        lower = text.lower()
        for key, (lat, lon, label) in KNOWN_PLACES.items():
            if re.search(rf'\b{re.escape(key)}\b', lower):
                pk = f'place:{key}'
                if pk not in seen:
                    seen.add(pk)
                    queries.append({
                        'type': 'known_place',
                        'query': label,
                        'latitude': lat,
                        'longitude': lon,
                        'place_key': key,
                    })

    return queries[:max_queries]


def extract_map_links(text: str) -> List[str]:
    """Xəritə URL-ləri."""
    if not text:
        return []
    urls = re.findall(
        r'https?://(?:www\.)?(?:maps\.google\.com|google\.com/maps|'
        r'openstreetmap\.org|www\.openstreetmap\.org|maps\.apple\.com)[^\s\)\]\"\'<>]+',
        text,
        re.I,
    )
    return list(dict.fromkeys(urls))[:10]


def scan_binary_for_coordinates(data: bytes, max_hits: int = 8) -> List[Dict[str, Any]]:
    """Fayl binary-sindən koordinat və URL axtarışı."""
    try:
        text = data.decode('utf-8', errors='ignore')
    except Exception:
        return []
    coords = extract_coordinates_from_text(text)
    links = extract_map_links(text)
    for url in links:
        for c in extract_coordinates_from_text(url):
            if c not in coords:
                coords.append(c)
    return coords[:max_hits]


def collect_text_sources(existing_result: Optional[dict] = None) -> List[str]:
    """Metadata sahələrindən mətn toplama."""
    texts = []
    if not existing_result:
        return texts
    if existing_result.get('description'):
        texts.extend(existing_result['description'].values())
    raw = existing_result.get('raw_tags') or {}
    for key in (
        'Image ImageDescription', 'EXIF UserComment', 'Image XPComment',
        'EXIF GPSProcessingMethod', 'GPS GPSAreaInformation',
    ):
        if raw.get(key):
            texts.append(str(raw[key]))
    return texts
