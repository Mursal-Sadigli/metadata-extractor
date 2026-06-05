"""Yüngül analiz CLI — /api/analyze exif üçün main.py tam import etmədən."""

import argparse
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def _attach_software_traces(payload, filepath, metadata=None):
    try:
        from analyzers.software_trace_analyzer import analyze_software_traces
        meta = metadata if metadata is not None else payload
        payload['software_traces'] = analyze_software_traces(filepath, meta)
    except Exception as e:
        payload['software_traces'] = {
            'error': str(e),
            'summary': 'Proqram izi analizi uğursuz oldu.',
            'traces': [],
        }
    return payload


def _video_frame_path(video_result, frame_index=0):
    frames = video_result.get('frames') or []
    if not frames:
        return None
    idx = min(max(0, frame_index), len(frames) - 1)
    return frames[idx].get('path')


def run_exif(filepath, video_frame=0):
    from utils.file_detector import detect_file_type
    from extractors.image_extractor import ImageExtractor
    from extractors.video_extractor import VideoExtractor

    file_info = detect_file_type(filepath)
    file_type = file_info['type']

    if file_type == 'video':
        video_result = VideoExtractor().extract(filepath, num_frames=3)
        frame_path = _video_frame_path(video_result, video_frame)
        if frame_path:
            img_meta = ImageExtractor().extract(frame_path)
            out = {
                'file_info': video_result.get('file_info'),
                'type': 'video',
                'video': video_result,
                'exif': img_meta.get('exif'),
                'raw_tags': img_meta.get('raw_tags'),
                'warnings': img_meta.get('warnings'),
            }
            out = _attach_software_traces(out, frame_path, img_meta)
            try:
                from analyzers.image_internal_analyzer import analyze_image_internal_structure
                internal = analyze_image_internal_structure(frame_path)
                if internal.get('status') == 'success':
                    out['internal_structure'] = internal
            except Exception:
                pass
            return out
        return {'file_info': video_result.get('file_info'), 'type': 'video', 'video': video_result}

    if file_type in ('audio', 'video'):
        from analyzers.media_metadata_analyzer import analyze_media_metadata
        return analyze_media_metadata(filepath, file_type, video_frame=video_frame)

    if file_type != 'image':
        return {'error': f'Dəstəklənməyən fayl tipi: {file_type}', 'file_info': file_info}

    result = ImageExtractor().extract(filepath)
    out = {
        'file_info': result.get('file_info'),
        'type': result.get('type'),
        'exif': result.get('exif'),
        'raw_tags': result.get('raw_tags'),
        'warnings': result.get('warnings'),
        'web_metadata': result.get('web_metadata'),
        'capture_date': result.get('capture_date'),
        'image_propagation': result.get('image_propagation'),
        'residual_recovery': result.get('residual_recovery'),
        'description': result.get('description'),
        'location': result.get('location'),
    }
    out = _attach_software_traces(out, filepath, result)
    try:
        from analyzers.image_internal_analyzer import analyze_image_internal_structure
        internal = analyze_image_internal_structure(filepath)
        if internal.get('status') == 'success':
            out['internal_structure'] = internal
            if internal.get('warnings'):
                out['warnings'] = (out.get('warnings') or []) + internal['warnings']
    except Exception:
        pass
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path')
    parser.add_argument('--only', choices=['exif'], default='exif')
    parser.add_argument('--video-frame', type=int, default=0)
    parser.add_argument('-q', '--quiet', action='store_true')
    args = parser.parse_args()

    if not os.path.isfile(args.path):
        print(json.dumps({'error': 'Fayl tapılmadı'}, ensure_ascii=False))
        sys.exit(1)

    try:
        result = run_exif(args.path, args.video_frame)
    except Exception as e:
        print(json.dumps({'error': f'Analiz xətası: {e}'}, ensure_ascii=False))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


if __name__ == '__main__':
    main()
