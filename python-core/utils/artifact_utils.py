"""Forensics artifact fayl adları və skorlar."""

import os


def path_to_filename(path):
    if not path:
        return None
    return os.path.basename(str(path).replace('\\', '/'))


def ela_manipulation_score(max_diff):
    """ELA max_difference → 0-100 skor və risk səviyyəsi."""
    try:
        d = float(max_diff)
    except (TypeError, ValueError):
        return 0, 'low'
    if d < 12:
        return min(35, int(d * 2.5)), 'low'
    if d < 35:
        return min(65, 25 + int(d * 1.1)), 'medium'
    return min(100, 45 + int(d * 1.3)), 'high'
