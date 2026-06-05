"""
URL Downloader

Şəkil URL (Google Images, birbaşa link) və sosial media yükləmə.
"""

import os
import re
import sys
import time
import random
import mimetypes
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs, unquote

import requests

IMAGE_MAGIC = [
    (b'\xff\xd8\xff', 'jpg'),
    (b'\x89PNG\r\n\x1a\n', 'png'),
    (b'GIF87a', 'gif'),
    (b'GIF89a', 'gif'),
    (b'RIFF', 'webp'),
]

MAX_IMAGE_BYTES = 26_214_400  # 25 MB

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
)


def is_url(path) -> bool:
    try:
        result = urlparse(path)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def is_social_media_url(url: str) -> bool:
    social_domains = [
        'instagram.com', 'twitter.com', 'x.com',
        'facebook.com', 'tiktok.com', 'vk.com',
        'youtube.com', 'youtu.be',
    ]
    domain = urlparse(url).netloc.lower()
    return any(s in domain for s in social_domains)


def is_google_image_url(url: str) -> bool:
    u = url.lower()
    domain = urlparse(url).netloc.lower()
    if 'imgurl=' in u or '/imgres' in u:
        return True
    google_hosts = (
        'googleusercontent.com', 'ggpht.com', 'gstatic.com',
        'google.com', 'google.az', 'google.ru',
    )
    return any(h in domain for h in google_hosts)


KNOWN_IMAGE_CDN_HOSTS = (
    'images.unsplash.com',
    'unsplash.com',
    'upload.wikimedia.org',
    'images-assets.nasa.gov',
    'i.imgur.com',
    'imgur.com',
    'pbs.twimg.com',
    'cloudinary.com',
    'res.cloudinary.com',
    'imgix.net',
    'cdninstagram.com',
    'fbcdn.net',
    'ytimg.com',
    'staticflickr.com',
    'live.staticflickr.com',
)


def is_known_cdn_image_url(url: str) -> bool:
    """Unsplash, Wikimedia və s. — uzantısız, amma tam CDN şəkil linki."""
    if not is_url(url):
        return False
    host = urlparse(url).netloc.lower()
    if any(cdn in host for cdn in KNOWN_IMAGE_CDN_HOSTS):
        return True
    path = urlparse(url).path.lower()
    if re.match(r'^/photo-', path):
        return True
    if re.search(r'/photo-|/image/|/images/|/media/|/thumb/', path):
        return True
    qs = urlparse(url).query.lower()
    if any(k in qs for k in ('auto=format', 'fit=crop', 'ixlib=', 'w=', 'h=', 'q=60', 'fm=')):
        return True
    return False


def is_probable_image_url(url: str) -> bool:
    """Şəkil URL-si kimi görünürsə (sosial post deyil)."""
    if not is_url(url):
        return False
    if is_social_media_url(url):
        return False
    if is_google_image_url(url) or is_known_cdn_image_url(url):
        return True
    path = urlparse(url).path.lower()
    if re.search(r'\.(jpe?g|png|webp|gif|heic|heif|bmp)(\?|$)', path):
        return True
    if re.search(r'/image|/photo|/media|thumbnail|preview', path):
        return True
    return False


def _google_wrapper_refs(url: str) -> Dict[str, Optional[str]]:
    """Google Images /imgres — imgref ilə mənbə səhifə linki."""
    out: Dict[str, Optional[str]] = {'page_url': None, 'imgref': None}
    if not url:
        return out
    qs = parse_qs(urlparse(url).query)
    for key in ('imgref', 'imgrefurl'):
        if key in qs and qs[key]:
            candidate = unquote(qs[key][0]).strip()
            if is_url(candidate) and not is_google_image_url(candidate):
                out['page_url'] = candidate
                out['imgref'] = candidate
                break
    return out


def _page_url_for_image_source(original: str, resolved: str) -> Optional[str]:
    """Şəkil URL-indən məqalə/səhifə linki (Google imgref, NASA və s.)."""
    for u in (original, resolved):
        if not u:
            continue
        g = _google_wrapper_refs(u)
        if g.get('page_url'):
            return g['page_url']
        low = u.lower()
        if 'nasa.gov' in low and '/image-' in low:
            return u.split('?')[0]
        if 'images-assets.nasa.gov' in low:
            return 'https://www.nasa.gov/'
        if 'wikimedia.org' in low:
            return u
    return original if original != resolved else None


