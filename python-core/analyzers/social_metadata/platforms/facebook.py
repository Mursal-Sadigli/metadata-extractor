"""Facebook URL və yt-dlp mapping."""

import re
from typing import Any, Dict

PLATFORM = 'facebook'

_VIDEO_RE = re.compile(r'facebook\.com/(?:watch/?\?v=|[\w.]+/videos/)(\d+)', re.I)


def matches_url(url: str) -> bool:
    u = url.lower()
    return 'facebook.com' in u or 'fb.watch' in u or 'fb.com' in u


def normalize_url(url: str) -> str:
    return url.strip().split('?')[0]


def parse_url_ids(url: str) -> Dict[str, Any]:
    ids = {'webpage_url': url}
    m = _VIDEO_RE.search(url)
    if m:
        ids['content_id'] = m.group(1)
    m2 = re.search(r'fb\.watch/([\w-]+)', url, re.I)
    if m2:
        ids['display_id'] = m2.group(1)
    return ids


def map_yt_dlp(data: dict, url: str) -> Dict[str, Any]:
    content_id = str(data.get('id') or '') or None
    m = _VIDEO_RE.search(url)
    if m and not content_id:
        content_id = m.group(1)

    return {
        'platform': PLATFORM,
        'title': data.get('title') or data.get('fulltitle'),
        'description': (data.get('description') or '')[:500],
        'unique_ids': {
            'content_id': content_id,
            'display_id': data.get('display_id'),
            'uploader_id': data.get('uploader_id') or data.get('channel'),
            'channel_id': data.get('channel_id'),
            'shortcode': None,
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
