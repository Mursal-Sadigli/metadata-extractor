"""Sosial metadata vahid cavab sxemi."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def empty_result(input_type: str = 'url') -> Dict[str, Any]:
    return {
        'status': 'success',
        'platform': None,
        'input_type': input_type,
        'confidence': 0.0,
        'sources': [],
        'unique_ids': {
            'content_id': None,
            'display_id': None,
            'uploader_id': None,
            'channel_id': None,
            'shortcode': None,
            'webpage_url': None,
        },
        'upload_date': None,
        'upload_date_iso': None,
        'location': {
            'latitude': None,
            'longitude': None,
            'place_name': None,
            'source': 'none',
        },
        'device': {
            'make': None,
            'model': None,
            'software': None,
            'os': None,
            'source': 'none',
        },
        'author': {'name': None, 'id': None},
        'engagement': {'views': None, 'likes': None, 'comments': None},
        'media': {'duration_sec': None, 'width': None, 'height': None},
        'title': None,
        'description': None,
        'tags': [],
        'thumbnail_url': None,
        'thumbnail_file': None,
        'thumbnail_exif': None,
        'thumbnail_location': None,
        'warnings': [],
        'raw': {},
    }


def error_result(message: str, input_type: str = 'url') -> Dict[str, Any]:
    out = empty_result(input_type)
    out['status'] = 'error'
    out['error'] = message
    return out


def format_upload_date(raw_date=None, timestamp=None) -> tuple:
    """(display, iso) tuple."""
    if timestamp is not None:
        try:
            dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
            return dt.strftime('%Y.%m.%d %H:%M UTC'), dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        except (TypeError, ValueError, OSError):
            pass

    if not raw_date:
        return None, None

    s = re.sub(r'\D', '', str(raw_date))
    if len(s) >= 14:
        try:
            dt = datetime.strptime(s[:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
            return dt.strftime('%Y.%m.%d %H:%M UTC'), dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            pass
    if len(s) >= 8:
        return f'{s[0:4]}.{s[4:6]}.{s[6:8]}', f'{s[0:4]}-{s[4:6]}-{s[6:8]}'

    return str(raw_date), None


def merge_location(result: Dict[str, Any], lat, lon, place_name=None, source='platform'):
    loc = result['location']
    if lat is not None and lon is not None and loc.get('latitude') is None:
        try:
            loc['latitude'] = float(lat)
            loc['longitude'] = float(lon)
            loc['source'] = source
        except (TypeError, ValueError):
            pass
    if place_name and not loc.get('place_name'):
        loc['place_name'] = place_name
        if loc['source'] == 'none':
            loc['source'] = source


def merge_device(result: Dict[str, Any], make=None, model=None, software=None, os_name=None, source='metadata'):
    dev = result['device']
    if make and not dev.get('make'):
        dev['make'] = make
        dev['source'] = source
    if model and not dev.get('model'):
        dev['model'] = model
        dev['source'] = source
    if software and not dev.get('software'):
        dev['software'] = software
        dev['source'] = source
    if os_name and not dev.get('os'):
        dev['os'] = os_name
        dev['source'] = source


def add_source(result: Dict[str, Any], source: str):
    if source and source not in result['sources']:
        result['sources'].append(source)


def add_warning(result: Dict[str, Any], message: str):
    if message and message not in result['warnings']:
        result['warnings'].append(message)


def compute_confidence(result: Dict[str, Any]) -> float:
    score = 0.0
    ids = result.get('unique_ids') or {}
    if ids.get('content_id'):
        score += 0.25
    if ids.get('uploader_id') or result.get('author', {}).get('id'):
        score += 0.15
    if result.get('upload_date'):
        score += 0.15
    loc = result.get('location') or {}
    if loc.get('latitude') is not None:
        score += 0.15
    dev = result.get('device') or {}
    if dev.get('make') or dev.get('software'):
        score += 0.1
    if result.get('title') or result.get('description'):
        score += 0.05
    eng = result.get('engagement') or {}
    if any(eng.get(k) for k in ('views', 'likes', 'comments')):
        score += 0.05
    if 'yt-dlp' in result.get('sources', []):
        score += 0.1
    return round(min(1.0, score), 2)


def finalize(result: Dict[str, Any]) -> Dict[str, Any]:
    result['confidence'] = compute_confidence(result)
    return result
