"""
Reverse Weather Forecast — EXIF vaxt + GPS əsasında tarixi hava və şəkil vizual uyğunluğu.
Mənbə: Open-Meteo Archive API (pulsuz meteoroloji arxiv).
"""

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

_DATETIME_FORMATS = (
    '%Y:%m:%d %H:%M:%S',
    '%Y-%m-%d %H:%M:%S',
    '%Y:%m:%d %H:%M',
    '%Y-%m-%d %H:%M',
)

WMO_DESC_AZ = {
    0: 'Açıq və günəşli',
    1: 'Əsasən açıq',
    2: 'Qismən buludlu',
    3: 'Buludlu',
    45: 'Dumanlı',
    48: 'Bu tuman',
    51: 'Çiskin yağış',
    53: 'Orta çiskin',
    55: 'Güclü çiskin',
    56: 'Donmuş çiskin',
    57: 'Güclü donmuş çiskin',
    61: 'Yağış',
    63: 'Orta yağış',
    65: 'Güclü yağış',
    66: 'Donmuş yağış',
    67: 'Güclü donmuş yağış',
    71: 'Qar',
    73: 'Orta qar',
    75: 'Güclü qar',
    77: 'Qar dənələri',
    80: 'Leysan',
    81: 'Orta leysan',
    82: 'Güclü leysan',
    85: 'Qar leysanı',
    86: 'Güclü qar leysanı',
    95: 'Tufan',
    96: 'Dolu ilə tufan',
    99: 'Güclü dolu ilə tufan',
}

RAIN_CODES = frozenset({
    51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99,
})
SNOW_CODES = frozenset({71, 73, 75, 77, 85, 86})
WINDY_KMH = 28.0


def _wmo_desc(code: Optional[int]) -> str:
    if code is None:
        return 'Bilinmir'
    return WMO_DESC_AZ.get(int(code), f'Kod {code}')


def _parse_datetime(dt_raw: Optional[str]) -> Optional[datetime]:
    if not dt_raw:
        return None
    s = str(dt_raw).strip()
    if len(s) >= 19:
        s = s[:19]
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _datetime_from_meta(img_meta: Optional[Dict]) -> Optional[str]:
    if not img_meta:
        return None
    exif = img_meta.get('exif') or {}
    dt_info = exif.get('datetime') or {}
    raw = (
        dt_info.get('original')
        or dt_info.get('digitized')
        or dt_info.get('modified')
        or dt_info.get('inferred_from_filename')
    )
    if raw:
        return str(raw)
    raw_tags = img_meta.get('raw_tags') or {}
    return raw_tags.get('EXIF DateTimeOriginal') or raw_tags.get('Image DateTime')


