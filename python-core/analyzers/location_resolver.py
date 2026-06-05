"""
Şəkil üçün ən etibarlı lokasiya seçimi — EXIF, carving, geoparsing birlikdə.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional, Tuple

from utils.coordinate_validator import (
    apply_sanitized_to_location,
    sanitize_coordinate_pair,
    TRUSTED_SOURCES,
    LOW_TRUST_SOURCES,
)
from utils.gps_converter import format_coordinates


def _pool_entry(
    lat: float,
    lon: float,
    source: str,
    confidence: float,
    label: str = '',
    detail: str = None,
    country_bias: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    check_water = source in LOW_TRUST_SOURCES or confidence < 0.7
    fixed = sanitize_coordinate_pair(
        lat, lon, source=source, country_bias=country_bias, check_water=check_water,
    )
    if not fixed.get('accepted'):
        return None
    base = format_coordinates(fixed['latitude'], fixed['longitude'])
    if not base:
        return None
    base['source'] = source
    base['confidence'] = confidence
    base['location_quality'] = fixed.get('quality_score')
    if fixed.get('lat_lon_swapped'):
        base['lat_lon_swapped'] = True
        base['coordinate_fix'] = 'lat_lon_swap'
    if label:
        base['label'] = label
    if detail:
        base['detail'] = detail
    if fixed.get('on_water'):
        base['on_water'] = True
    src_weight = 0.92 if source in TRUSTED_SOURCES or source == 'exif' else confidence
    base['pick_score'] = round(
        fixed.get('quality_score', 0) * 0.55 + min(src_weight, 0.95) * 0.45,
        3,
    )
    return base


WEB_LOCATION_SOURCES = frozenset({
    'web_meta_geo', 'web_json_ld', 'web_url_map', 'web_url_query', 'web_url_wikimedia',
    'web_url_at', 'web_page_html', 'web_gazetteer', 'web_nominatim_page',
})


def resolve_image_location(
    filepath: str,
    exif_location: Optional[Dict],
    carving: Optional[Dict] = None,
    inference: Optional[Dict] = None,
    extra_texts: Optional[List[str]] = None,
    web_candidates: Optional[List[Dict]] = None,
) -> Tuple[Optional[Dict], Optional[Dict], List[str]]:
    """
    Bütün mənbələrdən ən yaxşı lokasiyanı seçir.
    inference həmişə dolu qaytarıla bilər (xəritədə alternativlər üçün).
    """
    warnings: List[str] = []
    country_bias = None
    if inference:
        country_bias = (inference.get('geoparsing') or {}).get('country_bias')

    if inference is None and filepath:
        try:
            from analyzers.geolocation_analyzer import analyze_advanced_geolocation
            from extractors.image_extractor import ImageExtractor
            meta = ImageExtractor().extract(filepath)
            inference = analyze_advanced_geolocation(
                filepath, meta, extra_texts=extra_texts,
            )
            if not country_bias:
                country_bias = (inference.get('geoparsing') or {}).get('country_bias')
        except Exception as e:
            print(f'  [!] Geoparsing (resolver): {e}', file=sys.stderr)

    pool: List[Dict] = []

    if exif_location and exif_location.get('latitude') is not None:
        entry = _pool_entry(
            exif_location['latitude'],
            exif_location['longitude'],
            'exif',
            0.93,
            'EXIF GPS',
            country_bias=country_bias,
        )
        if entry:
            pool.append(entry)
        else:
            warnings.append(
                'EXIF GPS koordinatı etibarsız və ya su/null island — digər mənbələr axtarılır.'
            )

    if carving:
        for gps in carving.get('recovered_gps') or []:
            lat, lon = gps.get('latitude'), gps.get('longitude')
            if lat is None:
                continue
            entry = _pool_entry(
                lat, lon,
                gps.get('source') or 'file_carving_ml',
                float(gps.get('confidence', 0.6)),
                'File Carving GPS',
                carving.get('summary'),
                country_bias=country_bias,
            )
            if entry:
                pool.append(entry)

    if inference:
        for c in inference.get('candidates') or []:
            lat, lon = c.get('latitude'), c.get('longitude')
            if lat is None:
                continue
            src = c.get('source') or 'inference'
            entry = _pool_entry(
                lat, lon, src,
                float(c.get('fusion_score', c.get('confidence', 0.5))),
                c.get('label') or src,
                c.get('detail'),
                country_bias=country_bias,
            )
            if entry:
                pool.append(entry)

    for wc in web_candidates or []:
        lat, lon = wc.get('latitude'), wc.get('longitude')
        if lat is None:
            continue
        src = wc.get('source') or 'web_page'
        conf = float(wc.get('confidence', 0.65))
        entry = _pool_entry(
            lat, lon, src, conf,
            wc.get('label') or 'Veb mənbə',
            country_bias=country_bias,
        )
        if entry:
            pool.append(entry)

    if not pool:
        return None, inference, warnings

    pool.sort(key=lambda x: -x.get('pick_score', 0))
    best = pool[0]

    if best.get('lat_lon_swapped'):
        warnings.append(
            'Koordinatlar düzəldildi: enlik və uzunluq yer dəyişmişdi (kamera/EXIF formatı).'
        )
    if best.get('on_water'):
        warnings.append(
            'Seçilmiş nöqtə su massivi üzrədir — xəritəni yoxlayın; alternativ adaylara baxın.'
        )
    if best.get('source') in LOW_TRUST_SOURCES:
        warnings.append(
            f'Lokasiya əsasən {best.get("source")} mənbəsidir (zəif etibar). '
            'Mümkündürsə EXIF və ya ünvandan təsdiq edin.'
        )
    if best.get('source') in WEB_LOCATION_SOURCES:
        warnings.append(
            'Lokasiya veb mənbədən (Google URL / məqalə səhifəsi / yer adı) — EXIF GPS yoxdur.'
        )

    primary = dict(best)
    primary.setdefault('map_url', format_coordinates(best['latitude'], best['longitude'])['map_url'])
    primary['osm_url'] = format_coordinates(best['latitude'], best['longitude'])['osm_url']
    if best.get('source') != 'exif':
        primary['inferred'] = True

    return primary, inference, warnings
