"""
Canlı Şəkil Kəşfiyyatı — Tərsinə şəkil axtarışı (TinEye, Google Vision, SerpAPI, Bing, portal linkləri).
"""

import base64
import os
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

MAX_MATCHES_PER_PROVIDER = 15
MAX_FILE_BYTES = 8 * 1024 * 1024


def _env(key: str) -> Optional[str]:
    v = os.environ.get(key, '').strip()
    return v or None


def _public_image_url(filename: str, explicit_url: Optional[str] = None) -> Optional[str]:
    from analyzers.portal_search_urls import resolve_search_image_url
    url, _ = resolve_search_image_url(filename, explicit_url)
    return url


def _normalize_match(
    *,
    provider: str,
    page_url: str,
    title: str = '',
    image_url: str = '',
    domain: str = '',
    score: Optional[float] = None,
    match_type: str = 'similar',
    snippet: str = '',
) -> Dict[str, Any]:
    from urllib.parse import urlparse
    if not domain and page_url:
        try:
            domain = urlparse(page_url).netloc
        except Exception:
            domain = ''
    return {
        'provider': provider,
        'page_url': page_url,
        'title': title or domain or page_url,
        'image_url': image_url,
        'domain': domain,
        'score': score,
        'match_type': match_type,
        'snippet': snippet,
    }


def _search_tineye(filepath: str, public_url: Optional[str]) -> Dict[str, Any]:
    api_key = _env('TINEYE_API_KEY')
    if not api_key:
        return {
            'id': 'tineye',
            'name': 'TinEye',
            'status': 'needs_api_key',
            'message_az': 'TINEYE_API_KEY .env faylında təyin edin (tineye.com/api).',
        }

    from analyzers.portal_search_urls import resolve_tineye_search_urls
    from analyzers.tineye_date_extractor import _tineye_api_request

    fn = os.path.basename(filepath)
    url_candidates = resolve_tineye_search_urls(fn, filepath, public_url)
    params = {'limit': MAX_MATCHES_PER_PROVIDER, 'sort': 'score', 'order': 'desc'}

    data: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None
    search_via = 'file_upload'

    for try_url in url_candidates:
        data, err = _tineye_api_request(
            filepath, image_url=try_url, sort='score', order='desc', limit=MAX_MATCHES_PER_PROVIDER,
        )
        if err:
            last_error = err
            continue
        matches_n = len((data.get('results', {}) or {}).get('matches', []))
        if matches_n > 0:
            search_via = f'url:{try_url[:80]}'
            print(f'  [+] TinEye tərs axtarış (URL): {matches_n} uyğunluq', file=sys.stderr)
            break

    if not data or not (data.get('results', {}) or {}).get('matches'):
        data, err = _tineye_api_request(
            filepath, image_url=None, sort='score', order='desc', limit=MAX_MATCHES_PER_PROVIDER,
        )
        if err:
            last_error = err
        elif data and (data.get('results', {}) or {}).get('matches'):
            search_via = 'file_upload'
            print(
                f'  [+] TinEye tərs axtarış (fayl): '
                f'{len((data.get("results", {}) or {}).get("matches", []))} uyğunluq',
                file=sys.stderr,
            )

    if not data:
        return {
            'id': 'tineye', 'name': 'TinEye', 'status': 'error',
            'error': last_error or 'TinEye cavabı alınmadı',
        }

    if data.get('code') != 200:
        return {
            'id': 'tineye', 'name': 'TinEye', 'status': 'error',
            'error': data.get('messages', {}).get('error', ['API xətası'])[0]
            if isinstance(data.get('messages'), dict) else str(data),
        }

    matches = []
    crawl_dates: List[str] = []
    for m in (data.get('results', {}) or {}).get('matches', [])[:MAX_MATCHES_PER_PROVIDER]:
        backlinks = m.get('backlinks') or []
        bl0 = backlinks[0] if backlinks else {}
        page_url = bl0.get('backlink') or bl0.get('url') or m.get('image_url', '')
        crawl = bl0.get('crawl_date') or ''
        if crawl:
            crawl_dates.append(crawl)
        matches.append({
            **_normalize_match(
                provider='tineye',
                page_url=page_url,
                image_url=m.get('image_url', ''),
                score=m.get('score'),
                match_type='exact' if (m.get('score') or 0) >= 90 else 'similar',
                title=page_url,
            ),
            'crawl_date': crawl,
            'backlink': bl0.get('backlink') or page_url,
        })

    earliest_crawl = min(crawl_dates) if crawl_dates else None
    stats = data.get('stats', {})
    return {
        'id': 'tineye',
        'name': 'TinEye',
        'status': 'ok' if matches else 'no_matches',
        'match_count': len(matches),
        'total_available': stats.get('total_results'),
        'matches': matches,
        'earliest_crawl_date': earliest_crawl,
        'remaining_searches': stats.get('remaining_searches'),
        'search_via': search_via,
    }


