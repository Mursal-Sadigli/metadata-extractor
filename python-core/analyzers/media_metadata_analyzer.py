"""Səs və video metadata — konteyner, tezlik profili, akustik barmaq izi."""

import os
import sys
from typing import Any, Dict, Optional

from extractors.audio_extractor import AudioExtractor
from extractors.video_extractor import VideoExtractor
from analyzers.acoustic_fingerprint_analyzer import analyze_acoustic


def _normalize_tags(tags: Optional[Dict]) -> Dict[str, Any]:
    if not tags:
        return {}
    out = {}
    for k, v in tags.items():
        key = str(k).replace('_', ' ').strip()
        if v is not None and str(v).strip():
            out[key] = str(v)
    return out


def _enrich_video_container(container: Optional[Dict]) -> Dict[str, Any]:
    if not container or container.get('error'):
        return container or {}
    tags = _normalize_tags(container.get('tags'))
    return {
        **{k: v for k, v in container.items() if k != 'tags'},
        'metadata_tags': tags,
        'creation_time': tags.get('creation_time') or tags.get('date'),
        'encoder': tags.get('encoder') or tags.get('encoding tool'),
        'device': tags.get('com.apple.quicktime.make') or tags.get('model'),
        'gps': tags.get('location') or tags.get('com.apple.quicktime.location.ISO6709'),
    }


def analyze_media_metadata(
    filepath: str,
    file_type: str,
    video_frame: int = 0,
) -> Dict[str, Any]:
    """
    Audio (.mp3, .wav, …) və video (.mp4, .avi, …) üçün tam media analizi.
    """
    if file_type not in ('audio', 'video'):
        return {
            'module': 'media_metadata',
            'status': 'error',
            'error': 'Yalnız audio və video faylları dəstəklənir',
            'type': file_type,
        }

    print(f'  [i] Media metadata: {os.path.basename(filepath)} ({file_type})', file=sys.stderr)

    payload: Dict[str, Any] = {
        'module': 'media_metadata',
        'status': 'ok',
        'type': file_type,
        'media_type_az': 'Video' if file_type == 'video' else 'Audio',
        'file_info': None,
        'warnings': [],
    }

    audio_path = filepath
    video_block = None

    if file_type == 'video':
        video_block = VideoExtractor().extract(filepath, num_frames=3)
        payload['file_info'] = video_block.get('file_info')
        payload['video'] = {
            'container': _enrich_video_container(video_block.get('container')),
            'frames': video_block.get('frames', []),
            'warnings': video_block.get('warnings', []),
        }
        payload['warnings'].extend(video_block.get('warnings') or [])

        container = video_block.get('container') or {}
        if container.get('audio_codec'):
            payload['video']['has_audio_track'] = True
        else:
            payload['video']['has_audio_track'] = False
            payload['warnings'].append('Video-da audio track tapılmadı.')

        frames = video_block.get('frames') or []
        if frames:
            idx = min(max(0, video_frame), len(frames) - 1)
            fr = frames[idx]
            payload['active_frame'] = idx
            payload['frame_preview'] = {
                'index': fr.get('index'),
                'timestamp_sec': fr.get('timestamp_sec'),
                'filename': fr.get('filename'),
                'exif': fr.get('exif'),
                'location': fr.get('location'),
            }

        audio_ext = AudioExtractor().extract(filepath)
        payload['embedded_audio_tags'] = audio_ext.get('audio_info')

    else:
        audio_ext = AudioExtractor().extract(filepath)
        payload['file_info'] = audio_ext.get('file_info')
        payload['audio'] = {
            'tags': audio_ext.get('audio_info'),
        }

    payload['audio_analysis'] = analyze_acoustic(filepath, is_video=(file_type == 'video'))

    ac = payload.get('audio_analysis') or {}
    if ac.get('warnings'):
        payload['warnings'].extend(ac['warnings'])

    parts = [f'{payload["media_type_az"]} metadata analizi tamamlandı.']
    if file_type == 'video' and payload.get('video', {}).get('container', {}).get('duration_sec'):
        parts.append(f'Müddət: {payload["video"]["container"]["duration_sec"]:.1f}s.')
    if ac.get('acoustic_fingerprint', {}).get('hash_preview'):
        parts.append(f'Akustik iz: {ac["acoustic_fingerprint"]["hash_preview"]}.')
    payload['summary_az'] = ' '.join(parts)

    return payload
