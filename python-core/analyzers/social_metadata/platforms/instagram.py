"""Instagram URL, yt-dlp və opsional instaloader."""

import os
import re
import sys
from typing import Any, Dict, Optional

PLATFORM = 'instagram'

_SHORTCODE_RE = re.compile(r'instagram\.com/(?:p|reel|reels|tv)/([\w-]+)', re.I)
_PROFILE_RE = re.compile(
    r'(?:https?://)?(?:www\.)?instagram\.com/([\w.]+)/?(?:\?|#|$)',
    re.I,
)
_RESERVED_USERNAMES = frozenset({
    'p', 'reel', 'reels', 'tv', 'stories', 'explore', 'accounts', 'direct',
    'tags', 'about', 'legal', 'privacy', 'developer', 'api', 'www', 'login',
})


def matches_url(url: str) -> bool:
    return 'instagram.com' in url


def normalize_url(url: str) -> str:
    return url.strip().split('?')[0].rstrip('/')


def is_profile_url(url: str) -> bool:
    """Post/reel deyil, profil linkidirsə True."""
    u = url.lower().split('?')[0]
    if any(x in u for x in ('/p/', '/reel/', '/reels/', '/tv/', '/stories/')):
        return False
    username = extract_profile_username(url)
    return bool(username)


def extract_profile_username(url: str) -> Optional[str]:
    m = _PROFILE_RE.search(url.strip())
    if not m:
        return None
    name = m.group(1).lower()
    if name in _RESERVED_USERNAMES:
        return None
    return m.group(1)


def parse_url_ids(url: str) -> Dict[str, Any]:
    ids = {'webpage_url': url}
    if is_profile_url(url):
        username = extract_profile_username(url)
        if username:
            ids['uploader_id'] = f'@{username}'
        return ids
    m = _SHORTCODE_RE.search(url)
    if m:
        ids['shortcode'] = m.group(1)
        ids['content_id'] = m.group(1)
    return ids


def _session_directories():
    """instaloader sessiya qovluqları (Windows + Linux)."""
    dirs = []
    local = os.environ.get('LOCALAPPDATA')
    if local:
        dirs.append(os.path.join(local, 'Instaloader'))
    dirs.append(os.path.expanduser('~/.instaloader'))
    seen = set()
    out = []
    for d in dirs:
        norm = os.path.normcase(os.path.abspath(d))
        if norm not in seen and os.path.isdir(d):
            seen.add(norm)
            out.append(d)
    return out


def _load_session_file(loader, session_path: str) -> bool:
    basename = os.path.basename(session_path)
    if basename.startswith('session-'):
        username = basename.replace('session-', '').split('.')[0]
    else:
        username = os.path.splitext(basename)[0]
    loader.load_session_from_file(username, session_path)
    return True


def _load_instaloader(session_path: Optional[str] = None):
    import instaloader
    loader = instaloader.Instaloader(
        quiet=True,
        download_pictures=False,
        download_videos=False,
        save_metadata=False,
    )
    if session_path and os.path.isfile(session_path):
        try:
            _load_session_file(loader, session_path)
            return loader, True
        except Exception as e:
            print(f'  [!] Sessiya faylı yüklənmədi: {e}', file=sys.stderr)

    for session_dir in _session_directories():
        for fname in sorted(os.listdir(session_dir), reverse=True):
            if not fname.startswith('session-'):
                continue
            path = os.path.join(session_dir, fname)
            try:
                _load_session_file(loader, path)
                print(f'  [i] Instagram sessiya: {path}', file=sys.stderr)
                return loader, True
            except Exception:
                continue
    return loader, False


