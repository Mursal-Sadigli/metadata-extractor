"""
Şəklin çəkilmə tarixi — EXIF, XMP, fayl adı, veb mənbə (Unsplash, NASA və s.).
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
)

MONTHS_AZ = (
    '', 'yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
    'iyul', 'avqust', 'sentyabr', 'oktyabr', 'noyabr', 'dekabr',
)

SOURCE_LABELS_AZ = {
    'exif_original': 'EXIF — kamera çəkiliş vaxtı (DateTimeOriginal)',
    'exif_digitized': 'EXIF — rəqəmsallaşdırma',
    'exif_modified': 'EXIF — dəyişdirilmə',
    'xmp_created': 'XMP — yaradılama tarixi',
    'raw_exif': 'EXIF metadata tag',
    'filename': 'Fayl adından',
    'tineye_earliest': 'TinEye — ilk internetdə indekslənmə (ən erkən crawl_date)',
    'tineye_url': 'TinEye uyğunluğu — URL-də tarix',
    'wayback_earliest': 'Wayback Machine — ilk internet arxivi (snapshot)',
    'unsplash_page': 'Unsplash səhifə yükləmə tarixi (çəkiliş deyil)',
    'unsplash_photo_id': 'Unsplash platforma ID (çəkiliş deyil)',
    'page_published': 'Veb səhifə — dərc tarixi',
    'page_og': 'Veb metadata',
    'propagation_global': 'Yayılma analizi — məqalə + Wayback (ən erkən iz)',
    'embedded_text': 'Şəkil daxili metadata',
    'gps_date': 'GPS tarixi',
}

# date_type: capture | first_seen | platform | published | modified
SOURCE_META = {
    'exif_original': ('capture', 0.98),
    'exif_digitized': ('capture', 0.84),
    'raw_exif': ('capture', 0.9),
    'xmp_created': ('capture', 0.88),
    'embedded_text': ('capture', 0.8),
    'filename': ('capture', 0.82),
    'gps_date': ('capture', 0.85),
    'tineye_earliest': ('first_seen', 0.94),
    'tineye_url': ('first_seen', 0.86),
    'wayback_earliest': ('first_seen', 0.80),
    'propagation_global': ('first_seen', 0.82),
    'unsplash_photo_id': ('platform', 0.35),
    'unsplash_page': ('platform', 0.4),
    'page_published': ('published', 0.55),
    'page_og': ('published', 0.5),
    'exif_modified': ('modified', 0.45),
}

DATE_TYPE_TITLE_AZ = {
    'capture': 'Kamera çəkiliş tarixi',
    'first_seen': 'İlk internet izi (TinEye)',
    'platform': 'Platforma yükləmə tarixi',
    'published': 'Dərc / veb tarixi',
    'modified': 'Dəyişdirilmə tarixi',
    'unknown': 'Tarix',
}

DT_PATTERNS = [
    (re.compile(r'(\d{4})[:\-](\d{2})[:\-](\d{2})(?:\s+(\d{2}):(\d{2}):(\d{2}))?'), 'ymd'),
    (re.compile(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})'), 'iso'),
    (re.compile(r'(\d{2})\.(\d{2})\.(\d{4})(?:\s+(\d{2}):(\d{2}))?'), 'dmy'),
    (re.compile(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', re.I), 'dmy_en'),
]

EN_MONTHS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
}


def _format_az(year: int, month: int, day: int, hour: Optional[int] = None, minute: Optional[int] = None) -> str:
    if month < 1 or month > 12 or day < 1 or day > 31:
        return f'{day}.{month}.{year}'
    base = f'{day} {MONTHS_AZ[month]} {year}'
    if hour is not None and minute is not None:
        return f'{base}, {hour:02d}:{minute:02d}'
    return base


def _parse_datetime_string(text: str) -> Optional[Tuple[datetime, str]]:
    if not text or len(str(text).strip()) < 8:
        return None
    s = str(text).strip().replace('Z', '+00:00')

    for pat, kind in DT_PATTERNS:
        m = pat.search(s)
        if not m:
            continue
        try:
            if kind == 'ymd':
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                h = int(m.group(4)) if m.lastindex >= 4 and m.group(4) else 0
                mi = int(m.group(5)) if m.lastindex >= 5 and m.group(5) else 0
                sec = int(m.group(6)) if m.lastindex >= 6 and m.group(6) else 0
                return datetime(y, mo, d, h, mi, sec), kind
            if kind == 'iso':
                return datetime(
                    int(m.group(1)), int(m.group(2)), int(m.group(3)),
                    int(m.group(4)), int(m.group(5)), int(m.group(6)),
                ), kind
            if kind == 'dmy':
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                h = int(m.group(4)) if m.lastindex >= 4 and m.group(4) else 0
                mi = int(m.group(5)) if m.lastindex >= 5 and m.group(5) else 0
                return datetime(y, mo, d, h, mi, 0), kind
            if kind == 'dmy_en':
                d = int(m.group(1))
                mo = EN_MONTHS.get(m.group(2).lower(), 0)
                y = int(m.group(3))
                if mo:
                    return datetime(y, mo, d), kind
        except (ValueError, TypeError):
            continue
    return None


def _add_candidate(
    candidates: List[Dict],
    dt: datetime,
    source: str,
    confidence: float,
    raw: str = '',
) -> None:
    if dt.year < 1970 or dt.year > 2035:
        return
    date_type, meta_conf = SOURCE_META.get(source, ('unknown', 0.5))
    if source in SOURCE_META:
        final_conf = min(0.98, max(confidence, meta_conf))
    else:
        final_conf = min(0.98, confidence)
    candidates.append({
        'year': dt.year,
        'month': dt.month,
        'day': dt.day,
        'hour': dt.hour,
        'minute': dt.minute,
        'iso_date': dt.strftime('%Y-%m-%d'),
        'iso_datetime': dt.strftime('%Y-%m-%d %H:%M:%S'),
        'display_az': _format_az(dt.year, dt.month, dt.day, dt.hour, dt.minute),
        'source': source,
        'source_label_az': SOURCE_LABELS_AZ.get(source, source),
        'date_type': date_type,
        'confidence': round(final_conf, 2),
        'raw': (raw or '')[:120],
    })


def _from_exif_block(result: Dict, candidates: List[Dict]) -> None:
    exif = result.get('exif') or {}
    dt_block = exif.get('datetime') or {}
    mapping = {
        'original': ('exif_original', 0.96),
        'digitized': ('exif_digitized', 0.82),
        'modified': ('exif_modified', 0.7),
        'inferred_from_filename': ('filename', 0.75),
    }
    for key, (src, conf) in mapping.items():
        val = dt_block.get(key)
        if not val:
            continue
        parsed = _parse_datetime_string(val)
        if parsed:
            _add_candidate(candidates, parsed[0], src, conf, val)


def _from_raw_tags(result: Dict, candidates: List[Dict]) -> None:
    raw = result.get('raw_tags') or {}
    date_keys = (
        'DateTimeOriginal', 'DateTimeDigitized', 'DateTime', 'CreateDate',
        'ModifyDate', 'GPS Date', 'GPS GPSDate', 'EXIF DateTimeOriginal',
        'Image DateTime', 'XMP_CreateDate', 'XMP_DateTimeOriginal',
    )
    for k, v in raw.items():
        kl = k.lower()
        if any(dk.lower() in kl for dk in date_keys) or 'date' in kl or 'time' in kl:
            parsed = _parse_datetime_string(str(v))
            if parsed:
                conf = 0.9 if 'original' in kl or 'create' in kl else 0.75
                _add_candidate(candidates, parsed[0], 'raw_exif', conf, f'{k}={v}')


def _from_embedded(web_meta: Dict, candidates: List[Dict]) -> None:
    for k, v in (web_meta.get('embedded') or {}).items():
        if 'date' in k.lower() or 'time' in k.lower() or 'created' in k.lower():
            parsed = _parse_datetime_string(str(v))
            if parsed:
                _add_candidate(candidates, parsed[0], 'embedded_text', 0.78, str(v))


def _from_filename(filepath: str, candidates: List[Dict]) -> None:
    base = os.path.basename(filepath)
    m = re.search(r'(\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})', base)
    if m:
        try:
            dt = datetime(
                int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)), int(m.group(6)),
            )
            _add_candidate(candidates, dt, 'filename', 0.8, base)
        except ValueError:
            pass
    m2 = re.search(r'(\d{4})-(\d{2})-(\d{2})', base)
    if m2:
        try:
            dt = datetime(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
            _add_candidate(candidates, dt, 'filename', 0.72, base)
        except ValueError:
            pass


def _env_public_url(filepath: str) -> Optional[str]:
    base = os.environ.get('PUBLIC_APP_URL') or os.environ.get('PUBLIC_IMAGE_BASE_URL')
    if not base or not filepath:
        return None
    from urllib.parse import quote
    return f'{base.rstrip("/")}/uploads/{quote(os.path.basename(filepath))}'


def _build_user_message(best: Dict, tineye_note: Optional[str]) -> str:
    dt = best.get('date_type', 'unknown')
    title = DATE_TYPE_TITLE_AZ.get(dt, 'Tarix')
    msg = (
        f'{title}: {best["display_az"]} '
        f'({best["source_label_az"]}, etibar {int(best.get("confidence", 0) * 100)}%)'
    )
    if tineye_note and dt == 'first_seen':
        return f'{msg}. {tineye_note}'
    if dt == 'platform':
        return (
            f'{msg}. Diqqət: bu CDN/platforma ID-sidir, çəkiliş tarixi deyil; '
            'TinEye və ya EXIF daha etibarlıdır.'
        )
    return msg


def _from_wayback(urls: List[str], candidates: List[Dict]) -> Dict[str, Any]:
    """TinEye tapılmayanda — şəkil URL üçün Wayback ilk snapshot."""
    from analyzers.image_web_timeline_analyzer import _wayback_history

    meta: Dict[str, Any] = {'status': 'unavailable', 'urls_checked': []}
    best_dt: Optional[datetime] = None
    best_url: Optional[str] = None
    best_wb: Optional[Dict[str, Any]] = None

    seen: Set[str] = set()
    for url in urls:
        if not url or not str(url).startswith('http') or url in seen:
            continue
        seen.add(url)
        meta['urls_checked'].append(url)
        wb = _wayback_history(url)
        if not wb.get('available'):
            continue
        earliest = wb.get('earliest') or {}
        iso = earliest.get('iso_date')
        if not iso:
            continue
        parsed = _parse_datetime_string(iso)
        if not parsed:
            continue
        dt = parsed[0]
        if best_dt is None or dt < best_dt:
            best_dt = dt
            best_url = url
            best_wb = wb

    if not best_dt or not best_url or not best_wb:
        return meta

    earliest = best_wb.get('earliest') or {}
    _add_candidate(
        candidates,
        best_dt,
        'wayback_earliest',
        0.80,
        f'Wayback ilk snapshot — {best_url[:100]}',
    )
    return {
        'status': 'success',
        'earliest': best_dt,
        'iso_date': best_dt.strftime('%Y-%m-%d'),
        'url': best_url,
        'wayback_url': (
            f"https://web.archive.org/web/{earliest['timestamp']}/{best_url}"
            if earliest.get('timestamp') else None
        ),
        'snapshot_count': best_wb.get('snapshot_count', 0),
    }


def _from_tineye(filepath: str, public_url: Optional[str], candidates: List[Dict]) -> Dict[str, Any]:
    """TinEye ən erkən crawl_date — veb şəkillər üçün əsas tarix mənbəyi."""
    empty: Dict[str, Any] = {'status': 'skipped'}
    try:
        from analyzers.tineye_date_extractor import extract_tineye_earliest_date
        te = extract_tineye_earliest_date(filepath, public_url)
    except Exception as e:
        print(f'  [!] TinEye tarix: {e}', file=sys.stderr)
        return {**empty, 'status': 'error', 'error': str(e)}

    if te.get('status') != 'success' or not te.get('earliest'):
        return te

    dt = te['earliest']
    _add_candidate(
        candidates, dt, 'tineye_earliest', te.get('confidence', 0.94),
        f"TinEye crawl_date (ən erkən, {te.get('match_count', 0)} uyğunluq)",
    )
    for det in (te.get('details') or [])[:8]:
        if det.get('source') == 'url_path' and det.get('date'):
            parsed = _parse_datetime_string(det['date'])
            if parsed:
                _add_candidate(
                    candidates, parsed[0], 'tineye_url', 0.86,
                    det.get('page_url', '')[:80],
                )
    return te


def _unsplash_timestamp_from_url(source_url: str, resolved_url: str) -> Optional[Dict]:
    """
    Unsplash CDN photo-ID — platforma yükləmə vaxtıdır, çəkiliş tarixi DEYİL.
    """
    for u in (resolved_url or '', source_url or ''):
        m = re.search(r'/photo-(\d{10,13})-', u or '')
        if not m:
            continue
        raw = m.group(1)
        try:
            val = int(raw)
            if len(raw) >= 13:
                sec = val / 1000.0
            elif len(raw) == 10:
                sec = float(val)
            else:
                continue
            if 946684800 < sec < 1893456000:  # 2000–2030
                dt = datetime.fromtimestamp(sec, tz=timezone.utc).replace(tzinfo=None)
                return {'dt': dt, 'raw': raw, 'method': 'photo_id_ms'}
        except (ValueError, OSError):
            continue
    return None


def _fetch_unsplash_date(source_url: str, resolved_url: str) -> Optional[Dict]:
    slug = None
    for u in (resolved_url or '', source_url or ''):
        m = re.search(r'/photo-(\d+)-([a-zA-Z0-9_-]+)', u)
        if m:
            slug = m.group(2)
            break
        m2 = re.search(r'unsplash\.com/photos/([a-zA-Z0-9_-]+)', u)
        if m2:
            slug = m2.group(1)
            break
    if not slug:
        return None
    page_url = f'https://unsplash.com/photos/{slug}'
    try:
        resp = requests.get(
            page_url,
            headers={'User-Agent': USER_AGENT, 'Accept': 'text/html'},
            timeout=16,
        )
        if resp.status_code != 200:
            return None
        html = resp.text[:400000]
        for pat in (
            r'"created_at"\s*:\s*"([^"]+)"',
            r'"taken_at"\s*:\s*"([^"]+)"',
            r'"date"\s*:\s*"(\d{4}-\d{2}-\d{2})',
            r'"uploaded_at"\s*:\s*"([^"]+)"',
            r'datePublished["\']?\s*content=["\']([^"\']+)',
        ):
            m = re.search(pat, html)
            if m:
                parsed = _parse_datetime_string(m.group(1))
                if parsed:
                    return {
                        'dt': parsed[0],
                        'raw': m.group(1),
                        'page_url': page_url,
                        'field': pat[:20],
                    }
        m2 = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>({.+?})</script>', html, re.S)
        if m2:
            try:
                data = json.loads(m2.group(1))
                blob = json.dumps(data)[:50000]
                for pat in (r'created_at["\']:\s*["\']([^"\']+)', r'taken_at["\']:\s*["\']([^"\']+)'):
                    mm = re.search(pat, blob)
                    if mm:
                        parsed = _parse_datetime_string(mm.group(1))
                        if parsed:
                            return {'dt': parsed[0], 'raw': mm.group(1), 'page_url': page_url, 'field': 'next_data'}
            except json.JSONDecodeError:
                pass
    except Exception as e:
        print(f'  [!] Unsplash tarix: {e}', file=sys.stderr)
    return None


def _from_page_meta(web_meta: Dict, source_url: str, resolved_url: str, candidates: List[Dict]) -> None:
    page = web_meta.get('page') or {}
    for key, src, conf in (
        ('published', 'page_published', 0.65),
        ('og_published_time', 'page_og', 0.62),
        ('image_published', 'page_published', 0.6),
    ):
        val = page.get(key)
        if val:
            parsed = _parse_datetime_string(val)
            if parsed:
                _add_candidate(candidates, parsed[0], src, conf, val)

    domain = (web_meta.get('domain') or '').lower()
    if 'unsplash' in domain or 'unsplash' in (source_url or '').lower():
        id_hit = _unsplash_timestamp_from_url(source_url, resolved_url)
        if id_hit:
            _add_candidate(
                candidates, id_hit['dt'], 'unsplash_photo_id', 0.35,
                id_hit.get('raw', ''),
            )
        hit = _fetch_unsplash_date(source_url, resolved_url)
        if hit:
            _add_candidate(
                candidates, hit['dt'], 'unsplash_page', 0.38,
                hit.get('raw') or hit.get('page_url', ''),
            )


def _pick_best(candidates: List[Dict]) -> Optional[Dict]:
    """
    EXIF çəkiliş tarixi varsa üstünlük; yoxdursa TinEye ən erkən tarix (platform yükləmə yox).
    """
    if not candidates:
        return None

    capture = [c for c in candidates if c.get('date_type') == 'capture']
    first_seen = [c for c in candidates if c.get('date_type') == 'first_seen']
    platform = [c for c in candidates if c.get('date_type') == 'platform']

    exif_best = None
    if capture:
        exif_rank = {'exif_original': 5, 'raw_exif': 4, 'xmp_created': 3, 'filename': 2}
        capture.sort(
            key=lambda c: (exif_rank.get(c.get('source'), 0), c.get('confidence', 0)),
            reverse=True,
        )
        exif_best = capture[0]
        if exif_best.get('source') == 'exif_original' and exif_best.get('confidence', 0) >= 0.9:
            pool = [exif_best]
            for c in candidates:
                if c is not exif_best and c.get('iso_date') != exif_best.get('iso_date'):
                    pool.append(c)
            return _finalize_pick(exif_best, pool[1:6])

    if first_seen:
        # TinEye ən erkən — bütün first_seen arasında MIN tarix (TinEye.com ilə eyni məntiq)
        tineye = [c for c in first_seen if c.get('source', '').startswith('tineye')]
        pool = tineye if tineye else first_seen
        pool.sort(key=lambda c: (c.get('iso_date', '9999'), -c.get('confidence', 0)))
        best = pool[0]
        alts = [c for c in candidates if c.get('iso_date') != best.get('iso_date')][:5]
        return _finalize_pick(best, alts)

    if capture:
        return _finalize_pick(capture[0], capture[1:6])

    if platform:
        platform.sort(key=lambda c: -c.get('confidence', 0))
        return _finalize_pick(platform[0], platform[1:4])

    candidates.sort(key=lambda c: -c.get('confidence', 0))
    return _finalize_pick(candidates[0], candidates[1:5])


def _finalize_pick(best: Dict, alts: List[Dict]) -> Dict:
    seen = set()
    unique_alts = []
    for c in alts:
        k = c.get('iso_date')
        if k and k not in seen and k != best.get('iso_date'):
            seen.add(k)
            unique_alts.append(c)
    return {**best, 'alternatives': unique_alts}


def _build_warning_az(
    best: Dict[str, Any],
    tineye_meta: Dict[str, Any],
    wayback_meta: Dict[str, Any],
    result: Dict[str, Any],
) -> Optional[str]:
    prop = result.get('image_propagation') or {}
    if best.get('source') == 'propagation_global':
        note = prop.get('cdn_only_note_az') or (prop.get('cdn_warning') or {}).get('message_az')
        if note:
            return note
        fd = prop.get('free_discovery') or {}
        for p in fd.get('providers') or []:
            if p.get('id') == 'brave_web' and p.get('status') == 'needs_api_key':
                return p.get('message_az')
    if (
        best.get('date_type') == 'platform'
        and tineye_meta.get('status') != 'success'
        and tineye_meta.get('needs_api_key')
    ):
        return (
            'Dəqiq veb tarixi üçün .env faylına TINEYE_API_KEY əlavə edin (tineye.com/api). '
            'Unsplash foto-ID yalnız platforma yükləmə vaxtıdır, çəkiliş tarixi deyil.'
        )
    if best.get('source') == 'wayback_earliest':
        return None
    if best.get('date_type') == 'platform' and tineye_meta.get('status') != 'success':
        if wayback_meta.get('status') == 'success':
            return None
        return (
            'TinEye və Wayback-də dəqiq iz tapılmadı; tarix platforma/veb mənbələrindən '
            'götürülüb — çəkiliş tarixi deyil.'
        )
    if (
        tineye_meta.get('status') != 'success'
        and wayback_meta.get('status') != 'success'
        and best.get('date_type') == 'first_seen'
    ):
        return 'TinEye və Wayback-də uyğunluq tapılmadı; alternativ mənbə istifadə olunub.'
    return None


def _from_propagation(result: Dict[str, Any], candidates: List[Dict]) -> None:
    prop = result.get('image_propagation') or {}
    gfs = prop.get('global_first_seen')
    if not gfs:
        return
    parsed = _parse_datetime_string(gfs)
    if not parsed:
        return
    _add_candidate(
        candidates, parsed[0], 'propagation_global', 0.82,
        prop.get('summary_az', '')[:120],
    )


def analyze_capture_date(result: Dict[str, Any], filepath: str) -> Dict[str, Any]:
    """
    Şəklin çəkilmə tarixini müəyyən edir və result-a capture_date əlavə edir.
    """
    candidates: List[Dict] = []
    _from_exif_block(result, candidates)
    _from_raw_tags(result, candidates)
    _from_filename(filepath, candidates)

    web = result.get('web_metadata') or {}
    _from_embedded(web, candidates)

    source_url = web.get('source_url')
    resolved = web.get('resolved_url')
    try:
        from analyzers.web_image_metadata import load_url_sidecar
        sc = load_url_sidecar(filepath)
        if sc:
            source_url = source_url or sc.get('source_url')
            resolved = resolved or sc.get('resolved_url') or source_url
    except Exception:
        pass

    # TinEye: orijinal şəkil URL (ngrok/uploads deyil), sonra fayl yükləməsi
    tineye_meta = _from_tineye(filepath, resolved or source_url, candidates)
    _from_propagation(result, candidates)

    wayback_meta: Dict[str, Any] = {'status': 'skipped'}
    if tineye_meta.get('status') != 'success':
        from analyzers.portal_search_urls import is_indexed_image_url
        seed_urls: List[str] = []
        for u in (resolved, source_url):
            if is_indexed_image_url(u) and u not in seed_urls:
                seed_urls.append(u)
        if seed_urls:
            print('  [i] TinEye tapılmadı — Wayback tarix axtarışı...', file=sys.stderr)
            wayback_meta = _from_wayback(seed_urls, candidates)

    if source_url:
        _from_page_meta(web, source_url, resolved or source_url, candidates)

    # Təkrarlanan (eyni tarix+mənbə) adayları sil
    uniq = []
    seen_keys = set()
    for c in candidates:
        key = (c.get('iso_date'), c.get('source'))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        uniq.append(c)
    candidates = uniq

    best = _pick_best(candidates)

    tineye_note = None
    wayback_note = None
    platform_alt = None
    date_type_title = DATE_TYPE_TITLE_AZ.get(best.get('date_type'), 'Tarix') if best else 'Tarix'
    if best:
        src = best.get('source', '')
        if src == 'wayback_earliest':
            date_type_title = 'İlk internet izi (Wayback)'
            wayback_note = (
                'TinEye-də uyğunluq tapılmadı. Tarix Internet Archive (Wayback Machine) '
                'ilk snapshot əsasında təxmin edilib — şəkil URL-inin vebdə arxivlənmə vaxtı.'
            )
        elif src == 'propagation_global':
            date_type_title = 'İlk internet izi (Wayback + mənbələr)'
            wayback_note = (
                'TinEye-də uyğunluq yoxdur; tarix Wayback arxivi və əlaqəli səhifə '
                'metadata-sından birləşdirilib.'
            )
        elif best.get('date_type') == 'first_seen' and src.startswith('tineye'):
            tineye_note = (
                'Tarix TinEye indeksindən (ilk internetdə görünmə, crawl_date asc). '
                'TinEye.com ilə uyğunlaşır; çəkiliş vaxtı EXIF-də ola bilər.'
            )
        for c in candidates:
            if c.get('date_type') == 'platform' and c.get('iso_date') != best.get('iso_date'):
                platform_alt = c
                break

    if not best:
        out = {
            'status': 'unknown',
            'message_az': (
                'Çəkiliş tarixi tapılmadı. Veb şəkillərdə EXIF adətən silinir; '
                'orijinal kamera faylı və ya EXIF saxlanılan mənbə sınayın.'
            ),
            'candidates': [],
        }
        result['capture_date'] = out
        return out

    out = {
        'status': 'success',
        'year': best['year'],
        'month': best['month'],
        'day': best['day'],
        'hour': best.get('hour'),
        'minute': best.get('minute'),
        'iso_date': best['iso_date'],
        'iso_datetime': best.get('iso_datetime'),
        'display_az': best['display_az'],
        'calendar_az': {
            'gun': best['day'],
            'ay': MONTHS_AZ[best['month']],
            'il': best['year'],
        },
        'source': best['source'],
        'source_label_az': best['source_label_az'],
        'confidence': best['confidence'],
        'confidence_percent': int(best['confidence'] * 100),
        'raw': best.get('raw'),
        'alternatives': best.get('alternatives', []),
        'date_type': best.get('date_type', 'unknown'),
        'message_az': _build_user_message(best, tineye_note),
        'tineye_note_az': tineye_note,
        'wayback_note_az': wayback_note,
        'wayback_url': wayback_meta.get('wayback_url') if best.get('source') == 'wayback_earliest' else None,
        'date_type_title_az': date_type_title,
        'platform_misread_az': (
            f'Unsplash/CDN ID səhv tarix verirdi: {platform_alt["display_az"]} '
            f'({platform_alt["source_label_az"]}) — istifadə edilmədi.'
            if platform_alt and best.get('date_type') == 'first_seen'
            else None
        ),
        'tineye_status': tineye_meta.get('status'),
        'warning_az': _build_warning_az(best, tineye_meta, wayback_meta, result),
        'all_candidates': [
            {
                'display_az': c['display_az'],
                'source': c.get('source'),
                'confidence': c.get('confidence'),
                'date_type': c.get('date_type'),
            }
            for c in sorted(candidates, key=lambda x: x.get('iso_date', ''))[:12]
        ],
    }
    result['capture_date'] = out

    if result.get('exif') is not None:
        if not isinstance(result['exif'].get('datetime'), dict):
            result['exif']['datetime'] = {}
        if not result['exif']['datetime'].get('original'):
            result['exif']['datetime']['capture_inferred'] = best['iso_datetime']

    return out
