"""
İnternet/Google şəkilləri — silinmiş EXIF-dən qalan izlərin toplanması.
Fayl daxili carving, thumbnail GPS, XMP, binary, ML carving, veb mənbə.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from analyzers.web_image_metadata import load_url_sidecar
from utils.coordinate_validator import apply_sanitized_to_location
from utils.gps_converter import dms_to_decimal, format_coordinates


def _is_web_download(filepath: str) -> bool:
    sc = load_url_sidecar(filepath)
    return bool(sc and (sc.get('source_url') or sc.get('resolved_url')))


def _needs_residual_pass(result: Dict[str, Any], filepath: str) -> bool:
    if _is_web_download(filepath):
        return True
    loc = result.get('location') or {}
    if loc.get('latitude') is None:
        return True
    exif = result.get('exif') or {}
    if not exif.get('camera') and not exif.get('datetime'):
        raw = result.get('raw_tags') or {}
        if len(raw) < 3:
            return True
    return False


def _parse_exifread_coord_string(coord_str: str, ref: str) -> Optional[float]:
    try:
        vals = ast.literal_eval(str(coord_str).strip())
        if not isinstance(vals, (list, tuple)) or len(vals) < 2:
            return None
        while len(vals) < 3:
            vals = list(vals) + [0]
        return dms_to_decimal(vals[:3], ref)
    except (SyntaxError, ValueError, TypeError):
        return None


def _gps_from_tag_dict(tags: Dict[str, str]) -> Optional[Dict[str, Any]]:
    lat_s = tags.get('GPS GPSLatitude')
    lat_ref = tags.get('GPS GPSLatitudeRef') or tags.get('GPS LatitudeRef')
    lon_s = tags.get('GPS GPSLongitude')
    lon_ref = tags.get('GPS GPSLongitudeRef') or tags.get('GPS LongitudeRef')
    if not all([lat_s, lat_ref, lon_s, lon_ref]):
        return None
    lat = _parse_exifread_coord_string(lat_s, str(lat_ref))
    lon = _parse_exifread_coord_string(lon_s, str(lon_ref))
    if lat is None or lon is None:
        return None
    loc = apply_sanitized_to_location(
        format_coordinates(lat, lon), source='carved_exif',
    )
    if loc:
        loc['source'] = 'carved_exif'
        loc['confidence'] = 0.82
        loc['inferred'] = True
        loc['label'] = 'Bərpa: fayl daxili EXIF GPS'
    return loc


def _collect_gps_candidates(
    carved: Dict[str, Any],
    thumb_cand: Optional[Dict],
    xmp_cand: Optional[Dict],
    ml_carving: Optional[Dict],
) -> List[Dict[str, Any]]:
    pool: List[Dict[str, Any]] = []

    for block in carved.get('findings') or []:
        if block.get('type') == 'exif_segment':
            loc = _gps_from_tag_dict(block.get('tags') or {})
            if loc:
                pool.append(loc)
        elif block.get('type') == 'decimal_coordinates':
            lat, lon = block.get('latitude'), block.get('longitude')
            if lat is not None and lon is not None:
                loc = apply_sanitized_to_location(
                    format_coordinates(lat, lon), source='carved_binary',
                )
                if loc:
                    loc['source'] = 'carved_binary'
                    loc['confidence'] = float(block.get('confidence', 0.55))
                    loc['inferred'] = True
                    loc['label'] = 'Bərpa: binary koordinat'
                    pool.append(loc)

    for gps in carved.get('recovered_gps') or []:
        lat, lon = gps.get('latitude'), gps.get('longitude')
        if lat is not None and lon is not None:
            loc = apply_sanitized_to_location(
                format_coordinates(lat, lon), source=gps.get('source', 'carved_gps'),
            )
            if loc:
                loc['source'] = gps.get('source', 'carved_gps')
                loc['confidence'] = float(gps.get('confidence', 0.6))
                loc['inferred'] = True
                pool.append(loc)

    if thumb_cand and thumb_cand.get('latitude') is not None:
        loc = apply_sanitized_to_location(
            format_coordinates(thumb_cand['latitude'], thumb_cand['longitude']),
            source='thumbnail_exif',
        )
        if loc:
            loc['source'] = 'thumbnail_exif'
            loc['confidence'] = float(thumb_cand.get('confidence', 0.88))
            loc['inferred'] = True
            loc['label'] = thumb_cand.get('label', 'Thumbnail EXIF GPS')
            pool.append(loc)

    if xmp_cand and xmp_cand.get('latitude') is not None:
        loc = apply_sanitized_to_location(
            format_coordinates(xmp_cand['latitude'], xmp_cand['longitude']),
            source='xmp_metadata',
        )
        if loc:
            loc['source'] = 'xmp_metadata'
            loc['confidence'] = float(xmp_cand.get('confidence', 0.78))
            loc['inferred'] = True
            loc['label'] = xmp_cand.get('label', 'XMP GPS')
            pool.append(loc)

    if ml_carving:
        for gps in ml_carving.get('recovered_gps') or []:
            lat, lon = gps.get('latitude'), gps.get('longitude')
            if lat is None:
                continue
            loc = apply_sanitized_to_location(
                format_coordinates(lat, lon),
                source=gps.get('source', 'file_carving_ml'),
            )
            if loc:
                loc['source'] = gps.get('source', 'file_carving_ml')
                loc['confidence'] = float(gps.get('confidence', 0.65))
                loc['inferred'] = True
                pool.append(loc)

    pool.sort(key=lambda x: -float(x.get('confidence', 0)))
    return pool


def _merge_tags_into_result(result: Dict[str, Any], carved: Dict[str, Any]) -> int:
    raw = dict(result.get('raw_tags') or {})
    count = 0
    prefix = 'Qalıq_'

    for block in carved.get('findings') or []:
        tags = block.get('tags') or block.get('recovered_only_tags')
        if isinstance(tags, list):
            for item in tags:
                if isinstance(item, dict):
                    for k, v in item.items():
                        key = f'{prefix}{k}'
                        if key not in raw:
                            raw[key] = str(v)[:200]
                            count += 1
        elif isinstance(tags, dict):
            for k, v in tags.items():
                key = f'{prefix}{k}'
                if key not in raw:
                    raw[key] = str(v)[:200]
                    count += 1
        if block.get('type') == 'xmp_packet' and block.get('preview'):
            key = f'{prefix}XMP_{block.get("offset_hex", "xmp")}'
            if key not in raw:
                raw[key] = block['preview'][:300]
                count += 1
        if block.get('type') == 'datetime_string' and block.get('value'):
            key = f'{prefix}DateTime'
            if key not in raw:
                raw[key] = block['value']
                count += 1
        if block.get('type') == 'camera_string' and block.get('context'):
            key = f'{prefix}Camera_{block.get("hint", "cam")}'
            if key not in raw:
                raw[key] = block['context'][:120]
                count += 1

    for dt in carved.get('recovered_datetimes') or []:
        key = f'{prefix}DateTime_carved'
        if key not in raw:
            raw[key] = dt
            count += 1

    if count:
        result['raw_tags'] = raw
    return count


def _merge_datetime_into_exif(result: Dict[str, Any], carved: Dict[str, Any]) -> None:
    exif = result.get('exif') or {
        'camera': None, 'settings': None, 'datetime': None, 'image': {},
    }
    dt_block = dict(exif.get('datetime') or {})
    if not dt_block and carved.get('recovered_datetimes'):
        dt_block['recovered_from_file'] = carved['recovered_datetimes'][0]
    for block in carved.get('findings') or []:
        if block.get('type') == 'datetime_string' and block.get('value'):
            dt_block.setdefault('carved_string', block['value'])
            break
    if dt_block:
        exif['datetime'] = dt_block
        result['exif'] = exif


_RECOVERING: set = set()


def recover_residual_metadata(result: Dict[str, Any], filepath: str) -> Dict[str, Any]:
    """
    Silinmiş EXIF/GPS qalıqlarını toplayır; result-ı yerində zənginləşdirir.
    """
    if result.get('residual_recovery'):
        return result['residual_recovery']
    if not _needs_residual_pass(result, filepath):
        return {'status': 'skipped', 'reason': 'klassik metadata kifayətdir'}
    norm = os.path.normpath(os.path.abspath(filepath))
    if norm in _RECOVERING:
        return {'status': 'skipped', 'reason': 'already_running'}
    _RECOVERING.add(norm)

    print('  [i] Qalıq metadata bərpası (internet şəkli)...', file=sys.stderr)
    sources: List[str] = []
    carved: Dict[str, Any] = {}
    ml_carving: Optional[Dict] = None
    thumb_cand = None
    xmp_cand = None

    try:
        try:
            from analyzers.carved_metadata_analyzer import analyze_carved_metadata
            carved = analyze_carved_metadata(filepath) or {}
            if carved.get('status') not in ('error',):
                sources.append('binary_carving')
        except Exception as e:
            carved = {'status': 'error', 'message': str(e)}
            print(f'  [!] Carved: {e}', file=sys.stderr)

        try:
            from analyzers.geolocation_analyzer import recover_gps_from_thumbnail, scan_xmp_coordinates
            thumb_cand = recover_gps_from_thumbnail(filepath)
            if thumb_cand:
                sources.append('thumbnail_exif')
            xmp_cand = scan_xmp_coordinates(filepath)
            if xmp_cand:
                sources.append('xmp_scan')
        except Exception as e:
            print(f'  [!] Thumbnail/XMP: {e}', file=sys.stderr)

        try:
            from analyzers.file_carving_ml import analyze_file_carving_ml
            ml_carving = analyze_file_carving_ml(filepath)
            if ml_carving and (ml_carving.get('recovered_gps') or ml_carving.get('segments')):
                sources.append('file_carving_ml')
        except Exception as e:
            print(f'  [!] ML carving: {e}', file=sys.stderr)

        tag_count = _merge_tags_into_result(result, carved)
        _merge_datetime_into_exif(result, carved)

        gps_pool = _collect_gps_candidates(carved, thumb_cand, xmp_cand, ml_carving)
        best_gps = gps_pool[0] if gps_pool else None

        if best_gps and (result.get('location') or {}).get('latitude') is None:
            result['location'] = dict(best_gps)

        recovery_score = int(carved.get('recovery_score') or 0)
        if best_gps:
            recovery_score = min(100, recovery_score + 25)
        if tag_count:
            recovery_score = min(100, recovery_score + min(tag_count * 2, 20))

        parts = []
        if _is_web_download(filepath):
            parts.append('Google/internet axını — EXIF adətən silinir')
        if carved.get('carved_blocks_found'):
            parts.append(f'{carved["carved_blocks_found"]} daxili metadata bloku')
        if carved.get('deleted_remnants_found'):
            parts.append(f'{carved["deleted_remnants_found"]} aktiv olmayan qalıq')
        if tag_count:
            parts.append(f'{tag_count} bərpa olunmuş tag')
        if best_gps:
            parts.append('GPS qalığından koordinat')
        elif not parts:
            parts.append('Fayl daxilində güclü qalıq tapılmadı — veb/OCR lokasiya istifadə olunur')

        summary_az = '; '.join(parts)

        residual = {
            'status': 'success' if (tag_count or best_gps or carved.get('carved_blocks_found')) else 'weak',
            'summary_az': summary_az,
            'recovery_score': recovery_score,
            'sources_used': sources,
            'recovered_tag_count': tag_count,
            'gps_candidates_found': len(gps_pool),
            'best_gps_source': best_gps.get('source') if best_gps else None,
            'carved_metadata': carved,
            'file_carving_ml': ml_carving,
            'is_web_image': _is_web_download(filepath),
            'note_az': (
                'Messencer/CDN şəkillərində EXIF silinir; sistem faylın binary qalıqlarını, '
                'thumbnail, XMP və veb mənbəni birləşdirir.'
            ),
        }
        result['residual_recovery'] = residual
        result['carved_metadata'] = carved

        warnings = list(result.get('warnings') or [])
        if _is_web_download(filepath):
            msg = (
                'Kamera EXIF/GPS silinib (internet). Qalıq metadata bərpası işlədildi: '
                f'{", ".join(sources) or "veb kontekst"}.'
            )
            if msg not in warnings:
                warnings.append(msg)
        if best_gps and best_gps.get('inferred'):
            w2 = f'GPS bərpa edildi ({best_gps.get("source")}) — təsdiq üçün xəritəni yoxlayın.'
            if w2 not in warnings:
                warnings.append(w2)
        result['warnings'] = warnings or None

        if recovery_score >= 25 or tag_count >= 5:
            result['metadata_richness'] = 'high' if recovery_score >= 50 else 'medium'

        return residual
    finally:
        _RECOVERING.discard(norm)
