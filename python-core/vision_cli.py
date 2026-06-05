"""Yüngül CLI — Computer Vision (/api/vision-ml), main.py import etmədən."""

import argparse
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path')
    parser.add_argument('--confidence', type=float, default=0.16)
    args = parser.parse_args()

    if not os.path.isfile(args.path):
        print(json.dumps({'error': 'Fayl tapılmadı'}, ensure_ascii=False))
        sys.exit(1)

    from utils.file_detector import detect_file_type
    from analyzers.vision_ml_analyzer import analyze_vision_ml

    file_info = detect_file_type(args.path)
    vision = analyze_vision_ml(args.path, conf_threshold=args.confidence)
    payload = {
        'file_info': file_info,
        'type': file_info.get('type', 'image'),
        'vision_ml': vision,
    }
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0 if vision.get('status') != 'error' else 1)


if __name__ == '__main__':
    main()
