"""
Koordinat doğrulama — enlik/uzunluq düzəlişi, su/null island filtri, etibar skoru.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

OCEAN_NAME_RE = re.compile(
    r'\b(pacific|atlantic|indian|arctic|ocean|open sea|high seas|'
    r'okean|okeanı|dəniz|sea of|gulf of|bay of|water body)\b',
    re.I,
)

TRUSTED_SOURCES = frozenset({
    'exif',
    'thumbnail_exif',
    'xmp_metadata',
    'ml_segment_exif',
})

HIGH_TRUST_SOURCES = TRUSTED_SOURCES | frozenset({
    'pillow',
    'carved_metadata',
})

LOW_TRUST_SOURCES = frozenset({
    'binary_scan',
    'ml_segment_scan',
})


def normalize_hemisphere_ref(ref) -> str:
    """EXIF istiqamət referansını (N/S/E/W) təmizləyir."""
    if ref is None:
        return ''
    if isinstance(ref, bytes):
        ref = ref.decode('ascii', errors='ignore').strip()
    else:
        ref = str(ref).strip()
    if not ref:
        return ''
    upper = ref.upper()
    if upper in ('N', 'S', 'E', 'W'):
        return upper
    for ch in upper:
        if ch in 'NSEW':
            return ch
    return upper[:1] if upper else ''


def in_valid_range(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180


def is_null_island(lat: float, lon: float, eps: float = 0.02) -> bool:
    return abs(lat) < eps and abs(lon) < eps


def likely_lat_lon_swapped(lat: float, lon: float, country_bias: Optional[str] = None) -> bool:
    """Enlik və uzunluq yer dəyişib — tipik səhv (o cümlədən AZ/TR regionu)."""
    if not in_valid_range(lat, lon):
        return False
    if not in_valid_range(lon, lat):
        return False

    bias = (country_bias or '').upper()
    if bias in ('AZ', 'TR', 'GE', 'AM'):
        if 46 <= lat <= 52 and 38 <= lon <= 46:
            return True
        if 38 <= lat <= 46 and 46 <= lon <= 52:
            return False

    if abs(lat) > 55 and abs(lon) <= 55:
        return True
    if abs(lon) > 70 and abs(lat) < 40:
        return False
    if abs(lat) > 35 and abs(lon) < 20 and abs(lon) > 0.5:
        return True
    return False


def _reverse_geocode_score(lat: float, lon: float) -> Tuple[float, Dict[str, Any]]:
    """Yer üstü / şəhər yaxınlığı üçün sürətli skor (reverse_geocoder)."""
    meta: Dict[str, Any] = {}
    try:
        import reverse_geocoder as rg
        hits = rg.search((lat, lon))
        if not hits:
            return 0.0, meta
        res = hits[0]
        name = (res.get('name') or '').strip()
        cc = (res.get('cc') or '').upper()
        meta['geo_city'] = name
        meta['country_code'] = cc
        if not name or name.lower() in ('unknown', 'unpopulated', 'water'):
            return 0.15, meta
        score = 0.55
        if cc:
            score += 0.2
        if len(name) > 2:
            score += 0.15
        return min(score, 0.95), meta
    except Exception:
        return 0.0, meta


def _nominatim_water_hint(lat: float, lon: float) -> Tuple[bool, Optional[str]]:
    try:
        from analyzers.geo_analyzer import nominatim_reverse_full
        full = nominatim_reverse_full(lat, lon, delay=0.35)
        if not full:
            return False, None
        display = full.get('display_name') or ''
        category = (full.get('category') or '').lower()
        if category in ('water', 'bay', 'strait', 'sea'):
            return True, display
        if OCEAN_NAME_RE.search(display):
            addr = full.get('address') or {}
            if not (addr.get('city') or addr.get('road') or addr.get('suburb')):
                return True, display
        return False, display
    except Exception:
        return False, None


def score_coordinate_pair(
    lat: float,
    lon: float,
    source: str = 'unknown',
    country_bias: Optional[str] = None,
    check_water: bool = False,
) -> Tuple[float, Dict[str, Any]]:
    """Yüksək skor = etibarlı quru ərazi koordinatı."""
    info: Dict[str, Any] = {'source': source}
    if not in_valid_range(lat, lon):
        info['reason'] = 'range_invalid'
        return -1.0, info

    if is_null_island(lat, lon):
        info['reason'] = 'null_island'
        return -0.9, info

    score = 0.25
    if source in TRUSTED_SOURCES or source == 'exif':
        score += 0.45
    elif source in HIGH_TRUST_SOURCES:
        score += 0.35
    elif source in LOW_TRUST_SOURCES:
        score += 0.05
    else:
        score += 0.2

    geo_score, geo_meta = _reverse_geocode_score(lat, lon)
    score += geo_score * 0.35
    info.update(geo_meta)

    if country_bias and info.get('country_code') == country_bias.upper():
        score += 0.12

    bias = (country_bias or '').upper()
    if bias in ('AZ', 'TR', 'GE', 'AM'):
        if 46 <= lat <= 52 and 38 <= lon <= 46:
            score -= 0.5
        elif 38 <= lat <= 46 and 46 <= lon <= 52:
            score += 0.18

    if check_water:
        on_water, display = _nominatim_water_hint(lat, lon)
        info['on_water'] = on_water
        if display:
            info['display_name'] = display
        if on_water:
            score -= 0.75
            info['reason'] = 'on_water'

    return round(min(max(score, -1.0), 1.0), 3), info


def sanitize_coordinate_pair(
    lat: float,
    lon: float,
    source: str = 'unknown',
    country_bias: Optional[str] = None,
    check_water: bool = False,
) -> Dict[str, Any]:
    """
    Koordinatları yoxlayır; lazım olsa lat/lon dəyişir; ən yaxşı variantı qaytarır.
    """
    variants = [(float(lat), float(lon), False)]
    if likely_lat_lon_swapped(lat, lon, country_bias):
        variants.append((float(lon), float(lat), True))
    elif abs(lat) <= 90 and abs(lon) <= 90:
        variants.append((float(lon), float(lat), True))

    prefer_swap = likely_lat_lon_swapped(lat, lon, country_bias)

    best = None
    best_score = -999.0
    for la, lo, swapped in variants:
        if not in_valid_range(la, lo):
            continue
        sc, meta = score_coordinate_pair(
            la, lo, source=source, country_bias=country_bias, check_water=check_water,
        )
        if swapped and prefer_swap:
            sc += 0.08
        if sc > best_score:
            best_score = sc
            best = {
                'latitude': round(la, 6),
                'longitude': round(lo, 6),
                'lat_lon_swapped': swapped,
                'quality_score': sc,
                'accepted': sc >= 0.22,
                **meta,
            }

    if not best:
        return {
            'latitude': lat,
            'longitude': lon,
            'accepted': False,
            'quality_score': -1.0,
            'reason': 'no_valid_variant',
        }

    if best['quality_score'] < 0.22:
        best['accepted'] = False
        best.setdefault('reason', 'low_confidence')
    return best


def apply_sanitized_to_location(loc: Optional[dict], **kwargs) -> Optional[dict]:
    if not loc or loc.get('latitude') is None or loc.get('longitude') is None:
        return loc
    fixed = sanitize_coordinate_pair(
        loc['latitude'],
        loc['longitude'],
        source=loc.get('source') or 'exif',
        **kwargs,
    )
    if not fixed.get('accepted'):
        return None
    out = dict(loc)
    out['latitude'] = fixed['latitude']
    out['longitude'] = fixed['longitude']
    if fixed.get('lat_lon_swapped'):
        out['lat_lon_swapped'] = True
        out['coordinate_fix'] = 'lat_lon_swap'
    out['location_quality'] = fixed.get('quality_score')
    if fixed.get('display_name') and not out.get('display_name'):
        out['display_name'] = fixed['display_name']
    if fixed.get('country_code') and not out.get('address'):
        out['address'] = {'country_code': fixed['country_code'], 'city': fixed.get('geo_city')}
    return out