def _search_google_vision(filepath: str) -> Dict[str, Any]:
    api_key = _env('GOOGLE_VISION_API_KEY') or _env('GOOGLE_CLOUD_VISION_API_KEY')
    if not api_key:
        return {
            'id': 'google_vision',
            'name': 'Google Vision (Web Detection)',
            'status': 'needs_api_key',
            'message_az': 'GOOGLE_VISION_API_KEY .env — Cloud Vision Web Detection.',
        }

    try:
        with open(filepath, 'rb') as f:
            raw = f.read()
        if len(raw) > MAX_FILE_BYTES:
            return {'id': 'google_vision', 'name': 'Google Vision', 'status': 'error', 'error': 'Fayl çox böyükdür'}
        b64 = base64.b64encode(raw).decode('ascii')
    except Exception as e:
        return {'id': 'google_vision', 'name': 'Google Vision', 'status': 'error', 'error': str(e)}

    payload = {
        'requests': [{
            'image': {'content': b64},
            'features': [{'type': 'WEB_DETECTION', 'maxResults': MAX_MATCHES_PER_PROVIDER}],
        }],
    }
    try:
        resp = requests.post(
            f'https://vision.googleapis.com/v1/images:annotate?key={api_key}',
            json=payload,
            timeout=30,
        )
    except Exception as e:
        return {'id': 'google_vision', 'name': 'Google Vision', 'status': 'error', 'error': str(e)}

    if resp.status_code != 200:
        return {'id': 'google_vision', 'name': 'Google Vision', 'status': 'error', 'error': resp.text[:300]}

    data = resp.json()
    responses = data.get('responses') or [{}]
    web = responses[0].get('webDetection') or {}
    if responses[0].get('error'):
        return {
            'id': 'google_vision', 'name': 'Google Vision', 'status': 'error',
            'error': responses[0]['error'].get('message', 'Vision API xətası'),
        }

    matches = []
    seen = set()

    def _add(items, mtype):
        for item in items or []:
            u = item.get('url') if isinstance(item, dict) else None
            if not u or u in seen:
                continue
            seen.add(u)
            matches.append(_normalize_match(
                provider='google_vision',
                page_url=u,
                image_url=u if mtype != 'page' else '',
                title=item.get('pageTitle', '') if isinstance(item, dict) else '',
                score=item.get('score') if isinstance(item, dict) else None,
                match_type=mtype,
            ))

    _add(web.get('pagesWithMatchingImages'), 'page')
    _add(web.get('fullMatchingImages'), 'exact')
    _add(web.get('partialMatchingImages'), 'partial')
    for sim in (web.get('visuallySimilarImages') or [])[:8]:
        u = sim.get('url') if isinstance(sim, dict) else None
        if u and u not in seen:
            seen.add(u)
            matches.append(_normalize_match(provider='google_vision', page_url=u, image_url=u, match_type='similar'))

    entities = [
        e.get('description', '') for e in (web.get('webEntities') or [])
        if (e.get('score') or 0) > 0.4
    ][:8]

    return {
        'id': 'google_vision',
        'name': 'Google Vision (Web Detection)',
        'status': 'ok',
        'match_count': len(matches[:MAX_MATCHES_PER_PROVIDER]),
        'matches': matches[:MAX_MATCHES_PER_PROVIDER],
        'web_entities': entities,
        'best_guess_labels': web.get('bestGuessLabels', []),
    }


