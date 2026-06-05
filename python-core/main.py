"""
Metadata Extractor — CLI Entry Point
"""

import argparse
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from utils.file_detector import detect_file_type, scan_directory, is_supported_file
from extractors.image_extractor import ImageExtractor
from extractors.pdf_extractor import PdfExtractor
from extractors.audio_extractor import AudioExtractor
from extractors.document_extractor import DocumentExtractor
from extractors.video_extractor import VideoExtractor
from analyzers.geo_analyzer import analyze_location
from analyzers.geolocation_analyzer import (
    analyze_advanced_geolocation,
    analyze_text_geolocation,
    apply_best_guess_to_location,
)
from analyzers.language_analyzer import analyze_language, analyze_multiple_texts
from analyzers.ai_analyzer import analyze_image_ai
from analyzers.astronomy_analyzer import analyze_sun_position
from analyzers.terrain_analyzer import extract_skyline_and_terrain
from downloaders.url_downloader import is_url, download_from_url
from reporters.json_reporter import save_single_result, save_batch_results, print_summary
from reporters.csv_reporter import save_csv_report

EXTRACTORS = {
    'image': ImageExtractor(),
    'pdf': PdfExtractor(),
    'audio': AudioExtractor(),
    'document': DocumentExtractor(),
    'video': VideoExtractor(),
}


def _attach_software_traces(payload, filepath, metadata=None):
    """Agent/proqram izlərini cavaba əlavə edir."""
    if not filepath or not os.path.isfile(filepath):
        return payload
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


