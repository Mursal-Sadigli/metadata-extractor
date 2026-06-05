"""
Şəkil faylının daxili strukturu — marker/chunk analizi, mozaik, loop, gömülü fayl, metadata profilləri.
"""

import os
import re
import struct
import sys
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

JPEG_MARKER_AZ = {
    0xFFD8: 'SOI (Start of Image)',
    0xFFD9: 'EOI (End of Image)',
    0xFFE0: 'APP0 (JFIF)',
    0xFFE1: 'APP1 (EXIF/XMP)',
    0xFFE2: 'APP2 (ICC Profile)',
    0xFFE3: 'APP3',
    0xFFE4: 'APP4',
    0xFFE5: 'APP5',
    0xFFE6: 'APP6',
    0xFFE7: 'APP7',
    0xFFE8: 'APP8',
    0xFFE9: 'APP9',
    0xFFEA: 'APP10',
    0xFFEB: 'APP11',
    0xFFEC: 'APP12',
    0xFFED: 'APP13 (IPTC/Photoshop)',
    0xFFEE: 'APP14 (Adobe)',
    0xFFEF: 'APP15',
    0xFFDB: 'DQT (Quantization Table)',
    0xFFC0: 'SOF0 (Baseline DCT)',
    0xFFC1: 'SOF1',
    0xFFC2: 'SOF2 (Progressive DCT)',
    0xFFC3: 'SOF3',
    0xFFC4: 'DHT (Huffman Table)',
    0xFFC5: 'SOF5',
    0xFFC6: 'SOF6',
    0xFFC7: 'SOF7',
    0xFFC8: 'JPG',
    0xFFC9: 'SOF9',
    0xFFCA: 'SOF10',
    0xFFCB: 'SOF11',
    0xFFCC: 'DAC',
    0xFFCD: 'SOF13',
    0xFFCE: 'SOF14',
    0xFFCF: 'SOF15',
    0xFFDA: 'SOS (Start of Scan)',
    0xFFDD: 'DRI (Restart Interval)',
    0xFFFE: 'COM (Comment)',
    0xFFD0: 'RST0',
    0xFFD1: 'RST1',
    0xFFD2: 'RST2',
    0xFFD3: 'RST3',
    0xFFD4: 'RST4',
    0xFFD5: 'RST5',
    0xFFD6: 'RST6',
    0xFFD7: 'RST7',
}

EMBEDDED_SIGNATURES = [
    (b'\xff\xd8\xff', 'JPEG', 'image/jpeg'),
    (b'\x89PNG\r\n\x1a\n', 'PNG', 'image/png'),
    (b'GIF87a', 'GIF87a', 'image/gif'),
    (b'GIF89a', 'GIF89a', 'image/gif'),
    (b'PK\x03\x04', 'ZIP/Office', 'application/zip'),
    (b'%PDF', 'PDF', 'application/pdf'),
    (b'RIFF', 'RIFF (WebP/WAV/AVI)', 'application/octet-stream'),
    (b'\x1f\x8b', 'GZIP', 'application/gzip'),
    (b'MZ', 'Windows EXE/DLL', 'application/x-msdownload'),
    (b'\x7fELF', 'ELF binary', 'application/x-elf'),
    (b'BM', 'BMP', 'image/bmp'),
    (b'ftyp', 'MP4/MOV (ftyp)', 'video/mp4'),
]


def _marker_name(code: int) -> str:
    return JPEG_MARKER_AZ.get(code, f'0x{code:04X}')


