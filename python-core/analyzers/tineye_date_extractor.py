"""
TinEye və tərs axtarış nəticələrindən ən erkən tarix (ilk internet izi).
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

MAX_FILE_BYTES = 8 * 1024 * 1024

URL_DATE_PATTERNS = [
    re.compile(r'/(\d{4})/(\d{1,2})/(\d{1,2})(?:/|$)', re.I),
    re.compile(r'/(\d{4})-(\d{1,2})-(\d{1,2})(?:/|$)', re.I),
    re.compile(r'[?&]date=(\d{4})-(\d{1,2})-(\d{1,2})', re.I),
    re.compile(r'/(\d{4})/(\d{2})(\d{2})_', re.I),
]


def _env(key: str) -> Optional[str]:
    v = os.environ.get(key, '').strip()
    return v or None


def _public_url(filepath: str) -> Optional[str]:
    base = _env('PUBLIC_APP_URL') or _env('PUBLIC_IMAGE_BASE_URL')
    if not base or not filepath:
        return None
    from urllib.parse import quote
    return f'{base.rstrip("/")}/uploads/{quote(os.path.basename(filepath))}'


def _parse_crawl_date(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = str(s).strip()[:10]
    try:
        return datetime.strptime(s, '%Y-%m-%d')
    except ValueError:
        return None


def _dates_from_url(url: str) -> List[datetime]:
    if not url:
        return []
    found = []
    for pat in URL_DATE_PATTERNS:
        for m in pat.finditer(url):
            try:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if 1995 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
                    found.append(datetime(y, mo, d))
            except (ValueError, IndexError):
                continue
    return found


def _parse_tineye_response(data: Dict[str, Any]) -> Tuple[List[datetime], List[Dict[str, Any]], Optional[str]]:
    if data.get('code') != 200:
        err = data.get('messages', {})
        if isinstance(err, dict) and err.get('error'):
            return [], [], str(err['error'][0])
        return [], [], 'TinEye API xətası'

    dates: List[datetime] = []
    details: List[Dict[str, Any]] = []
    for m in (data.get('results', {}) or {}).get('matches', []):
        domain = m.get('domain', '')
        for bl in m.get('backlinks') or []:
            crawl = _parse_crawl_date(bl.get('crawl_date'))
            page_url = bl.get('backlink') or bl.get('url') or ''
            if crawl:
                dates.append(crawl)
                details.append({
                    'date': crawl.strftime('%Y-%m-%d'),
                    'crawl_date': bl.get('crawl_date'),
                    'page_url': page_url,
                    'domain': domain,
                })
            for dt in _dates_from_url(page_url):
                dates.append(dt)
                details.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'source': 'url_path',
                    'page_url': page_url,
                    'domain': domain,
                })
            for dt in _dates_from_url(bl.get('url') or ''):
                dates.append(dt)
    return dates, details, None


def _tineye_api_request(
    filepath: str,
    *,
    image_url: Optional[str] = None,
    sort: str = 'crawl_date',
    order: str = 'asc',
    limit: int = 80,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    api_key = _env('TINEYE_API_KEY')
    if not api_key:
        return None, 'TINEYE_API_KEY yoxdur'

    headers = {'x-api-key': api_key}
    params = {'limit': limit, 'sort': sort, 'order': order}
    api_url = 'https://api.tineye.com/rest/search/'

    try:
        if image_url:
            resp = requests.post(
                api_url, headers=headers, params=params,
                data={'url': image_url}, timeout=45,
            )
        else:
            with open(filepath, 'rb') as f:
                img = f.read()
            if len(img) > MAX_FILE_BYTES:
                return None, 'Fayl çox böyükdür'
            resp = requests.post(
                api_url, headers=headers, params=params,
                files={'image': (os.path.basename(filepath), img)},
                timeout=60,
            )
    except Exception as e:
        return None, str(e)

    if resp.status_code != 200:
        return None, f'HTTP {resp.status_code}'

    try:
        return resp.json(), None
    except Exception:
        return None, 'JSON xətası'


def _tineye_api_search(
    filepath: str,
    public_url: Optional[str],
    sort: str = 'crawl_date',
    order: str = 'asc',
    limit: int = 80,
) -> Tuple[List[datetime], List[Dict[str, Any]], Optional[str]]:
    data, err = _tineye_api_request(
        filepath, image_url=public_url, sort=sort, order=order, limit=limit,
    )
    if err:
        return [], [], err
    if not data:
        return [], [], 'TinEye cavabı boşdur'
    return _parse_tineye_response(data)


def extract_tineye_earliest_date(
    filepath: str,
    public_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    TinEye indeksindən ən erkən tarix — TinEye.com veb UI ilə uyğunlaşır.
    Əvvəl orijinal şəkil URL (sidecar), sonra fayl yükləməsi.
    """
    from analyzers.portal_search_urls import resolve_tineye_search_urls

    fn = os.path.basename(filepath)
    url_candidates = resolve_tineye_search_urls(fn, filepath, public_url)

    all_dates: List[datetime] = []
    all_details: List[Dict] = []
    errors: List[str] = []
    methods_tried: List[str] = []

    def _collect(use_url: Optional[str]) -> None:
        label = f'url:{use_url[:80]}' if use_url else 'file_upload'
        if label in methods_tried:
            return
        methods_tried.append(label)
        dts, det, err = _tineye_api_search(
            filepath, use_url, sort='crawl_date', order='asc', limit=100,
        )
        if err:
            errors.append(err)
            if use_url:
                print(f'  [!] TinEye URL ({use_url[:70]}…): {err}', file=sys.stderr)
            else:
                print(f'  [!] TinEye fayl yükləmə: {err}', file=sys.stderr)
            return
        if dts:
            if use_url:
                print(f'  [+] TinEye URL tapıntı: {len(dts)} tarix ({use_url[:70]}…)', file=sys.stderr)
            else:
                print(f'  [+] TinEye fayl yükləmə: {len(dts)} tarix', file=sys.stderr)
        all_dates.extend(dts)
        all_details.extend(det)

    for url in url_candidates:
        _collect(url)
        if all_dates:
            break

    if not all_dates:
        _collect(None)

    if not all_dates:
        return {
            'status': 'unavailable',
            'error': errors[0] if errors else 'Tarix tapılmadı',
            'needs_api_key': any('TINEYE_API_KEY yoxdur' in (e or '') for e in errors),
            'urls_tried': url_candidates,
            'methods_tried': methods_tried,
        }

    earliest = min(all_dates)
    same_day = sum(1 for d in all_dates if d.date() == earliest.date())
    confidence = min(0.97, 0.88 + min(same_day, 10) * 0.008)

    return {
        'status': 'success',
        'earliest': earliest,
        'iso_date': earliest.strftime('%Y-%m-%d'),
        'match_count': len(all_details),
        'confirmations': same_day,
        'confidence': confidence,
        'details': all_details[:15],
        'tineye_matches_sample': all_details[:5],
        'methods_tried': methods_tried,
    }
