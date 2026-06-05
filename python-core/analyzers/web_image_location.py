"""
Google / veb şəkil URL-lərindən lokasiya: səhifə HTML, JSON-LD, URL koordinatları, yer adları.
EXIF GPS olmasa belə geoparsing üçün kontekst və birbaşa koordinat adayları.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

import requests

from analyzers.web_image_metadata import USER_AGENT, load_url_sidecar
from analyzers.geoparsing_engine import extract_extended_coordinates, extract_geographic_entities
from data.places_gazetteer import GAZETTEER

GEO_POSITION_RE = re.compile(
    r'<meta[^>]+name=["\']geo\.position["\'][^>]+content=["\']([^"\']+)',
    re.I,
)
ICBM_RE = re.compile(
    r'<meta[^>]+name=["\']ICBM["\'][^>]+content=["\']([^"\']+)',
    re.I,
)
JSON_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
MAP_LINK_RE = re.compile(
    r'https?://(?:www\.)?(?:google\.[a-z.]+/maps|maps\.google\.[a-z.]+)[^\s"\'<>]+',
    re.I,
)
WIKIMEDIA_COORD_RE = re.compile(
    r'(?:lat|latitude)[_=](-?\d+\.?\d*)[^&]*(?:lon|lng|longitude)[_=](-?\d+\.?\d*)',
    re.I,
)


def _parse_coord_pair(text: str) -> Optional[Tuple[float, float]]:
    if not text:
        return None
    t = unquote(text).strip()
    for sep in (';', ',', ' '):
        if sep in t:
            parts = [p.strip() for p in t.replace(';', ',').split(',') if p.strip()]
            if len(parts) >= 2:
                try:
                    lat, lon = float(parts[0]), float(parts[1])
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        return lat, lon
                except ValueError:
                    pass
    return None


def _coords_from_urls(*urls: Optional[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for url in urls:
        if not url:
            continue
        u = unquote(url)
        for m in MAP_LINK_RE.finditer(u):
            link = m.group(0)
            for item in extract_extended_coordinates(link):
                key = (round(item['latitude'], 5), round(item['longitude'], 5))
                if key not in seen:
                    seen.add(key)
                    item['source'] = 'web_url_map'
                    item['label'] = 'Google Maps (URL)'
                    out.append(item)
        qm = re.search(r'[?&]q=(-?\d+\.?\d*),(-?\d+\.?\d*)', u, re.I)
        if qm:
            lat, lon = float(qm.group(1)), float(qm.group(2))
            key = (round(lat, 5), round(lon, 5))
            if key not in seen:
                seen.add(key)
                out.append({
                    'latitude': lat,
                    'longitude': lon,
                    'confidence': 0.82,
                    'source': 'web_url_query',
                    'label': 'URL ?q= koordinat',
                })
        wm = WIKIMEDIA_COORD_RE.search(u)
        if wm:
            lat, lon = float(wm.group(1)), float(wm.group(2))
            key = (round(lat, 5), round(lon, 5))
            if key not in seen:
                seen.add(key)
                out.append({
                    'latitude': lat,
                    'longitude': lon,
                    'confidence': 0.8,
                    'source': 'web_url_wikimedia',
                    'label': 'Wikimedia URL',
                })
        at_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', u)
        if at_match:
            lat, lon = float(at_match.group(1)), float(at_match.group(2))
            key = (round(lat, 5), round(lon, 5))
            if key not in seen:
                seen.add(key)
                out.append({
                    'latitude': lat,
                    'longitude': lon,
                    'confidence': 0.8,
                    'source': 'web_url_at',
                    'label': 'URL @lat,lon',
                })
    return out


def _json_ld_coords(obj: Any, found: List[Dict[str, Any]], seen: set) -> None:
    if isinstance(obj, list):
        for x in obj:
            _json_ld_coords(x, found, seen)
        return
    if not isinstance(obj, dict):
        return
    geo = obj.get('geo')
    if isinstance(geo, dict):
        lat = geo.get('latitude') or geo.get('lat')
        lon = geo.get('longitude') or geo.get('lon') or geo.get('lng')
        if lat is not None and lon is not None:
            try:
                la, lo = float(lat), float(lon)
                key = (round(la, 5), round(lo, 5))
                if key not in seen:
                    seen.add(key)
                    found.append({
                        'latitude': la,
                        'longitude': lo,
                        'confidence': 0.85,
                        'source': 'web_json_ld',
                        'label': obj.get('name') or 'JSON-LD geo',
                    })
            except (TypeError, ValueError):
                pass
    if obj.get('@type') in ('Place', 'TouristAttraction', 'LandmarksOrHistoricalBuildings'):
        lat = obj.get('latitude')
        lon = obj.get('longitude')
        if lat is not None and lon is not None:
            try:
                la, lo = float(lat), float(lon)
                key = (round(la, 5), round(lo, 5))
                if key not in seen:
                    seen.add(key)
                    found.append({
                        'latitude': la,
                        'longitude': lo,
                        'confidence': 0.84,
                        'source': 'web_json_ld',
                        'label': str(obj.get('name') or 'JSON-LD Place')[:120],
                    })
            except (TypeError, ValueError):
                pass
    for v in obj.values():
        if isinstance(v, (dict, list)):
            _json_ld_coords(v, found, seen)


def _fetch_page_geo(url: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {'texts': [], 'candidates': []}
    if not url or not url.startswith('http'):
        return out
    try:
        resp = requests.get(
            url,
            headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml'},
            timeout=16,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return out
        html = resp.text[:400000]
        seen = set()

        for pat in (GEO_POSITION_RE, ICBM_RE):
            m = pat.search(html)
            if m:
                pair = _parse_coord_pair(m.group(1))
                if pair:
                    key = (round(pair[0], 5), round(pair[1], 5))
                    if key not in seen:
                        seen.add(key)
                        out['candidates'].append({
                            'latitude': pair[0],
                            'longitude': pair[1],
                            'confidence': 0.86,
                            'source': 'web_meta_geo',
                            'label': 'Səhifə geo.position',
                        })

        for block in JSON_LD_RE.finditer(html):
            try:
                data = json.loads(block.group(1).strip())
                _json_ld_coords(data, out['candidates'], seen)
            except json.JSONDecodeError:
                continue

        for item in extract_extended_coordinates(html[:80000]):
            key = (round(item['latitude'], 5), round(item['longitude'], 5))
            if key not in seen:
                seen.add(key)
                item['source'] = 'web_page_html'
                item['label'] = 'Səhifədə koordinat'
                out['candidates'].append(item)

        title_m = re.search(r'<title>([^<]{3,250})</title>', html, re.I)
        if title_m:
            out['texts'].append(title_m.group(1).strip())
        desc_m = re.search(
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)',
            html,
            re.I,
        )
        if desc_m:
            out['texts'].append(desc_m.group(1).strip())
    except Exception as e:
        out['fetch_error'] = str(e)[:120]
    return out


def _gazetteer_from_texts(texts: List[str]) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    seen = set()
    combined = ' '.join(texts).lower()
    for key, (lat, lon, label, cc) in GAZETTEER.items():
        if len(key) < 4 and key not in combined.split():
            continue
        if key in combined:
            k = (round(lat, 5), round(lon, 5))
            if k not in seen:
                seen.add(k)
                found.append({
                    'latitude': lat,
                    'longitude': lon,
                    'confidence': 0.58,
                    'source': 'web_gazetteer',
                    'label': label,
                    'country_bias': cc,
                })
    for ent in extract_geographic_entities([combined]):
        if ent.get('latitude') is None:
            continue
        k = (round(ent['latitude'], 5), round(ent['longitude'], 5))
        if k in seen:
            continue
        seen.add(k)
        found.append({
            'latitude': ent['latitude'],
            'longitude': ent['longitude'],
            'confidence': float(ent.get('confidence', 0.55)),
            'source': 'web_gazetteer',
            'label': ent.get('value', 'Yer adı'),
        })
    return found


def _nominatim_place_from_texts(texts: List[str], country_bias: Optional[str]) -> List[Dict[str, Any]]:
    from analyzers.geo_analyzer import nominatim_search_advanced
    out: List[Dict[str, Any]] = []
    seen = set()
    for raw in texts[:4]:
        q = (raw or '').strip()
        if len(q) < 8 or len(q) > 180:
            continue
        if not re.search(r'[a-zA-Z\u00C0-\u024F\u0400-\u04FF]{4,}', q):
            continue
        for hit in nominatim_search_advanced(q, country_codes=country_bias, limit=2):
            key = (round(hit['latitude'], 5), round(hit['longitude'], 5))
            if key in seen:
                continue
            seen.add(key)
            out.append({
                'latitude': hit['latitude'],
                'longitude': hit['longitude'],
                'confidence': float(hit.get('confidence', 0.62)),
                'source': 'web_nominatim_page',
                'label': hit.get('display_name', q)[:160],
            })
    return out[:3]


def gather_web_location_hints(
    filepath: str,
    result: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Veb mənbədən mətn (geoparsing) və koordinat adayları.
    """
    texts: List[str] = []
    candidates: List[Dict[str, Any]] = []
    sidecar = load_url_sidecar(filepath)
    web = (result or {}).get('web_metadata') or {}

    source_url = web.get('source_url') or (sidecar or {}).get('source_url')
    resolved = web.get('resolved_url') or (sidecar or {}).get('resolved_url')
    page_url = web.get('page_url') or (sidecar or {}).get('page_url') or (sidecar or {}).get('imgref')

    for u in (source_url, resolved, page_url):
        if u:
            texts.append(u)

    page = web.get('page') or {}
    for key in ('og_title', 'page_title', 'og_description', 'description'):
        if page.get(key):
            texts.append(str(page[key]))

    if sidecar and sidecar.get('domain'):
        texts.append(sidecar['domain'])

    candidates.extend(_coords_from_urls(source_url, resolved, page_url))

    if page_url and page_url.startswith('http'):
        geo_page = _fetch_page_geo(page_url)
        texts.extend(geo_page.get('texts') or [])
        candidates.extend(geo_page.get('candidates') or [])

    country_bias = None
    if sidecar and sidecar.get('domain'):
        dom = sidecar['domain'].lower()
        if '.az' in dom or 'azertag' in dom:
            country_bias = 'az'

    unique_texts = list(dict.fromkeys(t.strip() for t in texts if t and len(t.strip()) > 2))
    candidates.extend(_gazetteer_from_texts(unique_texts))
    candidates.extend(_nominatim_place_from_texts(unique_texts, country_bias))

    seen = set()
    deduped: List[Dict[str, Any]] = []
    for c in candidates:
        if c.get('latitude') is None:
            continue
        key = (round(c['latitude'], 5), round(c['longitude'], 5))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    if deduped:
        print(
            f'  [i] Veb lokasiya: {len(deduped)} koordinat adayı, {len(unique_texts)} mətn',
            file=sys.stderr,
        )
    return unique_texts, deduped
