"""Çoxlu şəkil EXIF əsasında xronoloji marşrut (Timeline Mapping)."""

import math
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from extractors.image_extractor import ImageExtractor

_EXTRACTOR = ImageExtractor()

_DATETIME_FORMATS = (
    '%Y:%m:%d %H:%M:%S',
    '%Y-%m-%d %H:%M:%S',
    '%Y:%m:%d %H:%M',
    '%Y-%m-%d %H:%M',
    '%Y%m%d_%H%M%S',
    '%Y%m%d%H%M%S',
)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _parse_exif_datetime(dt_info: Optional[Dict]) -> Optional[datetime]:
    if not dt_info:
        return None
    raw = (
        dt_info.get('original')
        or dt_info.get('digitized')
        or dt_info.get('modified')
        or dt_info.get('inferred_from_filename')
    )
    if not raw:
        return None
    s = str(raw).strip()
    if len(s) >= 19:
        s = s[:19]
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _dt_to_iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _map_urls(lat: float, lon: float) -> Dict[str, str]:
    return {
        'google': f'https://www.google.com/maps?q={lat},{lon}',
        'osm': f'https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}',
    }


def _extract_point(filepath: str) -> Dict[str, Any]:
    basename = os.path.basename(filepath)
    row = {
        'filepath': filepath,
        'filename': basename,
        'has_gps': False,
        'has_datetime': False,
        'latitude': None,
        'longitude': None,
        'timestamp': None,
        'timestamp_iso': None,
        'datetime_source': None,
        'camera': None,
        'altitude_m': None,
        'error': None,
    }
    try:
        meta = _EXTRACTOR.extract(filepath)
    except Exception as e:
        row['error'] = str(e)
        return row

    loc = meta.get('location') or {}
    lat, lon = loc.get('latitude'), loc.get('longitude')
    if lat is not None and lon is not None:
        row['has_gps'] = True
        row['latitude'] = float(lat)
        row['longitude'] = float(lon)
        row['altitude_m'] = loc.get('altitude_m')
        row['map_urls'] = _map_urls(row['latitude'], row['longitude'])

    exif = meta.get('exif') or {}
    dt_info = exif.get('datetime') or {}
    parsed = _parse_exif_datetime(dt_info)
    if parsed:
        row['has_datetime'] = True
        row['timestamp'] = parsed.timestamp()
        row['timestamp_iso'] = _dt_to_iso(parsed)
        for key in ('original', 'digitized', 'modified', 'inferred_from_filename'):
            if dt_info.get(key):
                row['datetime_source'] = key
                break

    cam = exif.get('camera') or {}
    if cam:
        row['camera'] = {
            'make': cam.get('make'),
            'model': cam.get('model'),
        }

    fi = meta.get('file_info') or {}
    row['file_size_bytes'] = fi.get('size_bytes')
    return row


def _sort_key(point: Dict) -> Tuple:
    ts = point.get('timestamp')
    if ts is not None:
        return (0, ts, point.get('filename') or '')
    return (1, 0, point.get('filename') or '')


def _build_route(waypoints: List[Dict]) -> Dict[str, Any]:
    if len(waypoints) < 2:
        return {
            'segment_count': 0,
            'total_distance_m': 0,
            'total_distance_km': 0,
            'segments': [],
        }

    segments = []
    total_m = 0.0
    for i in range(len(waypoints) - 1):
        a, b = waypoints[i], waypoints[i + 1]
        dist = _haversine_m(a['latitude'], a['longitude'], b['latitude'], b['longitude'])
        total_m += dist
        seg = {
            'from_index': i + 1,
            'to_index': i + 2,
            'distance_m': round(dist, 1),
            'distance_km': round(dist / 1000, 3),
        }
        dt_a, dt_b = a.get('timestamp'), b.get('timestamp')
        if dt_a is not None and dt_b is not None and dt_b > dt_a:
            seg['duration_sec'] = round(dt_b - dt_a, 1)
            seg['avg_speed_kmh'] = round((dist / 1000) / ((dt_b - dt_a) / 3600), 2) if dt_b > dt_a else None
        segments.append(seg)

    duration_sec = None
    ts_first = waypoints[0].get('timestamp')
    ts_last = waypoints[-1].get('timestamp')
    if ts_first is not None and ts_last is not None and ts_last >= ts_first:
        duration_sec = round(ts_last - ts_first, 1)

    return {
        'segment_count': len(segments),
        'total_distance_m': round(total_m, 1),
        'total_distance_km': round(total_m / 1000, 3),
        'duration_sec': duration_sec,
        'segments': segments,
    }


