"""
Super geoparsing mühərriki — entity çıxarışı, çoxformat koordinat, ağıllı geocoding strategiyaları, skor birləşdirmə.
"""

import math
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

from data.places_gazetteer import GAZETTEER, COUNTRY_ALIASES
from utils.coordinate_extractor import (
    extract_coordinates_from_text,
    extract_address_queries,
    extract_map_links,
    dms_to_decimal,
    DECIMAL_PAIR,
    PLACE_HINT_WORDS,
)

# NMEA $GPGGA / $GPRMC
NMEA_GGA = re.compile(
    r'\$GPGGA,[^,]*,(\d{2})(\d{2}\.?\d*),([NS]),(\d{3})(\d{2}\.?\d*),([EW])',
    re.I,
)
NMEA_RMC = re.compile(
    r'\$GPRMC,[^,]*,[^,]*,([AV]),(\d{2})(\d{2}\.?\d*),([NS]),(\d{3})(\d{2}\.?\d*),([EW])',
    re.I,
)
# Decimal degrees minutes: 40° 26.767' N
DDM_PATTERN = re.compile(
    r'(\d{1,3})\s*°\s*(\d{1,2}(?:\.\d+)?)\s*[\'′]\s*([NSEW])',
    re.I,
)
# Lat lon with N/E suffix: 40.1234N 49.5678E
SUFFIX_PAIR = re.compile(
    r'(-?\d{1,3}\.\d{4,})\s*([NS])\s*[,;\s]+\s*(-?\d{1,3}\.\d{4,})\s*([EW])',
    re.I,
)
# UTM təxmini (Zone Easting Northing)
UTM_PATTERN = re.compile(
    r'\b(\d{1,2})\s*([C-X])\s+(\d{5,7})\s+(\d{5,8})\b',
    re.I,
)
# Ünvan strukturu: №5, m.28, AZ1000
STREET_NUM = re.compile(
    r'(?:№|#|No\.?)\s*(\d+[A-Za-z]?)|\b(\d{1,4})\s*(?:küç|kucə|street|st\.|bulvar|prospekt)\b',
    re.I,
)
LANDMARK_HINTS = re.compile(
    r'\b(hava\s*limanı|airport|aeroport|metro|məscid|mosque|xəstəxana|hospital|'
    r'universitet|university|mall|park|stadium|körpü|bridge|liman|port)\b',
    re.I,
)

SOURCE_WEIGHTS = {
    'thumbnail_exif': 0.95,
    'xmp_metadata': 0.88,
    'carved_metadata': 0.82,
    'file_carving_ml': 0.84,
    'text_map_url': 0.85,
    'text_dms_pair': 0.8,
    'text_nmea': 0.85,
    'text_decimal': 0.75,
    'ocr_coordinates': 0.72,
    'nominatim_structured': 0.7,
    'nominatim_geocode': 0.65,
    'known_place': 0.5,
    'gazetteer_entity': 0.55,
    'binary_scan': 0.58,
    'fusion_boost': 0.0,
}


def _nmea_to_decimal(dm: str, hemi: str, is_lat: bool) -> Optional[float]:
    try:
        dm = dm.replace('.', '')
        if is_lat:
            deg = int(dm[:2])
            minutes = float(dm[2:])
        else:
            deg = int(dm[:3])
            minutes = float(dm[3:])
        dec = deg + minutes / 60.0
        if hemi.upper() in ('S', 'W'):
            dec = -dec
        return round(dec, 6)
    except (ValueError, IndexError):
        return None


def extract_extended_coordinates(text: str) -> List[Dict[str, Any]]:
    """coordinate_extractor + NMEA, DDM, suffix, UTM qeydi."""
    found = extract_coordinates_from_text(text)
    seen = {(round(c['latitude'], 5), round(c['longitude'], 5)) for c in found if c.get('latitude') is not None}

    def add(lat, lon, fmt, raw, conf):
        if lat is None or lon is None:
            return
        key = (round(lat, 5), round(lon, 5))
        if key in seen:
            return
        seen.add(key)
        found.append({
            'latitude': lat, 'longitude': lon, 'format': fmt,
            'raw': raw[:200], 'confidence': conf,
        })

    for m in NMEA_GGA.finditer(text):
        lat = _nmea_to_decimal(m.group(2), m.group(3), True)
        lon = _nmea_to_decimal(m.group(4), m.group(5), False)
        add(lat, lon, 'nmea_gpgga', m.group(0), 0.88)

    for m in NMEA_RMC.finditer(text):
        if m.group(1).upper() != 'A':
            continue
        lat = _nmea_to_decimal(m.group(2), m.group(3), True)
        lon = _nmea_to_decimal(m.group(4), m.group(5), False)
        add(lat, lon, 'nmea_gprmc', m.group(0), 0.86)

    ddm = list(DDM_PATTERN.finditer(text))
    i = 0
    while i < len(ddm) - 1:
        m1, m2 = ddm[i], ddm[i + 1]
        if m1.group(3).upper() in ('N', 'S') and m2.group(3).upper() in ('E', 'W'):
            lat = dms_to_decimal(m1.group(1), m1.group(2), 0, m1.group(3))
            lon = dms_to_decimal(m2.group(1), m2.group(2), 0, m2.group(3))
            add(lat, lon, 'ddm', f'{m1.group(0)} {m2.group(0)}', 0.78)
            i += 2
        else:
            i += 1

    for m in SUFFIX_PAIR.finditer(text):
        lat = float(m.group(1))
        if m.group(2).upper() == 'S':
            lat = -lat
        lon = float(m.group(3))
        if m.group(4).upper() == 'W':
            lon = -lon
        add(lat, lon, 'suffix_ne', m.group(0), 0.8)

    for m in UTM_PATTERN.finditer(text):
        found.append({
            'format': 'utm',
            'raw': m.group(0),
            'latitude': None,
            'longitude': None,
            'confidence': 0.35,
            'note': f'UTM zona {m.group(1)}{m.group(2).upper()} — Nominatim ilə axtarılacaq',
            'utm_query': m.group(0),
        })

    return found


