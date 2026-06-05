"""
Super ağıllı GPS / geoparsing — thumbnail, XMP, binary, OCR, entity, Nominatim, fusion.
"""

import os
import re
import sys
import tempfile
from typing import Optional, List, Dict, Any

import exifread

from utils.gps_converter import dms_to_decimal, format_coordinates, decimal_to_dms_display
from utils.coordinate_extractor import collect_text_sources, PHONE_REGION
from analyzers.geo_analyzer import (
    analyze_location,
    nominatim_reverse,
    nominatim_reverse_full,
    nominatim_search_advanced,
)
from analyzers.geoparsing_engine import (
    full_geoparse_from_texts,
    extract_extended_coordinates,
    fuse_candidate_scores,
    cluster_candidates,
)

USER_AGENT = 'MetadataExtractor/2.0 (OSINT geoparsing)'

XMP_GPS_PATTERNS = [
    re.compile(r'<exif:GPSLatitude>([^<]+)</exif:GPSLatitude>', re.I),
    re.compile(r'<exif:GPSLongitude>([^<]+)</exif:GPSLongitude>', re.I),
    re.compile(r'GPSLatitude=["\']?([^"\'>\s]+)', re.I),
    re.compile(r'GPSLongitude=["\']?([^"\'>\s]+)', re.I),
]
COORD_IN_TEXT = re.compile(
    r'(-?\d{1,3}\.\d{4,})\s*[,;\s]\s*(-?\d{1,3}\.\d{4,})',
)


def _candidate(lat, lon, source, confidence, label, detail=None, query=None, fmt=None, raw=None):
    from utils.coordinate_validator import sanitize_coordinate_pair, LOW_TRUST_SOURCES
    fixed = sanitize_coordinate_pair(
        float(lat), float(lon), source=source,
        check_water=source in LOW_TRUST_SOURCES,
    )
    if not fixed.get('accepted'):
        return None
    lat, lon = fixed['latitude'], fixed['longitude']
    loc = format_coordinates(lat, lon)
    if not loc:
        return None
    if fixed.get('lat_lon_swapped'):
        loc['lat_lon_swapped'] = True
    loc['source'] = source
    loc['confidence'] = round(min(max(confidence, 0.0), 1.0), 2)
    loc['label'] = label
    if detail:
        loc['detail'] = detail
    if query:
        loc['query'] = query
    if fmt:
        loc['format'] = fmt
    if raw:
        loc['raw_match'] = raw[:120]
    dms = decimal_to_dms_display(float(lat), float(lon))
    if dms:
        loc['dms'] = dms
    return loc


def _enrich_top_candidates(candidates, limit=5):
    for i, c in enumerate(candidates[:limit]):
        lat, lon = c.get('latitude'), c.get('longitude')
        if lat is None:
            continue
        if not c.get('address'):
            geo = analyze_location(lat, lon)
            if geo:
                c['address'] = geo
        if i < 2 and not c.get('reverse_geocode'):
            full = nominatim_reverse_full(lat, lon, delay=1.05)
            if full:
                c['reverse_geocode'] = full
                c['display_name'] = full.get('display_name')
                if full.get('address'):
                    c['address'] = {**(c.get('address') or {}), **full['address']}


