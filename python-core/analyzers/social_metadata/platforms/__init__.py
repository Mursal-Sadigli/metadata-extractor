"""Platform parser registry."""

from analyzers.social_metadata.platforms import facebook, instagram, tiktok, twitter

PLATFORMS = [tiktok, instagram, twitter, facebook]


def detect_platform_from_url(url: str) -> str:
    u = (url or '').lower()
    for p in PLATFORMS:
        if p.matches_url(u):
            return p.PLATFORM
    if 'youtube.com' in u or 'youtu.be' in u:
        return 'youtube'
    return 'social'


def get_platform_module(name: str):
    for p in PLATFORMS:
        if p.PLATFORM == name:
            return p
    return None
