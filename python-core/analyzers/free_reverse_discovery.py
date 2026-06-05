"""
Pulsuz tərs şəkil / məqalə URL kəşfiyyatı (Google Vision billing olmadan).
- Brave Search API (ayda ~2000 pulsuz sorğu — BRAVE_API_KEY)
- Yandex Images URL axtarışı (PUBLIC_APP_URL və ya şəkil URL; yalnız dəqiq uyğunluqlar)
- Portal linkləri (TinEye, Yandex, Lens — əl ilə, pulsuz)
"""

from __future__ import annotations

import html
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote, urlparse

import requests

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
)
TIMEOUT = 22
MAX_MATCHES = 14

# CDN host → veb axtarış üçün əsas domenlər
CDN_SITE_HINTS: Dict[str, List[str]] = {
    'ichef.bbci.co.uk': ['site:bbc.co.uk', 'site:bbc.com', 'site:bbci.co.uk'],
    'i.guim.co.uk': ['site:theguardian.com'],
    'cdn.cnn.com': ['site:cnn.com'],
    'media.npr.org': ['site:npr.org'],
    'nytimes.com': ['site:nytimes.com'],
}

SKIP_DOMAINS = (
    'yandex.', 'yastatic.', 'avatars.mds.', 'google.', 'gstatic.',
    'facebook.com', 'twitter.com', 'x.com', 'instagram.com',
    'pinterest.', 'pinimg.com', 'dreamstime.com', 'alamy.com',
    'shutterstock.', 'gettyimages.', 'istockphoto.',
)


def _env(key: str) -> Optional[str]:
    v = os.environ.get(key, '').strip()
    return v or None


def _image_stem(url: str) -> Optional[str]:
    if not url:
        return None
    path = urlparse(url).path
    base = os.path.basename(path).split('.')[0]
    if len(base) >= 6 and re.match(r'^[a-zA-Z0-9_-]+$', base):
        return base
    m = re.search(r'/([a-zA-Z0-9_-]{6,})(?:\.[a-z]+)?(?:/|$)', path)
    return m.group(1) if m else None


def _site_hints_for_url(image_url: str) -> List[str]:
    host = urlparse(image_url).netloc.lower()
    for cdn_host, queries in CDN_SITE_HINTS.items():
        if cdn_host in host or host.endswith(cdn_host):
            return list(queries)
    root = '.'.join(host.split('.')[-2:]) if host.count('.') >= 1 else host
    if root and len(root) > 3:
        return [f'site:{root}']
    return []


def _normalize(provider: str, page_url: str, **kw) -> Dict[str, Any]:
    from analyzers.reverse_image_search_analyzer import _normalize_match
    return _normalize_match(provider=provider, page_url=page_url, **kw)


def _filter_url(u: str, stem: Optional[str], allow_broad: bool = False) -> bool:
    if not u or not u.startswith('http'):
        return False
    low = u.lower()
    if any(s in low for s in SKIP_DOMAINS):
        return False
    if stem and stem.lower() in low:
        return True
    if allow_broad:
        path = urlparse(u).path.lower()
        return not re.search(r'\.(jpe?g|png|webp|gif)(\?|$)', path) or stem in path
    return False


