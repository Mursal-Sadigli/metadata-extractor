"""
Agent və proqram izləri — faylın hansı proqram/cihaz tərəfindən yaradıldığını və ya redaktə edildiyini aşkarlayır.
"""

import os
import re
import sys
from typing import Any, Dict, List, Optional

# (regex, display_name, category, confidence_boost)
APPLICATION_PATTERNS = [
    (r'adobe\s*photoshop', 'Adobe Photoshop', 'image_editor', 0.9),
    (r'photoshop', 'Adobe Photoshop', 'image_editor', 0.75),
    (r'adobe\s*lightroom', 'Adobe Lightroom', 'image_editor', 0.88),
    (r'lightroom', 'Adobe Lightroom', 'image_editor', 0.7),
    (r'adobe\s*illustrator', 'Adobe Illustrator', 'image_editor', 0.88),
    (r'illustrator', 'Adobe Illustrator', 'image_editor', 0.65),
    (r'adobe\s*camera\s*raw', 'Adobe Camera Raw', 'image_editor', 0.85),
    (r'gimp', 'GIMP', 'image_editor', 0.9),
    (r'paint\.net', 'Paint.NET', 'image_editor', 0.9),
    (r'corel\s*paintshop', 'Corel PaintShop Pro', 'image_editor', 0.88),
    (r'affinity\s*photo', 'Affinity Photo', 'image_editor', 0.88),
    (r'canva', 'Canva', 'image_editor', 0.85),
    (r'pixelmator', 'Pixelmator', 'image_editor', 0.85),
    (r'snapseed', 'Snapseed', 'image_editor', 0.85),
    (r'vsco', 'VSCO', 'image_editor', 0.8),
    (r'picsart', 'PicsArt', 'image_editor', 0.85),
    (r'instagram', 'Instagram', 'social', 0.85),
    (r'facebook', 'Facebook / Meta', 'social', 0.8),
    (r'whatsapp', 'WhatsApp', 'messenger', 0.92),
    (r'telegram', 'Telegram', 'messenger', 0.9),
    (r'signal', 'Signal', 'messenger', 0.88),
    (r'viber', 'Viber', 'messenger', 0.88),
    (r'wechat', 'WeChat', 'messenger', 0.88),
    (r'tiktok', 'TikTok', 'social', 0.88),
    (r'capcut', 'CapCut', 'video_editor', 0.88),
    (r'imovie', 'Apple iMovie', 'video_editor', 0.85),
    (r'final\s*cut', 'Apple Final Cut Pro', 'video_editor', 0.88),
    (r'premiere', 'Adobe Premiere Pro', 'video_editor', 0.88),
    (r'da\s*vinci', 'DaVinci Resolve', 'video_editor', 0.88),
    (r'ffmpeg', 'FFmpeg', 'video_tool', 0.9),
    (r'handbrake', 'HandBrake', 'video_tool', 0.88),
    (r'microsoft\s*word', 'Microsoft Word', 'office', 0.92),
    (r'ms-word|msword|winword', 'Microsoft Word', 'office', 0.85),
    (r'microsoft\s*excel', 'Microsoft Excel', 'office', 0.92),
    (r'microsoft\s*powerpoint', 'Microsoft PowerPoint', 'office', 0.92),
    (r'microsoft\s*office', 'Microsoft Office', 'office', 0.85),
    (r'libreoffice|openoffice', 'LibreOffice / OpenOffice', 'office', 0.88),
    (r'google\s*docs', 'Google Docs', 'office', 0.85),
    (r'wps\s*office', 'WPS Office', 'office', 0.85),
    (r'adobe\s*acrobat|acrobat\s*distiller', 'Adobe Acrobat', 'pdf', 0.9),
    (r'pdflatex|latex', 'LaTeX', 'pdf', 0.88),
    (r'prince\s*xml', 'Prince XML', 'pdf', 0.85),
    (r'wkhtmltopdf', 'wkhtmltopdf', 'pdf', 0.88),
    (r'apple\s*iphone|iphone\s*os|ios\s*\d', 'Apple iPhone (iOS)', 'camera_device', 0.82),
    (r'apple\s*ipad', 'Apple iPad', 'camera_device', 0.82),
    (r'cupertino', 'Apple cihaz', 'camera_device', 0.7),
    (r'samsung\s*sm-|galaxy', 'Samsung Galaxy', 'camera_device', 0.8),
    (r'google\s*pixel|pixel\s*\d', 'Google Pixel', 'camera_device', 0.82),
    (r'huawei|honor', 'Huawei / Honor', 'camera_device', 0.78),
    (r'xiaomi|redmi|mi\s*\d', 'Xiaomi', 'camera_device', 0.78),
    (r'oppo|realme', 'OPPO / Realme', 'camera_device', 0.75),
    (r'vivo', 'Vivo', 'camera_device', 0.75),
    (r'oneplus', 'OnePlus', 'camera_device', 0.78),
    (r'nikon', 'Nikon kamera', 'camera_device', 0.85),
    (r'canon', 'Canon kamera', 'camera_device', 0.85),
    (r'sony', 'Sony kamera', 'camera_device', 0.8),
    (r'fujifilm|fuji', 'Fujifilm', 'camera_device', 0.85),
    (r'olympus', 'Olympus', 'camera_device', 0.85),
    (r'panasonic|lumix', 'Panasonic Lumix', 'camera_device', 0.85),
    (r'leica', 'Leica', 'camera_device', 0.88),
    (r'gopro', 'GoPro', 'camera_device', 0.9),
    (r'dji', 'DJI dron', 'camera_device', 0.88),
    (r'windows\s*photo|microsoft\s*windows', 'Windows Photo / OS', 'os', 0.7),
    (r'android', 'Android cihaz', 'os', 0.75),
    (r'google\s*photos', 'Google Photos', 'cloud', 0.85),
    (r'icloud', 'Apple iCloud', 'cloud', 0.82),
    (r'exiftool', 'ExifTool (metadata redaktəsi)', 'metadata_tool', 0.9),
    (r'metadata\s*editor', 'Metadata redaktoru', 'metadata_tool', 0.75),
]

