"""Opsional cookie/sessiya — .env və ya mühit dəyişənləri."""

import os
from typing import List, Optional, Tuple


def _load_dotenv():
    """Layihə kökündəki .env faylını oxuyur (python-dotenv olmadan)."""
    if getattr(_load_dotenv, '_done', False):
        return
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')),
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env')),
    ]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, _, val = line.partition('=')
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
        except OSError:
            pass
        break
    _load_dotenv._done = True


def _resolve_path(path: Optional[str]) -> Optional[str]:
    _load_dotenv()
    if not path:
        return None
    path = path.strip().strip('"').strip("'")
    if os.path.isfile(path):
        return path
    return None


def get_yt_dlp_cookie_args(platform: str) -> Tuple[List[str], List[str]]:
    """
    yt-dlp üçün --cookies argmentləri və xəbərdarlıqlar.
    Returns: (extra_cmd_args, warnings)
    """
    args: List[str] = []
    warnings: List[str] = []
    platform = (platform or '').lower()

    env_map = {
        'twitter': 'YTDLP_COOKIES_TWITTER',
        'x': 'YTDLP_COOKIES_TWITTER',
        'facebook': 'YTDLP_COOKIES_FACEBOOK',
        'instagram': 'YTDLP_COOKIES_INSTAGRAM',
    }

    key = env_map.get(platform)
    if key:
        cookie_path = _resolve_path(os.environ.get(key))
        if cookie_path:
            args.extend(['--cookies', cookie_path])
        elif platform in ('facebook', 'instagram'):
            warnings.append(
                f'{platform.capitalize()}: cookie faylı tapılmadı ({key}). '
                'Bəzi postlar üçün .env-də cookie təyin edin.'
            )

    generic = _resolve_path(os.environ.get('YTDLP_COOKIES'))
    if generic and not args:
        args.extend(['--cookies', generic])

    return args, warnings


def get_instagram_session_path() -> Optional[str]:
    """instaloader sessiya faylı."""
    for key in ('INSTAGRAM_SESSION_FILE', 'INSTALOADER_SESSION'):
        path = _resolve_path(os.environ.get(key))
        if path:
            return path
    return None