def _search_serpapi(public_url: Optional[str], filepath: str) -> Dict[str, Any]:
    key = _env('SERPAPI_KEY')
    if not key:
        return {
            'id': 'google_lens_serpapi',
            'name': 'Google Lens (SerpAPI)',
            'status': 'needs_api_key',
            'message_az': 'SERPAPI_KEY .env — serpapi.com Google Reverse Image.',
        }

    if not public_url:
        return {
            'id': 'google_lens_serpapi',
            'name': 'Google Lens (SerpAPI)',
            'status': 'needs_public_url',
            'message_az': 'PUBLIC_APP_URL təyin edin (şəkil URL SerpAPI üçün əlçatan olmalıdır).',
        }

    try:
        resp = requests.get(
            'https://serpapi.com/search.json',
            params={
                'engine': 'google_reverse_image',
                'image_url': public_url,
                'api_key': key,
                'hl': 'az',
            },
            timeout=45,
        )
    except Exception as e:
        return {'id': 'google_lens_serpapi', 'name': 'Google Lens (SerpAPI)', 'status': 'error', 'error': str(e)}

    if resp.status_code != 200:
        return {'id': 'google_lens_serpapi', 'name': 'Google Lens', 'status': 'error', 'error': f'HTTP {resp.status_code}'}

    data = resp.json()
    if data.get('error'):
        return {'id': 'google_lens_serpapi', 'name': 'Google Lens', 'status': 'error', 'error': data['error']}

    matches = []
    for item in (data.get('image_results') or data.get('inline_images') or [])[:MAX_MATCHES_PER_PROVIDER]:
        link = item.get('link') or item.get('source') or item.get('thumbnail')
        if link:
            matches.append(_normalize_match(
                provider='google_lens',
                page_url=link,
                title=item.get('title', ''),
                image_url=item.get('thumbnail') or item.get('image', ''),
                snippet=item.get('snippet', ''),
                match_type='similar',
            ))

    for item in (data.get('visual_matches') or [])[:MAX_MATCHES_PER_PROVIDER]:
        link = item.get('link')
        if link:
            matches.append(_normalize_match(
                provider='google_lens',
                page_url=link,
                title=item.get('title', '') or item.get('source', ''),
                image_url=item.get('thumbnail', ''),
                snippet=item.get('source', ''),
                match_type='visual',
            ))

    knowledge = data.get('knowledge_graph')
    return {
        'id': 'google_lens_serpapi',
        'name': 'Google Lens (SerpAPI)',
        'status': 'ok',
        'match_count': len(matches),
        'matches': matches,
        'knowledge_graph': knowledge,
    }


def _search_bing_visual(filepath: str) -> Dict[str, Any]:
    key = _env('BING_VISUAL_SEARCH_KEY') or _env('AZURE_BING_VISUAL_SEARCH_KEY')
    if not key:
        return {
            'id': 'bing_visual',
            'name': 'Bing Visual Search',
            'status': 'needs_api_key',
            'message_az': 'BING_VISUAL_SEARCH_KEY .env — Azure Bing Image Visual Search.',
        }

    try:
        with open(filepath, 'rb') as f:
            img = f.read()
    except Exception as e:
        return {'id': 'bing_visual', 'name': 'Bing Visual Search', 'status': 'error', 'error': str(e)}

    try:
        resp = requests.post(
            'https://api.bing.microsoft.com/v7.0/images/visualsearch',
            headers={'Ocp-Apim-Subscription-Key': key},
            files={'image': ('image', img)},
            timeout=35,
        )
    except Exception as e:
        return {'id': 'bing_visual', 'name': 'Bing Visual Search', 'status': 'error', 'error': str(e)}

    if resp.status_code != 200:
        return {'id': 'bing_visual', 'name': 'Bing Visual Search', 'status': 'error', 'error': resp.text[:250]}

    data = resp.json()
    matches = []
    for tag in data.get('tags') or []:
        for action in tag.get('actions') or []:
            if action.get('actionType') != 'PagesIncluding':
                continue
            for item in (action.get('data', {}).get('value') or [])[:MAX_MATCHES_PER_PROVIDER]:
                u = item.get('hostPageUrl') or item.get('thumbnailUrl')
                if u:
                    matches.append(_normalize_match(
                        provider='bing',
                        page_url=item.get('hostPageUrl', u),
                        image_url=item.get('thumbnailUrl', ''),
                        title=item.get('name', ''),
                        match_type='pagesIncluding',
                    ))

    return {
        'id': 'bing_visual',
        'name': 'Bing Visual Search',
        'status': 'ok',
        'match_count': len(matches[:MAX_MATCHES_PER_PROVIDER]),
        'matches': matches[:MAX_MATCHES_PER_PROVIDER],
    }


