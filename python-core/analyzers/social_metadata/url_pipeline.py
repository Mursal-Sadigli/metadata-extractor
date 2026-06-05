"""URL axını: yt-dlp + platform parser + thumbnail."""

import json
import os
import re
import subprocess
import sys
import tempfile

import requests

from downloaders.url_downloader import is_social_media_url
from analyzers.social_metadata.schema import (
    empty_result, error_result, finalize, format_upload_date,
    merge_location, merge_device, add_source, add_warning,
)
from analyzers.social_metadata.auth import get_yt_dlp_cookie_args, get_instagram_session_path
from analyzers.social_metadata.platforms import (
    tiktok, instagram, twitter, facebook,
)
from analyzers.social_metadata.platforms import detect_platform_from_url, get_platform_module

_PLATFORM_MODULES = {
    'tiktok': tiktok,
    'instagram': instagram,
    'twitter': twitter,
    'facebook': facebook,
}


def _normalize_url(url: str, platform: str) -> str:
    mod = _PLATFORM_MODULES.get(platform)
    if mod and hasattr(mod, 'normalize_url'):
        return mod.normalize_url(url)
    return url.strip()


def _parse_yt_dlp_json(stdout: str) -> dict:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith('{'):
            return json.loads(line)
    raise ValueError('yt-dlp JSON tapılmadı')


def _download_thumbnail(url: str, output_dir: str):
    try:
        r = requests.get(
            url,
            timeout=20,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; MetadataExtractor/1.0)'},
        )
        r.raise_for_status()
        path = os.path.join(output_dir, f'thumb_{abs(hash(url)) % 10 ** 8}.jpg')
        with open(path, 'wb') as f:
            f.write(r.content)
        return path
    except Exception as e:
        print(f'  [!] thumbnail: {e}', file=sys.stderr)
        return None


def _thumbnail_meta(filepath: str):
    try:
        from extractors.image_extractor import ImageExtractor
        meta = ImageExtractor().extract(filepath)
        return meta.get('exif'), meta.get('location')
    except Exception:
        return None, None


def _apply_url_parse_ids(result: dict, url: str, platform: str):
    mod = _PLATFORM_MODULES.get(platform)
    if not mod:
        return
    parsed = mod.parse_url_ids(url)
    ids = result.setdefault('unique_ids', {})
    for k, v in parsed.items():
        if v and not ids.get(k):
            ids[k] = v
    add_source(result, 'url_parse')


def _merge_platform_yt_dlp(result: dict, data: dict, url: str, platform: str):
    mod = get_platform_module(platform)
    if mod:
        mapped = mod.map_yt_dlp(data, url)
    else:
        mapped = {
            'platform': platform,
            'title': data.get('title'),
            'description': (data.get('description') or '')[:500],
            'unique_ids': {
                'content_id': str(data.get('id') or '') or None,
                'uploader_id': data.get('uploader_id'),
                'webpage_url': data.get('webpage_url') or url,
            },
            'author': {'name': data.get('uploader'), 'id': data.get('uploader_id')},
            'engagement': {
                'views': data.get('view_count'),
                'likes': data.get('like_count'),
                'comments': data.get('comment_count'),
            },
            'media': {
                'duration_sec': data.get('duration'),
                'width': data.get('width'),
                'height': data.get('height'),
            },
            'upload_date_raw': data.get('upload_date'),
            'timestamp': data.get('timestamp'),
            'tags': (data.get('tags') or [])[:15],
            'thumbnail_url': data.get('thumbnail'),
        }

    result['platform'] = mapped.get('platform') or platform
    result['title'] = mapped.get('title')
    result['description'] = mapped.get('description')
    result['tags'] = mapped.get('tags') or []
    result['thumbnail_url'] = mapped.get('thumbnail_url')

    for key in ('unique_ids', 'author', 'engagement', 'media'):
        incoming = mapped.get(key) or {}
        existing = result.setdefault(key, {})
        for k, v in incoming.items():
            if v is not None and existing.get(k) is None:
                existing[k] = v

    disp, iso = format_upload_date(
        mapped.get('upload_date_raw'),
        mapped.get('timestamp'),
    )
    if disp:
        result['upload_date'] = disp
        result['upload_date_iso'] = iso

    loc = data.get('location')
    if isinstance(loc, str):
        coords = re.findall(r'[-+]?\d*\.?\d+', loc)
        if len(coords) >= 2:
            merge_location(result, coords[0], coords[1], source='platform')
    elif isinstance(loc, dict):
        merge_location(
            result,
            loc.get('latitude') or loc.get('lat'),
            loc.get('longitude') or loc.get('lon') or loc.get('lng'),
            place_name=loc.get('name'),
            source='platform',
        )


