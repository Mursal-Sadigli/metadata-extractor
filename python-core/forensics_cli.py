"""Yüngül CLI — Kriminalistika (/api/analyze forensics), main.py import etmədən."""

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
    args = parser.parse_args()

    if not os.path.isfile(args.path):
        print(json.dumps({'error': 'Fayl tapılmadı'}, ensure_ascii=False))
        sys.exit(1)

    from utils.file_detector import detect_file_type
    from analyzers.forensics_analyzer import analyze_forensics

    file_info = detect_file_type(args.path)
    file_type = file_info.get('type')
    if file_type != 'image':
        print(json.dumps({
            'file_info': file_info,
            'type': file_type,
            'error': 'Kriminalistika yalnız şəkil faylları üçündür.',
        }, ensure_ascii=False))
        sys.exit(1)

    for_res = analyze_forensics(args.path)
    payload = {
        'file_info': file_info,
        'type': file_type,
        'forensics': for_res,
    }
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)


if __name__ == '__main__':
    main()