BINARY_SIGNATURES = [
    (b'Adobe Photoshop', 'Adobe Photoshop', 'image_editor', 0.85),
    (b'Adobe ImageReady', 'Adobe ImageReady', 'image_editor', 0.8),
    (b'http://ns.adobe.com/xap/1.0/', 'Adobe XMP (Photoshop/Lightroom izi)', 'image_editor', 0.6),
    (b'Paint.NET', 'Paint.NET', 'image_editor', 0.85),
    (b'GIMP', 'GIMP', 'image_editor', 0.8),
    (b'WhatsApp', 'WhatsApp', 'messenger', 0.7),
    (b'Canva', 'Canva', 'image_editor', 0.75),
    (b'Microsoft Office Word', 'Microsoft Word', 'office', 0.9),
    (b'Microsoft Office Excel', 'Microsoft Excel', 'office', 0.9),
    (b'Microsoft Office PowerPoint', 'Microsoft PowerPoint', 'office', 0.9),
    (b'LibreOffice', 'LibreOffice', 'office', 0.88),
    (b'wkhtmltopdf', 'wkhtmltopdf', 'pdf', 0.85),
]

EXIF_TRACE_KEYS = [
    ('Image Software', 'exif', 'Proqram (EXIF Software)'),
    ('Image ProcessingSoftware', 'exif', 'Emal proqramı'),
    ('Image Artist', 'exif', 'Müəllif / Artist'),
    ('Image HostComputer', 'exif', 'Host kompüter'),
    ('EXIF UserComment', 'exif', 'İstifadəçi şərhi'),
    ('Image Make', 'device', 'İstehsalçı (Make)'),
    ('Image Model', 'device', 'Model'),
    ('EXIF LensModel', 'device', 'Linza'),
]

