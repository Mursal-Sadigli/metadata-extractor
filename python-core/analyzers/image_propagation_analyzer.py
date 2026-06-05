"""
Tarix və yayılma analizi — Wayback, səhifə indeksi, şəkil variantları.
Böyük indeks yox; yalnız tapılan URL-lər və opsional tərs axtarış.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, quote, urlparse

from analyzers.image_web_timeline_analyzer import (
    MONTHS_AZ,
    _format_az,
    _page_dates,
    _parse_iso_date,
    _wayback_history,
)

VARIANT_URL_PATTERNS = (
    (re.compile(r'[?&](w|width|h|height|resize|size)=', re.I), 'url_params'),
    (re.compile(r'/(thumb|thumbnail|small|medium|large|preview|crop)/', re.I), 'path_resize'),
    (re.compile(r'[-_](thumb|small|sm|md|lg|xl|\d+x\d+)(\.|/|$)', re.I), 'filename_suffix'),
    (re.compile(r'/resize/|/crop/|/scale/', re.I), 'cdn_resize'),
)

CDN_HOST_HINTS = (
    'ichef.', 'cdn.', 'static.', 'img.', 'images.', 'media.', 'assets.',
    'cloudfront.net', 'akamaized.net', 'wp.com', 'ggpht.com',
)
CDN_PATH_HINTS = re.compile(
    r'/images/|/image/|/photo/|/thumb|/resize/|/crop/|/480xn/|/976xn/',
    re.I,
)


def _image_hashes(filepath: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    try:
        md5 = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                md5.update(chunk)
        out['md5'] = md5.hexdigest()
        out['image_hash'] = f'md5:{out["md5"]}'
    except OSError:
        pass
    try:
        import imagehash
        from PIL import Image
        ph = imagehash.phash(Image.open(filepath))
        out['phash'] = str(ph)
        out['image_hash'] = f'phash:{ph}|{out.get("md5", "")}'
    except Exception:
        if 'md5' in out:
            out['image_hash'] = f'md5:{out["md5"]}'
    return out


def _is_likely_page_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    if re.search(r'\.(jpe?g|png|webp|gif|avif|bmp|svg)(\?|$)', path):
        return False
    if '/images/' in path and re.search(r'\.(jpe?g|png|webp)', path):
        return False
    return True


def _is_cdn_image_url(url: str) -> bool:
    if not url or _is_likely_page_url(url):
        return False
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    if any(h in host for h in CDN_HOST_HINTS):
        return True
    return bool(CDN_PATH_HINTS.search(path))


def _site_root(netloc: str) -> str:
    parts = (netloc or '').lower().lstrip('www.').split('.')
    if len(parts) >= 2:
        return '.'.join(parts[-2:])
    return netloc or ''


def _prioritize_page_urls(page_urls: List[str], primary_image: Optional[str]) -> List[str]:
    if not page_urls or not primary_image:
        return page_urls
    root = _site_root(urlparse(primary_image).netloc)

    def key(u: str) -> Tuple[int, str]:
        d = urlparse(u).netloc.lower()
        same = 0 if root and root in d else 1
        return (same, u)

    return sorted(page_urls, key=key)


def _use_google_vision() -> bool:
    return os.environ.get('USE_GOOGLE_VISION', '').strip().lower() in ('1', 'true', 'yes')


def _discover_via_vision(filepath: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Opsional: USE_GOOGLE_VISION=1 — Google Cloud Vision (billing lazımdır)."""
    try:
        from analyzers.reverse_image_search_analyzer import _search_google_vision
        prov = _search_google_vision(filepath)
    except Exception as e:
        return [], {'status': 'error', 'error': str(e)[:120]}
    meta = {
        'status': prov.get('status'),
        'match_count': prov.get('match_count', 0),
        'message_az': prov.get('message_az'),
        'error': prov.get('error'),
    }
    if prov.get('status') != 'ok':
        return [], meta
    return list(prov.get('matches') or []), meta


