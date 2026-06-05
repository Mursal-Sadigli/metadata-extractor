"""Yüngül CLI — yüklənmiş fayl üçün sosial metadata (/api/social-meta)."""

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
    parser.add_argument('--video-frame', type=int, default=0)
    args = parser.parse_args()

    if not os.path.isfile(args.path):
        print(json.dumps({'error': 'Fayl tapılmadı'}, ensure_ascii=False))
        sys.exit(1)

    from analyzers.social_metadata import analyze_social_file
    res = analyze_social_file(args.path, video_frame=args.video_frame)
    print(json.dumps(res, ensure_ascii=False))
    sys.exit(0)


if __name__ == '__main__':
    main()
