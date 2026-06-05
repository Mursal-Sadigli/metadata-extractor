"""WhatsApp ZIP və Telegram export parser."""

import json
import os
import re
import sys
import zipfile
import shutil

from extractors.image_extractor import ImageExtractor

IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.mp4', '.mov'}
WHATSAPP_LINE = re.compile(
    r'^\[?(\d{1,2}[./]\d{1,2}[./]\d{2,4}[,\s]+\d{1,2}:\d{2}(?::\d{2})?)\]?[\s-]*([^:]+):\s*(.*)$'
)


def _is_image(path):
    return os.path.splitext(path)[1].lower() in IMAGE_EXT


def extract_zip_to_dir(zip_path, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(dest_dir)
    return dest_dir


def _find_media_files(root, limit=20):
    found = []
    for dirpath, _, files in os.walk(root):
        for fn in sorted(files):
            fp = os.path.join(dirpath, fn)
            if _is_image(fp):
                found.append(fp)
                if len(found) >= limit:
                    return found
    return found


def _parse_whatsapp_txt(root):
    messages = []
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if fn.lower().endswith('.txt') and 'whatsapp' in fn.lower():
                path = os.path.join(dirpath, fn)
                try:
                    with open(path, encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            m = WHATSAPP_LINE.match(line.strip())
                            if m:
                                messages.append({
                                    'date': m.group(1),
                                    'sender': m.group(2).strip(),
                                    'text': m.group(3).strip(),
                                })
                except OSError:
                    pass
    return messages


def _parse_telegram_json(root):
    for dirpath, _, files in os.walk(root):
        if 'result.json' in files:
            path = os.path.join(dirpath, 'result.json')
            try:
                with open(path, encoding='utf-8') as f:
                    data = json.load(f)
                return data.get('messages', [])
            except (OSError, json.JSONDecodeError) as e:
                print(f'  [!] Telegram JSON: {e}', file=sys.stderr)
    return []


def _telegram_media_paths(root, messages, limit=20):
    paths = []
    for msg in messages:
        if len(paths) >= limit:
            break
        for key in ('photo', 'file'):
            if key not in msg:
                continue
            val = msg[key]
            if isinstance(val, str):
                candidates = [os.path.join(root, val), val]
            elif isinstance(val, dict):
                p = val.get('file') or val.get('local_path') or ''
                candidates = [os.path.join(root, p), p]
            else:
                continue
            for c in candidates:
                if c and os.path.isfile(c) and _is_image(c):
                    paths.append(c)
                    break
    return paths


def analyze_archive(zip_path, output_base, max_items=20):
    extract_dir = os.path.join(output_base, f'archive_{os.path.splitext(os.path.basename(zip_path))[0]}')
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir, ignore_errors=True)
    extract_zip_to_dir(zip_path, extract_dir)

    archive_type = 'unknown'
    if _parse_whatsapp_txt(extract_dir):
        archive_type = 'whatsapp'
    tg_msgs = _parse_telegram_json(extract_dir)
    if tg_msgs:
        archive_type = 'telegram'

    media_files = _find_media_files(extract_dir, limit=max_items)
    if archive_type == 'telegram' and tg_msgs:
        tg_media = _telegram_media_paths(extract_dir, tg_msgs, limit=max_items)
        seen = set(media_files)
        for p in tg_media:
            if p not in seen:
                media_files.append(p)
                seen.add(p)

    img_ext = ImageExtractor()
    items = []
    for fp in media_files[:max_items]:
        item = {
            'source': archive_type,
            'filepath': fp,
            'filename': os.path.basename(fp),
            'file_info': img_ext.get_file_info(fp),
        }
        try:
            meta = img_ext.extract(fp)
            item['exif'] = meta.get('exif')
            item['location'] = meta.get('location')
            item['has_gps'] = bool(meta.get('location'))
        except Exception as e:
            item['error'] = str(e)
        items.append(item)

    return {
        'archive_type': archive_type,
        'extract_dir': extract_dir,
        'messages_sample': (_parse_whatsapp_txt(extract_dir) or tg_msgs)[:5],
        'media_count': len(media_files),
        'items': items,
    }