def _discover_free(
    filepath: str,
    image_urls: List[str],
    public_image_url: Optional[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    from analyzers.free_reverse_discovery import discover_free_reverse
    return discover_free_reverse(
        filepath,
        image_urls=image_urls,
        public_image_url=public_image_url,
    )


def _merge_matches_into_seeds(
    matches: List[Dict[str, Any]],
    image_urls: List[str],
    page_urls: List[str],
    seen: Set[str],
) -> None:
    for m in matches:
        for u, as_page in (
            (m.get('page_url'), True),
            (m.get('image_url'), False),
            (m.get('backlink'), True),
        ):
            if not u or not u.startswith('http') or u in seen:
                continue
            seen.add(u)
            if as_page or _is_likely_page_url(u):
                page_urls.append(u)
            else:
                image_urls.append(u)


def _variant_type(url: str, match_type: str = '') -> str:
    u = url.lower()
    if match_type in ('partial', 'similar'):
        return 'similar_or_crop'
    for pat, vtype in VARIANT_URL_PATTERNS:
        if pat.search(u):
            return vtype
    return 'exact_match'


def _dimensions_hint(url: str) -> Optional[str]:
    qs = parse_qs(urlparse(url).query)
    parts = []
    for k in ('w', 'width', 'h', 'height'):
        if k in qs and qs[k]:
            parts.append(f'{k}={qs[k][0]}')
    if parts:
        return ', '.join(parts)
    m = re.search(r'(\d{2,5})[xX](\d{2,5})', url)
    if m:
        return f'{m.group(1)}×{m.group(2)}'
    return None


def _collect_seed_urls(result: Dict[str, Any], filepath: str) -> Tuple[List[str], List[str]]:
    """(image_urls, page_urls)"""
    image_urls: List[str] = []
    page_urls: List[str] = []
    seen: Set[str] = set()

    def add(u: Optional[str], as_page: bool = False) -> None:
        if not u or not u.startswith('http') or u in seen:
            return
        seen.add(u)
        if as_page or _is_likely_page_url(u):
            page_urls.append(u)
        else:
            image_urls.append(u)

    web = result.get('web_metadata') or {}
    add(web.get('resolved_url'))
    add(web.get('source_url'))
    add(web.get('page_url'), as_page=True)

    try:
        from analyzers.web_image_metadata import load_url_sidecar
        sc = load_url_sidecar(filepath)
        if sc:
            add(sc.get('resolved_url'))
            add(sc.get('source_url'))
            add(sc.get('page_url'), as_page=True)
    except Exception:
        pass

    ris = result.get('reverse_image_search') or {}
    for m in ris.get('matches') or []:
        add(m.get('image_url'))
        add(m.get('page_url'), as_page=True)

    return image_urls[:12], page_urls[:10]


def _occurrence(
    *,
    image_hash: str,
    image_url: str,
    first_seen: Optional[str],
    last_seen: Optional[str],
    source: str,
    confidence: float,
    page_url: Optional[str] = None,
    extra: Optional[Dict] = None,
) -> Dict[str, Any]:
    row = {
        'image_hash': image_hash,
        'image_url': image_url,
        'first_seen': first_seen,
        'last_seen': last_seen,
        'source': source,
        'confidence': round(min(max(confidence, 0.35), 0.98), 2),
    }
    if page_url:
        row['page_url'] = page_url
    if extra:
        row.update(extra)
    return row


def _analyze_wayback_targets(
    image_urls: List[str],
    page_urls: List[str],
    image_hash: str,
) -> Tuple[Dict[str, Any], List[Dict], List[Dict]]:
    """Wayback ilk snapshot + səhifə indekslənmə."""
    wayback_block: Dict[str, Any] = {'image': [], 'pages': []}
    page_indexing: List[Dict] = []
    occurrences: List[Dict] = []

    for url in image_urls[:8]:
        wb = _wayback_history(url)
        entry = {
            'url': url,
            'available': wb.get('available'),
            'first_snapshot': (wb.get('earliest') or {}).get('iso_date'),
            'first_snapshot_display_az': (
                _format_az(wb['earliest']['dt']) if wb.get('earliest') else None
            ),
            'last_snapshot': (wb.get('latest') or {}).get('iso_date'),
            'snapshot_count': wb.get('snapshot_count', 0),
            'wayback_url': (
                wb['earliest'].get('wayback_url')
                if wb.get('earliest') else None
            ),
            'modifications': len(wb.get('modifications') or []),
        }
        wayback_block['image'].append(entry)
        if wb.get('available') and wb.get('earliest'):
            e = wb['earliest']
            occurrences.append(_occurrence(
                image_hash=image_hash,
                image_url=url,
                first_seen=e.get('iso_date'),
                last_seen=(wb.get('latest') or {}).get('iso_date'),
                source='wayback_image',
                confidence=0.88,
                extra={
                    'note_az': 'Şəkil URL — Wayback-də ilk snapshot',
                    'wayback_url': f"https://web.archive.org/web/{e['timestamp']}/{url}",
                },
            ))

    for url in page_urls[:8]:
        wb = _wayback_history(url)
        pg = _page_dates(url)
        first_meta = pg.get('published')
        first_wb = (wb.get('earliest') or {}).get('iso_date')
        candidates = [d for d in (first_wb, first_meta) if d]
        first_seen = min(candidates) if candidates else None
        last_seen = (wb.get('latest') or {}).get('iso_date') or pg.get('modified')

        conf = 0.75
        if first_wb and first_meta:
            try:
                if abs(
                    (datetime.strptime(first_wb, '%Y-%m-%d')
                     - datetime.strptime(first_meta, '%Y-%m-%d')).days
                ) <= 30:
                    conf = 0.9
            except ValueError:
                pass

        page_indexing.append({
            'page_url': url,
            'domain': urlparse(url).netloc,
            'first_seen': first_seen,
            'first_seen_display_az': (
                _format_az(datetime.strptime(first_seen, '%Y-%m-%d'))
                if first_seen else None
            ),
            'last_seen': last_seen,
            'wayback_first_snapshot': first_wb,
            'page_published': first_meta,
            'page_modified': pg.get('modified'),
            'snapshot_count': wb.get('snapshot_count', 0),
            'confidence': conf,
            'wayback_url': (
                f"https://web.archive.org/web/{wb['earliest']['timestamp']}/{url}"
                if wb.get('earliest') else None
            ),
        })
        wayback_block['pages'].append({
            'url': url,
            'wayback_available': wb.get('available'),
            'first_snapshot': first_wb,
            'page_published': first_meta,
        })
        if first_seen:
            occurrences.append(_occurrence(
                image_hash=image_hash,
                image_url=url,
                first_seen=first_seen,
                last_seen=last_seen,
                source='page_indexing',
                confidence=conf,
                page_url=url,
                extra={'note_az': 'Məqalə/səhifə — Wayback + səhifə metadata'},
            ))

    return wayback_block, page_indexing, occurrences


def _cdn_only_limitation(
    wayback_data: Dict[str, Any],
    page_indexing: List[Dict],
    vision_meta: Dict[str, Any],
    global_first: Optional[str],
) -> Optional[str]:
    """Yalnız CDN Wayback varsa — TinEye ilə uyğunsuzluq izahı."""
    if page_indexing:
        return None
    img_wb = [x for x in (wayback_data.get('image') or []) if x.get('first_snapshot')]
    if not img_wb:
        return None
    gfs = global_first or min(x['first_snapshot'] for x in img_wb)
    vstat = vision_meta.get('status')
    extra = ''
    if discovery_meta.get('providers'):
        needs = [p for p in discovery_meta['providers'] if p.get('status') == 'needs_api_key']
        if needs and any(p.get('id') == 'brave_web' for p in needs):
            extra = ' Pulsuz: .env-ə BRAVE_API_KEY (brave.com/search/api, ~2000 sorğu/ay).'
    return (
        f'Yalnız şəkil CDN linki Wayback-də arxivlənib (məs. {gfs}); '
        'TinEye eyni piksellər üçün köhnə məqalə URL-lərini də göstərə bilər (məs. 2020). '
        f'Məqalə URL: BRAVE_API_KEY, TinEye veb linki (paneldə), və ya TINEYE_API_KEY.{extra}'
    )


def _build_cdn_warning(
    wayback_data: Dict[str, Any],
    page_indexing: List[Dict],
    global_first: Optional[str],
) -> Optional[Dict[str, Any]]:
    img_snaps = [
        x.get('first_snapshot') for x in (wayback_data.get('image') or [])
        if x.get('first_snapshot')
    ]
    page_first = [
        x.get('first_seen') for x in page_indexing if x.get('first_seen')
    ]
    if not img_snaps or not page_first:
        return None
    cdn_min = min(img_snaps)
    article_min = min(page_first)
    if cdn_min <= article_min:
        return None
    return {
        'type': 'cdn_later_than_article',
        'cdn_first_snapshot': cdn_min,
        'article_first_seen': article_min,
        'global_first_seen': global_first,
        'message_az': (
            f'CDN şəkil URL Wayback-də ən erkən {cdn_min}; məqalə/səhifələr {article_min}. '
            'TinEye eyni şəkil üçün bütün indeksdəki URL-lərə baxır (məs. 2020); '
            'yalnız CDN linkinə Wayback baxanda tarix gec görünə bilər.'
        ),
    }


def _find_variants(
    matches: List[Dict[str, Any]],
    primary_urls: List[str],
    image_hash: str,
) -> List[Dict[str, Any]]:
    variants: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    primary_set = set(primary_urls)

    for m in matches:
        for u in (m.get('image_url'), m.get('page_url')):
            if not u or not u.startswith('http') or u in seen:
                continue
            seen.add(u)
            vtype = _variant_type(u, m.get('match_type', ''))
            is_variant = (
                u not in primary_set
                or vtype != 'exact_match'
                or m.get('match_type') in ('partial', 'similar')
            )
            if not is_variant and u in primary_set:
                continue
            dim = _dimensions_hint(u)
            variants.append({
                'image_hash': image_hash,
                'image_url': u if not _is_likely_page_url(u) else m.get('image_url') or u,
                'page_url': m.get('page_url') or u,
                'variant_type': vtype,
                'variant_type_az': {
                    'url_params': 'URL ölçü parametrləri',
                    'path_resize': 'Kiçik/böyük versiya yolu',
                    'filename_suffix': 'Fayl adında ölçü',
                    'cdn_resize': 'CDN resize/crop',
                    'similar_or_crop': 'Oxşar və ya kəsilmiş',
                    'exact_match': 'Eyni şəkil',
                }.get(vtype, vtype),
                'dimensions_hint': dim,
                'source': m.get('provider', 'reverse_search'),
                'confidence': min(0.92, 0.55 + (m.get('score') or 0) / 200),
                'match_type': m.get('match_type'),
                'title': (m.get('title') or '')[:100],
            })

    variants.sort(key=lambda x: -x.get('confidence', 0))
    return variants[:25]


def analyze_image_propagation(
    filepath: str,
    result: Optional[Dict[str, Any]] = None,
    *,
    include_reverse_search: bool = False,
    include_free_discovery: bool = True,
    public_image_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Tarix və yayılma: Wayback, səhifə indeksi, variantlar.
    """
    if not filepath or not os.path.isfile(filepath):
        return {
            'module': 'image_propagation',
            'status': 'error',
            'error': 'Şəkil faylı tapılmadı',
            'summary_az': 'Fayl mövcud deyil.',
        }

    result = result or {}
    print('  [i] Tarix və yayılma analizi...', file=sys.stderr)

    hashes = _image_hashes(filepath)
    image_hash = hashes.get('image_hash', '')

    image_urls, page_urls = _collect_seed_urls(result, filepath)
    seed_seen: Set[str] = set(image_urls + page_urls)
    discovery_meta: Dict[str, Any] = {'status': 'skipped'}
    manual_portals: List[Dict[str, Any]] = []

    if include_reverse_search and not result.get('reverse_image_search'):
        try:
            from analyzers.reverse_image_search_analyzer import analyze_reverse_image_search
            fn = os.path.basename(filepath)
            pub = public_image_url
            if not pub:
                base = os.environ.get('PUBLIC_APP_URL') or os.environ.get('PUBLIC_IMAGE_BASE_URL')
                if base:
                    pub = f'{base.rstrip("/")}/uploads/{quote(fn)}'
            ris = analyze_reverse_image_search(filepath, pub, fn)
            result['reverse_image_search'] = ris
        except Exception as e:
            print(f'  [!] Tərs axtarış (yayılma): {e}', file=sys.stderr)

    all_matches: List[Dict] = []
    ris = result.get('reverse_image_search') or {}
    for m in ris.get('matches') or []:
        all_matches.append(m)
    for p in ris.get('providers') or []:
        if p.get('status') == 'ok':
            for m in p.get('matches') or []:
                all_matches.append(m)

    from analyzers.portal_search_urls import resolve_search_image_url
    pub, _pub_src = resolve_search_image_url(
        os.path.basename(filepath), public_image_url, filepath,
    )

    need_pages = len(page_urls) < 2 or any(_is_cdn_image_url(u) for u in image_urls[:3])
    if include_free_discovery and need_pages and not include_reverse_search:
        fm, discovery_meta = _discover_free(filepath, image_urls, pub)
        all_matches.extend(fm)
        _merge_matches_into_seeds(fm, image_urls, page_urls, seed_seen)
        manual_portals = discovery_meta.get('manual_portals') or []
        if _use_google_vision():
            print('  [i] Google Vision (USE_GOOGLE_VISION=1)...', file=sys.stderr)
            vm, vmeta = _discover_via_vision(filepath)
            discovery_meta['vision'] = vmeta
            all_matches.extend(vm)
            _merge_matches_into_seeds(vm, image_urls, page_urls, seed_seen)

    primary_image = image_urls[0] if image_urls else None
    page_urls = _prioritize_page_urls(page_urls, primary_image)
    image_urls = image_urls[:12]
    page_urls = page_urls[:10]

    wayback_data, page_indexing, occurrences = _analyze_wayback_targets(
        image_urls, page_urls, image_hash,
    )

    variants = _find_variants(all_matches, image_urls, image_hash)

    earliest_dates = [o['first_seen'] for o in occurrences if o.get('first_seen')]
    global_first = min(earliest_dates) if earliest_dates else None
    cdn_dates = [
        x.get('first_snapshot') for x in (wayback_data.get('image') or [])
        if x.get('first_snapshot') and _is_cdn_image_url(x.get('url', ''))
    ]
    cdn_warning = _build_cdn_warning(wayback_data, page_indexing, global_first)
    cdn_only_az = _cdn_only_limitation(wayback_data, page_indexing, discovery_meta, global_first)

    if not manual_portals and pub:
        from analyzers.portal_search_urls import build_portal_links
        manual_portals = build_portal_links(pub)

    out = {
        'module': 'image_propagation',
        'status': 'ok',
        'summary_az': '',
        'image_hash': image_hash,
        'hashes': hashes,
        'primary_image_url': primary_image,
        'wayback': wayback_data,
        'page_indexing': page_indexing,
        'variants': variants,
        'occurrences': occurrences,
        'global_first_seen': global_first,
        'global_first_seen_display_az': (
            _format_az(datetime.strptime(global_first, '%Y-%m-%d'))
            if global_first else None
        ),
        'cdn_first_snapshot': min(cdn_dates) if cdn_dates else None,
        'free_discovery': discovery_meta,
        'manual_reverse_portals': manual_portals,
        'search_image_url': pub,
        'cdn_warning': cdn_warning,
        'cdn_only_note_az': cdn_only_az,
        'limitations_az': (
            'Tarixlər Wayback arxivi və səhifə metadata əsasındadır; '
            'bütün saytlar arxivlənməyə bilər. TinEye şəkil fingerprint üzrə bütün URL-ləri indeksləyir; '
            'biz CDN + Vision tapıntıları + məqalə Wayback birləşdiririk.'
        ),
    }

    parts = []
    if global_first:
        parts.append(f'Ən erkən iz: {out["global_first_seen_display_az"]}.')
    img_wb = [x for x in wayback_data.get('image', []) if x.get('first_snapshot')]
    if img_wb:
        parts.append(f'{len(img_wb)} şəkil URL Wayback-də.')
    if page_indexing:
        parts.append(f'{len(page_indexing)} səhifə indeksi.')
    if variants:
        parts.append(f'{len(variants)} variant/oxşar URL.')
    if cdn_warning:
        parts.append(cdn_warning['message_az'])
    elif cdn_only_az:
        parts.append(cdn_only_az)
    if discovery_meta.get('match_count'):
        parts.append(f'Pulsuz axtarış: {discovery_meta["match_count"]} URL.')
    if manual_portals:
        parts.append('TinEye/Yandex portal linkləri paneldə.')
    if not parts:
        out['status'] = 'partial'
        parts.append(
            'URL və ya Wayback izi tapılmadı. Şəkil URL ilə yükləyin və ya «Tam yayılma analizi» işə salın.'
        )
    out['summary_az'] = ' '.join(parts)

    if result is not None:
        result['image_propagation'] = out

    return out