def _referer_for_url(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        if 'chinadaily.com' in host:
            return 'https://www.chinadaily.com.cn/'
        if host:
            return f'https://{host}/'
    except Exception:
        pass
    return 'https://www.google.com/'


def _wayback_image_url(original_url: str) -> str:
    """Internet Archive vasitəsilə bloklanmış (403) şəkil linkləri."""
    return f'https://web.archive.org/web/{original_url}'


def _download_bytes(url: str) -> tuple:
    """GET — (data, response) və ya exception."""
    resp = requests.get(
        url,
        headers=_download_headers(url),
        timeout=90,
        allow_redirects=True,
        stream=True,
    )
    resp.raise_for_status()
    chunks = []
    size = 0
    for chunk in resp.iter_content(chunk_size=65536):
        if not chunk:
            continue
        size += len(chunk)
        if size > MAX_IMAGE_BYTES:
            raise ValueError('Şəkil 25 MB-dan böyükdür')
        chunks.append(chunk)
    return b''.join(chunks), resp


def _url_looks_truncated(url: str) -> bool:
    """Kopyalanarkən kəsilmiş link (404 riski) — CDN şəkil linkləri istisna."""
    if is_known_cdn_image_url(url):
        return False

    path = urlparse(url).path.lower()
    basename = os.path.basename(path)

    if re.search(r'\.(jpe?g|png|webp|gif|avif|heic|bmp)(\?|#|$)', path):
        return False
    if re.search(r'\.(jpe?g|png|webp|gif)', url, re.I):
        return False

    # CNET tipli: /hub/.../uuid — .jpg olmadan bitirsə kəsilmişdir
    if ('/hub/' in path or '/a/img/resize/' in path) and not re.search(
        r'\.(jpe?g|png|webp|gif)', basename, re.I
    ):
        if re.search(r'[0-9a-f]{8,}$', basename, re.I) and len(basename) < 40:
            return True

    # Natamam UUID (12 simvoldan az hex son hissə)
    if re.search(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{11}$', path, re.I):
        return True

    if path.endswith('/') or (len(path) < 12 and not urlparse(url).query):
        return True
    return False


def resolve_image_url(url: str) -> str:
    """
    Google Images wrapper linklərindən birbaşa şəkil URL çıxarır.
    """
    url = (url or '').strip()
    if not url:
        return url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for key in ('imgurl', 'url', 'mediaurl'):
        if key in qs and qs[key]:
            candidate = unquote(qs[key][0]).strip()
            if is_url(candidate):
                return candidate
    return url


def upgrade_googleusercontent_url(url: str, max_edge: int = 1920) -> Tuple[str, Optional[str]]:
    """
    lh3.googleusercontent.com/...=w243-h174 kimi kiçik önizləməni analiz üçün böyüdür.
    =s0 və ya =w1920 tam ölçüyə yaxın şəkil verir (OCR, obyekt, qalıq metadata üçün).
    """
    if not url or 'googleusercontent.com' not in url.lower():
        return url, None
    # =w243-h174-n-k-no-nu və ya =s128
    if re.search(r'=[whs]\d+', url, re.I):
        base = re.sub(r'=[whs]\d+.*$', '', url, flags=re.I)
        if not base:
            return url, None
        upgraded = f'{base}=s0'
        note = (
            'Google önizləmə linki avtomatik tam ölçüyə çevrildi (=s0). '
            'Kiçik w243-h174 versiyasında metadata/OCR zəif olur.'
        )
        return upgraded, note
    return url, None


def _guess_extension(data: bytes, content_type: Optional[str], url: str) -> str:
    if len(data) >= 12 and data[4:8] == b'ftyp' and b'avif' in data[8:16]:
        return '.avif'
    for magic, ext in IMAGE_MAGIC:
        if ext == 'webp' and len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return '.webp'
        if data[: len(magic)] == magic:
            return f'.{ext}' if ext != 'jpg' else '.jpg'
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(';')[0].strip())
        if ext and ext in ('.jpe', '.jpeg'):
            ext = '.jpg'
        if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
            return ext
    path = urlparse(url).path.lower()
    m = re.search(r'\.(jpe?g|png|webp|gif)$', path)
    if m:
        e = m.group(1)
        return '.jpg' if e in ('jpeg', 'jpg') else f'.{e}'
    return '.jpg'


def _is_image_bytes(data: bytes) -> bool:
    if len(data) < 12:
        return False
    if data[:3] == b'\xff\xd8\xff':
        return True
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return True
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return True
    if data[:4] == b'RIFF' and len(data) >= 12 and data[8:12] == b'WEBP':
        return True
    if len(data) >= 12 and data[4:8] == b'ftyp' and b'avif' in data[8:16]:
        return True
    return False


def _download_headers(url: str) -> Dict[str, str]:
    """CDN-lər AVIF əvəzinə JPEG versin deyə Accept seçimi."""
    base = {
        'User-Agent': USER_AGENT,
        'Referer': _referer_for_url(url),
    }
    if is_known_cdn_image_url(url):
        base['Accept'] = 'image/jpeg,image/png,image/webp,image/*;q=0.9,*/*;q=0.5'
    else:
        base['Accept'] = 'image/jpeg,image/png,image/webp,image/apng,image/*;q=0.8'
    return base


def _safe_filename(name: str, ext: str) -> str:
    base = re.sub(r'[^a-zA-Z0-9._-]+', '_', name or 'image')[:80]
    if not base.lower().endswith(ext.lower()):
        base = os.path.splitext(base)[0] + ext
    unique = f'{int(time.time() * 1000)}-{random.randint(100000, 999999)}-{base}'
    return unique.replace('..', '.')


def download_from_url(url, output_dir=None, keep=False):
    """URL-dən fayl yüklə (köhnə API — sosial və ya birbaşa)."""
    if not output_dir:
        import tempfile
        output_dir = tempfile.gettempdir()

    if is_social_media_url(url):
        return download_social_media(url, output_dir)

    try:
        resolved = resolve_image_url(url)
        response = requests.get(
            resolved, stream=True, headers=_download_headers(resolved),
            timeout=90, allow_redirects=True,
        )
        response.raise_for_status()
        chunks = []
        size = 0
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            size += len(chunk)
            if size > MAX_IMAGE_BYTES:
                print('  [!] Fayl çox böyükdür (>25MB)', flush=True)
                return None
            chunks.append(chunk)
        data = b''.join(chunks)
        if not _is_image_bytes(data):
            print('  [!] URL şəkil formatı deyil', flush=True)
            return None
        ext = _guess_extension(data, response.headers.get('Content-Type'), resolved)
        filename = os.path.basename(urlparse(resolved).path) or f'downloaded{ext}'
        if '.' not in filename:
            filename = f'downloaded{ext}'
        filepath = os.path.join(output_dir, _safe_filename(filename, ext))
        with open(filepath, 'wb') as f:
            f.write(data)
        return filepath
    except Exception as e:
        print(f'  [!] Birbaşa yükləmə xətası: {e}', flush=True)
        return None


def fetch_image_to_uploads(url: str, output_dir: str) -> Dict[str, Any]:
    """Birbaşa şəkil URL → uploads + metadata üçün fayl."""
    original_input_url = (url or '').strip()
    url = original_input_url
    if not is_url(url):
        return {'status': 'error', 'error': 'Keçərli URL daxil edin (https://...)'}

    if is_social_media_url(url):
        return {
            'status': 'error',
            'error': 'Bu sosial media linkidir. «Link analizi» düyməsini istifadə edin.',
            'hint': 'social_media',
        }

    if 'tbm=isch' in url.lower() and 'imgurl=' not in url.lower():
        return {
            'status': 'error',
            'error': (
                'Google axtarış səhifə linki deyil, şəklin özünün linki lazımdır: '
                'şəkilə sağ klik → «Şəkil ünvanını kopyala» və ya «imgurl=» olan link.'
            ),
            'hint': 'google_search_page',
        }

    resolved = resolve_image_url(url)
    warnings = []
    original_resolved = resolved
    upgrade_note = None
    if is_google_image_url(resolved):
        upgraded, upgrade_note = upgrade_googleusercontent_url(resolved)
        if upgrade_note and upgraded != resolved:
            resolved = upgraded

    if _url_looks_truncated(resolved):
        return {
            'status': 'error',
            'error': (
                'URL kəsilmiş və ya natamam görünür (adətən 404). '
                'Tam linki yenidən kopyalayın — .jpg / .png ilə bitməlidir '
                '(məs: .../unmoonearth.jpg?auto=webp).'
            ),
            'hint': 'truncated_url',
        }

    if is_google_image_url(url) or is_google_image_url(resolved):
        warnings.append(
            'Google/CDN şəkillərində EXIF və GPS adətən silinir. '
            'Qalıq bərpa + OCR/geoparsing işləyir; imgref olan link məqalə konteksti verir.'
        )
    if upgrade_note:
        warnings.append(upgrade_note)

    data = None
    resp = None
    used_wayback = False
    download_urls = [resolved]
    if resolved != original_resolved:
        download_urls.append(original_resolved)

    last_http_error = None
    for idx, try_url in enumerate(download_urls):
        try:
            data, resp = _download_bytes(try_url)
            if idx > 0:
                resolved = try_url
                warnings.append('Tam ölçü (=s0) yüklənmədi; önizləmə versiyası istifadə olundu.')
            break
        except requests.HTTPError as e:
            last_http_error = e
            continue
        except requests.RequestException as e:
            if idx == len(download_urls) - 1:
                return {'status': 'error', 'error': f'Şəkil yüklənmədi: {e}', 'resolved_url': resolved}
            continue

    if data is None and last_http_error is not None:
        e = last_http_error
        status = e.response.status_code if e.response is not None else 0
        if status == 404:
            return {
                'status': 'error',
                'error': (
                    'Şəkil tapılmadı (404). URL tam deyil — sağ klik → Şəkil ünvanını kopyala.'
                ),
                'hint': 'http_404',
                'resolved_url': resolved,
            }
        if status in (401, 403):
            try:
                wb_url = _wayback_image_url(resolved)
                data, resp = _download_bytes(wb_url)
                if _is_image_bytes(data):
                    used_wayback = True
                    warnings.append(
                        'Sayt birbaşa yükləməyə icazə vermir (HTTP 403). '
                        'Şəkil Internet Archive (Wayback) arxivindən götürüldü.'
                    )
                else:
                    data = None
            except Exception:
                data = None
        if data is None:
            if status == 403:
                return {
                    'status': 'error',
                    'error': (
                        'Google şəkli xarici yükləməyə icazə verməyə bilər (HTTP 403). '
                        'Brauzerdə şəkli saxlayıb fayl kimi yükləyin.'
                    ),
                    'hint': 'http_403_hotlink',
                    'resolved_url': resolved,
                }
            return {
                'status': 'error',
                'error': f'Şəkil yüklənmədi (HTTP {status}).',
                'resolved_url': resolved,
            }
    elif data is None:
        return {'status': 'error', 'error': 'Şəkil yüklənmədi', 'resolved_url': resolved}

    if not _is_image_bytes(data):
        alt = resolved
        if 'auto=webp' in alt or 'format=webp' in alt:
            alt = re.sub(r'[?&]auto=webp', '', alt)
            alt = re.sub(r'[?&]format=webp', '', alt)
            try:
                data, resp = _download_bytes(alt)
            except Exception:
                pass
        if not _is_image_bytes(data):
            return {
                'status': 'error',
                'error': (
                    'URL şəkil faylı qaytarmadı. Birbaşa şəkil linki yapışdırın '
                    '(googleusercontent, .jpg, .png və s.).'
                ),
                'resolved_url': resolved,
                'hint': 'not_image_bytes',
            }

    ext = _guess_extension(data, resp.headers.get('Content-Type'), resolved)
    orig = os.path.basename(urlparse(resolved).path) or 'google_image'
    if '.' not in orig:
        orig += ext
    filename = _safe_filename(orig, ext)
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(data)

    grefs = _google_wrapper_refs(url)
    is_google = is_google_image_url(url) or is_google_image_url(resolved)
    sidecar = {
        'source_url': original_input_url,
        'resolved_url': resolved,
        'preview_url': original_resolved if original_resolved != resolved else None,
        'content_type': resp.headers.get('Content-Type') if resp else None,
        'content_length': len(data),
        'downloaded_at': datetime.now(timezone.utc).isoformat(),
        'domain': urlparse(resolved).netloc,
        'page_url': _page_url_for_image_source(original_input_url, resolved),
        'imgref': grefs.get('imgref'),
        'source_kind': 'google' if is_google else 'image_url',
        'fetched_via_wayback': used_wayback,
    }
    if resp is not None:
        hdrs = {}
        for h in ('Last-Modified', 'ETag', 'Cache-Control', 'Content-Length'):
            v = resp.headers.get(h)
            if v:
                hdrs[h] = v
        if hdrs:
            sidecar['http_headers'] = hdrs

    return {
        'status': 'success',
        'filename': filename,
        'originalName': orig,
        'source': 'image_url',
        'source_url': original_input_url,
        'resolved_url': resolved,
        'size_bytes': len(data),
        'warnings': warnings,
        'sidecar': sidecar,
        'note_az': 'URL-dən yüklənib; metadata avtomatik analiz olunur.',
        'auto_metadata': True,
    }


def download_social_media(url, output_dir):
    """Sosial media URL-indən fayl yüklə (yt-dlp vasitəsilə)."""
    import subprocess
    import tempfile
    try:
        temp_dl_dir = tempfile.mkdtemp(dir=output_dir)
        template = os.path.join(temp_dl_dir, '%(title)s.%(ext)s')
        cmd = ['yt-dlp', '-o', template, url]
        subprocess.run(cmd, capture_output=True)
        files = os.listdir(temp_dl_dir)
        if files:
            return os.path.join(temp_dl_dir, files[0])
    except Exception as e:
        print(f'  [!] Sosial media yükləmə xətası: {e}', flush=True)
    return None