XMP_PATTERNS = [
    (re.compile(r'<xmp:CreatorTool[^>]*>([^<]+)<', re.I), 'xmp', 'Creator Tool'),
    (re.compile(r'<dc:creator>.*?<rdf:li>([^<]+)</rdf:li>', re.I | re.DOTALL), 'xmp', 'Müəllif (dc:creator)'),
    (re.compile(r'<pdf:Producer[^>]*>([^<]+)<', re.I), 'xmp_pdf', 'PDF Producer'),
    (re.compile(r'<pdf:Creator[^>]*>([^<]+)<', re.I), 'xmp_pdf', 'PDF Creator'),
    (re.compile(r'photoshop:History', re.I), 'xmp', 'Photoshop redaktə tarixi'),
    (re.compile(r'crs:'), 'xmp', 'Adobe Camera Raw'),
]

CATEGORY_LABELS = {
    'image_editor': 'Şəkil redaktoru',
    'camera_device': 'Kamera / cihaz',
    'messenger': 'Messencer',
    'social': 'Sosial şəbəkə',
    'office': 'Ofis proqramı',
    'pdf': 'PDF yaradıcı',
    'video_editor': 'Video redaktor',
    'video_tool': 'Video alət',
    'os': 'Əməliyyat sistemi',
    'cloud': 'Bulud xidməti',
    'metadata_tool': 'Metadata aləti',
    'binary': 'Fayl imzası',
    'exif': 'EXIF metadata',
    'xmp': 'XMP metadata',
    'document': 'Sənəd metadata',
    'unknown': 'Naməlum',
}


def _match_application(raw: str) -> Optional[Dict[str, Any]]:
    if not raw or not str(raw).strip():
        return None
    text = str(raw).strip()
    lower = text.lower()
    best = None
    for pattern, name, category, conf in APPLICATION_PATTERNS:
        if re.search(pattern, lower, re.I):
            if best is None or conf > best['confidence']:
                best = {
                    'application': name,
                    'category': category,
                    'confidence': conf,
                    'raw': text[:300],
                }
    if best:
        return best
    return {
        'application': text[:120],
        'category': 'unknown',
        'confidence': 0.45,
        'raw': text[:300],
    }


def _add_trace(traces: List[Dict], seen: set, source: str, field: str, raw: str, trace_type: str = 'metadata'):
    if not raw or not str(raw).strip():
        return
    key = (str(raw).strip().lower()[:80], field)
    if key in seen:
        return
    seen.add(key)
    matched = _match_application(str(raw))
    if not matched:
        return
    traces.append({
        'source': source,
        'field': field,
        'raw_value': matched['raw'],
        'application': matched['application'],
        'category': matched['category'],
        'category_label': CATEGORY_LABELS.get(matched['category'], matched['category']),
        'confidence': round(matched['confidence'], 2),
        'type': trace_type,
    })


def _scan_binary_signatures(filepath: str, max_bytes: int = 800000) -> List[Dict[str, Any]]:
    hits = []
    seen = set()
    try:
        with open(filepath, 'rb') as f:
            data = f.read(max_bytes)
        for sig, name, category, conf in BINARY_SIGNATURES:
            if sig in data and name not in seen:
                seen.add(name)
                hits.append({
                    'source': 'binary_signature',
                    'field': 'file_content',
                    'raw_value': sig.decode('utf-8', errors='replace')[:80],
                    'application': name,
                    'category': category,
                    'category_label': CATEGORY_LABELS.get(category, category),
                    'confidence': conf,
                    'type': 'binary',
                })
    except Exception as e:
        print(f"  [!] Binary proqram skanı: {e}", file=sys.stderr)
    return hits


def _scan_xmp_text(filepath: str) -> List[Dict[str, Any]]:
    traces = []
    seen = set()
    try:
        with open(filepath, 'rb') as f:
            raw = f.read(600000)
        text = raw.decode('utf-8', errors='ignore')
        if 'xmp' not in text.lower() and 'xap' not in text.lower():
            return traces
        for pat, src, label in XMP_PATTERNS:
            if pat.groups == 0:
                if pat.search(text):
                    _add_trace(traces, seen, src, label, 'Adobe XMP redaktə zənciri', 'xmp')
                continue
            for m in pat.finditer(text):
                _add_trace(traces, seen, src, label, m.group(1).strip(), 'xmp')
    except Exception as e:
        print(f"  [!] XMP proqram skanı: {e}", file=sys.stderr)
    return traces