def _parse_jpeg_segments(data: bytes) -> Tuple[List[Dict[str, Any]], Optional[int], int]:
    """JPEG marker seqmentlərini parse et; SOS sonrası RST sayı."""
    segments: List[Dict[str, Any]] = []
    rst_count = 0
    eoi_offset = None

    if len(data) < 2 or data[:2] != b'\xff\xd8':
        return segments, None, 0

    i = 2
    in_scan = False

    while i < len(data):
        if not in_scan:
            if data[i] != 0xFF:
                i += 1
                continue
            start = i
            while i < len(data) and data[i] == 0xFF:
                i += 1
            if i >= len(data):
                break
            marker_byte = data[i]
            i += 1
            code = (0xFF << 8) | marker_byte

            if code == 0xFFD9:
                segments.append({
                    'type': 'EOI',
                    'name': _marker_name(code),
                    'offset': start,
                    'length': i - start,
                    'payload_size': 0,
                })
                eoi_offset = start
                break

            if code == 0xFFDA:
                payload_size = 0
                if i + 2 <= len(data):
                    seg_len = struct.unpack('>H', data[i:i + 2])[0]
                    payload_size = max(0, seg_len - 2)
                    i += seg_len
                segments.append({
                    'type': 'SOS',
                    'name': _marker_name(code),
                    'offset': start,
                    'length': i - start,
                    'payload_size': payload_size,
                })
                in_scan = True
                continue

            if marker_byte == 0x00 or (0xD0 <= marker_byte <= 0xD7):
                continue

            if i + 2 > len(data):
                break
            seg_len = struct.unpack('>H', data[i:i + 2])[0]
            payload_start = i + 2
            payload_end = i + seg_len
            payload = data[payload_start:payload_end] if payload_end <= len(data) else b''

            entry: Dict[str, Any] = {
                'type': _marker_name(code).split()[0],
                'name': _marker_name(code),
                'offset': start,
                'length': min(seg_len + (payload_start - start), len(data) - start),
                'payload_size': len(payload),
            }

            if code == 0xFFDD and len(payload) >= 2:
                entry['restart_interval'] = struct.unpack('>H', payload[:2])[0]
            if code in (0xFFC0, 0xFFC1, 0xFFC2, 0xFFC3) and len(payload) >= 7:
                entry['image_height'] = struct.unpack('>H', payload[1:3])[0]
                entry['image_width'] = struct.unpack('>H', payload[3:5])[0]
                entry['components'] = payload[5]
            if code == 0xFFE1 and payload[:6] == b'Exif\x00\x00':
                entry['contains'] = 'EXIF'
            elif code == 0xFFE1 and b'http://ns.adobe.com/xap/' in payload[:512]:
                entry['contains'] = 'XMP'
            elif code == 0xFFE2 and payload[:11] == b'ICC_PROFILE':
                entry['contains'] = 'ICC'
            elif code == 0xFFED and payload[:14] == b'Photoshop 3.0':
                entry['contains'] = 'IPTC/Photoshop'

            segments.append(entry)
            i = payload_end
        else:
            if data[i] == 0xFF:
                if i + 1 < len(data):
                    nb = data[i + 1]
                    if nb == 0x00:
                        i += 2
                        continue
                    if 0xD0 <= nb <= 0xD7:
                        rst_count += 1
                        i += 2
                        continue
                    if nb == 0xD9:
                        segments.append({
                            'type': 'EOI',
                            'name': _marker_name(0xFFD9),
                            'offset': i,
                            'length': 2,
                            'payload_size': 0,
                        })
                        eoi_offset = i
                        break
                    in_scan = False
                    i += 1
                    continue
            i += 1

    return segments, eoi_offset, rst_count


def _parse_png_chunks(data: bytes) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    chunks: List[Dict[str, Any]] = []
    iend_end = None

    if len(data) < 8 or data[:8] != PNG_SIGNATURE:
        return chunks, None

    i = 8
    while i + 12 <= len(data):
        length = struct.unpack('>I', data[i:i + 4])[0]
        ctype = data[i + 4:i + 8].decode('latin-1', errors='replace')
        payload_start = i + 8
        payload_end = payload_start + length
        if payload_end + 4 > len(data):
            break
        payload = data[payload_start:payload_end]

        entry: Dict[str, Any] = {
            'type': ctype,
            'offset': i,
            'length': length,
            'total_size': 12 + length,
        }

        if ctype == 'IHDR' and len(payload) >= 8:
            entry['width'] = struct.unpack('>I', payload[0:4])[0]
            entry['height'] = struct.unpack('>I', payload[4:8])[0]
        elif ctype == 'iCCP' or ctype == 'sRGB':
            entry['contains'] = 'ICC/color'
        elif ctype in ('tEXt', 'iTXt', 'zTXt') and b'XML:com.adobe.xmp' in payload:
            entry['contains'] = 'XMP'
        elif ctype == 'eXIf':
            entry['contains'] = 'EXIF'
        elif ctype == 'acTL' and len(payload) >= 8:
            entry['num_frames'] = struct.unpack('>I', payload[0:4])[0]
            entry['num_plays'] = struct.unpack('>I', payload[4:8])[0]
        elif ctype == 'fdAT':
            entry['note'] = 'APNG frame'

        chunks.append(entry)
        i = payload_end + 4
        if ctype == 'IEND':
            iend_end = i
            break

    return chunks, iend_end