def _search_brave(query: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    key = _env('BRAVE_API_KEY')
    meta: Dict[str, Any] = {'id': 'brave_web', 'status': 'skipped'}
    if not key:
        meta['status'] = 'needs_api_key'
        meta['message_az'] = (
            'BRAVE_API_KEY — pulsuz (~2000 sorğu/ay): https://brave.com/search/api/'
        )
        return [], meta
    try:
        resp = requests.get(
            'https://api.search.brave.com/res/v1/web/search',
            headers={'Accept': 'application/json', 'X-Subscription-Token': key},
            params={'q': query, 'count': 10},
            timeout=TIMEOUT,
        )
    except Exception as e:
        meta['status'] = 'error'
        meta['error'] = str(e)[:120]
        return [], meta
    if resp.status_code != 200:
        meta['status'] = 'error'
        meta['error'] = f'HTTP {resp.status_code}: {resp.text[:150]}'
        return [], meta
    data = resp.json()
    matches = []
    for item in (data.get('web', {}) or {}).get('results') or []:
        u = item.get('url') or ''
        if not u:
            continue
        matches.append(_normalize(
            'brave_web',
            u,
            title=item.get('title', ''),
            snippet=(item.get('description') or '')[:200],
            match_type='search_hit',
        ))
    meta['status'] = 'ok' if matches else 'empty'
    meta['match_count'] = len(matches)
    return matches[:MAX_MATCHES], meta


def _search_brave_for_cdn(image_url: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    stem = _image_stem(image_url)
    if not stem:
        return [], {'id': 'brave_web', 'status': 'skipped', 'message_az': 'Şəkil ID çıxarılmadı'}
    hints = _site_hints_for_url(image_url)
    queries = [f'{h} {stem}' for h in hints[:3]] or [f'"{stem}"']
    all_m: List[Dict[str, Any]] = []
    meta: Dict[str, Any] = {'id': 'brave_web', 'status': 'skipped'}
    for q in queries[:2]:
        m, meta = _search_brave(q)
        for x in m:
            if _filter_url(x.get('page_url', ''), stem, allow_broad=True):
                all_m.append(x)
        if all_m:
            break
    seen: Set[str] = set()
    uniq = []
    for x in all_m:
        u = x.get('page_url')
        if u and u not in seen:
            seen.add(u)
            uniq.append(x)
    meta['match_count'] = len(uniq)
    if uniq:
        meta['status'] = 'ok'
    return uniq[:MAX_MATCHES], meta


def _extract_yandex_page_urls(html_text: str, stem: Optional[str]) -> List[str]:
    text = html.unescape(html_text)
    raw = re.findall(
        r'https?://[a-zA-Z0-9][-a-zA-Z0-9.]*\.[a-zA-Z]{2,}(?:/[^\s"\'<>\\&]*)?',
        text,
    )
    out: List[str] = []
    seen: Set[str] = set()
    for u in raw:
        u = u.rstrip('.,;)\'"')
        if not _filter_url(u, stem, allow_broad=False):
            continue
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:MAX_MATCHES]


def _search_yandex_image_url(image_url: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Yandex — şəkil URL ilə; yalnız fayl adı/stem URL-də keçən səhifələr."""
    meta: Dict[str, Any] = {'id': 'yandex_url', 'status': 'skipped'}
    stem = _image_stem(image_url)
    if not stem:
        meta['message_az'] = 'Şəkil stem tapılmadı'
        return [], meta
    try:
        resp = requests.get(
            'https://yandex.com/images/search',
            params={'rpt': 'imageview', 'url': image_url},
            headers={'User-Agent': USER_AGENT, 'Accept-Language': 'en'},
            timeout=TIMEOUT,
        )
    except Exception as e:
        meta['status'] = 'error'
        meta['error'] = str(e)[:100]
        return [], meta
    if resp.status_code != 200:
        meta['status'] = 'error'
        meta['error'] = f'HTTP {resp.status_code}'
        return [], meta
    urls = _extract_yandex_page_urls(resp.text, stem)
    matches = [
        _normalize('yandex_url', u, match_type='exact_stem', title=u)
        for u in urls
    ]
    meta['status'] = 'ok' if matches else 'empty'
    meta['match_count'] = len(matches)
    return matches, meta


def _portal_links(image_url: str, public_url: Optional[str]) -> List[Dict[str, Any]]:
    from analyzers.portal_search_urls import build_portal_links
    pub = public_url or image_url
    return build_portal_links(pub)


def discover_free_reverse(
    filepath: str,
    *,
    image_urls: Optional[List[str]] = None,
    public_image_url: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Pulsuz mənbələrdən məqalə/şəkil URL-ləri.
    Vision/TinEye API olmadan.
    """
    image_urls = [u for u in (image_urls or []) if u and u.startswith('http')]
    primary = image_urls[0] if image_urls else None
    pub = public_image_url or primary

    all_matches: List[Dict[str, Any]] = []
    providers: List[Dict[str, Any]] = []

    if primary:
        print('  [i] Pulsuz axtarış: Brave / Yandex URL...', file=sys.stderr)
        bm, bmeta = _search_brave_for_cdn(primary)
        providers.append(bmeta)
        all_matches.extend(bm)

        ym, ymeta = _search_yandex_image_url(pub or primary)
        providers.append(ymeta)
        all_matches.extend(ym)

    seen: Set[str] = set()
    unique: List[Dict[str, Any]] = []
    for m in all_matches:
        u = m.get('page_url') or m.get('image_url')
        if u and u not in seen:
            seen.add(u)
            unique.append(m)

    portals = _portal_links(primary or '', pub if pub != primary else None)

    return unique[:MAX_MATCHES], {
        'status': 'ok' if unique else 'partial',
        'providers': providers,
        'match_count': len(unique),
        'manual_portals': portals,
        'message_az': (
            'Pulsuz avtomatik axtarış: Brave API və ya Yandex (dəqiq stem). '
            'TinEye ilə eyni tarix üçün portalda «TinEye (veb)» və ya TINEYE_API_KEY.'
            if not unique
            else f'{len(unique)} URL tapıldı (Brave/Yandex).'
        ),
    }