def _fetch_historical(lat: float, lon: float, target_date: str, capture_dt: Optional[datetime]) -> Dict[str, Any]:
    url = (
        'https://archive-api.open-meteo.com/v1/archive'
        f'?latitude={lat}&longitude={lon}'
        f'&start_date={target_date}&end_date={target_date}'
        '&hourly=temperature_2m,precipitation,weathercode,windspeed_10m,cloudcover,relativehumidity_2m'
        '&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode,windspeed_10m_max'
        '&timezone=auto'
    )
    try:
        resp = requests.get(url, timeout=15)
    except Exception as e:
        return {'error': str(e)}

    if resp.status_code != 200:
        return {'error': f'Open-Meteo API: HTTP {resp.status_code}'}

    data = resp.json()
    hourly = data.get('hourly') or {}
    daily = data.get('daily') or {}
    times = hourly.get('time') or []

    at_capture = None
    capture_hour_label = None
    if times and capture_dt:
        target_h = capture_dt.hour
        best_idx = 0
        best_diff = 24
        for i, t in enumerate(times):
            try:
                hour = int(str(t).split('T')[1].split(':')[0])
            except (IndexError, ValueError):
                continue
            diff = abs(hour - target_h)
            if diff < best_diff:
                best_diff = diff
                best_idx = i
        capture_hour_label = str(times[best_idx]).split('T')[-1][:5] if best_idx < len(times) else None

        def _hval(key):
            arr = hourly.get(key) or []
            return arr[best_idx] if best_idx < len(arr) else None

        wcode = _hval('weathercode')
        at_capture = {
            'time': times[best_idx] if best_idx < len(times) else None,
            'temperature_c': _hval('temperature_2m'),
            'precipitation_mm': _hval('precipitation'),
            'weather_code': wcode,
            'description_az': _wmo_desc(wcode),
            'wind_speed_kmh': _hval('windspeed_10m'),
            'cloud_cover_pct': _hval('cloudcover'),
            'humidity_pct': _hval('relativehumidity_2m'),
            'is_rainy': wcode in RAIN_CODES or (_hval('precipitation') or 0) > 0.1,
            'is_snowy': wcode in SNOW_CODES,
            'is_windy': (_hval('windspeed_10m') or 0) >= WINDY_KMH,
            'is_clear': wcode in (0, 1),
        }

    daily_summary = None
    if daily.get('time') and len(daily['time']) > 0:
        dw = daily.get('weathercode', [None])[0]
        daily_summary = {
            'date': target_date,
            'max_temp_c': (daily.get('temperature_2m_max') or [None])[0],
            'min_temp_c': (daily.get('temperature_2m_min') or [None])[0],
            'precipitation_mm': (daily.get('precipitation_sum') or [None])[0],
            'max_wind_kmh': (daily.get('windspeed_10m_max') or [None])[0],
            'weather_code': dw,
            'description_az': _wmo_desc(dw),
        }

    if not at_capture and not daily_summary:
        return {'error': 'Həmin tarix üçün arxiv məlumatı tapılmadı'}

    return {
        'source': 'Open-Meteo Archive API',
        'date': target_date,
        'capture_hour': capture_hour_label,
        'at_capture': at_capture,
        'daily_summary': daily_summary,
    }