def _parse_gif_loop(data: bytes) -> Optional[Dict[str, Any]]:
    if len(data) < 6 or data[:3] != b'GIF':
        return None
    loop_count = None
    infinite = False
    idx = data.find(b'NETSCAPE2.0')
    if idx >= 0 and idx + 17 <= len(data):
        loop_count = struct.unpack('<H', data[idx + 15:idx + 17])[0]
        infinite = loop_count == 0
    return {
        'loop_count': loop_count,
        'infinite_loop': infinite,
        'max_repeats': 'sonsuz' if infinite else (str(loop_count) if loop_count is not None else '1 (default)'),
    }


def _parse_webp_info(data: bytes) -> Optional[Dict[str, Any]]:
    if len(data) < 12 or data[:4] != b'RIFF' or data[8:12] != b'WEBP':
        return None
    loop_info = None
    pos = 12
    while pos + 8 <= len(data):
        fourcc = data[pos:pos + 4].decode('latin-1', errors='replace')
        size = struct.unpack('<I', data[pos + 4:pos + 8])[0]
        chunk_start = pos + 8
        chunk_end = chunk_start + size + (size & 1)
        if fourcc == 'ANIM' and size >= 6:
            loop_info = {
                'loop_count': struct.unpack('<H', data[chunk_start + 4:chunk_start + 6])[0],
                'infinite_loop': struct.unpack('<H', data[chunk_start + 4:chunk_start + 6])[0] == 0,
            }
        pos = chunk_end
    return loop_info


def _detect_mosaic_jpeg(segments: List[Dict], rst_count: int, width: int, height: int) -> Dict[str, Any]:
    sof_count = sum(1 for s in segments if str(s.get('type', '')).startswith('SOF'))
    dri = next((s for s in segments if s.get('type') == 'DRI'), None)
    sos_count = sum(1 for s in segments if s.get('type') == 'SOS')
    large = (width or 0) * (height or 0) >= 4_000_000
    tiled_hint = bool(dri and dri.get('restart_interval'))
    progressive = any('Progressive' in s.get('name', '') for s in segments)

    return {
        'detected': tiled_hint or sof_count > 1 or (large and rst_count > 8),
        'likely_tiled_jpeg': tiled_hint,
        'restart_markers': rst_count,
        'restart_interval': dri.get('restart_interval') if dri else None,
        'sof_segment_count': sof_count,
        'sos_scan_count': sos_count,
        'progressive_jpeg': progressive,
        'large_image': large,
        'dimensions': f'{width}×{height}' if width and height else None,
        'summary_az': _mosaic_summary_az(tiled_hint, sof_count, rst_count, large, progressive, width, height),
    }


def _mosaic_summary_az(tiled, sof_count, rst_count, large, progressive, w, h):
    parts = []
    if tiled:
        parts.append('DRI restart interval — mozaik/MCU grid izi')
    if sof_count > 1:
        parts.append(f'{sof_count} SOF seqmenti (anomal)')
    if rst_count > 0:
        parts.append(f'{rst_count} RST marker')
    if progressive:
        parts.append('Progressive JPEG (çoxlu scan)')
    if large and w and h:
        parts.append(f'Böyük ölçü ({w}×{h})')
    if not parts:
        return 'Standart tək-parça JPEG strukturu; mozaik/tile izi aşkar edilmədi.'
    return '; '.join(parts)


def _detect_mosaic_png(chunks: List[Dict]) -> Dict[str, Any]:
    idat_count = sum(1 for c in chunks if c.get('type') == 'IDAT')
    ihdr = next((c for c in chunks if c.get('type') == 'IHDR'), None)
    w, h = (ihdr or {}).get('width'), (ihdr or {}).get('height')
    large = (w or 0) * (h or 0) >= 4_000_000
    return {
        'detected': idat_count > 12 or large,
        'idat_chunk_count': idat_count,
        'large_image': large,
        'dimensions': f'{w}×{h}' if w and h else None,
        'summary_az': (
            f'{idat_count} IDAT chunk' + (f', böyük ölçü {w}×{h}' if large else '')
            if idat_count > 1 else 'Tək IDAT axını; xüsusi tile strukturu yoxdur.'
        ),
    }


