"""
Silinmiş Metadata Bərpası (Carved Data Recovery)

Faylın aktiv EXIF/GPS-i silinibsə belə, binary daxilində qalan
EXIF, XMP, IPTC və mətn izlərini axtarır və bərpa etməyə çalışır.
"""

import os
import re
import sys
import tempfile
from typing import Any, Dict, Optional, Tuple

import exifread

from utils.gps_converter import format_coordinates

MAX_SCAN_BYTES = 80 * 1024 * 1024  # 80 MB
EXIF_MARKER = b'Exif\x00\x00'
XMP_MARKERS = (b'<?xpacket', b'<x:xmpmeta', b'http://ns.adobe.com/xap/1.0/')
IPTC_MARKER = b'Photoshop 3.0'
DATETIME_RE = re.compile(rb'(\d{4}):(\d{2}):(\d{2})\s+(\d{2}):(\d{2}):(\d{2})')
CAMERA_HINTS = (
    b'Canon', b'NIKON', b'SONY', b'Apple', b'Samsung', b'HUAWEI',
    b'iPhone', b'Google', b'OLYMPUS', b'FUJIFILM', b'GoPro',
)
GPS_TAG_NAMES = (b'GPSLatitude', b'GPSLongitude', b'GPS GPSLatitude')


def _read_file_bytes(filepath, limit=MAX_SCAN_BYTES):
    size = os.path.getsize(filepath)
    with open(filepath, 'rb') as f:
        return f.read(min(size, limit)), size


def _active_metadata_snapshot(filepath):
    """Cari (aktiv) metadata — tam extract çağırmır (rekursiya qarşısı)."""
    meta: Dict[str, Any] = {'raw_tags': {}, 'location': None, 'exif': None}
    active = {
        'has_exif': False,
        'has_gps': False,
        'tags': set(),
        'gps': None,
    }
    try:
        with open(filepath, 'rb') as f:
            tags = exifread.process_file(f, details=False)
        if tags:
            active['has_exif'] = True
            meta['raw_tags'] = {
                str(k): str(v)[:200]
                for k, v in tags.items()
                if not str(k).startswith(('Thumbnail', 'JPEGThumbnail', 'EXIF MakerNote'))
            }
            for k, v in meta['raw_tags'].items():
                active['tags'].add(f'{k}={v[:80]}')
            from utils.gps_converter import dms_to_decimal, format_coordinates
            from utils.coordinate_validator import apply_sanitized_to_location
            lat = tags.get('GPS GPSLatitude')
            lat_ref = tags.get('GPS GPSLatitudeRef')
            lon = tags.get('GPS GPSLongitude')
            lon_ref = tags.get('GPS GPSLongitudeRef')
            if all([lat, lat_ref, lon, lon_ref]):
                la = dms_to_decimal(lat.values, str(lat_ref))
                lo = dms_to_decimal(lon.values, str(lon_ref))
                if la is not None and lo is not None:
                    loc = apply_sanitized_to_location(
                        format_coordinates(la, lo), source='exif',
                    )
                    if loc:
                        meta['location'] = loc
                        active['has_gps'] = True
                        active['gps'] = (round(la, 5), round(lo, 5))
    except Exception:
        pass

    return active, meta