def detect_country_bias(texts: List[str], regional_hints: List[dict]) -> Optional[str]:
    combined = ' '.join(texts).lower()
    for alias, cc in COUNTRY_ALIASES.items():
        if re.search(rf'\b{re.escape(alias)}\b', combined, re.I):
            return cc
    for h in regional_hints or []:
        if h.get('type') == 'phone_country_code':
            v = h.get('value', '')
            if v == 'AZ':
                return 'az'
            if v == 'TR':
                return 'tr'
    return None


def extract_geographic_entities(texts: List[str]) -> List[Dict[str, Any]]:
    """Geoparsing: şəhər, ölkə, landmark, ünvan sətri entity-ləri."""
    entities = []
    seen = set()

    for text in texts:
        if not text:
            continue
        lower = str(text).lower()

        for key, (lat, lon, label, cc) in GAZETTEER.items():
            if len(key) < 3 and key not in ('az',):
                continue
            if re.search(rf'\b{re.escape(key)}\b', lower):
                ek = f'place:{key}'
                if ek not in seen:
                    seen.add(ek)
                    entities.append({
                        'entity_type': 'place',
                        'value': label,
                        'place_key': key,
                        'latitude': lat,
                        'longitude': lon,
                        'country_code': cc,
                        'confidence': 0.72 if len(key) > 5 else 0.55,
                    })

        for alias, cc in COUNTRY_ALIASES.items():
            if re.search(rf'\b{re.escape(alias)}\b', lower, re.I):
                ek = f'country:{cc}'
                if ek not in seen:
                    seen.add(ek)
                    entities.append({
                        'entity_type': 'country',
                        'value': alias,
                        'country_code': cc,
                        'confidence': 0.6,
                    })

        lm_match = LANDMARK_HINTS.search(text)
        if lm_match:
            lm = lm_match.group(0)
            snippet = text[max(0, lm_match.start() - 40):lm_match.end() + 40]
            ek = f'landmark:{lm.lower()}'
            if ek not in seen:
                seen.add(ek)
                entities.append({
                    'entity_type': 'landmark',
                    'value': lm,
                    'context': snippet.strip()[:120],
                    'confidence': 0.65,
                })

        if PLACE_HINT_WORDS.search(text) or ',' in text or STREET_NUM.search(text):
            clean = re.sub(r'[^\w\s,.\-əğıöüşçƏĞİÖÜŞÇа-яА-ЯёЁ°\'#№]', ' ', text)
            clean = re.sub(r'\s+', ' ', clean).strip()
            if len(clean) >= 8:
                ek = f'addr:{clean[:60]}'
                if ek not in seen:
                    seen.add(ek)
                    structured = _parse_address_structure(clean)
                    entities.append({
                        'entity_type': 'address',
                        'value': clean,
                        'structured': structured,
                        'confidence': 0.68 if structured.get('street') else 0.55,
                    })

    entities.sort(key=lambda x: -x.get('confidence', 0))
    return entities[:35]


def _parse_address_structure(line: str) -> Dict[str, Optional[str]]:
    """Sadə ünvan komponentləri."""
    parts = [p.strip() for p in line.split(',') if p.strip()]
    out = {'street': None, 'city': None, 'country': None, 'postal': None}
    for p in parts:
        pl = p.lower()
        for alias, cc in COUNTRY_ALIASES.items():
            if alias in pl:
                out['country'] = p
        for key in GAZETTEER:
            if re.search(rf'\b{re.escape(key)}\b', pl):
                out['city'] = GAZETTEER[key][2]
        if re.match(r'^AZ?\s*\d{4}$', p, re.I) or re.match(r'^\d{4,6}$', p):
            out['postal'] = p
        if PLACE_HINT_WORDS.search(p) or STREET_NUM.search(p):
            out['street'] = p
    if parts and not out['street']:
        out['street'] = parts[0]
    if len(parts) >= 2 and not out['city']:
        out['city'] = parts[-2] if len(parts) > 2 else parts[-1]
    return out


