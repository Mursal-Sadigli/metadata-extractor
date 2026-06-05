"""
Şəklin internetdə yayılma xronologiyası (TinEye olmadan).
Google Vision / SerpAPI uyğunluqları + Wayback Machine + səhifə metadata.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import requests

from analyzers.web_image_metadata import USER_AGENT

MAX_URLS_ENRICH = 18
MAX_WAYBACK_URLS = 14
WAYBACK_TIMEOUT = 18
PAGE_TIMEOUT = 10

GOOGLE_DOMAINS = (
    'google.com', 'google.az', 'google.ru', 'googleusercontent.com',
    'ggpht.com', 'gstatic.com', 'blogspot.com', 'blogger.com',
    'googleapis.com', 'goo.gl',
)

PAGE_DATE_PATTERNS = [
    (re.compile(r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)', re.I), 'published'),
    (re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']article:published_time', re.I), 'published'),
    (re.compile(r'<meta[^>]+property=["\']article:modified_time["\'][^>]+content=["\']([^"\']+)', re.I), 'modified'),
    (re.compile(r'<meta[^>]+property=["\']og:updated_time["\'][^>]+content=["\']([^"\']+)', re.I), 'modified'),
    (re.compile(r'<meta[^>]+property=["\']og:published_time["\'][^>]+content=["\']([^"\']+)', re.I), 'published'),
    (re.compile(r'"datePublished"\s*:\s*"([^"]+)"', re.I), 'published'),
    (re.compile(r'"dateModified"\s*:\s*"([^"]+)"', re.I), 'modified'),
]

MONTHS_AZ = (
    '', 'yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
    'iyul', 'avqust', 'sentyabr', 'oktyabr', 'noyabr', 'dekabr',
)


def _format_az(dt: datetime) -> str:
    if dt.month < 1 or dt.month > 12:
        return dt.strftime('%Y-%m-%d')
    return f'{dt.day} {MONTHS_AZ[dt.month]} {dt.year}'


def _parse_iso_date(text: str) -> Optional[datetime]:
    if not text:
        return None
    s = str(text).strip()[:25].replace('Z', '+00:00')
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s[:19] if 'T' in fmt else s[:10], fmt)
        except ValueError:
            continue
    return None


def _wayback_ts_to_dt(ts: str) -> Optional[datetime]:
    if not ts or len(ts) < 8:
        return None
    try:
        return datetime.strptime(ts[:8], '%Y%m%d')
    except ValueError:
        return None


def _is_google_domain(domain: str) -> bool:
    d = (domain or '').lower().lstrip('www.')
    return any(d == g or d.endswith('.' + g) for g in GOOGLE_DOMAINS)


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ''


def _collect_urls_from_providers(providers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """TinEye istisna — Google, SerpAPI, Bing uyğunluqları."""
    refs: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    skip_providers = {'tineye', 'tineye_web', 'tineye_home'}

    for prov in providers or []:
        pid = prov.get('id', '')
        if pid in skip_providers or prov.get('status') != 'ok':
            continue
        for m in prov.get('matches') or []:
            for u in (m.get('page_url'), m.get('image_url'), m.get('backlink')):
                if not u or not u.startswith('http') or u in seen:
                    continue
                seen.add(u)
                dom = _domain(u)
                refs.append({
                    'url': u,
                    'domain': dom,
                    'is_google': _is_google_domain(dom),
                    'provider': pid,
                    'match_type': m.get('match_type', ''),
                    'title': (m.get('title') or '')[:120],
                })
    return refs


def _wayback_history(url: str) -> Dict[str, Any]:
    """Wayback CDX — ən erkən, son, digest dəyişiklikləri (redaktə izləri)."""
    out: Dict[str, Any] = {
        'url': url,
        'available': False,
        'earliest': None,
        'latest': None,
        'snapshot_count': 0,
        'modifications': [],
    }
    try:
        resp = requests.get(
            'https://web.archive.org/cdx/search/cdx',
            params={
                'url': url,
                'output': 'json',
                'fl': 'timestamp,digest,statuscode',
                'filter': 'statuscode:200',
                'collapse': 'digest',
                'limit': 40,
            },
            timeout=WAYBACK_TIMEOUT,
            headers={'User-Agent': USER_AGENT},
        )
        if resp.status_code != 200:
            return out
        rows = resp.json()
        if not rows or len(rows) < 2:
            return out
        snapshots = []
        for row in rows[1:]:
            if len(row) < 2:
                continue
            ts, digest = row[0], row[1] if len(row) > 1 else ''
            dt = _wayback_ts_to_dt(ts)
            if dt:
                snapshots.append({'timestamp': ts, 'iso_date': dt.strftime('%Y-%m-%d'), 'digest': digest, 'dt': dt})
        if not snapshots:
            return out
        snapshots.sort(key=lambda x: x['dt'])
        out['available'] = True
        out['earliest'] = snapshots[0]
        out['latest'] = snapshots[-1]
        out['snapshot_count'] = len(snapshots)
        prev_digest = None
        for i, snap in enumerate(snapshots):
            if prev_digest and snap['digest'] != prev_digest:
                out['modifications'].append({
                    'iso_date': snap['iso_date'],
                    'display_az': _format_az(snap['dt']),
                    'wayback_url': f"https://web.archive.org/web/{snap['timestamp']}/{url}",
                    'note_az': 'Arxivdə məzmun dəyişib (digest fərqi)',
                })
            prev_digest = snap['digest']
    except Exception as e:
        out['error'] = str(e)[:100]
    return out


def _page_dates(url: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not url.startswith('http'):
        return out
    try:
        resp = requests.get(
            url,
            headers={'User-Agent': USER_AGENT, 'Accept': 'text/html'},
            timeout=PAGE_TIMEOUT,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return out
        html = resp.text[:200000]
        for pat, key in PAGE_DATE_PATTERNS:
            m = pat.search(html)
            if m and key not in out:
                parsed = _parse_iso_date(m.group(1))
                if parsed:
                    out[key] = parsed.strftime('%Y-%m-%d')
                    out[f'{key}_display_az'] = _format_az(parsed)
    except Exception as e:
        out['fetch_error'] = str(e)[:80]
    return out


def _file_md5(filepath: str) -> str:
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _build_events(
    refs: List[Dict[str, Any]],
    wayback_by_url: Dict[str, Dict],
    page_by_url: Dict[str, Dict],
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []

    for ref in refs:
        url = ref['url']
        dom = ref['domain']
        wb = wayback_by_url.get(url) or {}
        pg = page_by_url.get(url) or {}

        if ref.get('is_google') and wb.get('earliest'):
            e = wb['earliest']
            events.append({
                'iso_date': e['iso_date'],
                'display_az': _format_az(e['dt']),
                'event_type': 'google_first_archive',
                'source': 'wayback',
                'domain': dom,
                'page_url': url,
                'provider': ref.get('provider'),
                'confidence': 0.82,
                'note_az': 'Google ekosistemində Wayback-də ilk arxiv izi',
                'wayback_url': f"https://web.archive.org/web/{e['timestamp']}/{url}",
            })

        if wb.get('earliest') and not ref.get('is_google'):
            e = wb['earliest']
            events.append({
                'iso_date': e['iso_date'],
                'display_az': _format_az(e['dt']),
                'event_type': 'site_first_seen',
                'source': 'wayback',
                'domain': dom,
                'page_url': url,
                'provider': ref.get('provider'),
                'confidence': 0.78,
                'note_az': 'Saytda ilk arxiv snapshot (Wayback)',
                'wayback_url': f"https://web.archive.org/web/{e['timestamp']}/{url}",
            })

        for mod in wb.get('modifications') or []:
            events.append({
                'iso_date': mod['iso_date'],
                'display_az': mod['display_az'],
                'event_type': 'content_modified',
                'source': 'wayback',
                'domain': dom,
                'page_url': url,
                'provider': ref.get('provider'),
                'confidence': 0.72,
                'note_az': mod.get('note_az', 'Məzmun dəyişib'),
                'wayback_url': mod.get('wayback_url'),
            })

        if pg.get('published'):
            events.append({
                'iso_date': pg['published'],
                'display_az': pg.get('published_display_az', pg['published']),
                'event_type': 'page_published',
                'source': 'page_meta',
                'domain': dom,
                'page_url': url,
                'provider': ref.get('provider'),
                'confidence': 0.7,
                'note_az': 'Səhifə metadata — dərc tarixi',
            })
        if pg.get('modified') and pg.get('modified') != pg.get('published'):
            events.append({
                'iso_date': pg['modified'],
                'display_az': pg.get('modified_display_az', pg['modified']),
                'event_type': 'page_modified',
                'source': 'page_meta',
                'domain': dom,
                'page_url': url,
                'provider': ref.get('provider'),
                'confidence': 0.68,
                'note_az': 'Səhifə metadata — son redaktə',
            })

        if ref.get('provider') in ('google_vision', 'google_lens', 'google_lens_serpapi'):
            events.append({
                'iso_date': datetime.utcnow().strftime('%Y-%m-%d'),
                'display_az': 'bu gün',
                'event_type': 'google_match_now',
                'source': 'google_api',
                'domain': dom,
                'page_url': url,
                'provider': ref['provider'],
                'confidence': 0.95,
                'note_az': 'Google Vision/Lens hazırda bu URL-i uyğunluq kimi göstərir',
                'title': ref.get('title'),
            })

    # Dedupe: same date+type+url
    seen_ev: Set[Tuple] = set()
    unique: List[Dict] = []
    for ev in events:
        key = (ev.get('iso_date'), ev.get('event_type'), ev.get('page_url'))
        if key in seen_ev:
            continue
        seen_ev.add(key)
        unique.append(ev)

    unique.sort(key=lambda x: (x.get('iso_date') or '9999', x.get('event_type', '')))
    return unique


def analyze_image_web_timeline(
    filepath: str,
    public_image_url: Optional[str] = None,
    providers: Optional[List[Dict[str, Any]]] = None,
    skip_google_api: bool = False,
) -> Dict[str, Any]:
    """
    TinEye istifadə etmədən şəklin veb yayılma xronologiyası.
    """
    if not filepath or not os.path.isfile(filepath):
        return {
            'module': 'image_web_timeline',
            'status': 'error',
            'error': 'Şəkil faylı tapılmadı',
            'summary_az': 'Fayl mövcud deyil.',
        }

    print('  [i] Veb şəkil xronologiyası (Google + Wayback)...', file=sys.stderr)

    prov_list = list(providers or [])
    if not prov_list and not skip_google_api:
        from analyzers.reverse_image_search_analyzer import (
            _public_image_url,
            _search_google_vision,
            _search_serpapi,
        )
        fn = os.path.basename(filepath)
        pub = public_image_url or _public_image_url(fn, public_image_url)
        prov_list = [
            _search_google_vision(filepath),
            _search_serpapi(pub, filepath),
        ]

    refs = _collect_urls_from_providers(prov_list)
    google_refs = [r for r in refs if r['is_google']]
    other_refs = [r for r in refs if not r['is_google']]

    # Prioritet: Google URL-lər, sonra digər saytlar
    enrich_order = (google_refs + other_refs)[:MAX_URLS_ENRICH]
    wayback_urls = [r['url'] for r in enrich_order[:MAX_WAYBACK_URLS]]

    wayback_by_url: Dict[str, Dict] = {}
    page_by_url: Dict[str, Dict] = {}

    for url in wayback_urls:
        wayback_by_url[url] = _wayback_history(url)

    for ref in enrich_order[:10]:
        u = ref['url']
        if u.startswith('http') and '.' in _domain(u):
            page_by_url[u] = _page_dates(u)

    events = _build_events(enrich_order, wayback_by_url, page_by_url)

    google_archive_dates = [
        e['iso_date'] for e in events
        if e.get('event_type') == 'google_first_archive' and e.get('iso_date')
    ]
    site_dates = [
        e['iso_date'] for e in events
        if e.get('event_type') in ('site_first_seen', 'page_published') and e.get('iso_date')
    ]
    mod_events = [e for e in events if e.get('event_type') in ('content_modified', 'page_modified')]

    google_first = min(google_archive_dates) if google_archive_dates else None
    first_site = min(site_dates) if site_dates else None

    sites_after_google: List[Dict[str, Any]] = []
    if google_first:
        for ref in other_refs:
            wb = wayback_by_url.get(ref['url']) or {}
            earliest = (wb.get('earliest') or {}).get('iso_date')
            pub = (page_by_url.get(ref['url']) or {}).get('published')
            first_on_site = earliest or pub
            if first_on_site and first_on_site >= google_first:
                disp = pub
                if wb.get('earliest'):
                    disp = _format_az(wb['earliest']['dt'])
                sites_after_google.append({
                    'domain': ref['domain'],
                    'page_url': ref['url'],
                    'first_seen': first_on_site,
                    'display_az': disp,
                    'provider': ref.get('provider'),
                    'after_google': True,
                })

    sites_after_google.sort(key=lambda x: x.get('first_seen', ''))

    try:
        local_md5 = _file_md5(filepath)
    except OSError:
        local_md5 = ''

    result = {
        'module': 'image_web_timeline',
        'status': 'ok' if events else 'partial',
        'uses_tineye': False,
        'local_file_md5': local_md5,
        'google': {
            'first_archive_date': google_first,
            'first_archive_display_az': (
                _format_az(datetime.strptime(google_first, '%Y-%m-%d'))
                if google_first else None
            ),
            'match_count': len(google_refs),
            'lens_search_url': None,
        },
        'sites': {
            'total_references': len(refs),
            'domains': sorted({r['domain'] for r in refs if r['domain']})[:30],
            'added_after_google': sites_after_google[:25],
        },
        'modifications': {
            'count': len(mod_events),
            'events': mod_events[:20],
        },
        'timeline': events[:40],
        'providers_used': [
            {'id': p.get('id'), 'status': p.get('status'), 'matches': p.get('match_count', 0)}
            for p in prov_list
        ],
        'limitations_az': (
            'Google dəqiq indekslənmə tarixi ictimai API ilə verilmir; '
            'Wayback arxivi və səhifə metadata istifadə olunur. '
            'Bəzi saytlar arxivdə olmaya bilər.'
        ),
    }

    pub = public_image_url
    if pub:
        result['google']['lens_search_url'] = f'https://lens.google.com/uploadbyurl?url={pub}'

    if not events:
        result['status'] = 'no_data'
        result['summary_az'] = (
            'Uyğunluq tapılmadı. GOOGLE_VISION_API_KEY və PUBLIC_APP_URL yoxlayın; '
            'şəkil internetdə indekslənməyə bilər.'
        )
    else:
        parts = []
        if google_first:
            parts.append(f'Google arxivində ilk iz: {result["google"]["first_archive_display_az"]}.')
        elif google_refs:
            parts.append(f'Google {len(google_refs)} uyğunluq (Wayback tarixi yoxdur).')
        if first_site and (not google_first or first_site != google_first):
            parts.append(f'Ən erkən sayt izi: {first_site}.')
        if sites_after_google:
            parts.append(f'Google-dan sonra {len(sites_after_google)} sayt.')
        if mod_events:
            parts.append(f'{len(mod_events)} dəyişiklik/redaktə izi.')
        result['summary_az'] = ' '.join(parts) if parts else f'{len(events)} hadisə toplandı.'

    return result