def _try_parse_exif_at(data, offset):
    """Exif marker ətrafındakı bloku exifread ilə parse et."""
    start = max(0, offset - 4)
    chunk = data[start:start + 65536]
    if len(chunk) < 20:
        return None

    # JPEG APP1 başlığı ilə sarıla
    app1 = b'\xff\xd8\xff\xe1'
    length = len(chunk) + 2
    if length > 65535:
        length = 65535
        chunk = chunk[: length - 2]

    payload = app1 + length.to_bytes(2, 'big') + chunk

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp.write(payload)
            tmp_path = tmp.name
        with open(tmp_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
        if not tags:
            return None
        return {
            str(k): str(v)[:200]
            for k, v in tags.items()
            if not str(k).startswith('Thumbnail')
        }
    except Exception:
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _gps_from_tag_dict(tag_dict):
    """String tag dict-dən GPS cəhdi."""
    lat = tag_dict.get('GPS GPSLatitude') or tag_dict.get('GPS Latitude')
    lat_ref = tag_dict.get('GPS GPSLatitudeRef') or tag_dict.get('GPS LatitudeRef')
    lon = tag_dict.get('GPS GPSLongitude') or tag_dict.get('GPS Longitude')
    lon_ref = tag_dict.get('GPS GPSLongitudeRef') or tag_dict.get('GPS LongitudeRef')
    if not all([lat, lat_ref, lon, lon_ref]):
        return None
    # String DMS parse: "[40, 49, 1234/100]" style from exifread str
    return {'raw_lat': lat, 'raw_lon': lon, 'display': f'{lat} {lat_ref}, {lon} {lon_ref}'}


def _scan_exif_segments(data):
    findings = []
    seen_offsets = set()
    start = 0
    while start < len(data):
        idx = data.find(EXIF_MARKER, start)
        if idx == -1:
            break
        if idx not in seen_offsets:
            seen_offsets.add(idx)
            tags = _try_parse_exif_at(data, idx)
            if tags:
                findings.append({
                    'type': 'exif_segment',
                    'offset': idx,
                    'offset_hex': hex(idx),
                    'tag_count': len(tags),
                    'tags': tags,
                    'confidence': 0.85,
                })
        start = idx + 6
    return findings


def _scan_xmp(data):
    found = []
    for marker in XMP_MARKERS:
        start = 0
        while start < len(data):
            idx = data.find(marker, start)
            if idx == -1:
                break
            snippet = data[idx:idx + 800].decode('utf-8', errors='replace')
            snippet = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', snippet)[:400]
            if snippet.strip():
                found.append({
                    'type': 'xmp_packet',
                    'offset': idx,
                    'offset_hex': hex(idx),
                    'preview': snippet.strip(),
                    'confidence': 0.7,
                })
            start = idx + len(marker)
    return found[:10]


def _scan_datetime_strings(data):
    found = []
    seen = set()
    for m in DATETIME_RE.finditer(data):
        dt = m.group(0).decode('ascii', errors='replace')
        if dt not in seen:
            seen.add(dt)
            found.append({
                'type': 'datetime_string',
                'offset': m.start(),
                'offset_hex': hex(m.start()),
                'value': dt,
                'confidence': 0.65,
            })
    return found[:15]


def _scan_camera_strings(data):
    found = []
    seen = set()
    for hint in CAMERA_HINTS:
        start = 0
        while start < len(data):
            idx = data.find(hint, start)
            if idx == -1:
                break
            ctx = data[max(0, idx - 20):idx + 60].decode('utf-8', errors='replace')
            ctx = re.sub(r'[^\x20-\x7e]', '.', ctx).strip()
            key = (hint.decode('ascii', errors='ignore'), ctx[:50])
            if key not in seen and len(ctx) > 3:
                seen.add(key)
                found.append({
                    'type': 'camera_string',
                    'offset': idx,
                    'offset_hex': hex(idx),
                    'hint': hint.decode('ascii', errors='ignore'),
                    'context': ctx[:80],
                    'confidence': 0.55,
                })
            start = idx + len(hint)
    return found[:12]


def _scan_iptc(data):
    findings = []
    start = 0
    while start < len(data):
        idx = data.find(IPTC_MARKER, start)
        if idx == -1:
            break
        findings.append({
            'type': 'iptc_photoshop',
            'offset': idx,
            'offset_hex': hex(idx),
            'confidence': 0.6,
        })
        start = idx + 12
    return findings[:5]


def _scan_decimal_gps_in_binary(data):
    """Binary mətnində decimal koordinat cütləri."""
    text = data.decode('utf-8', errors='ignore')
    found = []
    seen = set()
    for m in re.finditer(r'(-?\d{1,2}\.\d{5,})\s*[,;\s]\s*(-?\d{1,3}\.\d{5,})', text):
        lat, lon = float(m.group(1)), float(m.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180 and abs(lat) > 0.01:
            key = (round(lat, 5), round(lon, 5))
            if key not in seen:
                seen.add(key)
                loc = format_coordinates(lat, lon)
                if loc:
                    found.append({
                        'type': 'decimal_coordinates',
                        'latitude': lat,
                        'longitude': lon,
                        'display': loc.get('display'),
                        'confidence': 0.5,
                    })
    return found[:5]


def _gps_lat_lon_from_tags(tags: Dict[str, str]) -> Optional[Tuple[float, float]]:
    import ast
    lat_s = tags.get('GPS GPSLatitude')
    lat_ref = tags.get('GPS GPSLatitudeRef')
    lon_s = tags.get('GPS GPSLongitude')
    lon_ref = tags.get('GPS GPSLongitudeRef')
    if not all([lat_s, lat_ref, lon_s, lon_ref]):
        return None
    try:
        from utils.gps_converter import dms_to_decimal
        lat_vals = ast.literal_eval(str(lat_s).strip())
        lon_vals = ast.literal_eval(str(lon_s).strip())
        if not isinstance(lat_vals, (list, tuple)) or not isinstance(lon_vals, (list, tuple)):
            return None
        while len(lat_vals) < 3:
            lat_vals = list(lat_vals) + [0]
        while len(lon_vals) < 3:
            lon_vals = list(lon_vals) + [0]
        lat = dms_to_decimal(lat_vals[:3], str(lat_ref))
        lon = dms_to_decimal(lon_vals[:3], str(lon_ref))
        if lat is None or lon is None:
            return None
        return lat, lon
    except (SyntaxError, ValueError, TypeError):
        return None


def _merge_recovered_gps(exif_findings, decimal_gps):
    gps_list = list(decimal_gps)
    for block in exif_findings:
        tags = block.get('tags') or {}
        pair = _gps_lat_lon_from_tags(tags)
        if pair:
            lat, lon = pair
            loc = format_coordinates(lat, lon)
            if loc:
                gps_list.append({
                    **loc,
                    'source': 'carved_exif',
                    'confidence': 0.8,
                })
            continue
        gps = _gps_from_tag_dict(tags)
        if gps:
            gps_list.append({**gps, 'source': 'carved_exif', 'confidence': 0.8})
    return gps_list


def _diff_with_active(carved_items, active_tags, active_gps):
    """Aktiv metadata-da olmayan bərpa olunmuş izlər."""
    only_carved = []
    for item in carved_items:
        if item.get('type') == 'exif_segment':
            new_tags = []
            for k, v in (item.get('tags') or {}).items():
                entry = f'{k}={v}'
                if entry not in active_tags:
                    new_tags.append({k: v})
            if new_tags:
                only_carved.append({
                    **item,
                    'recovered_only_tags': new_tags,
                    'is_deleted_remnant': True,
                })
        elif item.get('type') in ('datetime_string', 'xmp_packet', 'camera_string', 'iptc_photoshop'):
            only_carved.append({**item, 'is_deleted_remnant': True})
        elif item.get('type') == 'decimal_coordinates':
            key = (round(item.get('latitude', 0), 5), round(item.get('longitude', 0), 5))
            if active_gps != key:
                only_carved.append({**item, 'is_deleted_remnant': True})
    return only_carved


def analyze_carved_metadata(filepath):
    """
    Silinmiş / qalıq metadata bərpası.
    """
    print('  [i] Silinmiş metadata bərpası (carving) başlayır...', file=sys.stderr)

    try:
        data, file_size = _read_file_bytes(filepath)
        active, active_meta = _active_metadata_snapshot(filepath)

        exif_blocks = _scan_exif_segments(data)
        xmp_blocks = _scan_xmp(data)
        datetime_hits = _scan_datetime_strings(data)
        camera_hits = _scan_camera_strings(data)
        iptc_hits = _scan_iptc(data)
        decimal_gps = _scan_decimal_gps_in_binary(data)

        all_carved = exif_blocks + xmp_blocks + datetime_hits + camera_hits + iptc_hits
        recovered_gps = _merge_recovered_gps(exif_blocks, decimal_gps)
        only_carved = _diff_with_active(all_carved, active['tags'], active['gps'])

        block_count = len(all_carved)
        remnant_count = len(only_carved)

        if not active['has_exif'] and block_count > 0:
            recovery_score = min(95, 40 + block_count * 8 + len(recovered_gps) * 15)
        elif remnant_count > 0:
            recovery_score = min(90, 20 + remnant_count * 10)
        else:
            recovery_score = 0 if block_count == 0 else 15

        status = 'success'
        if block_count == 0:
            status = 'no_carved_data'

        summary_parts = []
        if not active['has_exif'] and block_count:
            summary_parts.append('Aktiv EXIF yoxdur, lakin fayl daxilində köhnə metadata izləri tapıldı.')
        if remnant_count:
            summary_parts.append(f'{remnant_count} ədəd aktiv metadata-da olmayan qalıq tapıldı.')
        if recovered_gps and not active['has_gps']:
            summary_parts.append('Bərpa olunmuş GPS koordinat izləri mövcuddur.')
        if not summary_parts:
            summary_parts.append(
                'Gömük metadata tapılmadı və ya tapılanlar artıq aktiv metadata ilə eynidir.'
            )

        return {
            'status': status,
            'file_size_bytes': file_size,
            'scanned_bytes': len(data),
            'active_metadata': {
                'has_exif': active['has_exif'],
                'has_gps': active['has_gps'],
            },
            'carved_blocks_found': block_count,
            'deleted_remnants_found': remnant_count,
            'recovery_score': recovery_score,
            'recovered_gps': recovered_gps[:5],
            'recovered_datetimes': [d['value'] for d in datetime_hits[:8]],
            'findings': only_carved[:25],
            'all_carved_preview': [
                {'type': x['type'], 'offset_hex': x.get('offset_hex'), 'confidence': x.get('confidence')}
                for x in all_carved[:15]
            ],
            'summary': ' '.join(summary_parts),
            'note': (
                'Carved data sübut deyil — messencer sıxışdırması və ya redaktə sonrası '
                'qalan artefaktlar ola bilər. Orijinal faylla müqayisə edin.'
            ),
        }
    except Exception as e:
        print(f'  [!] Carved metadata: {e}', file=sys.stderr)
        return {'status': 'error', 'message': str(e)}