def fetch_profile_metadata(username: str, session_path: Optional[str] = None) -> dict:
    """Profil URL üçün vahid sosial metadata (instaloader)."""
    from analyzers.social_metadata.schema import (
        empty_result, error_result, finalize, add_source, add_warning, format_upload_date,
    )

    username = (username or '').strip().lstrip('@')
    if not username:
        return error_result('Instagram istifadəçi adı tapılmadı.')

    try:
        import instaloader
    except ImportError:
        return error_result('instaloader quraşdırılmayıb: pip install instaloader')

    result = empty_result('url')
    result['platform'] = PLATFORM
    result['content_type'] = 'profile'
    result['title'] = f'@{username}'
    result['unique_ids']['uploader_id'] = f'@{username}'
    result['unique_ids']['webpage_url'] = f'https://www.instagram.com/{username}/'

    try:
        loader, session_ok = _load_instaloader(session_path)
        if not session_ok:
            add_warning(
                result,
                'Instagram sessiya/cookie yoxdur — bəzi profillər bloklana bilər. '
                '.env faylında INSTAGRAM_SESSION_FILE təyin edin.',
            )

        profile = instaloader.Profile.from_username(loader.context, username)
        add_source(result, 'instaloader')

        result['unique_ids']['content_id'] = str(profile.userid)
        result['unique_ids']['channel_id'] = str(profile.userid)
        result['author'] = {'name': profile.full_name or username, 'id': str(profile.userid)}
        result['title'] = profile.full_name or f'@{username}'
        result['description'] = (profile.biography or '')[:500]
        result['thumbnail_url'] = profile.profile_pic_url
        result['engagement'] = {
            'views': None,
            'likes': None,
            'comments': None,
            'followers': profile.followers,
            'following': profile.followees,
        }
        result['raw']['profile'] = {
            'username': username,
            'is_private': profile.is_private,
            'is_verified': profile.is_verified,
            'external_url': profile.external_url,
            'posts_count': profile.mediacount,
        }

        if profile.is_private:
            add_warning(result, 'Profil gizlidir — post metadata əlçatan deyil.')
            return finalize(result)

        # Son postdan nümunə metadata (tarix, lokasiya)
        try:
            for post in profile.get_posts():
                if post.date_utc:
                    disp, iso = format_upload_date(timestamp=int(post.date_utc.timestamp()))
                    result['raw']['latest_post_date'] = disp
                    result['raw']['latest_post_date_iso'] = iso
                if post.location:
                    from analyzers.social_metadata.schema import merge_location
                    merge_location(
                        result,
                        post.location.lat,
                        post.location.lng,
                        place_name=post.location.name,
                        source='platform',
                    )
                    result['raw']['latest_post_location'] = post.location.name
                result['raw']['latest_post_url'] = f'https://www.instagram.com/p/{post.shortcode}/'
                break
        except Exception as pe:
            add_warning(result, f'Son post metadata: {pe}')

        return finalize(result)

    except instaloader.exceptions.ProfileNotExistsException:
        if not session_ok:
            return error_result(_login_required_message(username))
        return error_result(f'Instagram profili tapılmadı: @{username}')
    except instaloader.exceptions.ConnectionException as e:
        return error_result(_instagram_error_message(username, str(e), session_ok))
    except Exception as e:
        return error_result(_instagram_error_message(username, str(e), session_ok))


def _login_required_message(username: str) -> str:
    local = os.environ.get('LOCALAPPDATA', '')
    session_hint = os.path.join(local, 'Instaloader', f'session-{username}') if local else ''
    default_session = r'C:\Users\...\AppData\Local\Instaloader\session-ISTIFADECI'
    return (
        f'Instagram giriş tələb edir (@{username}).\n'
        '1) 15–30 dəqiqə gözləyin (Instagram rate-limit).\n'
        '2) Brauzerdə instagram.com-a daxil olun.\n'
        '3) Terminal: instaloader --login SIZIN_IG_ISTIFADECINIZ\n'
        f'4) .env: INSTAGRAM_SESSION_FILE={session_hint or default_session}'
    )