def build_geocode_strategies(
    texts: List[str],
    entities: List[dict],
    country_bias: Optional[str],
    max_strategies: int = 14,
) -> List[Dict[str, Any]]:
    """Nominatim üçün ağıllı sorğu strategiyaları."""
    strategies = []
    seen_q = set()

    def add(query, stype, cc=None, structured=None, priority=5):
        qn = query.lower().strip()[:200]
        if not qn or qn in seen_q or len(qn) < 4:
            return
        seen_q.add(qn)
        strategies.append({
            'query': query.strip()[:200],
            'strategy': stype,
            'country_codes': cc or country_bias,
            'structured': structured,
            'priority': priority,
        })

    for ent in entities:
        if ent['entity_type'] == 'address':
            s = ent.get('structured') or {}
            if s.get('street') and s.get('city'):
                add(f"{s['street']}, {s['city']}", 'structured_full', country_bias, s, 9)
            add(ent['value'], 'address_entity', country_bias, s, 8)
        elif ent['entity_type'] == 'landmark' and ent.get('context'):
            add(ent['context'], 'landmark_context', country_bias, None, 7)
        elif ent['entity_type'] == 'place':
            add(ent['value'], 'gazetteer_place', ent.get('country_code') or country_bias, None, 6)

    for text in texts:
        for line in re.split(r'[\n;|]+', text):
            line = line.strip()
            if len(line) < 6:
                continue
            if PLACE_HINT_WORDS.search(line) or ',' in line:
                add(line, 'line_split', country_bias, _parse_address_structure(line), 5)
            for m in re.finditer(r'\b([23456789CFGHJMPQRVWX]{4,8}\+[23456789CFGHJMPQRVWX]{2,})\b', line):
                add(m.group(1), 'plus_code', country_bias, None, 8)

    for item in extract_address_queries(texts, max_queries=12):
        add(item.get('query', ''), f"legacy_{item.get('type')}", country_bias, None, 4)

    strategies.sort(key=lambda x: -x['priority'])
    return strategies[:max_strategies]


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def cluster_candidates(candidates: List[dict], km_threshold: float = 2.5) -> List[dict]:
    """Yaxın nöqtələri klasterləşdirir, ən yüksək skoru saxlayır."""
    if not candidates:
        return []
    sorted_c = sorted(candidates, key=lambda x: -x.get('fusion_score', x.get('confidence', 0)))
    kept = []
    for c in sorted_c:
        lat, lon = c.get('latitude'), c.get('longitude')
        if lat is None:
            continue
        merge = False
        for k in kept:
            if haversine_km(lat, lon, k['latitude'], k['longitude']) < km_threshold:
                merge = True
                k['cluster_size'] = k.get('cluster_size', 1) + 1
                k['also_sources'] = list(dict.fromkeys(
                    (k.get('also_sources') or [k.get('source')]) + [c.get('source')]
                ))
                break
        if not merge:
            c['cluster_size'] = 1
            kept.append(c)
    return kept


def fuse_candidate_scores(candidates: List[dict], country_bias: Optional[str]) -> List[dict]:
    """Çoxlu mənbəni vahid etibar skoruna çevirir."""
    for c in candidates:
        src = c.get('source', 'unknown')
        base = c.get('confidence', 0.5)
        weight = SOURCE_WEIGHTS.get(src, 0.55)
        if src.startswith('text_'):
            weight = max(weight, SOURCE_WEIGHTS.get('text_decimal', 0.7))
        fusion = min(base * 0.5 + weight * 0.5, 0.98)
        if c.get('cluster_size', 1) > 1:
            fusion = min(fusion + 0.05 * (c['cluster_size'] - 1), 0.95)
        if country_bias and c.get('address', {}).get('country_code') == country_bias:
            fusion = min(fusion + 0.04, 0.96)
        c['fusion_score'] = round(fusion, 3)
        c['confidence'] = round(fusion, 2)
    return sorted(candidates, key=lambda x: -x.get('fusion_score', 0))


def full_geoparse_from_texts(
    texts: List[str],
    regional_hints: Optional[List[dict]] = None,
) -> Dict[str, Any]:
    """Mətnlər üçün tam geoparsing paketi."""
    country_bias = detect_country_bias(texts, regional_hints or [])
    all_coords = []
    seen_c = set()

    for text in texts:
        for c in extract_extended_coordinates(text):
            if c.get('latitude') is not None:
                key = (round(c['latitude'], 5), round(c['longitude'], 5))
                if key not in seen_c:
                    seen_c.add(key)
                    all_coords.append(c)
            else:
                all_coords.append(c)

    entities = extract_geographic_entities(texts)
    strategies = build_geocode_strategies(texts, entities, country_bias)
    place_queries = extract_address_queries(texts, max_queries=22)
    map_links = []
    for t in texts:
        map_links.extend(extract_map_links(t))
    map_links = list(dict.fromkeys(map_links))[:15]

    return {
        'country_bias': country_bias,
        'geographic_entities': entities,
        'extracted_coordinates': all_coords[:30],
        'geocode_strategies': strategies,
        'place_queries': place_queries,
        'map_links': map_links,
    }
