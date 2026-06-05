"""Yüklənmiş fayl axını: platform aşkarlanması + EXIF/ffprobe."""

import os
import re
from typing import Any, Dict, Optional, Tuple

from analyzers.social_metadata.schema import (
    empty_result, error_result, finalize, format_upload_date,
    merge_location, merge_device, add_source, add_warning,
)

_FILENAME_PATTERNS = [
    (r'tiktok', 'tiktok'),
    (r'instagram|insta_|^ig[_-]', 'instagram'),
    (r'twitter|^x[_-]|tweet', 'twitter'),
    (r'facebook|fb[_-]|fbvideo', 'facebook'),
]

_SOCIAL_APPS = {'instagram', 'tiktok', 'facebook', 'twitter', 'capcut'}


def detect_platform_from_file(filepath: str, traces: Optional[dict] = None) -> Tuple[Optional[str], float]:
    """(platform, confidence)"""
    basename = os.path.basename(filepath).lower()
    scores: Dict[str, float] = {}

    for pattern, platform in _FILENAME_PATTERNS:
        if re.search(pattern, basename, re.I):
            scores[platform] = scores.get(platform, 0) + 0.5

    if traces:
        for t in traces.get('traces') or []:
            name = (t.get('application') or '').lower()
            cat = t.get('category') or ''
            if cat == 'social' or any(a in name for a in _SOCIAL_APPS):
                for platform in ('instagram', 'tiktok', 'twitter', 'facebook'):
                    if platform in name or (platform == 'twitter' and 'x' == name):
                        scores[platform] = scores.get(platform, 0) + (t.get('confidence') or 0.5)

    if not scores:
        return None, 0.0

    best = max(scores, key=scores.get)
    return best, min(1.0, scores[best])


def _parse_ffprobe_location(tags: dict) -> Tuple[Optional[float], Optional[float]]:
    loc = tags.get('location') or tags.get('com.apple.quicktime.location.ISO6709')
    if not loc:
        return None, None
    coords = re.findall(r'[-+]?\d+\.?\d*', str(loc))
    if len(coords) >= 2:
        try:
            return float(coords[0]), float(coords[1])
        except ValueError:
            pass
    return None, None


def _parse_creation_time(tags: dict) -> Tuple[Optional[str], Optional[str]]:
    raw = tags.get('creation_time') or tags.get('date') or tags.get('com.apple.quicktime.creationdate')
    if not raw:
        return None, None
    s = str(raw).replace('T', ' ').replace('Z', ' UTC')
    iso = str(raw)
    if 'T' in iso and not iso.endswith('Z'):
        iso = iso + 'Z' if '+' not in iso else iso
    return s[:19] + (' UTC' if 'UTC' not in s else ''), iso


def _extract_image_metadata(filepath: str) -> dict:
    from extractors.image_extractor import ImageExtractor
    return ImageExtractor().extract(filepath)


def _extract_video_metadata(filepath: str) -> dict:
    from extractors.video_extractor import VideoExtractor
    return VideoExtractor().extract(filepath, num_frames=1)


def analyze_social_file(filepath: str, video_frame: int = 0) -> Dict[str, Any]:
    if not os.path.isfile(filepath):
        return error_result('Fayl tapılmadı', 'file')

    ext = os.path.splitext(filepath)[1].lower()
    image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.heif', '.bmp'}
    video_exts = {'.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v'}

    if ext not in image_exts and ext not in video_exts:
        return error_result('Sosial metadata yalnız şəkil və video faylları üçündür.', 'file')

    result = empty_result('file')
    add_warning(
        result,
        'Fayl analizi: post ID çox vaxt tapılmır. Dəqiq metadata üçün orijinal post URL istifadə edin.',
    )

    traces = None
    try:
        from analyzers.software_trace_analyzer import analyze_software_traces
        traces = analyze_software_traces(filepath, None)
        add_source(result, 'software_trace')
    except Exception:
        pass

    platform, plat_conf = detect_platform_from_file(filepath, traces)
    result['platform'] = platform
    if platform:
        add_source(result, 'filename')
    else:
        add_warning(result, 'Platform avtomatik aşkarlanmadı — ümumi fayl metadata göstərilir.')

    meta = None
    container_tags = {}

    if ext in image_exts:
        meta = _extract_image_metadata(filepath)
        add_source(result, 'exif')
    else:
        video_meta = _extract_video_metadata(filepath)
        add_source(result, 'ffprobe')
        container = video_meta.get('container') or {}
        container_tags = container.get('tags') or {}
        frames = video_meta.get('frames') or []
        idx = min(max(0, video_frame), max(0, len(frames) - 1))
        frame_path = frames[idx].get('path') if frames else None
        if frame_path and os.path.isfile(frame_path):
            meta = _extract_image_metadata(frame_path)
            add_source(result, 'frame_exif')
        result['media']['duration_sec'] = container.get('duration_sec')
        result['media']['width'] = container.get('width')
        result['media']['height'] = container.get('height')

        lat, lon = _parse_ffprobe_location(container_tags)
        if lat is not None:
            merge_location(result, lat, lon, source='ffprobe')

        disp, iso = _parse_creation_time(container_tags)
        if disp:
            result['upload_date'] = disp
            result['upload_date_iso'] = iso

        encoder = container_tags.get('encoder') or container_tags.get('com.android.version')
        if encoder:
            merge_device(result, software=str(encoder), source='ffprobe')

        make = container_tags.get('com.apple.quicktime.make') or container_tags.get('make')
        model = container_tags.get('com.apple.quicktime.model') or container_tags.get('model')
        software = container_tags.get('com.apple.quicktime.software') or container_tags.get('software')
        if make or model or software:
            merge_device(result, make=make, model=model, software=software, source='ffprobe')

    if meta:
        exif = meta.get('exif') or {}
        cam = exif.get('camera') or {}
        if cam.get('make') or cam.get('model'):
            merge_device(
                result,
                make=cam.get('make'),
                model=cam.get('model'),
                software=cam.get('software') or cam.get('lens'),
                source='exif',
            )

        dt = exif.get('datetime') or {}
        raw_dt = dt.get('original') or dt.get('modified') or dt.get('inferred_from_filename')
        if raw_dt and not result.get('upload_date'):
            result['upload_date'] = str(raw_dt).replace(':', '-', 2)

        loc = meta.get('location')
        if loc and loc.get('latitude') is not None:
            merge_location(
                result,
                loc.get('latitude'),
                loc.get('longitude'),
                source='exif',
            )

        img_info = exif.get('image') or {}
        if not result['media'].get('width'):
            result['media']['width'] = img_info.get('width')
            result['media']['height'] = img_info.get('height')

    if traces:
        for t in traces.get('traces') or []:
            app = t.get('application')
            if app and not result['device'].get('software'):
                merge_device(result, software=app, source='inferred')
                break

    result['raw']['file_basename'] = os.path.basename(filepath)
    result['raw']['platform_detection_confidence'] = round(plat_conf, 2)
    if traces:
        result['raw']['software_traces'] = traces.get('traces', [])[:5]

    return finalize(result)