def _instagram_error_message(username: str, msg: str, session_ok: bool) -> str:
    low = msg.lower()
    if 'wait a few minutes' in low or 'please wait' in low:
        return (
            'Instagram müvəqqəti sorğuları bloklayıb (rate-limit). '
            '15–30 dəqiqə gözləyin, brauzerdə hesaba daxil olun, sonra yenidən cəhd edin.'
        )
    if 'unexpected null login' in low:
        return (
            'Instagram CLI girişi rədd etdi. Səbəblər: səhv şifrə, 2FA, və ya blok. '
            'Brauzerdə daxil olun; instaloader-i bir neçə saat sonra yenidən işə salın.'
        )
    if '401' in msg or '403' in msg or 'forbidden' in low or 'unauthorized' in low:
        if not session_ok:
            return _login_required_message(username)
        return (
            f'Instagram sessiyası etibarsızdır (@{username}). '
            'Köhnə session faylını silin və instaloader --login ilə yenidən daxil olun.'
        )
    return f'Instagram profil analizi uğursuz: {msg[:250]}'


def map_yt_dlp(data: dict, url: str) -> Dict[str, Any]:
    shortcode = None
    m = _SHORTCODE_RE.search(url)
    if m:
        shortcode = m.group(1)

    return {
        'platform': PLATFORM,
        'title': data.get('title') or data.get('fulltitle'),
        'description': (data.get('description') or '')[:500],
        'unique_ids': {
            'content_id': str(data.get('id') or shortcode or '') or None,
            'display_id': data.get('display_id'),
            'uploader_id': data.get('uploader_id') or data.get('channel'),
            'channel_id': data.get('channel_id'),
            'shortcode': shortcode,
            'webpage_url': data.get('webpage_url') or url,
        },
        'author': {
            'name': data.get('uploader') or data.get('channel'),
            'id': data.get('uploader_id') or data.get('channel_id'),
        },
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
        'timestamp': data.get('timestamp') or data.get('release_timestamp'),
        'tags': (data.get('tags') or [])[:15],
        'thumbnail_url': data.get('thumbnail'),
    }


def enrich_with_instaloader(result: dict, url: str, session_path: Optional[str]) -> dict:
    """Sessiya varsa shortcode üzrə əlavə metadata."""
    shortcode = (result.get('unique_ids') or {}).get('shortcode')
    if not shortcode:
        m = _SHORTCODE_RE.search(url)
        shortcode = m.group(1) if m else None
    if not shortcode:
        return result

    try:
        import instaloader
    except ImportError:
        result.setdefault('warnings', []).append(
            'instaloader quraşdırılmayıb — Instagram post metadata məhdud qalacaq.'
        )
        return result

    try:
        loader, _ = _load_instaloader(session_path)

        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        from analyzers.social_metadata.schema import (
            add_source, merge_device, merge_location, format_upload_date,
        )

        add_source(result, 'instaloader')
        ids = result.setdefault('unique_ids', {})
        ids['content_id'] = ids.get('content_id') or str(post.mediaid)
        ids['shortcode'] = post.shortcode
        ids['uploader_id'] = ids.get('uploader_id') or f'@{post.owner_username}'

        if post.date_utc:
            disp, iso = format_upload_date(timestamp=int(post.date_utc.timestamp()))
            result['upload_date'] = result.get('upload_date') or disp
            result['upload_date_iso'] = result.get('upload_date_iso') or iso

        if post.location:
            merge_location(result, post.location.lat, post.location.lng,
                           place_name=post.location.name, source='platform')

        caption = post.caption or ''
        if caption and not result.get('description'):
            result['description'] = caption[:500]

        result.setdefault('engagement', {})
        result['engagement']['likes'] = result['engagement'].get('likes') or post.likes
        result['engagement']['comments'] = result['engagement'].get('comments') or post.comments

        result.setdefault('author', {})
        result['author']['name'] = result['author'].get('name') or post.owner_username
        result['author']['id'] = result['author'].get('id') or str(post.owner_id)

        cap_lower = caption.lower()
        if 'iphone' in cap_lower:
            merge_device(result, make='Apple', model='iPhone', source='inferred')
        elif 'android' in cap_lower or 'samsung' in cap_lower:
            merge_device(result, software='Android', source='inferred')

    except Exception as e:
        result.setdefault('warnings', []).append(
            f'Instagram instaloader: {e}. Cookie/sessiya tələb oluna bilər.'
        )
        print(f'  [!] instaloader: {e}', file=sys.stderr)

    return result
