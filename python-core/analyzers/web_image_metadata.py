"""
İnternetdən yüklənmiş və EXIF-siz şəkillər üçün metadata zənginləşdirmə.
Veb mənbə, səhifə OG teqləri, PNG/JPEG daxili bloklar, XMP, IPTC, hash.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
)

OG_PATTERNS = [
    (re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', re.I), 'og_title'),
    (re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title', re.I), 'og_title'),
    (re.compile(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)', re.I), 'og_description'),
    (re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', re.I), 'description'),
    (re.compile(r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)', re.I), 'published'),
    (re.compile(r'<title>([^<]{3,200})</title>', re.I), 'page_title'),
]

XMP_TAG_RE = re.compile(
    r'<(?:rdf:)?(?:Description|li)[^>]*?(?:dc:|exif:|tiff:|xmp:|photoshop:)([a-zA-Z]+)[^>]*>([^<]{1,500})<',
    re.I,
)


def _sidecar_path(filepath: str) -> str:
    base, _ = os.path.splitext(filepath)
    return base + '.source.json'


def load_url_sidecar(filepath: str) -> Optional[Dict[str, Any]]:
    path = _sidecar_path(filepath)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def save_url_sidecar(filepath: str, payload: Dict[str, Any]) -> None:
    path = _sidecar_path(filepath)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f'  [!] Sidecar yazılmadı: {e}', file=sys.stderr)


def _file_hashes(filepath: str) -> Dict[str, str]:
    out = {}
    try:
        h = hashlib.md5()
        s = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
                s.update(chunk)
        out['md5'] = h.hexdigest()
        out['sha256'] = s.hexdigest()[:32] + '…'
    except OSError:
        pass
    return out


def _scan_jpeg_segments(data: bytes) -> Dict[str, Any]:
    """JPEG APP/COM seqmentlərindən metadata."""
    found: Dict[str, Any] = {'markers': [], 'comments': [], 'xmp_snippets': []}
    if len(data) < 4 or data[:2] != b'\xff\xd8':
        return found
    i = 2
    n = len(data)
    while i < n - 4:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0xD9):
            i += 2
            continue
        if marker == 0x00:
            i += 1
            continue
        if i + 4 > n:
            break
        seg_len = (data[i + 2] << 8) + data[i + 3]
        if seg_len < 2 or i + 2 + seg_len > n:
            break
        seg = data[i + 4:i + 2 + seg_len]
        code = 0xFF00 | marker
        name = {0xFFE1: 'APP1_EXIF_XMP', 0xFFE2: 'APP2_ICC', 0xFFED: 'APP13_IPTC', 0xFFFE: 'COM'}.get(code)
        if name and name not in found['markers']:
            found['markers'].append(name)
        if marker == 0xFE:
            try:
                txt = seg.decode('utf-8', errors='replace').strip()
                if txt and len(txt) > 2:
                    found['comments'].append(txt[:300])
            except Exception:
                pass
        if marker == 0xE1 and (b'http://ns.adobe.com' in seg or b'xmp' in seg[:50].lower()):
            text = seg.decode('utf-8', errors='ignore')
            for m in XMP_TAG_RE.finditer(text):
                key = f'XMP_{m.group(1)}'
                if key not in found['xmp_snippets']:
                    found['xmp_snippets'].append({key: m.group(2).strip()[:200]})
        i += 2 + seg_len
    return found


def _scan_png_chunks(data: bytes) -> Dict[str, Any]:
    found: Dict[str, Any] = {'chunks': [], 'text': {}}
    if len(data) < 8 or data[:8] != b'\x89PNG\r\n\x1a\n':
        return found
    i = 8
    while i + 12 <= len(data):
        length = int.from_bytes(data[i:i + 4], 'big')
        ctype = data[i + 4:i + 8].decode('ascii', errors='replace')
        if ctype not in found['chunks']:
            found['chunks'].append(ctype)
        if ctype in ('tEXt', 'zTXt', 'iTXt', 'eXIf'):
            chunk_data = data[i + 8:i + 8 + length]
            if ctype == 'tEXt' and b'\x00' in chunk_data:
                k, v = chunk_data.split(b'\x00', 1)
                found['text'][k.decode('latin-1', errors='replace')] = v.decode('latin-1', errors='replace')[:400]
            elif ctype == 'iTXt':
                try:
                    found['text'][f'iTXt_{len(found["text"])}'] = chunk_data.decode('utf-8', errors='replace')[:400]
                except Exception:
                    pass
        i += 12 + length
        if i > len(data):
            break
    return found


def _fetch_page_metadata(url: str) -> Dict[str, Any]:
    """NASA, Wikimedia və s. üçün səhifə başlığı/təsvir."""
    out: Dict[str, Any] = {}
    if not url or not url.startswith('http'):
        return out
    try:
        resp = requests.get(
            url,
            headers={'User-Agent': USER_AGENT, 'Accept': 'text/html'},
            timeout=14,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return out
        html = resp.text[:250000]
        for pat, key in OG_PATTERNS:
            m = pat.search(html)
            if m and key not in out:
                out[key] = m.group(1).strip()[:500]
    except Exception as e:
        out['fetch_error'] = str(e)[:120]
    return out


def _merge_into_raw_tags(result: Dict[str, Any], tags: Dict[str, str]) -> None:
    if not tags:
        return
    raw = dict(result.get('raw_tags') or {})
    raw.update(tags)
    result['raw_tags'] = raw


def enrich_web_image_metadata(result: Dict[str, Any], filepath: str) -> Dict[str, Any]:
    """
    EXIF olmasa belə metadata paketi: texniki, veb mənbə, daxili bloklar.
    """
    sidecar = load_url_sidecar(filepath)
    source_url = (sidecar or {}).get('source_url') or (sidecar or {}).get('resolved_url')

    try:
        with open(filepath, 'rb') as f:
            data = f.read(min(os.path.getsize(filepath), 2_500_000))
    except OSError:
        data = b''

    embedded: Dict[str, str] = {}
    technical: Dict[str, Any] = {}
    page_meta: Dict[str, Any] = {}

    jpeg = _scan_jpeg_segments(data)
    png = _scan_png_chunks(data)
    if jpeg.get('markers'):
        technical['jpeg_markers'] = jpeg['markers']
    if jpeg.get('comments'):
        for i, c in enumerate(jpeg['comments'][:5]):
            embedded[f'JPEG_COM_{i}'] = c
    for item in jpeg.get('xmp_snippets') or []:
        embedded.update({k: str(v) for k, v in item.items()})
    if png.get('chunks'):
        technical['png_chunks'] = png['chunks']
    embedded.update(png.get('text') or {})

    try:
        from PIL import Image
        with Image.open(filepath) as img:
            technical['width'] = img.width
            technical['height'] = img.height
            technical['mode'] = img.mode
            technical['format'] = img.format
            if img.info:
                for k in ('dpi', 'compression', 'icc_profile', 'exif'):
                    if k in img.info and img.info[k]:
                        if k == 'icc_profile' and isinstance(img.info[k], bytes):
                            technical['icc_profile_bytes'] = len(img.info[k])
                        elif k != 'exif':
                            technical[k] = str(img.info[k])[:200]
            exif_b = img.info.get('exif') if img.info else None
            if exif_b and len(exif_b) > 20:
                technical['pillow_exif_bytes'] = len(exif_b)
    except Exception:
        pass

    hashes = _file_hashes(filepath)
    resolved_url = (sidecar or {}).get('resolved_url') or source_url
    domain = urlparse(source_url).netloc if source_url else ''
    if sidecar and sidecar.get('domain'):
        domain = sidecar['domain']

    google_hints = _parse_google_cdn_hints(resolved_url or '')
    if google_hints:
        technical['google_cdn'] = google_hints
        for k, v in google_hints.items():
            if k.startswith('cdn_') and v:
                embedded[f'Google_{k}'] = str(v)

    page_url = source_url
    if sidecar and sidecar.get('page_title'):
        page_meta['page_title'] = sidecar['page_title']
        embedded['Scrape_Page_Title'] = sidecar['page_title'][:300]
    if sidecar and sidecar.get('page_url'):
        page_url = sidecar['page_url']
    elif sidecar and sidecar.get('imgref'):
        page_url = sidecar['imgref']
    elif source_url and any(x in (domain or '').lower() for x in ('nasa.gov', 'wikimedia', 'esa.int', 'noaa.gov')):
        page_url = source_url

    if page_url and page_url.startswith('http') and not page_url.startswith('data:'):
        page_meta = _fetch_page_metadata(page_url)
        if source_url and page_url != source_url:
            img_page = _fetch_page_metadata(source_url)
            for k, v in img_page.items():
                if k not in page_meta:
                    page_meta[f'image_{k}'] = v

    if sidecar:
        technical['download'] = {
            'source_url': sidecar.get('source_url'),
            'resolved_url': sidecar.get('resolved_url'),
            'content_type': sidecar.get('content_type'),
            'content_length': sidecar.get('content_length'),
            'downloaded_at': sidecar.get('downloaded_at'),
            'domain': sidecar.get('domain') or domain,
            'source_kind': sidecar.get('source_kind'),
            'page_url': sidecar.get('page_url'),
            'imgref': sidecar.get('imgref'),
            'fetched_via_wayback': sidecar.get('fetched_via_wayback'),
        }
        if sidecar.get('http_headers'):
            technical['http_headers'] = sidecar['http_headers']
            for hk, hv in sidecar['http_headers'].items():
                embedded[f'HTTP_{hk}'] = str(hv)[:300]

    if page_meta.get('og_title') or page_meta.get('page_title'):
        title = page_meta.get('og_title') or page_meta.get('page_title')
        embedded['Page_Title'] = title
        if not result.get('description'):
            result['description'] = {'PageTitle': title}
    if page_meta.get('og_description') or page_meta.get('description'):
        embedded['Page_Description'] = (
            page_meta.get('og_description') or page_meta.get('description')
        )

    _merge_into_raw_tags(result, embedded)

    if not result.get('exif'):
        result['exif'] = {
            'camera': None,
            'settings': None,
            'datetime': None,
            'image': {
                'width': technical.get('width'),
                'height': technical.get('height'),
                'mode': technical.get('mode'),
                'format': technical.get('format'),
            },
        }
    elif result['exif'].get('image'):
        img = result['exif']['image']
        for k in ('width', 'height', 'mode', 'format'):
            if not img.get(k) and technical.get(k):
                img[k] = technical[k]

    field_count = len(embedded) + len(technical) + len(hashes) + len(page_meta)
    has_classic_exif = bool(
        (result.get('exif') or {}).get('camera')
        or (result.get('exif') or {}).get('settings')
        or result.get('location')
    )

    web_meta = {
        'source': 'web_enrichment',
        'source_url': source_url,
        'resolved_url': resolved_url,
        'domain': domain or (sidecar or {}).get('domain'),
        'source_kind': (sidecar or {}).get('source_kind'),
        'page_url': (sidecar or {}).get('page_url'),
        'page': page_meta,
        'embedded': embedded,
        'technical': technical,
        'hashes': hashes,
        'has_embedded_blocks': bool(embedded or jpeg.get('markers') or png.get('chunks')),
        'has_classic_exif': has_classic_exif,
        'field_count': field_count,
        'summary_az': _build_summary(sidecar, domain, embedded, page_meta, technical, has_classic_exif),
    }
    result['web_metadata'] = web_meta
    result['metadata_richness'] = 'high' if field_count >= 5 else ('medium' if field_count >= 2 else 'low')
    return result


def _parse_google_cdn_hints(url: str) -> Dict[str, Any]:
    """googleusercontent linklərindən ölçü/ipuçları (=w800-h600 və s.)."""
    if not url:
        return {}
    hints: Dict[str, Any] = {}
    m = re.search(r'=w(\d+)-h(\d+)', url)
    if m:
        hints['cdn_width'] = int(m.group(1))
        hints['cdn_height'] = int(m.group(2))
    m2 = re.search(r'=s(\d+)', url)
    if m2:
        hints['cdn_max_edge'] = int(m2.group(1))
    if 'googleusercontent.com' in (url or '').lower():
        hints['cdn'] = 'Google'
    return hints


def _build_summary(sidecar, domain, embedded, page_meta, technical, has_classic_exif) -> str:
    parts = []
    if sidecar and sidecar.get('source_kind') == 'google':
        parts.append('Google şəkil axını')
    if domain:
        parts.append(f'Mənbə: {domain}')
    if sidecar and sidecar.get('page_url'):
        parts.append('məqalə/səhifə metadata əlavə edildi')
    if page_meta.get('og_title'):
        parts.append(f'Başlıq: {page_meta["og_title"][:80]}')
    if technical.get('width'):
        parts.append(f'{technical["width"]}×{technical.get("height", "?")} px')
    if embedded:
        parts.append(f'{len(embedded)} daxili mətn/blok')
    if technical.get('jpeg_markers'):
        parts.append('JPEG: ' + ', '.join(technical['jpeg_markers'][:4]))
    if not has_classic_exif:
        parts.append('klassik kamera EXIF yoxdur (veb axını)')
    return '; '.join(parts) if parts else 'Texniki fayl metadata'