def _analyze_visual(filepath: str) -> Dict[str, Any]:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {'error': 'OpenCV quraşdırılmayıb', 'status': 'skipped'}

    try:
        img = cv2.imread(filepath)
        if img is None:
            return {'error': 'Şəkil oxuna bilmədi', 'status': 'skipped'}
    except Exception as e:
        return {'error': str(e), 'status': 'skipped'}

    h, w = img.shape[:2]
    sky = img[: max(h // 4, 1), :]
    ground = img[int(h * 0.55) :, :]

    sky_hsv = cv2.cvtColor(sky, cv2.COLOR_BGR2HSV)
    sh, ss, sv = [float(x) for x in cv2.mean(sky_hsv)[:3]]

    if sv > 180 and ss < 80:
        sky_condition = 'sunny'
        sky_az = 'Günəşli səma'
    elif sv < 100:
        sky_condition = 'overcast'
        sky_az = 'Tutqun/buludlu səma'
    elif 90 < sh < 130 and ss > 40:
        sky_condition = 'rainy'
        sky_az = 'Yağışlı səma tonu'
    else:
        sky_condition = 'cloudy'
        sky_az = 'Buludlu səma'

    g_gray = cv2.cvtColor(ground, cv2.COLOR_BGR2GRAY)
    g_hsv = cv2.cvtColor(ground, cv2.COLOR_BGR2HSV)

    block = 32
    gh, gw = g_gray.shape
    local_stds = []
    for y in range(0, max(gh - block, 1), block):
        for x in range(0, max(gw - block, 1), block):
            patch = g_gray[y:y + block, x:x + block]
            if patch.size > 50:
                local_stds.append(float(np.std(patch)))

    reflection_score = min(100, (np.mean(local_stds) if local_stds else 0) * 2.2)
    dark_frac = float(np.mean(g_gray < 70)) * 100
    sat_mean = float(np.mean(g_hsv[:, :, 1]))
    edges = cv2.Canny(g_gray, 40, 120)
    edge_density = float(np.mean(edges > 0)) * 100

    wetness = min(100, reflection_score * 0.45 + dark_frac * 0.25 + edge_density * 0.2 + min(sat_mean, 80) * 0.15)
    snow_likelihood = min(100, max(0, (float(np.mean(g_gray)) - 140) * 0.5 + max(0, 60 - sat_mean) * 0.4))

    gray_full = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur_var = float(cv2.Laplacian(gray_full, cv2.CV_64F).var())
    motion_blur_hint = blur_var < 80

    ground_state = 'dry'
    ground_az = 'Quru / adi səth'
    if wetness >= 58:
        ground_state = 'wet'
        ground_az = 'Islak səth və ya su ləkələri (yağış izi)'
    elif snow_likelihood >= 55:
        ground_state = 'snow'
        ground_az = 'Ağ/açıq örtük — qar ehtimalı'

    inferred_weather = sky_condition
    if ground_state == 'wet' and sky_condition != 'sunny':
        inferred_weather = 'rainy'
    elif ground_state == 'snow':
        inferred_weather = 'snowy'
    elif sky_condition == 'sunny' and wetness < 40:
        inferred_weather = 'sunny'

    WEATHER_AZ = {
        'sunny': 'Günəşli',
        'cloudy': 'Buludlu',
        'overcast': 'Tutqun',
        'rainy': 'Yağışlı',
        'snowy': 'Qarlı',
    }

    return {
        'status': 'ok',
        'sky_condition': sky_condition,
        'sky_summary_az': sky_az,
        'ground_state': ground_state,
        'ground_summary_az': ground_az,
        'ground_wetness_score': round(wetness, 1),
        'snow_likelihood': round(snow_likelihood, 1),
        'reflection_score': round(reflection_score, 1),
        'inferred_weather': inferred_weather,
        'inferred_weather_az': WEATHER_AZ.get(inferred_weather, inferred_weather),
        'motion_blur_hint': motion_blur_hint,
        'blur_variance': round(blur_var, 1),
    }


def _check_consistency(historical: Dict, visual: Dict) -> Dict[str, Any]:
    if historical.get('error') or visual.get('error') or visual.get('status') == 'skipped':
        return {
            'score': None,
            'verdict': 'insufficient_data',
            'verdict_az': 'Kifayət qədər məlumat yoxdur',
            'findings': [],
            'summary_az': 'Tarixi hava və ya vizual analiz tamamlanmadı.',
        }

    findings: List[str] = []
    score = 50
    at = historical.get('at_capture') or {}
    daily = historical.get('daily_summary') or {}

    hist_rainy = at.get('is_rainy') or (daily.get('precipitation_mm') or 0) > 2
    hist_snowy = at.get('is_snowy')
    hist_windy = at.get('is_windy')
    hist_clear = at.get('is_clear')

    vis = visual.get('inferred_weather', 'cloudy')
    wet = visual.get('ground_wetness_score', 0) or 0
    snowy = visual.get('snow_likelihood', 0) or 0

    if hist_rainy:
        if vis in ('rainy', 'overcast') or wet >= 50:
            score += 28
            findings.append('Tarixi yağış məlumatı şəkildə yağışlı/tutqun səma və ya islak sərtlə uyğun gəlir.')
        elif vis == 'sunny' and wet < 35:
            score -= 32
            findings.append('Tarixdə yağış qeydə alınıb, lakin şəkil güclü günəşli/quru görünür — uyğunsuzluq.')
        else:
            score += 5
            findings.append('Tarixdə yağış var; vizual sübut zəif və ya qismən uyğundur.')
    elif hist_clear:
        if vis == 'sunny' and wet < 45:
            score += 28
            findings.append('Tarixi açıq hava ilə günəşli səma və quru səth uyğun gəlir.')
        elif wet >= 60:
            score -= 25
            findings.append('Tarixdə açıq hava, lakin zəmin güclü islak görünür — şübhəli.')
        else:
            score += 10
            findings.append('Tarixi açıq hava; vizual qismən buludlu ola bilər (foto vaxtı fərqi).')

    if hist_snowy:
        if vis == 'snowy' or snowy >= 50:
            score += 22
            findings.append('Tarixi qar havası ilə vizual ağ örtük uyğundur.')
        elif vis == 'sunny' and wet < 30:
            score -= 20
            findings.append('Tarixdə qar, lakin şəkil quru/günəşli — uyğunsuzluq.')

    if hist_windy:
        if visual.get('motion_blur_hint'):
            score += 12
            findings.append('Tarixi güclü külək və şəkildə hərəkət bulanıqlığı ipucu uyğun gəlir.')
        else:
            findings.append('Tarixdə küləkli hava qeydə alınıb; vizual külək sübutu zəifdir.')

    precip = at.get('precipitation_mm')
    if precip is not None and precip == 0 and wet >= 65 and vis != 'snowy':
        score -= 15
        findings.append('Həmin saatda yağış qeydə alınmayıb, amma zəmin güclü islakdır.')

    score = max(0, min(100, score))
    if score >= 75:
        verdict, verdict_az = 'consistent', 'Uyğun'
    elif score >= 50:
        verdict, verdict_az = 'partial', 'Qismən uyğun'
    else:
        verdict, verdict_az = 'inconsistent', 'Uyğunsuz / şübhəli'

    summary = (
        f'Uyğunlaşma skoru: {score}/100 ({verdict_az}). '
        f'Tarixi: {at.get("description_az") or daily.get("description_az") or "?"}. '
        f'Vizual: {visual.get("inferred_weather_az", "?")}.'
    )

    return {
        'score': score,
        'verdict': verdict,
        'verdict_az': verdict_az,
        'findings': findings,
        'summary_az': summary,
    }


def analyze_reverse_weather(
    filepath: Optional[str],
    img_meta: Optional[Dict] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    datetime_raw: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Metadata koordinat/vaxt + Open-Meteo arxivi + şəkil vizual analizi.
    """
    meta = img_meta or {}
    loc = meta.get('location') or {}
    lat = latitude if latitude is not None else loc.get('latitude')
    lon = longitude if longitude is not None else loc.get('longitude')

    if lat is None or lon is None:
        return {
            'module': 'reverse_weather_forecast',
            'status': 'no_coordinates',
            'error': 'GPS koordinatları lazımdır',
            'summary_az': 'Hava uyğunlaşdırması üçün EXIF GPS tələb olunur.',
        }

    dt_raw = datetime_raw or _datetime_from_meta(meta)
    capture_dt = _parse_datetime(dt_raw)
    if capture_dt:
        target_date = capture_dt.strftime('%Y-%m-%d')
    else:
        target_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    print(
        f'  [i] Reverse weather: {lat:.4f}, {lon:.4f} @ {target_date}'
        + (f' {capture_dt.strftime("%H:%M")}' if capture_dt else ' (tarixsiz)'),
        file=sys.stderr,
    )

    historical = _fetch_historical(float(lat), float(lon), target_date, capture_dt)
    visual = _analyze_visual(filepath) if filepath and os.path.isfile(filepath) else {'status': 'skipped', 'error': 'Fayl yoxdur'}

    consistency = _check_consistency(historical, visual)

    legacy_weather = None
    if not historical.get('error'):
        daily = historical.get('daily_summary') or {}
        at = historical.get('at_capture') or {}
        legacy_weather = {
            'date': historical.get('date'),
            'max_temp_c': daily.get('max_temp_c'),
            'min_temp_c': daily.get('min_temp_c'),
            'precipitation_mm': daily.get('precipitation_mm'),
            'weather_code': at.get('weather_code') or daily.get('weather_code'),
            'description': at.get('description_az') or daily.get('description_az'),
            'capture_hour': historical.get('capture_hour'),
            'wind_speed_kmh': at.get('wind_speed_kmh'),
        }

    out = {
        'module': 'reverse_weather_forecast',
        'status': 'ok' if not historical.get('error') else 'error',
        'capture_datetime': dt_raw,
        'capture_datetime_parsed': capture_dt.isoformat() if capture_dt else None,
        'coordinates': {'latitude': float(lat), 'longitude': float(lon)},
        'historical': historical,
        'visual_analysis': visual,
        'consistency': consistency,
        'summary_az': consistency.get('summary_az', ''),
    }
    if historical.get('error'):
        out['error'] = historical['error']
        out['summary_az'] = historical['error']
    if legacy_weather:
        out['weather_legacy'] = legacy_weather
    return out