def _scan_embedded_payloads(data: bytes, logical_end: Optional[int]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    seen_offsets = set()

    start_search = logical_end if logical_end is not None else 0
    if logical_end is not None and logical_end < len(data):
        trailing = len(data) - logical_end
        if trailing > 16:
            findings.append({
                'kind': 'trailing_data',
                'offset': logical_end,
                'size_bytes': trailing,
                'description_az': f'Fayl sonu markerindən sonra {trailing} byte əlavə data',
                'risk': 'medium' if trailing > 128 else 'low',
            })

    for offset in range(start_search, len(data) - 8):
        if offset in seen_offsets:
            continue
        for sig, label, mime in EMBEDDED_SIGNATURES:
            if offset + len(sig) <= len(data) and data[offset:offset + len(sig)] == sig:
                if offset < 4 and label in ('JPEG', 'PNG', 'GIF87a', 'GIF89a'):
                    continue
                if logical_end and offset < logical_end and label == 'JPEG' and offset == 0:
                    continue
                est_size = _estimate_embedded_size(data, offset, label)
                findings.append({
                    'kind': 'embedded_signature',
                    'offset': offset,
                    'signature': label,
                    'mime_hint': mime,
                    'estimated_size_bytes': est_size,
                    'description_az': f'Offset {offset}: {label} imzası',
                    'risk': 'high' if label in ('ZIP/Office', 'PDF', 'Windows EXE/DLL', 'ELF binary') else 'medium',
                })
                seen_offsets.add(offset)
                break

    return findings[:25]


def _estimate_embedded_size(data: bytes, offset: int, label: str) -> Optional[int]:
    if label == 'JPEG':
        end = data.find(b'\xff\xd9', offset + 2)
        return (end - offset + 2) if end > offset else None
    if label == 'PNG':
        if data[offset:offset + 8] != PNG_SIGNATURE:
            return None
        pos = offset + 8
        while pos + 12 <= len(data):
            ln = struct.unpack('>I', data[pos:pos + 4])[0]
            ctype = data[pos + 4:pos + 8]
            if ctype == b'IEND':
                return pos + 12 - offset
            pos += 12 + ln
        return None
    if label == 'ZIP/Office':
        return min(len(data) - offset, 512 * 1024)
    return min(len(data) - offset, 64 * 1024)


def _analyze_metadata_profiles(data: bytes, fmt: str, segments, chunks) -> Dict[str, Any]:
    profiles = {
        'exif': {'present': False, 'size_bytes': 0, 'locations': []},
        'xmp': {'present': False, 'size_bytes': 0, 'locations': []},
        'iptc': {'present': False, 'size_bytes': 0, 'locations': []},
        'icc': {'present': False, 'size_bytes': 0, 'locations': []},
    }

    if fmt == 'JPEG':
        for seg in segments:
            contains = seg.get('contains')
            ps = seg.get('payload_size', 0)
            loc = f"offset {seg.get('offset')} ({seg.get('name')})"
            if contains == 'EXIF':
                profiles['exif']['present'] = True
                profiles['exif']['size_bytes'] += ps
                profiles['exif']['locations'].append(loc)
            elif contains == 'XMP':
                profiles['xmp']['present'] = True
                profiles['xmp']['size_bytes'] += ps
                profiles['xmp']['locations'].append(loc)
            elif contains == 'IPTC/Photoshop':
                profiles['iptc']['present'] = True
                profiles['iptc']['size_bytes'] += ps
                profiles['iptc']['locations'].append(loc)
            elif contains == 'ICC':
                profiles['icc']['present'] = True
                profiles['icc']['size_bytes'] += ps
                profiles['icc']['locations'].append(loc)
            elif seg.get('type') == 'APP1' and not contains:
                payload_hint = seg.get('name', '')
                if ps > 0:
                    profiles['xmp']['locations'].append(f'{loc} (naməlum APP1)')

    elif fmt == 'PNG':
        for ch in chunks:
            c = ch.get('contains')
            loc = f"chunk {ch.get('type')} @ {ch.get('offset')}"
            ln = ch.get('length', 0)
            if c == 'EXIF':
                profiles['exif']['present'] = True
                profiles['exif']['size_bytes'] += ln
                profiles['exif']['locations'].append(loc)
            elif c == 'XMP':
                profiles['xmp']['present'] = True
                profiles['xmp']['size_bytes'] += ln
                profiles['xmp']['locations'].append(loc)
            elif c == 'ICC/color':
                profiles['icc']['present'] = True
                profiles['icc']['size_bytes'] += ln
                profiles['icc']['locations'].append(loc)
        if b'XML:com.adobe.xmp' in data[: min(len(data), 2_000_000)]:
            if not profiles['xmp']['present']:
                profiles['xmp']['present'] = True
                profiles['xmp']['locations'].append('tEXt/iTXt (skan)')

    # Pillow fallback
    return profiles


def _pillow_metadata_boost(filepath: str, profiles: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from PIL import Image
        with Image.open(filepath) as img:
            if img.info.get('icc_profile') and not profiles['icc']['present']:
                profiles['icc']['present'] = True
                profiles['icc']['size_bytes'] = len(img.info['icc_profile'])
                profiles['icc']['locations'].append('Pillow icc_profile')
            exif = img.getexif()
            if exif and not profiles['exif']['present']:
                profiles['exif']['present'] = True
                profiles['exif']['locations'].append('Pillow EXIF IFD')
            xmp = img.info.get('xmp') or img.info.get('XML:com.adobe.xmp')
            if xmp and not profiles['xmp']['present']:
                profiles['xmp']['present'] = True
                profiles['xmp']['size_bytes'] = len(xmp) if isinstance(xmp, (bytes, str)) else 0
                profiles['xmp']['locations'].append('Pillow XMP')
    except Exception:
        pass
    return profiles


def _segment_summary(segments: List[Dict], chunks: List[Dict], fmt: str) -> Dict[str, Any]:
    if fmt == 'JPEG':
        counter = Counter(s.get('type') for s in segments)
        return {
            'format': 'JPEG',
            'total_segments': len(segments),
            'counts': dict(counter),
            'details': [
                {
                    'type': s.get('type'),
                    'name': s.get('name'),
                    'offset': s.get('offset'),
                    'payload_size': s.get('payload_size'),
                    'extra': {k: v for k, v in s.items() if k not in ('type', 'name', 'offset', 'length', 'payload_size')},
                }
                for s in segments
            ],
        }
    if fmt == 'PNG':
        counter = Counter(c.get('type') for c in chunks)
        return {
            'format': 'PNG',
            'total_chunks': len(chunks),
            'counts': dict(counter),
            'details': chunks,
        }
    return {'format': fmt, 'total_segments': 0, 'counts': {}}


def analyze_image_internal_structure(filepath: str) -> Dict[str, Any]:
    """Şəkil faylının daxili struktur və metadata profil analizi."""
    if not os.path.isfile(filepath):
        return {'status': 'error', 'error': 'Fayl tapılmadı'}

    ext = os.path.splitext(filepath)[1].lower()
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except OSError as e:
        return {'status': 'error', 'error': str(e)}

    file_size = len(data)
    fmt = 'UNKNOWN'
    segments: List[Dict] = []
    chunks: List[Dict] = []
    logical_end = None
    rst_count = 0
    width = height = None
    loop_info = None
    mosaic = {'detected': False, 'summary_az': 'Format dəstəklənmir və ya analiz edilmədi.'}

    if data[:2] == b'\xff\xd8':
        fmt = 'JPEG'
        segments, eoi_off, rst_count = _parse_jpeg_segments(data)
        logical_end = (eoi_off + 2) if eoi_off is not None else None
        sof = next((s for s in segments if str(s.get('type', '')).startswith('SOF')), None)
        if sof:
            width, height = sof.get('image_width'), sof.get('image_height')
        mosaic = _detect_mosaic_jpeg(segments, rst_count, width or 0, height or 0)
    elif data[:8] == PNG_SIGNATURE:
        fmt = 'PNG'
        chunks, logical_end = _parse_png_chunks(data)
        ihdr = next((c for c in chunks if c.get('type') == 'IHDR'), None)
        if ihdr:
            width, height = ihdr.get('width'), ihdr.get('height')
        mosaic = _detect_mosaic_png(chunks)
        actl = next((c for c in chunks if c.get('type') == 'acTL'), None)
        if actl:
            plays = actl.get('num_plays', 0)
            loop_info = {
                'loop_count': plays,
                'infinite_loop': plays == 0,
                'max_repeats': 'sonsuz' if plays == 0 else str(plays),
                'format': 'APNG',
            }
    elif data[:3] == b'GIF':
        fmt = 'GIF'
        loop_info = _parse_gif_loop(data)
        loop_info['format'] = 'GIF'
        try:
            from PIL import Image
            with Image.open(filepath) as img:
                width, height = img.size
        except Exception:
            pass
    elif len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        fmt = 'WEBP'
        loop_info = _parse_webp_info(data)
        if loop_info:
            loop_info['format'] = 'WebP ANIM'
            loop_info['max_repeats'] = 'sonsuz' if loop_info.get('infinite_loop') else str(loop_info.get('loop_count'))
        try:
            from PIL import Image
            with Image.open(filepath) as img:
                width, height = img.size
        except Exception:
            pass
    else:
        try:
            from PIL import Image
            with Image.open(filepath) as img:
                fmt = img.format or 'UNKNOWN'
                width, height = img.size
        except Exception:
            pass

    profiles = _analyze_metadata_profiles(data, fmt, segments, chunks)
    profiles = _pillow_metadata_boost(filepath, profiles)

    embedded = _scan_embedded_payloads(data, logical_end)
    has_embedded = any(f['kind'] == 'embedded_signature' for f in embedded)
    trailing_only = any(f['kind'] == 'trailing_data' for f in embedded)

    stego_related = has_embedded or trailing_only or (
        fmt == 'JPEG' and logical_end and (file_size - logical_end) > 64
    )

    summary_lines = [
        f'Format: {fmt} · {file_size:,} byte',
        f'Seqment/chunk: {_segment_summary(segments, chunks, fmt).get("total_segments") or _segment_summary(segments, chunks, fmt).get("total_chunks") or 0}',
    ]
    present_meta = [k.upper() for k, v in profiles.items() if v.get('present')]
    summary_lines.append(
        'Metadata profilləri: ' + (', '.join(present_meta) if present_meta else 'tapılmadı')
    )
    if loop_info:
        summary_lines.append(f'Döngə limiti: {loop_info.get("max_repeats", "—")}')
    if embedded:
        summary_lines.append(f'Gömülü/trailing: {len(embedded)} tapıntı')

    return {
        'status': 'success',
        'format': fmt,
        'file_size_bytes': file_size,
        'dimensions': {'width': width, 'height': height},
        'segments': _segment_summary(segments, chunks, fmt),
        'mosaic': mosaic,
        'loop': loop_info,
        'metadata_profiles': profiles,
        'embedded_findings': embedded,
        'embedded_file_detected': has_embedded,
        'steganography_suspicious': stego_related,
        'summary_az': summary_lines,
        'warnings': _build_warnings(profiles, embedded, mosaic, fmt),
    }


def _build_warnings(profiles, embedded, mosaic, fmt) -> List[str]:
    warnings = []
    if not any(profiles[k]['present'] for k in profiles):
        warnings.append('EXIF/XMP/IPTC/ICC profillərindən heç biri aşkar edilmədi — metadata silinmiş ola bilər.')
    high_risk = [e for e in embedded if e.get('risk') == 'high']
    if high_risk:
        warnings.append(f'{len(high_risk)} yüksək riskli gömülü fayl imzası tapıldı (ZIP/PDF/EXE və s.).')
    if mosaic.get('likely_tiled_jpeg'):
        warnings.append('JPEG DRI/restart interval — mozaik kompressiya izi.')
    if fmt == 'JPEG' and mosaic.get('sof_segment_count', 0) > 1:
        warnings.append('Birdən çox SOF seqmenti — fayl strukturunda anomaliya və ya birləşdirilmiş görüntü.')
    return warnings
