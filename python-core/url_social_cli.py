"""Yüngül CLI — sosial media URL analizi (/api/analyze-url)."""

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
    parser.add_argument('url')
    args = parser.parse_args()

    from analyzers.social_metadata import fetch_social_metadata

    out_dir = os.path.join(os.path.dirname(__file__), '..', 'backend', 'uploads')
    os.makedirs(out_dir, exist_ok=True)
    res = fetch_social_metadata(args.url.strip(), output_dir=out_dir)
    print(json.dumps(res, ensure_ascii=False))
    sys.exit(0)


if __name__ == '__main__':
    main()