def process_file(filepath, args):
    file_info = detect_file_type(filepath)
    file_type = file_info['type']
    
    if file_type == 'unknown':
        return None

    if args.only == 'ai':
        if file_type == 'image':
            ai_res = analyze_image_ai(filepath)
            # OCR mətnini dil analizi edək
            lang_res = None
            if ai_res and ai_res.get('extracted_text'):
                texts = {"ocr": " ".join(ai_res['extracted_text'])}
                lang_res = analyze_multiple_texts(texts)
            return {'file_info': file_info, 'type': file_type, 'ai': ai_res, 'language': lang_res}
        return {'file_info': file_info, 'type': file_type}

    if args.only == 'restore':
        if file_type != 'image':
            return {'file_info': file_info, 'type': file_type, 'error': 'Bərpa analizi yalnız şəkil üçündür.'}
        from analyzers.image_restoration_analyzer import analyze_restore_and_metadata
        extra = getattr(args, 'text', None)
        restore_res = analyze_restore_and_metadata(filepath, extra_text=extra)
        return {'file_info': file_info, 'type': file_type, 'restore_analyze': restore_res}

    if args.only == 'vision':
        from analyzers.vision_ml_analyzer import analyze_vision_ml
        if file_type == 'image':
            conf = getattr(args, 'object_confidence', 0.15) or 0.15
            vision = analyze_vision_ml(filepath, conf_threshold=conf)
            return {'file_info': file_info, 'type': file_type, 'vision_ml': vision}
        if file_type == 'video':
            vision = analyze_vision_ml(filepath, conf_threshold=getattr(args, 'object_confidence', 0.15) or 0.15)
            num_frames = getattr(args, 'video_frames', 3) or 3
            video_result = VideoExtractor().extract(filepath, num_frames=num_frames)
            return {
                'file_info': file_info,
                'type': file_type,
                'video': video_result,
                'active_frame': getattr(args, 'video_frame', 0),
                'vision_ml': vision,
            }
        return {'file_info': file_info, 'type': file_type, 'error': 'Computer Vision yalnız şəkil/video/GIF üçündür.'}

    if args.only == 'faces':
        from analyzers.face_privacy_analyzer import analyze_face_privacy
        if file_type == 'image':
            fp_res = analyze_face_privacy(
                filepath,
                anonymize=getattr(args, 'anonymize', False),
                method=getattr(args, 'anon_method', 'blur') or 'blur',
                strength=getattr(args, 'anon_strength', 3) or 3,
                padding=getattr(args, 'anon_padding', 0.18) or 0.18,
            )
            return {'file_info': file_info, 'type': file_type, **fp_res}
        if file_type == 'video':
            num_frames = getattr(args, 'video_frames', 3) or 3
            video_result = VideoExtractor().extract(filepath, num_frames=num_frames)
            frame_path = _video_frame_path(video_result, getattr(args, 'video_frame', 0))
            if not frame_path:
                return {'file_info': file_info, 'type': file_type, 'video': video_result, 'error': 'Frame çıxarılmadı'}
            fp_res = analyze_face_privacy(
                frame_path,
                anonymize=getattr(args, 'anonymize', False),
                method=getattr(args, 'anon_method', 'blur') or 'blur',
                strength=getattr(args, 'anon_strength', 3) or 3,
                padding=getattr(args, 'anon_padding', 0.18) or 0.18,
            )
            return {
                'file_info': file_info,
                'type': file_type,
                'video': video_result,
                'active_frame': getattr(args, 'video_frame', 0),
                **fp_res,
            }
        return {'file_info': file_info, 'type': file_type, 'error': 'Üz məxfiliyi yalnız şəkil/video üçündür.'}

    if args.only == 'social_meta':
        from analyzers.social_metadata import analyze_social_file
        if file_type not in ('image', 'video'):
            return {
                'file_info': file_info,
                'type': file_type,
                'error': 'Sosial metadata yalnız şəkil və video faylları üçündür.',
            }
        target = filepath
        video_result = None
        if file_type == 'video':
            num_frames = getattr(args, 'video_frames', 3) or 3
            video_result = VideoExtractor().extract(filepath, num_frames=num_frames)
        social_res = analyze_social_file(
            filepath,
            video_frame=getattr(args, 'video_frame', 0),
        )
        payload = {
            'file_info': file_info,
            'type': file_type,
            'social_meta': social_res,
        }
        if video_result:
            payload['video'] = video_result
            payload['active_frame'] = getattr(args, 'video_frame', 0)
        return payload

    if args.only == 'tracking':
        if file_type != 'video':
            return {'file_info': file_info, 'type': file_type, 'error': 'Video izləmə yalnız video faylları üçündür.'}
        from analyzers.video_tracking_analyzer import analyze_video_tracking
        tr = analyze_video_tracking(
            filepath,
            tracker=getattr(args, 'tracker', 'bytetrack') or 'bytetrack',
            conf_threshold=getattr(args, 'object_confidence', 0.15) or 0.15,
            sample_fps=getattr(args, 'sample_fps', 2.0) or 2.0,
            max_duration_sec=getattr(args, 'max_duration', 120) or 120,
            enable_face_reid=getattr(args, 'face_reid', False),
            anonymize_first=getattr(args, 'anonymize', False),
            anon_method=getattr(args, 'anon_method', 'blur') or 'blur',
            anon_strength=getattr(args, 'anon_strength', 3) or 3,
        )
        return {'file_info': file_info, 'type': file_type, 'video_tracking': tr}

    if args.only == 'objects':
        from analyzers.object_detection_analyzer import analyze_object_detection
        conf = getattr(args, 'object_confidence', 0.15) or 0.15
        if file_type == 'image':
            od_res = analyze_object_detection(filepath, conf_threshold=conf)
            return {'file_info': file_info, 'type': file_type, **od_res}
        if file_type == 'video':
            num_frames = getattr(args, 'video_frames', 3) or 3
            video_result = VideoExtractor().extract(filepath, num_frames=num_frames)
            frame_path = _video_frame_path(video_result, getattr(args, 'video_frame', 0))
            if not frame_path:
                return {'file_info': file_info, 'type': file_type, 'video': video_result, 'error': 'Frame çıxarılmadı'}
            od_res = analyze_object_detection(frame_path, conf_threshold=conf)
            return {
                'file_info': file_info,
                'type': file_type,
                'video': video_result,
                'active_frame': getattr(args, 'video_frame', 0),
                **od_res,
            }
        return {'file_info': file_info, 'type': file_type, 'error': 'Obyekt aşkarlanması yalnız şəkil/video üçündür.'}

    if args.only == 'forensics':
        if file_type == 'image':
            from analyzers.forensics_analyzer import analyze_forensics
            for_res = analyze_forensics(filepath)
            return {'file_info': file_info, 'type': file_type, 'forensics': for_res}
        if file_type == 'video':
            num_frames = getattr(args, 'video_frames', 3) or 3
            video_result = VideoExtractor().extract(filepath, num_frames=num_frames)
            frame_path = _video_frame_path(video_result, getattr(args, 'video_frame', 0))
            if not frame_path:
                return {'file_info': file_info, 'type': file_type, 'video': video_result, 'error': 'Frame çıxarılmadı'}
            from analyzers.forensics_analyzer import analyze_forensics
            return {
                'file_info': file_info, 'type': file_type, 'video': video_result,
                'forensics': analyze_forensics(frame_path),
                'active_frame': getattr(args, 'video_frame', 0),
            }
        return {'file_info': file_info, 'type': file_type, 'error': 'Forensics yalnız şəkil/video üçündür.'}

    extractor = EXTRACTORS.get(file_type)
    if not extractor:
        return None

    if file_type == 'video':
        num_frames = getattr(args, 'video_frames', 3) or 3
        result = extractor.extract(filepath, num_frames=num_frames)
        frame_path = _video_frame_path(result, getattr(args, 'video_frame', 0))
        if frame_path and args.only in ('exif', 'location', 'osint', 'all'):
            img_meta = ImageExtractor().extract(frame_path)
            result['frame_metadata'] = img_meta
            if args.only == 'exif':
                out = {
                    'file_info': result.get('file_info'),
                    'type': 'video',
                    'video': result,
                    'exif': img_meta.get('exif'),
                    'raw_tags': img_meta.get('raw_tags'),
                    'warnings': img_meta.get('warnings'),
                }
                out = _attach_software_traces(out, frame_path, img_meta)
                from analyzers.image_internal_analyzer import analyze_image_internal_structure
                internal = analyze_image_internal_structure(frame_path)
                if internal.get('status') == 'success':
                    out['internal_structure'] = internal
                return out
            if args.only == 'location':
                from analyzers.file_carving_ml import analyze_file_carving_ml
                from analyzers.location_resolver import resolve_image_location
                from analyzers.web_image_location import gather_web_location_hints

                extra = [args.text] if getattr(args, 'text', None) else None
                web_texts, web_cands = gather_web_location_hints(frame_path, img_meta)
                merged = list(extra or []) + web_texts
                file_carving_ml = analyze_file_carving_ml(frame_path)
                location, location_inference, loc_warnings = resolve_image_location(
                    frame_path,
                    img_meta.get('location'),
                    carving=file_carving_ml,
                    extra_texts=merged or None,
                    web_candidates=web_cands,
                )
                if loc_warnings:
                    img_meta['warnings'] = (img_meta.get('warnings') or []) + loc_warnings
                if location and location.get('latitude') is not None:
                    geo = analyze_location(location['latitude'], location['longitude'])
                    if geo:
                        location['address'] = geo
                return {
                    'file_info': result.get('file_info'),
                    'type': 'video',
                    'video': result,
                    'location': location,
                    'location_inference': location_inference,
                    'file_carving_ml': file_carving_ml,
                    'warnings': img_meta.get('warnings'),
                    'active_frame': getattr(args, 'video_frame', 0),
                }
            if args.only == 'osint' and frame_path:
                from analyzers.osint_analyzer import analyze_osint
                osint_res = analyze_osint(frame_path, img_meta)
                terr_res = extract_skyline_and_terrain(frame_path)
                if terr_res.get('status') == 'success':
                    osint_res['terrain'] = terr_res
                ai_res = analyze_image_ai(frame_path)
                if ai_res:
                    osint_res['ai'] = ai_res
                return {
                    'file_info': result.get('file_info'),
                    'type': 'video',
                    'video': result,
                    'osint': osint_res,
                }
            if args.only == 'all':
                return result
        return {'file_info': result.get('file_info'), 'type': 'video', 'video': result}
    else:
        result = extractor.extract(filepath)

    if args.only == 'exif':
        if file_type in ('audio', 'video'):
            from analyzers.media_metadata_analyzer import analyze_media_metadata
            return analyze_media_metadata(
                filepath, file_type, video_frame=getattr(args, 'video_frame', 0),
            )
        out = {
            'file_info': result.get('file_info'),
            'type': result.get('type'),
            'exif': result.get('exif'),
            'raw_tags': result.get('raw_tags'),
            'warnings': result.get('warnings'),
        }
        out = _attach_software_traces(out, filepath, result)
        if file_type == 'image':
            from analyzers.image_internal_analyzer import analyze_image_internal_structure
            internal = analyze_image_internal_structure(filepath)
            if internal.get('status') == 'success':
                out['internal_structure'] = internal
                if internal.get('warnings'):
                    out['warnings'] = (out.get('warnings') or []) + internal['warnings']
        return out

    if args.only == 'location':
        location = result.get('location')
        location_inference = None
        carved_metadata = None
        file_carving_ml = None
        extra_texts = [args.text] if getattr(args, 'text', None) else None

        if file_type == 'image':
            from analyzers.file_carving_ml import analyze_file_carving_ml
            from analyzers.location_resolver import resolve_image_location
            from analyzers.web_image_location import gather_web_location_hints

            file_carving_ml = analyze_file_carving_ml(filepath)
            web_texts, web_cands = gather_web_location_hints(filepath, result)
            merged_texts = list(extra_texts or []) + web_texts
            location, location_inference, loc_warnings = resolve_image_location(
                filepath,
                result.get('location'),
                carving=file_carving_ml,
                extra_texts=merged_texts or None,
                web_candidates=web_cands,
            )
            if loc_warnings:
                result['warnings'] = (result.get('warnings') or []) + loc_warnings
            from analyzers.carved_metadata_analyzer import analyze_carved_metadata
            carved_metadata = analyze_carved_metadata(filepath)

        if location:
            lat = location.get('latitude')
            lon = location.get('longitude')
            if lat is not None and lon is not None:
                geo = analyze_location(lat, lon)
                if geo:
                    location['address'] = geo

                if result.get('exif') and result['exif'].get('datetime'):
                    dt = (
                        result['exif']['datetime'].get('original')
                        or result['exif']['datetime'].get('modified')
                        or result['exif']['datetime'].get('inferred_from_filename')
                    )
                    if dt:
                        astro = analyze_sun_position(lat, lon, dt)
                        if astro and "error" not in astro:
                            location['astronomy'] = astro

                if file_type == 'image':
                    from analyzers.reverse_weather_analyzer import analyze_reverse_weather
                    rw = analyze_reverse_weather(filepath, result, lat, lon, None)
                    if rw and rw.get('status') != 'no_coordinates':
                        location['reverse_weather'] = rw

            return {
                'file_info': result.get('file_info'),
                'type': result.get('type'),
                'location': location,
                'location_inference': location_inference,
                'carved_metadata': carved_metadata,
                'file_carving_ml': file_carving_ml,
                'warnings': result.get('warnings'),
            }
        return {
            'file_info': result.get('file_info'),
            'type': result.get('type'),
            'location': None,
            'location_inference': location_inference,
            'carved_metadata': carved_metadata,
            'file_carving_ml': file_carving_ml,
            'warnings': result.get('warnings'),
        }
        
    if args.only == 'media':
        if file_type not in ('audio', 'video'):
            return {
                'file_info': file_info,
                'type': file_type,
                'error': 'Media analizi yalnız audio/video üçündür',
            }
        from analyzers.media_metadata_analyzer import analyze_media_metadata
        return analyze_media_metadata(
            filepath, file_type, video_frame=getattr(args, 'video_frame', 0),
        )

    if args.only == 'propagation':
        if file_type != 'image':
            return {'file_info': result.get('file_info'), 'type': file_type, 'error': 'Yayılma analizi yalnız şəkil üçündür.'}
        from analyzers.image_propagation_analyzer import analyze_image_propagation
        pub = os.environ.get('PUBLIC_APP_URL') or os.environ.get('PUBLIC_IMAGE_BASE_URL')
        public_url = None
        if pub and result.get('file_info'):
            fn = os.path.basename(filepath)
            public_url = f'{pub.rstrip("/")}/uploads/{fn}'
        prop = analyze_image_propagation(
            filepath, result,
            include_reverse_search=True,
            public_image_url=public_url,
        )
        return {
            'file_info': result.get('file_info'),
            'type': file_type,
            'image_propagation': prop,
        }

    if args.only == 'web_timeline':
        if file_type != 'image':
            return {'file_info': result.get('file_info'), 'type': file_type, 'error': 'Veb xronologiya yalnız şəkil üçündür.'}
        from analyzers.image_web_timeline_analyzer import analyze_image_web_timeline
        pub = os.environ.get('PUBLIC_APP_URL') or os.environ.get('PUBLIC_IMAGE_BASE_URL')
        public_url = None
        if pub and result.get('file_info'):
            fn = os.path.basename(filepath)
            public_url = f'{pub.rstrip("/")}/uploads/{fn}'
        tl = analyze_image_web_timeline(filepath, public_url)
        return {
            'file_info': result.get('file_info'),
            'type': file_type,
            'web_timeline': tl,
        }

    if args.only == 'reverse_image':
        if file_type != 'image':
            return {'file_info': result.get('file_info'), 'type': file_type, 'error': 'Tərs şəkil axtarışı yalnız şəkil üçündür.'}
        from analyzers.reverse_image_search_analyzer import analyze_reverse_image_search
        pub = os.environ.get('PUBLIC_APP_URL') or os.environ.get('PUBLIC_IMAGE_BASE_URL')
        public_url = None
        if pub and result.get('file_info'):
            fn = os.path.basename(filepath)
            public_url = f'{pub.rstrip("/")}/uploads/{fn}'
        ris = analyze_reverse_image_search(filepath, public_url)
        return {
            'file_info': result.get('file_info'),
            'type': file_type,
            'reverse_image_search': ris,
        }

    if args.only == 'osint':
        from analyzers.osint_analyzer import analyze_osint
        # Hava durumu üçün əvvəlcə exif/location məlumatını çıxarırıq
        osint_res = analyze_osint(filepath, result)
        
        if file_type == 'image':
            from analyzers.terrain_analyzer import extract_skyline_and_terrain
            from analyzers.steganography_analyzer import analyze_steganography

            terr_res = extract_skyline_and_terrain(filepath)
            if terr_res.get('status') == 'success':
                osint_res['terrain'] = terr_res

            stego_res = analyze_steganography(filepath)
            if stego_res and stego_res.get('status') != 'error':
                osint_res['steganography'] = stego_res

            from analyzers.image_internal_analyzer import analyze_image_internal_structure
            internal = analyze_image_internal_structure(filepath)
            if internal.get('status') == 'success':
                osint_res['internal_structure'] = {
                    'embedded_file_detected': internal.get('embedded_file_detected'),
                    'embedded_findings': internal.get('embedded_findings'),
                    'steganography_suspicious': internal.get('steganography_suspicious'),
                }
                if stego_res and internal.get('embedded_findings'):
                    stego_res['embedded_findings'] = internal['embedded_findings']
                    if internal.get('embedded_file_detected'):
                        stego_res['findings'] = (stego_res.get('findings') or []) + [
                            f"Struktur skanı: {len(internal['embedded_findings'])} gömülü/trailing tapıntı"
                        ]
                        stego_res['stego_score'] = max(stego_res.get('stego_score', 0), 60)
                        stego_res['suspicious'] = stego_res['stego_score'] >= 55

            ai_res = analyze_image_ai(filepath)
            if ai_res:
                osint_res['ai'] = ai_res

        payload = {
            'file_info': result.get('file_info'),
            'type': result.get('type'),
            'osint': osint_res,
        }
        return payload

    # Bütün analiz (all)
    if result.get('location'):
        lat = result['location'].get('latitude')
        lon = result['location'].get('longitude')
        if lat is not None and lon is not None:
            geo = analyze_location(lat, lon)
            if geo: result['location']['address'] = geo
            
            if result.get('exif') and result['exif'].get('datetime'):
                dt = (
                    result['exif']['datetime'].get('original')
                    or result['exif']['datetime'].get('modified')
                    or result['exif']['datetime'].get('inferred_from_filename')
                )
                if dt:
                    astro = analyze_sun_position(lat, lon, dt)
                    if astro and "error" not in astro:
                        result['location']['astronomy'] = astro

            if file_type == 'image':
                from analyzers.reverse_weather_analyzer import analyze_reverse_weather
                rw = analyze_reverse_weather(filepath, result)
                if rw and rw.get('status') != 'no_coordinates':
                    result['location']['reverse_weather'] = rw

    if file_type == 'image':
        terr_res = extract_skyline_and_terrain(filepath)
        if terr_res.get('status') == 'success':
            result['terrain'] = terr_res

    if args.ai and file_type == 'image':
        ai_res = analyze_image_ai(filepath)
        if ai_res: result['ai'] = ai_res

    texts_to_analyze = {}
    if result.get('description'): texts_to_analyze.update(result['description'])
    if result.get('ai') and result['ai'].get('extracted_text'):
        texts_to_analyze['ocr'] = " ".join(result['ai']['extracted_text'])
    if args.text: texts_to_analyze['user_input'] = args.text

    if texts_to_analyze:
        result['language'] = analyze_multiple_texts(texts_to_analyze)

    if file_type in ('image', 'pdf', 'document', 'video'):
        _attach_software_traces(result, filepath, result)

    return result