def recover_gps_from_thumbnail(filepath):
    try:
        with open(filepath, 'rb') as f:
            tags = exifread.process_file(f, details=True)
        thumb = tags.get('JPEGThumbnail')
        if not thumb:
            return None
        raw = bytes(thumb) if not isinstance(thumb, bytes) else thumb
        if len(raw) < 100:
            return None
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        try:
            with open(tmp_path, 'rb') as f:
                thumb_tags = exifread.process_file(f, details=False)
            gps_lat = thumb_tags.get('GPS GPSLatitude')
            gps_lat_ref = thumb_tags.get('GPS GPSLatitudeRef')
            gps_lon = thumb_tags.get('GPS GPSLongitude')
            gps_lon_ref = thumb_tags.get('GPS GPSLongitudeRef')
            if not all([gps_lat, gps_lat_ref, gps_lon, gps_lon_ref]):
                return None
            latitude = dms_to_decimal(gps_lat.values, str(gps_lat_ref))
            longitude = dms_to_decimal(gps_lon.values, str(gps_lon_ref))
            if latitude is None or longitude is None:
                return None
            return _candidate(
                latitude, longitude, 'thumbnail_exif', 0.88,
                'Thumbnail EXIF GPS',
                'Messencer EXIF silsə də önizləmədə GPS qala bilər.',
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception as e:
        print(f"  [!] Thumbnail GPS: {e}", file=sys.stderr)
    return None


def scan_xmp_coordinates(filepath):
    try:
        with open(filepath, 'rb') as f:
            raw = f.read(800000)
        text = raw.decode('utf-8', errors='ignore')
        if 'GPS' not in text and 'gps' not in text and 'xmp' not in text.lower():
            return None
        lat_m = XMP_GPS_PATTERNS[0].search(text) or XMP_GPS_PATTERNS[2].search(text)
        lon_m = XMP_GPS_PATTERNS[1].search(text) or XMP_GPS_PATTERNS[3].search(text)
        if lat_m and lon_m:
            try:
                lat = float(lat_m.group(1).replace(',', '.'))
                lon = float(lon_m.group(1).replace(',', '.'))
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return _candidate(lat, lon, 'xmp_metadata', 0.8, 'XMP GPS', 'XMP blokundan.')
            except ValueError:
                pass
        for m in COORD_IN_TEXT.finditer(text):
            lat, lon = float(m.group(1)), float(m.group(2))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return _candidate(lat, lon, 'xmp_metadata', 0.65, 'XMP/Text koordinat', 'Metadata mətnində.')
    except Exception as e:
        print(f"  [!] XMP skanı: {e}", file=sys.stderr)
    return None


def scan_file_binary_coordinates(filepath, max_bytes=1500000):
    hits = []
    try:
        with open(filepath, 'rb') as f:
            data = f.read(max_bytes)
        text = data.decode('utf-8', errors='ignore')
        for item in extract_extended_coordinates(text):
            lat, lon = item.get('latitude'), item.get('longitude')
            if lat is not None and lon is not None:
                c = _candidate(
                    lat, lon, 'binary_scan', item.get('confidence', 0.58),
                    f"Binary: {item.get('format')}",
                    item.get('raw', ''),
                    fmt=item.get('format'),
                    raw=item.get('raw'),
                )
                if c:
                    hits.append(c)
    except Exception as e:
        print(f"  [!] Binary skan: {e}", file=sys.stderr)
    return hits


def collect_ocr_texts(filepath, existing_result=None, run_ocr_if_missing=True):
    texts = list(collect_text_sources(existing_result))

    if existing_result:
        ai = existing_result.get('ai') or {}
        if ai.get('extracted_text'):
            texts.extend(ai['extracted_text'])
            return list(dict.fromkeys(t for t in texts if t and len(str(t).strip()) > 2))

    if not run_ocr_if_missing:
        return list(dict.fromkeys(t for t in texts if t and len(str(t).strip()) > 2))

    try:
        from analyzers.ai_analyzer import analyze_image_ai
        ai = analyze_image_ai(filepath)
        if ai.get('extracted_text'):
            texts.extend(ai['extracted_text'])
    except Exception as e:
        print(f"  [!] OCR geolocation: {e}", file=sys.stderr)

    return list(dict.fromkeys(t for t in texts if t and len(str(t).strip()) > 2))


def infer_region_hints(texts):
    hints = []
    combined = ' '.join(texts)
    if not combined.strip():
        return hints
    try:
        from analyzers.language_analyzer import analyze_language
        lang = analyze_language(combined[:800])
        if lang:
            hints.append({
                'type': 'language',
                'value': lang.get('language_name') or lang.get('language'),
                'confidence': lang.get('confidence'),
            })
    except Exception:
        pass
    for m in PHONE_REGION.finditer(combined):
        cc = m.group(1)
        mapping = {
            '+994': 'AZ', '+90': 'TR', '+7': 'RU/KZ', '+380': 'UA',
            '+49': 'DE', '+44': 'GB', '+1': 'US/CA',
        }
        hints.append({'type': 'phone_country_code', 'value': mapping.get(cc, cc), 'confidence': 0.55})
    return hints


def _apply_geoparse_to_candidates(geoparse, candidates, methods_used):
    """Geoparsing nəticələrini adaylara çevirir."""
    for ec in geoparse.get('extracted_coordinates', []):
        lat, lon = ec.get('latitude'), ec.get('longitude')
        if lat is None:
            continue
        src = f"text_{ec.get('format', 'coord')}"
        c = _candidate(
            lat, lon, src, ec.get('confidence', 0.68),
            f"Geoparse: {ec.get('format')}",
            ec.get('raw', ''),
            fmt=ec.get('format'),
            raw=ec.get('raw'),
        )
        if c:
            candidates.append(c)
            methods_used.append(src)

    for ent in geoparse.get('geographic_entities', []):
        if ent.get('entity_type') == 'place' and ent.get('latitude'):
            candidates.append(_candidate(
                ent['latitude'], ent['longitude'], 'gazetteer_entity',
                ent.get('confidence', 0.6),
                ent.get('value', 'Yer'),
                'Gazetteer entity uyğunluğu.',
            ))
            methods_used.append('gazetteer_entity')

    for pq in geoparse.get('place_queries', []):
        if pq.get('type') == 'coord_pair' and pq.get('latitude'):
            candidates.append(_candidate(
                pq['latitude'], pq['longitude'], 'ocr_coordinates', 0.74,
                'Koordinat cütü', pq.get('query', ''),
            ))
            methods_used.append('ocr_coordinates')
        elif pq.get('type') == 'known_place' and pq.get('latitude'):
            candidates.append(_candidate(
                pq['latitude'], pq['longitude'], 'known_place', 0.52,
                pq.get('query', ''), 'Məlum şəhər mərkəzi.',
            ))
            methods_used.append('known_place')


def _run_smart_geocoding(geoparse, candidates, methods_used, max_calls=10):
    """Strategiya əsaslı Nominatim — ölkə bias ilə."""
    calls = 0
    for strat in geoparse.get('geocode_strategies', []):
        if calls >= max_calls:
            break
        query = strat.get('query', '')
        if not query:
            continue
        if strat.get('strategy') == 'plus_code':
            query = f"{query} Azerbaijan"

        hits = nominatim_search_advanced(
            query,
            country_codes=strat.get('country_codes'),
            structured=strat.get('structured'),
            limit=3,
        )
        calls += 1
        for h in hits:
            src = 'nominatim_structured' if strat.get('structured') else 'nominatim_geocode'
            c = _candidate(
                h['latitude'], h['longitude'], src, h.get('confidence', 0.65),
                h.get('display_name', query)[:140],
                f"Geocoding: {strat.get('strategy')}",
                query=query,
            )
            if c:
                if h.get('address'):
                    c['address'] = h['address']
                candidates.append(c)
        if hits and 'nominatim_geocode' not in methods_used:
            methods_used.append('nominatim_geocode')


def _ml_carving_gps_candidates(filepath):
    out = []
    try:
        from analyzers.file_carving_ml import analyze_file_carving_ml
        carving = analyze_file_carving_ml(filepath)
        for gps in carving.get('recovered_gps') or []:
            lat, lon = gps.get('latitude'), gps.get('longitude')
            if lat is None:
                continue
            c = _candidate(
                lat, lon, 'file_carving_ml', gps.get('confidence', 0.62),
                'File Carving 4.0 GPS',
                carving.get('summary', ''),
            )
            if c:
                out.append(c)
    except Exception as e:
        print(f'  [!] ML carving GPS: {e}', file=sys.stderr)
    return out


def _carved_gps_candidates(filepath):
    out = []
    try:
        from analyzers.carved_metadata_analyzer import analyze_carved_metadata
        carved = analyze_carved_metadata(filepath)
        for gps in carved.get('recovered_gps') or []:
            lat, lon = gps.get('latitude'), gps.get('longitude')
            if lat is None:
                continue
            c = _candidate(
                lat, lon, 'carved_metadata', gps.get('confidence', 0.58),
                'Silinmiş metadata GPS',
                'Carved binary bərpası.',
            )
            if c:
                out.append(c)
    except Exception as e:
        print(f"  [!] Carved GPS: {e}", file=sys.stderr)
    return out


def _finalize_candidates(candidates, country_bias):
    candidates = [c for c in candidates if c]
    candidates = cluster_candidates(candidates, km_threshold=1.8)
    candidates = fuse_candidate_scores(candidates, country_bias)
    _enrich_top_candidates(candidates, limit=6)
    return candidates


def _build_response(candidates, methods_used, regional_hints, texts, geoparse, best):
    return {
        'candidates': candidates,
        'best_guess': best,
        'methods_used': list(dict.fromkeys(methods_used)),
        'regional_hints': regional_hints,
        'ocr_texts_analyzed': texts[:25],
        'geoparsing': {
            'country_bias': geoparse.get('country_bias'),
            'entity_count': len(geoparse.get('geographic_entities', [])),
            'strategy_count': len(geoparse.get('geocode_strategies', [])),
        },
        'geographic_entities': geoparse.get('geographic_entities', []),
        'extracted_coordinates': geoparse.get('extracted_coordinates', []),
        'place_queries': geoparse.get('place_queries', []),
        'map_links': geoparse.get('map_links', []),
        'geocode_strategies': geoparse.get('geocode_strategies', [])[:8],
        'limitations': (
            'Super geoparsing: EXIF, XMP, binary, OCR sətir-sətir, entity gazetteer, '
            'Nominatim (ölkə bias), klaster + fusion skoru. Messencer şəkillərində GPS '
            'adətən silinir — nəticələr OSINT yönəltməsidir, sübut deyil.'
        ),
    }


def analyze_advanced_geolocation(filepath, existing_result=None, extra_texts=None):
    methods_used = []
    candidates = []

    print('  [i] Super geoparsing lokasiya analizi...', file=sys.stderr)

    thumb = recover_gps_from_thumbnail(filepath)
    if thumb:
        candidates.append(thumb)
        methods_used.append('thumbnail_exif')

    xmp = scan_xmp_coordinates(filepath)
    if xmp:
        candidates.append(xmp)
        methods_used.append('xmp_metadata')

    for bc in scan_file_binary_coordinates(filepath):
        candidates.append(bc)
        methods_used.append('binary_scan')

    texts = collect_ocr_texts(filepath, existing_result, run_ocr_if_missing=True)
    if extra_texts:
        texts.extend(str(t).strip() for t in extra_texts if t and str(t).strip())
    texts = list(dict.fromkeys(texts))

    regional_hints = infer_region_hints(texts)
    geoparse = full_geoparse_from_texts(texts, regional_hints)

    _apply_geoparse_to_candidates(geoparse, candidates, methods_used)
    _run_smart_geocoding(geoparse, candidates, methods_used, max_calls=12)

    for cg in _carved_gps_candidates(filepath):
        candidates.append(cg)
        if 'carved_metadata' not in methods_used:
            methods_used.append('carved_metadata')

    for mg in _ml_carving_gps_candidates(filepath):
        candidates.append(mg)
        if 'file_carving_ml' not in methods_used:
            methods_used.append('file_carving_ml')

    candidates = _finalize_candidates(candidates, geoparse.get('country_bias'))
    best = candidates[0] if candidates else None
    if best:
        best['geoparse_summary'] = (
            f"Fusion {best.get('fusion_score', best.get('confidence'))} | "
            f"{len(geoparse.get('geographic_entities', []))} entity | "
            f"bias={geoparse.get('country_bias') or '—'}"
        )

    return _build_response(candidates, methods_used, regional_hints, texts, geoparse, best)


def analyze_text_geolocation(text: str) -> Dict[str, Any]:
    if not text.strip():
        return {'error': 'Mətn boşdur', 'candidates': []}

    texts = [ln.strip() for ln in text.splitlines() if ln.strip()] or [text.strip()]
    regional_hints = infer_region_hints(texts)
    geoparse = full_geoparse_from_texts(texts, regional_hints)

    candidates = []
    methods_used = []
    _apply_geoparse_to_candidates(geoparse, candidates, methods_used)
    _run_smart_geocoding(geoparse, candidates, methods_used, max_calls=14)

    candidates = _finalize_candidates(candidates, geoparse.get('country_bias'))
    best = candidates[0] if candidates else None

    out = _build_response(candidates, methods_used, regional_hints, texts, geoparse, best)
    out['input_preview'] = text[:600]
    return out


def apply_best_guess_to_location(best_guess):
    if not best_guess:
        return None
    loc = dict(best_guess)
    loc['inferred'] = True
    return loc