def _bounds(waypoints: List[Dict]) -> Optional[Dict]:
    lats = [w['latitude'] for w in waypoints]
    lons = [w['longitude'] for w in waypoints]
    if not lats:
        return None
    return {
        'south': min(lats),
        'north': max(lats),
        'west': min(lons),
        'east': max(lons),
        'center': {
            'latitude': sum(lats) / len(lats),
            'longitude': sum(lons) / len(lons),
        },
    }


def analyze_timeline_mapping(filepaths: List[str]) -> Dict[str, Any]:
    """
    Çoxlu şəkil faylından EXIF GPS + tarix əsasında xronoloji marşrut qurur.
    """
    paths = [os.path.abspath(p) for p in filepaths if p and os.path.isfile(p)]
    result = {
        'status': 'ok',
        'module': 'timeline_mapping',
        'files_requested': len(filepaths),
        'files_processed': 0,
        'waypoints': [],
        'route': None,
        'bounds': None,
        'polyline': [],
        'skipped': [],
        'warnings': [],
        'summary': '',
    }

    if len(paths) < 2:
        result['status'] = 'insufficient_files'
        result['summary'] = 'Marşrut analizi üçün ən azı 2 şəkil lazımdır.'
        result['warnings'].append('Minimum 2 fayl tələb olunur.')
        return result

    points = []
    skipped = []
    for fp in paths:
        pt = _extract_point(fp)
        result['files_processed'] += 1
        if pt.get('error'):
            skipped.append({**pt, 'reason': 'extract_error'})
            continue
        if not pt['has_gps']:
            skipped.append({**pt, 'reason': 'no_gps'})
            continue
        points.append(pt)

    dated = [p for p in points if p.get('timestamp') is not None]
    undated = [p for p in points if p.get('timestamp') is None]
    dated.sort(key=_sort_key)
    undated.sort(key=lambda p: p.get('filename') or '')
    waypoints = dated + undated

    for i, w in enumerate(waypoints, start=1):
        w['sequence'] = i

    result['waypoints'] = waypoints
    result['skipped'] = skipped
    result['polyline'] = [
        [w['latitude'], w['longitude']] for w in waypoints
    ]

    if len(waypoints) < 2:
        result['status'] = 'insufficient_gps'
        result['summary'] = (
            f'{len(paths)} fayldan yalnız {len(waypoints)}-ində GPS tapıldı. '
            'Marşrut üçün ən azı 2 koordinat lazımdır.'
        )
        if undated and dated:
            result['warnings'].append(
                f'{len(undated)} şəkildə EXIF tarix yoxdur — fayl adı sırası ilə əlavə edildi.'
            )
        return result

    result['route'] = _build_route(waypoints)
    result['bounds'] = _bounds(waypoints)

    no_date = len(undated)
    skip_gps = len([s for s in skipped if s.get('reason') == 'no_gps'])
    parts = [
        f'{len(waypoints)} GPS nöqtəsi xronoloji ardıcıllıqla birləşdirildi.',
        f'Ümumi məsafə: {result["route"]["total_distance_km"]} km.',
    ]
    if result['route'].get('duration_sec'):
        hrs = result['route']['duration_sec'] / 3600
        parts.append(f'Zaman intervalı: {hrs:.1f} saat.')
    if skip_gps:
        parts.append(f'{skip_gps} faylda GPS yoxdur.')
    if no_date:
        parts.append(f'{no_date} şəkildə tarix metadata yoxdur.')
    result['summary'] = ' '.join(parts)

    if no_date:
        result['warnings'].append(
            'Tarixsiz şəkillər sıranın sonuna əlavə olunub; marşrut dəqiqliyi məhdudlaşa bilər.'
        )

    print(
        f'  [i] Timeline mapping: {len(waypoints)} waypoints, '
        f'{result["route"]["total_distance_km"]} km',
        file=sys.stderr,
    )
    return result