def _load_env_file():
    """Layihə kökündəki .env faylını oxuyur (məs. RAPIDAPI_KEY)."""
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key and value and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


def main():
    _load_env_file()
    parser = argparse.ArgumentParser()
    parser.add_argument('path', nargs='?', help='Fayl yolu, qovluq və ya URL')
    parser.add_argument('--instagram', help='İnstagram istifadəçi adını kəşfiyyat etmək üçün')
    parser.add_argument('--max-posts', type=int, default=5, help='İnstagram OSINT-də maksimum post sayı (default: 5)')
    parser.add_argument('-r', '--recursive', action='store_true')
    parser.add_argument('-o', '--output')
    parser.add_argument('--format', choices=['json', 'csv', 'both'], default='json')
    parser.add_argument('--ai', action='store_true')
    parser.add_argument('--only', choices=['exif', 'location', 'geocode', 'ai', 'vision', 'restore', 'forensics', 'faces', 'objects', 'tracking', 'osint', 'reverse_image', 'web_timeline', 'propagation', 'media', 'social_meta', 'all'], default='all')
    parser.add_argument('--object-confidence', type=float, default=0.15, help='YOLO etibar həddi (0.08-0.9)')
    parser.add_argument('--tracker', choices=['bytetrack', 'botsort'], default='bytetrack', help='Video MOT tracker')
    parser.add_argument('--sample-fps', type=float, default=2.0, help='Video tracking nümunə FPS')
    parser.add_argument('--max-duration', type=float, default=120, help='Video tracking max saniyə')
    parser.add_argument('--face-reid', action='store_true', help='Video üz re-id (SFace)')
    parser.add_argument('--anonymize', action='store_true', help='Üz regionlarını blur/pixelate et')
    parser.add_argument('--anon-method', choices=['blur', 'pixelate'], default='blur')
    parser.add_argument('--anon-strength', type=int, default=3, help='Blur/pixelate gücü (1-5)')
    parser.add_argument('--anon-padding', type=float, default=0.18, help='Üz bbox genişləndirmə nisbəti')
    parser.add_argument('--geocode-text', help='Mətn/ünvan/koordinat geocoding (faylsız)')
    parser.add_argument('--compare', nargs=2, metavar=('FILE_A', 'FILE_B'), help='İki şəkli müqayisə et')
    parser.add_argument('--timeline', nargs='+', metavar='FILE', help='Çoxlu şəkil EXIF marşrut analizi')
    parser.add_argument('--archive', help='WhatsApp/Telegram ZIP export')
    parser.add_argument('--url', help='Sosial media URL (social_meta)')
    parser.add_argument('--fetch-image-url', help='Birbaşa şəkil URL — uploads')
    parser.add_argument('--upload-dir', help='--fetch-image-url üçün hədəf qovluq')
    parser.add_argument('--video-frames', type=int, default=3)
    parser.add_argument('--video-frame', type=int, default=0)
    parser.add_argument('--max-archive-items', type=int, default=20)
    parser.add_argument('--gps-only', action='store_true')
    parser.add_argument('-t', '--text')
    parser.add_argument('--thumbnails', action='store_true')
    parser.add_argument('--keep', action='store_true')
    parser.add_argument('-q', '--quiet', action='store_true')

    args = parser.parse_args()

    # gps-only geriyə uyğunluq üçün
    if args.gps_only: args.only = 'location'

    if args.geocode_text or (args.only == 'geocode' and args.text):
        text = args.geocode_text or args.text or ''
        print(json.dumps(analyze_text_geolocation(text), ensure_ascii=False))
        sys.exit(0)

    if args.instagram:
        try:
            from analyzers.instagram_analyzer import analyze_instagram_profile
            ig_res = analyze_instagram_profile(args.instagram, max_posts=args.max_posts)
            print(json.dumps(ig_res, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"error": f"İnstagram analizi xətası: {str(e)}"}, ensure_ascii=False))
        sys.exit(0)

    if getattr(args, 'timeline', None):
        from analyzers.timeline_mapping_analyzer import analyze_timeline_mapping
        paths = [p for p in args.timeline if os.path.isfile(p)]
        if len(paths) < 2:
            print(json.dumps({
                "status": "insufficient_files",
                "error": "Ən azı 2 mövcud fayl lazımdır",
                "module": "timeline_mapping",
            }, ensure_ascii=False))
            sys.exit(1)
        print(json.dumps(analyze_timeline_mapping(paths), ensure_ascii=False))
        sys.exit(0)

    if args.compare:
        from analyzers.compare_analyzer import compare_images
        a, b = args.compare
        if not os.path.isfile(a) or not os.path.isfile(b):
            print(json.dumps({"error": "Müqayisə faylları tapılmadı"}, ensure_ascii=False))
            sys.exit(1)
        print(json.dumps(compare_images(a, b), ensure_ascii=False))
        sys.exit(0)

    if args.archive:
        from extractors.archive_extractor import analyze_archive
        out_dir = os.path.dirname(os.path.abspath(args.archive))
        res = analyze_archive(args.archive, out_dir, max_items=args.max_archive_items)
        print(json.dumps(res, ensure_ascii=False))
        sys.exit(0)

    if getattr(args, 'fetch_image_url', None):
        from downloaders.url_downloader import fetch_image_to_uploads
        upload_dir = args.upload_dir or os.path.join(
            os.path.dirname(__file__), '..', 'backend', 'uploads',
        )
        res = fetch_image_to_uploads(
            args.fetch_image_url,
            os.path.abspath(upload_dir),
        )
        if res.get('status') == 'success' and res.get('sidecar') and res.get('filename'):
            from analyzers.web_image_metadata import save_url_sidecar
            fpath = os.path.join(os.path.abspath(upload_dir), res['filename'])
            save_url_sidecar(fpath, res['sidecar'])
        print(json.dumps(res, ensure_ascii=False))
        sys.exit(0 if res.get('status') == 'success' else 1)

    url_target = args.url or (args.path if args.path and is_url(args.path) else None)
    if url_target and args.only == 'social_meta':
        from analyzers.social_metadata import fetch_social_metadata
        out_dir = os.path.join(os.path.dirname(__file__), '..', 'backend', 'uploads')
        os.makedirs(out_dir, exist_ok=True)
        res = fetch_social_metadata(url_target, output_dir=out_dir)
        print(json.dumps(res, ensure_ascii=False))
        sys.exit(0)

    if not args.path:
        print(json.dumps({"error": "Path, --instagram, --archive, --compare və ya --url lazımdır"}))
        sys.exit(1)

    downloaded_file = None
    target_path = args.path

    if is_url(args.path):
        downloaded_file = download_from_url(args.path, keep=args.keep)
        if not downloaded_file:
            sys.exit(1)
        target_path = downloaded_file

    results = []
    try:
        if os.path.isfile(target_path):
            res = process_file(target_path, args)
            if res: results.append(res)
        elif os.path.isdir(target_path):
            files = scan_directory(target_path, recursive=args.recursive)
            for f in files:
                res = process_file(f, args)
                if res: results.append(res)
    finally:
        if downloaded_file and not args.keep:
            try: os.unlink(downloaded_file)
            except OSError: pass

    if not results:
        sys.exit(0)

    if args.quiet:
        print(json.dumps(results if len(results)>1 else results[0], ensure_ascii=False))
        sys.exit(0)

    if args.format in ['json', 'both']:
        if len(results) == 1: save_single_result(results[0], args.output)
        else: save_batch_results(results, args.output)
        
    if args.format in ['csv', 'both']:
        save_csv_report(results, args.output)

if __name__ == '__main__':
    main()