def _portal_links(search_url: Optional[str], filename: str = '') -> List[Dict[str, Any]]:
    """Portal linkləri — search_url ilə avtomatik tərs şəkil axtarışı."""
    from analyzers.portal_search_urls import build_portal_links
    return build_portal_links(search_url)


def analyze_reverse_image_search(
    filepath: str,
    public_image_url: Optional[str] = None,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Çoxlu provayder ilə tərs şəkil axtarışı.
    """
    if not filepath or not os.path.isfile(filepath):
        return {
            'module': 'reverse_image_search',
            'status': 'error',
            'error': 'Şəkil faylı tapılmadı',
            'summary_az': 'Fayl mövcud deyil.',
        }

    ext = os.path.splitext(filepath)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff'):
        return {
            'module': 'reverse_image_search',
            'status': 'error',
            'error': 'Yalnız şəkil formatları dəstəklənir',
            'summary_az': 'Tərs axtarış üçün şəkil faylı lazımdır.',
        }

    fn = filename or os.path.basename(filepath)
    from analyzers.portal_search_urls import resolve_search_image_url
    pub, pub_source = resolve_search_image_url(fn, public_image_url, filepath)

    print(f'  [i] Reverse image search: {fn}', file=sys.stderr)
    if pub:
        print(f'  [i] Tərs axtarış URL ({pub_source}): {pub[:90]}...', file=sys.stderr)

    providers = [
        _search_tineye(filepath, public_image_url or pub),
        _search_google_vision(filepath),
        _search_serpapi(pub, filepath),
        _search_bing_visual(filepath),
    ]

    all_matches: List[Dict[str, Any]] = []
    for p in providers:
        if p.get('status') == 'ok':
            for m in p.get('matches') or []:
                all_matches.append(m)

    # Domen üzrə dedupe
    seen_urls = set()
    unique = []
    for m in sorted(all_matches, key=lambda x: -(x.get('score') or 0)):
        u = m.get('page_url')
        if u and u not in seen_urls:
            seen_urls.add(u)
            unique.append(m)

    api_ok = [p for p in providers if p.get('status') == 'ok']
    configured = sum(1 for p in providers if p.get('status') != 'needs_api_key')

    summary_parts = []
    if unique:
        summary_parts.append(f'{len(unique)} unikal internet uyğunluğu tapıldı.')
    else:
        summary_parts.append('API ilə birbaşa uyğunluq tapılmadı.')
    summary_parts.append(f'{len(api_ok)}/{len(providers)} provayder cavab verdi.')
    if not pub:
        summary_parts.append('PUBLIC_APP_URL təyin edin — Google/Yandex URL axtarışı üçün.')

    web_timeline = None
    try:
        from analyzers.image_web_timeline_analyzer import analyze_image_web_timeline
        web_timeline = analyze_image_web_timeline(filepath, pub, providers=providers)
        if web_timeline.get('summary_az'):
            summary_parts.append(web_timeline['summary_az'])
    except Exception as e:
        print(f'  [!] Veb xronologiya: {e}', file=sys.stderr)
        web_timeline = {
            'module': 'image_web_timeline',
            'status': 'error',
            'error': str(e),
            'summary_az': 'Veb xronologiya qurulmadı.',
        }

    return {
        'module': 'reverse_image_search',
        'status': 'ok',
        'filename': fn,
        'public_image_url': pub,
        'search_image_url': pub,
        'search_url_source': pub_source,
        'providers': providers,
        'portal_links': _portal_links(pub, fn),
        'matches': unique[:50],
        'total_matches': len(unique),
        'providers_active': len(api_ok),
        'providers_configured': configured,
        'summary_az': ' '.join(summary_parts),
        'web_timeline': web_timeline,
        'setup_hints_az': [
            'BRAVE_API_KEY — pulsuz veb axtarış (~2000 sorğu/ay, billing yox)',
            'Portal linkləri — TinEye/Yandex/Lens (API ödənişi olmadan)',
            'TINEYE_API_KEY — TinEye REST (fayl yükləmə, ödənişli plan)',
            'USE_GOOGLE_VISION=1 + GOOGLE_VISION_API_KEY — yalnız Cloud billing aktiv olanda',
            'SERPAPI_KEY + PUBLIC_APP_URL — Google Lens (ödənişli)',
        ],
    }
