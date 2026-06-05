"""TikTok URL və yt-dlp mapping."""

import re
from typing import Any, Dict

PLATFORM = 'tiktok'

_URL_RE = re.compile(
    r'tiktok\.com/(?:@[\w.]+/video/(\d+)|t/(\w+))',
    re.I,
)


def matches_url(url: str) -> bool:
    return 'tiktok.com' in url or 'vm.tiktok.com' in url


def normalize_url(url: str) -> str:
    url = url.strip()
    m = re.search(r'(https?://(?:www\.)?tiktok\.com/@[\w.]+/video/\d+)', url, re.I)
    if m:
        return m.group(1)
    return url


def parse_url_ids(url: str) -> Dict[str, Any]:
    ids = {}
    m = _URL_RE.search(url)
    if m:
        ids['content_id'] = m.group(1) or m.group(2)
    m2 = re.search(r'tiktok\.com/@([\w.]+)', url, re.I)
    if m2:
        ids['uploader_id'] = f'@{m2.group(1)}'
    ids['webpage_url'] = url
    return ids


def map_yt_dlp(data: dict, url: str) -> Dict[str, Any]:
    out = {
        'platform': PLATFORM,
        'title': data.get('title') or data.get('fulltitle'),
        'description': (data.get('description') or '')[:500],
        'unique_ids': {
            'content_id': str(data.get('id') or '') or None,
            'display_id': data.get('display_id'),
            'uploader_id': data.get('uploader_id') or data.get('creator'),
            'channel_id': data.get('channel_id'),
            'shortcode': None,
            'webpage_url': data.get('webpage_url') or url,
        },
        'author': {
            'name': data.get('uploader') or data.get('creator'),
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
    track = data.get('track')
    if track:
        out['description'] = (out.get('description') or '') + f' | Track: {track}'
    return out