def _from_metadata_result(meta: Optional[dict]) -> List[Dict[str, Any]]:
    traces = []
    seen = set()
    if not meta:
        return traces

    raw_tags = meta.get('raw_tags') or {}
    for key, src_type, label in EXIF_TRACE_KEYS:
        val = raw_tags.get(key)
        if val:
            _add_trace(traces, seen, src_type, label, str(val), src_type)

    exif = meta.get('exif') or {}
    cam = exif.get('camera') or {}
    if cam.get('software'):
        _add_trace(traces, seen, 'exif', 'Software (struktur)', str(cam['software']), 'exif')
    if cam.get('make'):
        device = cam.get('make', '')
        if cam.get('model'):
            device = f"{device} {cam['model']}"
        _add_trace(traces, seen, 'device', 'Kamera cihazı', device, 'device')

    doc = meta.get('document_info') or {}
    for key in ('last_modified_by', 'author'):
        if doc.get(key):
            _add_trace(traces, seen, 'document', f'DOCX {key}', str(doc[key]), 'document')

    pdf = meta.get('pdf_info') or {}
    for key in ('creator', 'producer'):
        if pdf.get(key):
            _add_trace(traces, seen, 'pdf', f'PDF {key}', str(pdf[key]), 'pdf')

    return traces


def _build_device_hints(traces: List[Dict]) -> List[str]:
    devices = []
    seen = set()
    for t in traces:
        if t.get('category') == 'camera_device' or t.get('type') == 'device':
            name = t.get('application') or t.get('raw_value')
            if name and name not in seen:
                seen.add(name)
                devices.append(name)
        elif t.get('field') == 'Kamera cihazı':
            name = t.get('raw_value')
            if name and name not in seen:
                seen.add(name)
                devices.append(name)
    return devices


def _build_editing_chain(traces: List[Dict]) -> List[str]:
    order = []
    seen = set()
    for t in sorted(traces, key=lambda x: -x.get('confidence', 0)):
        app = t.get('application')
        if app and app not in seen:
            seen.add(app)
            order.append(app)
    return order[:8]


def analyze_software_traces(filepath: str, metadata_result: Optional[dict] = None) -> Dict[str, Any]:
    """
    Faylın yaradılması/redaktə proqram və cihaz izlərini toplayır.
    """
    print('  [i] Agent və proqram izləri analizi...', file=sys.stderr)

    traces: List[Dict[str, Any]] = []
    seen_global = set()

    for t in _from_metadata_result(metadata_result):
        key = (t.get('application'), t.get('field'))
        if key not in seen_global:
            seen_global.add(key)
            traces.append(t)

    for t in _scan_xmp_text(filepath):
        key = (t.get('application'), t.get('field'))
        if key not in seen_global:
            seen_global.add(key)
            traces.append(t)

    for t in _scan_binary_signatures(filepath):
        key = (t.get('application'), t.get('source'))
        if key not in seen_global:
            seen_global.add(key)
            traces.append(t)

    traces.sort(key=lambda x: x.get('confidence', 0), reverse=True)

    primary = traces[0] if traces else None
    device_hints = _build_device_hints(traces)
    editing_chain = _build_editing_chain(traces)

    summary_parts = []
    if primary:
        summary_parts.append(f"Əsas iz: {primary['application']} ({primary.get('category_label', '')})")
    if device_hints:
        summary_parts.append(f"Cihaz: {', '.join(device_hints[:2])}")
    if len(editing_chain) > 1:
        summary_parts.append(f"Zəncir: {' → '.join(editing_chain[:4])}")

    return {
        'primary_application': primary['application'] if primary else None,
        'primary_category': primary.get('category') if primary else None,
        'primary_category_label': primary.get('category_label') if primary else None,
        'confidence': primary.get('confidence') if primary else 0,
        'traces': traces,
        'device_hints': device_hints,
        'editing_chain': editing_chain,
        'trace_count': len(traces),
        'summary': ' | '.join(summary_parts) if summary_parts else 'Proqram/cihaz izi tapılmadı.',
    }
