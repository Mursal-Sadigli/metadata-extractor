"""Yüngül CLI — URL şəkil yükləmə (main.py ağır import etmədən)."""

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
    parser.add_argument('--upload-dir', required=True)
    args = parser.parse_args()

    from downloaders.url_downloader import fetch_image_to_uploads

    upload_dir = os.path.abspath(args.upload_dir)
    res = fetch_image_to_uploads(args.url, upload_dir)
    if res.get('status') == 'success' and res.get('sidecar') and res.get('filename'):
        try:
            from analyzers.web_image_metadata import save_url_sidecar
            fpath = os.path.join(upload_dir, res['filename'])
            save_url_sidecar(fpath, res['sidecar'])
        except Exception:
            pass
    print(json.dumps(res, ensure_ascii=False))
    sys.exit(0 if res.get('status') == 'success' else 1)


if __name__ == '__main__':
    main()
