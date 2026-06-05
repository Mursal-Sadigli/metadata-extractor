"""
Tərs şəkil portal linkləri — xarici servislərin şəkil URL ilə avtomatik axtarışı.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse


def _is_fetchable_url(url: Optional[str]) -> bool:
    if not url or not str(url).startswith('http'):
        return False
    low = str(url).lower()
    if 'localhost' in low or '127.0.0.1' in low:
        return False
    return True


def is_indexed_image_url(url: Optional[str]) -> bool:
    """
    TinEye və portallar üçün orijinal şəkil URL-i.
    ngrok / localhost / müvəqqəti uploads linkləri indeksdə olmur.
    """
    if not _is_fetchable_url(url):
        return False
    low = str(url).lower()
    if 'ngrok' in low:
        return False
    path = urlparse(url).path
    if re.search(r'/uploads/\d', path):
        return False
    return True


def resolve_tineye_search_urls(
    filename: str,
    filepath: Optional[str] = None,
    explicit_url: Optional[str] = None,
) -> List[str]:
    """TinEye API üçün URL siyahısı — əvvəl orijinal mənbə, sonda ngrok/uploads."""
    urls: List[str] = []

    if is_indexed_image_url(explicit_url) and explicit_url not in urls:
        urls.append(explicit_url)

    if filepath:
        try:
            from analyzers.web_image_metadata import load_url_sidecar
            sc = load_url_sidecar(filepath)
            if sc:
                for key in ('resolved_url', 'source_url'):
                    u = sc.get(key)
                    if is_indexed_image_url(u) and u not in urls:
                        urls.append(u)
        except Exception:
            pass

    if not urls:
        pub, _ = resolve_search_image_url(filename, explicit_url, filepath)
        if pub and _is_fetchable_url(pub) and pub not in urls:
            urls.append(pub)
    return urls


def resolve_search_image_url(
    filename: str,
    explicit_url: Optional[str] = None,
    filepath: Optional[str] = None,
) -> Tuple[Optional[str], str]:
    """
    Xarici tərs-şəkil servislərinin çəkə biləcəyi URL.
    Prioritet: explicit (fetchable) → sidecar resolved/source → PUBLIC_APP_URL/uploads
    """
    if _is_fetchable_url(explicit_url):
        return explicit_url, 'explicit'

    if filepath:
        try:
            from analyzers.web_image_metadata import load_url_sidecar
            sc = load_url_sidecar(filepath)
            if sc:
                for key in ('resolved_url', 'source_url'):
                    u = sc.get(key)
                    if _is_fetchable_url(u):
                        return u, key
        except Exception:
            pass

    base = (os.environ.get('PUBLIC_APP_URL') or os.environ.get('PUBLIC_IMAGE_BASE_URL') or '').strip()
    if base and filename:
        u = f'{base.rstrip("/")}/uploads/{quote(os.path.basename(filename))}'
        if _is_fetchable_url(u):
            return u, 'public_app'

    return None, ''


def build_portal_links(search_url: Optional[str]) -> List[Dict[str, Any]]:
    """Portal linkləri — search_url varsa hər biri avtomatik şəkil axtarışı açır."""
    if not _is_fetchable_url(search_url):
        return [
            {
                'id': 'hint',
                'name': 'URL lazımdır',
                'search_url': '',
                'method': 'info',
                'note_az': (
                    'Şəkli birbaşa şəkil URL-indən yükləyin (məs. BBC ichef linki) və ya '
                    '.env-də PUBLIC_APP_URL (ngrok) təyin edin.'
                ),
            },
        ]

    enc = quote(search_url, safe='')
    links: List[Dict[str, Any]] = [
        {
            'id': 'google_lens',
            'name': 'Google Lens',
            'search_url': f'https://lens.google.com/uploadbyurl?url={enc}',
            'method': 'url',
            'note_az': 'Şəkil URL ilə avtomatik Lens axtarışı',
        },
        {
            'id': 'google_images',
            'name': 'Google Images',
            'search_url': f'https://www.google.com/searchbyimage?image_url={enc}&safe=off',
            'method': 'url',
            'note_az': 'Google — şəkil URL ilə tərs axtarış',
        },
        {
            'id': 'yandex_images',
            'name': 'Yandex Images',
            'search_url': f'https://yandex.com/images/search?rpt=imageview&url={enc}',
            'method': 'url',
            'note_az': 'Yandex — şəkil URL ilə avtomatik axtarış',
        },
        {
            'id': 'tineye_web',
            'name': 'TinEye (veb)',
            'search_url': f'https://tineye.com/search?url={enc}',
            'method': 'url',
            'note_az': 'TinEye — şəkil URL ilə avtomatik axtarış',
        },
        {
            'id': 'tineye',
            'name': 'TinEye',
            'search_url': f'https://tineye.com/search?url={enc}',
            'method': 'url',
            'note_az': 'TinEye əsas səhifə — eyni URL axtarışı',
        },
        {
            'id': 'bing_images',
            'name': 'Bing Images',
            'search_url': (
                f'https://www.bing.com/images/search?view=detailv2&iss=sbiupload'
                f'&sbisrc=ImgPaste&q=imgurl:{enc}'
            ),
            'method': 'url',
            'note_az': 'Bing — şəkil URL ilə tərs axtarış',
        },
    ]

    host = urlparse(search_url).netloc.lower()
    if re.search(r'\.(jpe?g|png|webp|gif|avif|bmp)(\?|$)', urlparse(search_url).path, re.I):
        links.append({
            'id': 'direct_image',
            'name': 'Şəkil linki',
            'search_url': search_url,
            'method': 'url',
            'note_az': 'Orijinal şəkil URL (yüklədiyiniz mənbə)',
        })

    links.append({
        'id': 'pimeyes',
        'name': 'PimEyes',
        'search_url': 'https://pimeyes.com/en',
        'method': 'manual_upload',
        'note_az': (
            'PimEyes URL ilə avtomatik açmır — şəkil faylını sayta sürüşdürün. '
            f'Və ya əvvəlcə TinEye/Lens ilə eyni şəkli tapın.'
        ),
        'privacy_warning': True,
    })
    return links
