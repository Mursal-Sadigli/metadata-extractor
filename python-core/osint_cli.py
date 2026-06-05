"""Yüngül CLI — OSINT analizi (/api/analyze osint), main.py + EasyOCR yükləmədən."""

import argparse
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def _light_osint() -> bool:
    if os.environ.get('LIGHT_OSINT', '').strip().lower() in ('0', 'false', 'no'):
        return False
    if os.environ.get('LIGHT_OSINT', '').strip().lower() in ('1', 'true', 'yes'):
        return True
    return os.environ.get('RENDER', '').strip().lower() in ('true', '1')


def run_osint(filepath: str) -> dict:
    from utils.file_detector import detect_file_type
    from extractors.image_extractor import ImageExtractor
    from analyzers.osint_analyzer import analyze_osint

    file_info = detect_file_type(filepath)
    file_type = file_info.get('type')
    if file_type not in ('image', 'video'):
        return {
            'file_info': file_info,
            'type': file_type,
            'error': 'OSINT yalnız şəkil və video üçündür.',
        }

    result = ImageExtractor().extract(filepath) if file_type == 'image' else {'file_info': file_info, 'type': file_type}
    osint_res = analyze_osint(filepath, result if file_type == 'image' else None)
    light = _light_osint()

    if file_type == 'image' and not light:
        from analyzers.terrain_analyzer import extract_skyline_and_terrain
        from analyzers.steganography_analyzer import analyze_steganography
        terr_res = extract_skyline_and_terrain(filepath)
        if terr_res.get('status') == 'success':
            osint_res['terrain'] = terr_res
        stego_res = analyze_steganography(filepath)
        if stego_res and stego_res.get('status') != 'error':
            osint_res['steganography'] = stego_res
        try:
            from analyzers.image_internal_analyzer import analyze_image_internal_structure
            internal = analyze_image_internal_structure(filepath)
            if internal.get('status') == 'success':
                osint_res['internal_structure'] = {
                    'embedded_file_detected': internal.get('embedded_file_detected'),
                    'embedded_findings': internal.get('embedded_findings'),
                    'steganography_suspicious': internal.get('steganography_suspicious'),
                }
        except Exception:
            pass
        try:
            from analyzers.ai_analyzer import analyze_image_ai
            ai_res = analyze_image_ai(filepath)
            if ai_res:
                osint_res['ai'] = ai_res
        except Exception as e:
            osint_res['ai'] = {'error': str(e)}
    elif light:
        osint_res['light_mode'] = True
        osint_res['note_az'] = (
            'Render yüngül OSINT: tərs şəkil axtarışı və hava. '
            'Steganografiya/OCR/terrain lokal serverdə aktivdir.'
        )

    return {
        'file_info': result.get('file_info') or file_info,
        'type': result.get('type') or file_type,
        'osint': osint_res,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path')
    args = parser.parse_args()

    if not os.path.isfile(args.path):
        print(json.dumps({'error': 'Fayl tapılmadı'}, ensure_ascii=False))
        sys.exit(1)

    try:
        payload = run_osint(args.path)
    except Exception as e:
        print(json.dumps({'error': f'OSINT xətası: {e}'}, ensure_ascii=False))
        sys.exit(1)

    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)


if __name__ == '__main__':
    main()