def _parse_location_from_description(desc: str, result: dict):
    if not desc:
        return
    m = re.search(r'(?:📍|location:|at:)\s*([^\n#|]{3,80})', desc, re.I)
    if m:
        merge_location(result, None, None, place_name=m.group(1).strip(), source='inferred')
        add_warning(result, 'Lokasiya təsvir mətnindən çıxarılıb (aşağı etibar).')


def fetch_social_metadata(url: str, output_dir=None):
    if not is_social_media_url(url):
        return error_result('Dəstəklənməyən URL (Instagram, TikTok, X, Facebook, YouTube və s.)')

    platform = detect_platform_from_url(url)

    # Instagram profil linki — yt-dlp post extractor deyil
    if platform == 'instagram' and instagram.is_profile_url(url):
        username = instagram.extract_profile_username(url)
        session = get_instagram_session_path()
        return instagram.fetch_profile_metadata(username, session)

    url = _normalize_url(url, platform)

    if not output_dir:
        output_dir = tempfile.gettempdir()
    os.makedirs(output_dir, exist_ok=True)

    result = empty_result('url')
    result['platform'] = platform
    _apply_url_parse_ids(result, url, platform)

    cookie_args, cookie_warnings = get_yt_dlp_cookie_args(platform)
    for w in cookie_warnings:
        add_warning(result, w)

    try:
        cmd = [
            'yt-dlp',
            '--dump-json',
            '--skip-download',
            '--no-warnings',
            '--no-playlist',
            '--user-agent',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            *cookie_args,
            url,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            encoding='utf-8',
            errors='replace',
        )

        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or 'yt-dlp uğursuz').strip()
            if len(err) > 400:
                err = err[:400] + '...'
            if result['unique_ids'].get('content_id'):
                add_warning(result, f'yt-dlp uğursuz: {err}')
                add_source(result, 'url_parse')
            elif platform == 'instagram' and '[instagram:user]' in err.lower():
                return error_result(
                    'Bu Instagram profil linkidir, post/reel linki deyil. '
                    'Post üçün: instagram.com/p/... və ya instagram.com/reel/... istifadə edin. '
                    'Profil analizi üçün yenidən cəhd edin — sessiya lazım ola bilər (.env: INSTAGRAM_SESSION_FILE).'
                )
            else:
                return error_result(err)

        else:
            data = _parse_yt_dlp_json(proc.stdout)
            add_source(result, 'yt-dlp')
            result['raw']['yt_dlp_keys'] = sorted(data.keys())[:40]
            _merge_platform_yt_dlp(result, data, url, platform)

            if platform == 'instagram':
                session = get_instagram_session_path()
                instagram.enrich_with_instaloader(result, url, session)
                if not session:
                    add_warning(
                        result,
                        'Instagram: INSTAGRAM_SESSION_FILE yoxdur — bəzi sahələr boş qala bilər.',
                    )

            _parse_location_from_description(result.get('description'), result)

            thumb = data.get('thumbnail')
            if thumb:
                thumb_path = _download_thumbnail(thumb, output_dir)
                if thumb_path:
                    result['thumbnail_file'] = os.path.basename(thumb_path)
                    exif, location = _thumbnail_meta(thumb_path)
                    if exif:
                        result['thumbnail_exif'] = exif
                        add_source(result, 'thumbnail_exif')
                    if location:
                        result['thumbnail_location'] = location
                        merge_location(
                            result,
                            location.get('latitude'),
                            location.get('longitude'),
                            source='exif',
                        )

        return finalize(result)

    except subprocess.TimeoutExpired:
        return error_result('yt-dlp vaxtı keçdi (120s). Yenidən cəhd edin.')
    except json.JSONDecodeError as e:
        return error_result(f'JSON parse: {e}')
    except FileNotFoundError:
        return error_result('yt-dlp quraşdırılmayıb. Terminalda: pip install -U yt-dlp')
    except Exception as e:
        return error_result(str(e))
