"""
Elmi / Kriminalistika — AI/synthetic, manipulyasiya, işıq, məsafə, kölgə,
səs-küy, lens, kontekstual/temporal/sosial çıxarım, vahid JSON hesabat.
"""

import hashlib
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

SEASON_AZ = {'spring': 'Yaz', 'summer': 'Yay', 'autumn': 'Payız', 'winter': 'Qış'}
TIME_AZ = {
    'morning': 'Səhər', 'noon': 'Günorta', 'afternoon': 'Günorta/axşam',
    'evening': 'Axşam', 'night': 'Gecə',
}
WEATHER_AZ = {
    'sunny': 'Günəşli', 'cloudy': 'Buludlu', 'rainy': 'Yağışlı',
    'snowy': 'Qarlı', 'overcast': 'Tutqun',
}
CULTURE_AZ = {
    'europe': 'Avropa', 'asia': 'Asiya', 'middle_east': 'Yaxın Şərq',
    'western': 'Qərb', 'local_caucasus': 'Qafqaz/MDB',
}

CAR_YEAR_HINTS = {
    'car': (2010, 2025), 'truck': (2010, 2025), 'bus': (2010, 2025),
    'motorcycle': (2010, 2025),
}


def _read_image(filepath: str) -> Optional[np.ndarray]:
    img = cv2.imread(filepath)
    return img


def _sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _safe_call(fn, *args, default=None):
    try:
        return fn(*args)
    except Exception as e:
        print(f'  [!] {fn.__name__}: {e}', file=sys.stderr)
        return default if default is not None else {'error': str(e)}


def _detect_ai_synthetic(img: np.ndarray, c2pa: Dict, ela_score: int, stego_score: int) -> Dict[str, Any]:
    """Real foto vs AI/synthetic — ensemble heuristika."""
    scores = []
    signals = []

    gray_u8 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = gray_u8.astype(np.float32)
    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    mag = np.log1p(np.abs(fshift))
    hf_ratio = float(np.mean(mag[mag.shape[0] // 4:3 * mag.shape[0] // 4, mag.shape[1] // 4:3 * mag.shape[1] // 4]))
    lf_ratio = float(np.mean(mag)) + 1e-6
    hf_norm = hf_ratio / lf_ratio
    if hf_norm < 0.85:
        scores.append(0.65)
        signals.append('Aşağı yüksək tezlik enerjisi (synthetic/GAN izi ola bilər)')
    elif hf_norm > 1.8:
        scores.append(0.35)
        signals.append('Təbii yüksək tezlik paylanması')

    color_std = float(np.std(img))
    if color_std < 28:
        scores.append(0.55)
        signals.append('Rəng paylanması həddən az (over-smooth AI)')

    if c2pa.get('is_ai_generated') or c2pa.get('ai_generated'):
        scores.append(0.92)
        signals.append('C2PA/Content Credentials: AI generasiya işarəsi')

    if ela_score > 55:
        scores.append(0.4)
        signals.append('ELA: yüksək manipulyasiya skoru')

    lap_var = float(cv2.Laplacian(gray_u8, cv2.CV_64F).var())
    if lap_var < 80:
        scores.append(0.5)
        signals.append('Aşağı Laplacian variansiya (süni yumşaltma)')

    ai_prob = float(np.mean(scores)) if scores else 0.15
    ai_prob = min(0.98, max(0.02, ai_prob))

    return {
        'is_ai_generated_probability': round(ai_prob, 3),
        'is_real_photo_probability': round(1.0 - ai_prob, 3),
        'verdict_az': (
            'AI/synthetic ehtimalı yüksək' if ai_prob > 0.6
            else 'Real foto ehtimalı yüksək' if ai_prob < 0.35
            else 'Qeyri-müəyyən — əlavə yoxlama lazımdır'
        ),
        'signals': signals,
        'methods': ['FFT spektral', 'rəng variansiya', 'ELA', 'C2PA', 'Laplacian'],
    }


def _detect_copy_move(img: np.ndarray, block: int = 32, stride: int = 16) -> Dict[str, Any]:
    """Sadə copy-move: ORB descriptor oxşarlığı eyni şəkildə."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    if h < 128 or w < 128:
        return {'detected': False, 'regions': [], 'score': 0}

    orb = cv2.ORB_create(500)
    kp, des = orb.detectAndCompute(gray, None)
    if des is None or len(kp) < 20:
        return {'detected': False, 'regions': [], 'score': 0}

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des, des)
    suspicious = []
    min_dist = 30
    for m in matches:
        if m.distance > min_dist:
            continue
        i, j = m.queryIdx, m.trainIdx
        if i == j:
            continue
        p1, p2 = kp[i].pt, kp[j].pt
        if np.hypot(p1[0] - p2[0], p1[1] - p2[1]) < 40:
            continue
        suspicious.append({'from': p1, 'to': p2, 'distance': m.distance})

    score = min(100, len(suspicious) * 3)
    return {
        'detected': len(suspicious) >= 8,
        'match_pairs': len(suspicious),
        'score': score,
        'risk': 'high' if score > 40 else 'medium' if score > 15 else 'low',
        'summary_az': (
            f'Copy-move şübhəsi: {len(suspicious)} uzaq ORB cütü'
            if suspicious else 'Copy-move izi aşkar edilmədi'
        ),
    }


def _noise_inconsistency(img: np.ndarray) -> Dict[str, Any]:
    """Splicing/inpainting — blok səs-küy variansiyası."""
    gray_u8 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray_u8.shape
    bs = 64
    vars_ = []
    for y in range(0, h - bs, bs):
        for x in range(0, w - bs, bs):
            patch = gray_u8[y:y + bs, x:x + bs]
            blur = cv2.GaussianBlur(patch, (0, 0), 3)
            noise = patch.astype(np.float32) - blur.astype(np.float32)
            vars_.append(float(np.var(noise)))
    if len(vars_) < 4:
        return {'inconsistent': False, 'score': 0}
    cv_ratio = float(np.std(vars_) / (np.mean(vars_) + 1e-6))
    return {
        'inconsistent': cv_ratio > 1.2,
        'coefficient_of_variation': round(cv_ratio, 3),
        'score': min(100, int(cv_ratio * 35)),
        'summary_az': (
            'Splicing/inpainting: səs-küy blokları arasında uyğunsuzluq'
            if cv_ratio > 1.2 else 'Səs-küy paylanması homogen görünür'
        ),
    }


def _analyze_manipulation(img: np.ndarray, ela: Dict) -> Dict[str, Any]:
    copy_move = _detect_copy_move(img)
    noise_inc = _noise_inconsistency(img)
    ela_score = ela.get('manipulation_score', 0) if ela else 0
    composite = min(100, ela_score * 0.5 + copy_move['score'] * 0.3 + noise_inc['score'] * 0.2)
    return {
        'is_manipulated': composite > 45 or copy_move['detected'],
        'composite_score': round(composite, 1),
        'copy_move': copy_move,
        'splicing_noise': noise_inc,
        'retouching_ela_score': ela_score,
        'inpainting_hint': noise_inc['inconsistent'] and ela_score > 30,
        'types_detected': [
            t for t, cond in [
                ('copy-move', copy_move['detected']),
                ('splicing', noise_inc['inconsistent']),
                ('retouching', ela_score > 40),
                ('inpainting', noise_inc['inconsistent'] and ela_score > 25),
            ] if cond
        ],
        'summary_az': (
            'Manipulyasiya ehtimalı: ' + ', '.join([
                t for t, cond in [
                    ('copy-move', copy_move['detected']),
                    ('splicing', noise_inc['inconsistent']),
                    ('retouching', ela_score > 40),
                ] if cond
            ]) if composite > 35 else 'Güclü manipulyasiya izi tapılmadı'
        ),
    }


def _analyze_lighting(img: np.ndarray) -> Dict[str, Any]:
    """Işıq mənbəyi istiqaməti — luminans gradient."""
    l = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = l.shape
    top = l[: h // 3, :]
    bottom = l[2 * h // 3:, :]
    top_mean = float(np.mean(top))
    bot_mean = float(np.mean(bottom))
    gx = cv2.Sobel(l, cv2.CV_32F, 1, 0, ksize=5)
    gy = cv2.Sobel(l, cv2.CV_32F, 0, 1, ksize=5)
    angle_rad = np.arctan2(np.mean(gy), np.mean(gx) + 1e-6)
    angle_deg = int(np.degrees(angle_rad)) % 360

    direction_map = {
        (315, 360): 'şimal/qərb', (0, 45): 'şimal/şərq',
        (45, 135): 'şərq', (135, 225): 'cənub',
        (225, 315): 'qərb',
    }
    dir_az = 'müəyyən deyil'
    for (a1, a2), name in direction_map.items():
        if a1 <= angle_deg < a2 or (a1 > a2 and (angle_deg >= a1 or angle_deg < a2)):
            dir_az = name
            break

    return {
        'light_source_angle_deg': angle_deg,
        'direction_az': dir_az,
        'top_brightness': round(top_mean, 1),
        'bottom_brightness': round(bot_mean, 1),
        'likely_overhead': top_mean > bot_mean + 15,
        'summary_az': f'Təxmini işıq istiqaməti: {dir_az} ({angle_deg}°)',
    }


def _estimate_distance(img: np.ndarray, img_meta: Optional[Dict]) -> Dict[str, Any]:
    """Kamera-obyekt məsafəsi — EXIF focal + person/face bbox."""
    exif = (img_meta or {}).get('exif') or {}
    settings = exif.get('settings') or {}
    focal_str = settings.get('focal_length') or settings.get('focal_length_35mm') or ''
    focal_mm = None
    m = re.search(r'([\d.]+)', str(focal_str))
    if m:
        focal_mm = float(m.group(1))

    return {
        'estimated_distance_m': None,
        'method': 'insufficient_data',
        'focal_length_mm': focal_mm,
        'confidence': 'low',
        'summary_az': (
            f'Focal {focal_mm} mm — obyekt bbox lazımdır'
            if focal_mm else 'Məsafə: EXIF focal və ya obyekt ölçüsü yetərli deyil'
        ),
    }


def _estimate_distance_from_file(filepath: str, img: np.ndarray, img_meta: Optional[Dict]) -> Dict[str, Any]:
    base = _estimate_distance(img, img_meta)
    try:
        from analyzers.object_detection_analyzer import detect_objects
        det = detect_objects(filepath, conf_threshold=0.35)
        persons = [o for o in (det.get('objects') or []) if o.get('class_name') == 'person']
        if persons:
            largest = max(persons, key=lambda o: o['bbox']['h'])
            person_h_px = largest['bbox']['h']
            exif = (img_meta or {}).get('exif') or {}
            settings = exif.get('settings') or {}
            focal_str = settings.get('focal_length') or ''
            m = re.search(r'([\d.]+)', str(focal_str))
            if m:
                focal_mm = float(m.group(1))
                h_img = img.shape[0]
                f_px = (focal_mm / 24.0) * h_img
                dist_m = (1.7 * f_px) / max(person_h_px, 1)
                base['estimated_distance_m'] = round(dist_m, 1)
                base['method'] = 'pinhole+YOLO person'
                base['confidence'] = 'medium'
                base['focal_length_mm'] = focal_mm
                base['person_height_px'] = person_h_px
                base['summary_az'] = f'Təxmini məsafə: ~{round(dist_m, 1)} m (insan bbox + focal {focal_mm} mm)'
    except Exception:
        pass
    return base


def _analyze_shadows(img: np.ndarray, lighting: Dict) -> Dict[str, Any]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dark = (gray < 60).astype(np.uint8) * 255
    dark_ratio = float(np.sum(dark > 0) / dark.size)
    kernel = np.ones((5, 5), np.uint8)
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel)
    cnts, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    large_shadows = [c for c in cnts if cv2.contourArea(c) > 500]

    inconsistency = False
    if large_shadows and lighting.get('likely_overhead'):
        bottom_dark = float(np.mean(gray[int(gray.shape[0] * 0.7):, :]))
        if bottom_dark < 80 and lighting.get('top_brightness', 0) > 140:
            inconsistency = False
    elif dark_ratio > 0.4 and lighting.get('top_brightness', 0) > 180:
        inconsistency = True

    return {
        'shadow_region_count': len(large_shadows),
        'dark_pixel_ratio': round(dark_ratio, 3),
        'inconsistency_detected': inconsistency,
        'forgery_hint': inconsistency,
        'summary_az': (
            'Kölgə/işıq uyğunsuzluğu — saxtakarlıq ehtimalı'
            if inconsistency else f'{len(large_shadows)} kölgə regionu; işıq-kölgə ümumən uyğun'
        ),
    }


def _analyze_noise_sensor(img: np.ndarray, img_meta: Optional[Dict]) -> Dict[str, Any]:
    gray_u8 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray_u8, (0, 0), 3)
    noise = gray_u8.astype(np.float32) - blur.astype(np.float32)
    noise_std = float(np.std(noise))
    exif_iso = None
    settings = ((img_meta or {}).get('exif') or {}).get('settings') or {}
    iso_raw = settings.get('iso')
    if iso_raw:
        try:
            exif_iso = int(re.search(r'\d+', str(iso_raw)).group())
        except Exception:
            pass

    iso_match = None
    if exif_iso:
        if exif_iso < 200 and noise_std < 4:
            iso_match = 'consistent'
        elif exif_iso > 800 and noise_std > 6:
            iso_match = 'consistent'
        elif exif_iso < 200 and noise_std > 8:
            iso_match = 'inconsistent_reencoding'

    return {
        'noise_std': round(noise_std, 3),
        'exif_iso': exif_iso,
        'iso_noise_consistency': iso_match,
        'sensor_hint': (
            'Aşağı səs-küy — sensor/ISO aşağı və ya heavy NR'
            if noise_std < 3 else 'Yüksək səs-küy — yüksək ISO və ya ağır sıxılma'
        ),
        'summary_az': f'Səs-küy σ={noise_std:.2f}' + (f', EXIF ISO {exif_iso}' if exif_iso else ''),
    }


def _analyze_lens(img: np.ndarray) -> Dict[str, Any]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 80, minLineLength=80, maxLineGap=10)
    curvature_score = 0.0
    if lines is not None and len(lines) > 3:
        angles = []
        for ln in lines[:30]:
            x1, y1, x2, y2 = ln[0]
            angles.append(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        curvature_score = float(np.std(angles))

    b, g, r = cv2.split(img)
    edge_b = cv2.Canny(b, 80, 160)
    edge_r = cv2.Canny(r, 80, 160)
    shift = float(np.mean(cv2.absdiff(edge_b, edge_r)) / 255.0)
    chromatic = shift > 0.08

    return {
        'line_count': len(lines) if lines is not None else 0,
        'distortion_hint_score': round(curvature_score, 2),
        'likely_wide_angle_distortion': curvature_score > 35,
        'chromatic_aberration_detected': chromatic,
        'chromatic_score': round(shift, 3),
        'summary_az': (
            ('Xromatik aberatsiya izi; ' if chromatic else '')
            + ('Geniş bucaqlı lens distorsiyası ehtimalı' if curvature_score > 35 else 'Lens anomaliyası zəif')
        ),
    }


def _sky_region_stats(img: np.ndarray) -> Dict[str, float]:
    h = img.shape[0]
    sky = img[: max(h // 4, 1), :]
    hsv = cv2.cvtColor(sky, cv2.COLOR_BGR2HSV)
    mean_h, mean_s, mean_v = [float(x) for x in cv2.mean(hsv)[:3]]
    return {'hue': mean_h, 'saturation': mean_s, 'value': mean_v}


def _infer_contextual(img: np.ndarray, img_meta: Optional[Dict], vision: Optional[Dict]) -> Dict[str, Any]:
    sky = _sky_region_stats(img)
    season = 'unknown'
    month = None
    dt = ((img_meta or {}).get('exif') or {}).get('datetime') or {}
    orig = dt.get('original') or dt.get('modified') or ''
    if orig:
        m = re.search(r':(\d{2}):', orig)
        if m:
            month = int(m.group(1))
            if month in (3, 4, 5):
                season = 'spring'
            elif month in (6, 7, 8):
                season = 'summer'
            elif month in (9, 10, 11):
                season = 'autumn'
            else:
                season = 'winter'

    if sky['value'] > 180 and sky['saturation'] < 80:
        weather = 'sunny'
    elif sky['value'] < 100:
        weather = 'overcast'
    elif sky['hue'] > 90 and sky['hue'] < 130:
        weather = 'rainy'
    else:
        weather = 'cloudy'

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean_l = float(np.mean(gray))
    if mean_l > 140:
        tod = 'noon'
    elif mean_l > 90:
        tod = 'afternoon'
    elif mean_l > 45:
        tod = 'evening'
    else:
        tod = 'night'

    loc = (img_meta or {}).get('location') or {}
    culture = 'western'
    if loc.get('latitude') is not None:
        lat = abs(float(loc['latitude']))
        if 35 <= lat <= 50 and 44 <= abs(float(loc.get('longitude', 0))) <= 52:
            culture = 'local_caucasus'
        elif lat < 35:
            culture = 'asia'
        elif lat > 50:
            culture = 'europe'

    place = None
    if vision and vision.get('scene', {}).get('primary'):
        place = vision['scene']['primary'].get('place_az')

    return {
        'estimated_season': season,
        'estimated_season_az': SEASON_AZ.get(season, 'Naməlum'),
        'estimated_time_of_day': tod,
        'estimated_time_of_day_az': TIME_AZ.get(tod, tod),
        'sky_weather': weather,
        'sky_weather_az': WEATHER_AZ.get(weather, weather),
        'culture_style': culture,
        'culture_style_az': CULTURE_AZ.get(culture, culture),
        'place_type': place,
        'summary_az': (
            f'{SEASON_AZ.get(season, "?")}, {TIME_AZ.get(tod, "?")}, '
            f'hava: {WEATHER_AZ.get(weather, "?")}, mədəniyyət konteksti: {CULTURE_AZ.get(culture, "?")}'
        ),
    }


def _infer_temporal(img_meta: Optional[Dict], vision: Optional[Dict]) -> Dict[str, Any]:
    year_hints = []
    dt = ((img_meta or {}).get('exif') or {}).get('datetime') or {}
    orig = dt.get('original') or ''
    if orig:
        ym = re.search(r'(20\d{2})', orig)
        if ym:
            year_hints.append({'source': 'exif_datetime', 'year': int(ym.group(1)), 'confidence': 0.95})

    camera = ((img_meta or {}).get('exif') or {}).get('camera') or {}
    model = (camera.get('model') or '').lower()
    if 'iphone 15' in model or 'iphone 14' in model:
        year_hints.append({'source': 'device_model', 'year_range': '2023-2025', 'confidence': 0.7})
    elif 'iphone' in model:
        year_hints.append({'source': 'device_model', 'year_range': '2015-2023', 'confidence': 0.5})

    car_years = []
    objects = (vision or {}).get('objects_coco') or {}
    for obj in (objects.get('objects') or []):
        cn = obj.get('class_name')
        if cn in CAR_YEAR_HINTS:
            lo, hi = CAR_YEAR_HINTS[cn]
            car_years.append({'class': cn, 'year_range': f'{lo}-{hi}', 'confidence': 0.4})

    pixel_hint = None
    img_info = ((img_meta or {}).get('exif') or {}).get('image') or {}
    w = img_info.get('width')
    if w and int(w) >= 4000:
        pixel_hint = '2018-2025 (yüksək rezolyusiya sensor)'
    elif w and int(w) <= 1024:
        pixel_hint = '2005-2015 (aşağı rezolyusiya)'

    est_range = None
    if year_hints:
        est_range = str(year_hints[0].get('year') or year_hints[0].get('year_range'))
    elif pixel_hint:
        est_range = pixel_hint
    elif car_years:
        est_range = car_years[0]['year_range']

    return {
        'estimated_year_range': est_range,
        'year_hints': year_hints,
        'car_model_year_hints': car_years,
        'pixel_era_hint': pixel_hint,
        'fashion_hint': 'OCR/vision moda analizi məhdud — metadata tarixinə baxın',
        'summary_az': f'Təxmini dövr: {est_range or "müəyyən deyil"}',
    }


def _infer_social(vision: Optional[Dict], img_meta: Optional[Dict]) -> Dict[str, Any]:
    people = (vision or {}).get('people') or {}
    count = people.get('person_count', 0)
    relationship = 'unknown'
    if count == 1:
        relationship = 'tək şəxs / portret'
    elif count == 2:
        relationship = 'cütlük — ailə/partner/dost ola bilər (təxmini)'
    elif count <= 5:
        relationship = 'kiçik qrup — dostlar/həmkarlar'
    elif count > 5:
        relationship = 'kollektiv / ictimai tədbir'

    brands = (vision or {}).get('brands_logos') or {}
    logo_event = None
    if brands.get('brands'):
        names = [b['brand'] for b in brands['brands'][:3]]
        logo_event = f'Loqolar: {", ".join(names)} — sponsorluq/ticarət konteksti ola bilər'

    return {
        'person_count': count,
        'relationship_hint_az': relationship,
        'face_database_match': {
            'available': False,
            'note': 'Üz DB axtarışı aktiv deyil — yalnız lokal analiz',
        },
        'gps_related_images': {
            'available': False,
            'note': 'GPS ilə əlaqəli şəkillər üçün xarici DB lazımdır',
        },
        'logo_event_hint': logo_event,
        'summary_az': relationship + (f'; {logo_event}' if logo_event else ''),
    }


def _security_integrity(filepath: str, img_meta: Optional[Dict], internal: Optional[Dict]) -> Dict[str, Any]:
    ext = os.path.splitext(filepath)[1].lower()
    reencode_hint = None
    if internal and internal.get('segments', {}).get('counts', {}).get('APP') is not None:
        pass
    if ext in ('.jpg', '.jpeg'):
        reencode_hint = 'JPEG — double compression yoxlaması ELA/stego ilə'

    file_info = (img_meta or {}).get('file_info') or {}
    digest = _sha256(filepath)
    return {
        'sha256': digest,
        'format': ext.lstrip('.').upper() or 'UNKNOWN',
        'size_bytes': file_info.get('size_bytes') or os.path.getsize(filepath),
        'integrity': 'computed_hash',
        'reencoding_artifacts': reencode_hint,
        'summary_az': f'SHA-256: {digest[:16]}...',
    }


def _extract_thumbnail(filepath: str) -> Dict[str, Any]:
    try:
        from extractors.image_extractor import ImageExtractor
        out_dir = os.path.dirname(filepath)
        thumb = ImageExtractor().extract_thumbnail(filepath, out_dir)
        if thumb:
            from utils.artifact_utils import path_to_filename
            return {'found': True, 'filename': path_to_filename(thumb), 'path': thumb}
    except Exception as e:
        return {'found': False, 'error': str(e)}
    return {'found': False}


def analyze_forensic_scientific(
    filepath: str,
    img_meta: Optional[Dict] = None,
    forensics_partial: Optional[Dict] = None,
    vision_ml: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Tam elmi/kriminalistika analizi."""
    img = _read_image(filepath)
    if img is None:
        return {'status': 'error', 'error': 'Şəkil oxunmadı'}

    if img_meta is None:
        try:
            from extractors.image_extractor import ImageExtractor
            img_meta = ImageExtractor().extract(filepath)
        except Exception:
            img_meta = {}

    fp = forensics_partial or {}
    ela = fp.get('ela') or {}
    c2pa = fp.get('c2pa') or {}
    stego = fp.get('steganography') or {}

    if vision_ml is None:
        try:
            from analyzers.vision_ml_analyzer import analyze_vision_ml
            vision_ml = analyze_vision_ml(filepath)
        except Exception as e:
            print(f'  [!] Vision ML (forensics): {e}', file=sys.stderr)
            vision_ml = {}

    internal = None
    try:
        from analyzers.image_internal_analyzer import analyze_image_internal_structure
        internal = analyze_image_internal_structure(filepath)
    except Exception:
        pass

    lighting = _safe_call(_analyze_lighting, img, default={'summary_az': 'Işıq analizi uğursuz'})
    authenticity = _detect_ai_synthetic(
        img, c2pa, ela.get('manipulation_score', 0), stego.get('stego_score', 0),
    )
    manipulation = _safe_call(_analyze_manipulation, img, ela, default={'summary_az': '—', 'is_manipulated': False})
    distance = _estimate_distance_from_file(filepath, img, img_meta)
    shadows = _safe_call(_analyze_shadows, img, lighting, default={'summary_az': '—'})
    noise = _safe_call(_analyze_noise_sensor, img, img_meta, default={'summary_az': '—'})
    lens = _safe_call(_analyze_lens, img, default={'summary_az': '—'})
    contextual = _infer_contextual(img, img_meta, vision_ml)
    temporal = _infer_temporal(img_meta, vision_ml)
    social = _infer_social(vision_ml, img_meta)
    security = _security_integrity(filepath, img_meta, internal)
    thumbnail = _extract_thumbnail(filepath)

    return {
        'status': 'success',
        'authenticity': authenticity,
        'manipulation': manipulation,
        'lighting': lighting,
        'distance': distance,
        'shadows': shadows,
        'noise_analysis': noise,
        'lens_analysis': lens,
        'contextual_inference': contextual,
        'temporal_inference': temporal,
        'social_inference': social,
        'security': security,
        'hidden': {
            'steganography': stego,
            'embedded': (internal or {}).get('embedded_findings', []),
            'jpeg_thumbnail': thumbnail,
        },
        'prnu': fp.get('prnu'),
        'c2pa': c2pa,
        'software_traces': fp.get('software_traces'),
    }


def build_unified_forensic_json(
    filepath: str,
    img_meta: Optional[Dict],
    forensics: Dict[str, Any],
    scientific: Dict[str, Any],
    vision_ml: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Nümunə JSON strukturuna uyğun vahid hesabat."""
    fi = (img_meta or {}).get('file_info') or {}
    exif = (img_meta or {}).get('exif') or {}
    loc = (img_meta or {}).get('location')
    camera = exif.get('camera') or {}
    settings = exif.get('settings') or {}
    image_info = exif.get('image') or {}
    vm = vision_ml or {}
    sci = scientific or {}
    auth = sci.get('authenticity') or {}
    manip = sci.get('manipulation') or {}
    ctx = sci.get('contextual_inference') or {}

    return {
        'image_metadata': {
            'filename': os.path.basename(filepath),
            'size_bytes': fi.get('size_bytes') or os.path.getsize(filepath),
            'dimensions': {
                'width': image_info.get('width'),
                'height': image_info.get('height'),
            },
            'format': image_info.get('format') or os.path.splitext(filepath)[1].lstrip('.').upper(),
            'file_hash_sha256': (sci.get('security') or {}).get('sha256'),
        },
        'exif': {
            'device': {
                'make': camera.get('make'),
                'model': camera.get('model'),
                'software': camera.get('software'),
            },
            'photo': {
                'aperture': settings.get('aperture'),
                'exposure_time': settings.get('shutter_speed'),
                'iso': settings.get('iso'),
                'focal_length_mm': settings.get('focal_length'),
            },
            'gps': loc,
            'timestamp': exif.get('datetime'),
        },
        'ai_vision': {
            'faces_detected': (vm.get('people') or {}).get('person_count', 0),
            'emotions': list((vm.get('people') or {}).get('emotion_summary', {}).keys()),
            'objects_detected': list(((vm.get('objects_coco') or {}).get('summary') or {}).get('class_list', [])),
            'text_detected_ocr': [
                w.get('word') for w in ((vm.get('ocr') or {}).get('words') or [])[:20]
            ],
            'place_type': (vm.get('scene') or {}).get('primary', {}).get('place_en'),
            'is_deepfake_probability': auth.get('is_ai_generated_probability'),
            'is_manipulated': manip.get('is_manipulated', False),
        },
        'forensics': {
            'image_originality': (
                'likely_ai' if auth.get('is_ai_generated_probability', 0) > 0.6
                else 'likely_original' if auth.get('is_ai_generated_probability', 0) < 0.35
                else 'uncertain'
            ),
            'steganography_detected': (forensics.get('steganography') or {}).get('suspicious', False),
            'last_edit_tool': (
                (forensics.get('software_traces') or {}).get('primary_application')
                or camera.get('software')
            ),
            'gps_accuracy': 'high (GPS direct)' if loc and loc.get('latitude') else 'none',
            'manipulation_types': manip.get('types_detected', []),
            'ela_score': (forensics.get('ela') or {}).get('manipulation_score'),
        },
        'inferred': {
            'estimated_season': ctx.get('estimated_season'),
            'estimated_season_az': ctx.get('estimated_season_az'),
            'estimated_time_of_day': ctx.get('estimated_time_of_day'),
            'estimated_time_of_day_az': ctx.get('estimated_time_of_day_az'),
            'sky_weather_az': ctx.get('sky_weather_az'),
            'culture_style_az': ctx.get('culture_style_az'),
            'social_context': (sci.get('social_inference') or {}).get('relationship_hint_az'),
            'estimated_year_range': (sci.get('temporal_inference') or {}).get('estimated_year_range'),
            'location_description': loc.get('address', {}).get('display') if isinstance(loc, dict) else None,
        },
        'scientific_detail': sci,
    }


def enrich_forensics_report(filepath: str, forensics_result: Dict[str, Any]) -> Dict[str, Any]:
    """Mövcud forensics nəticəsini elmi modul + vahid JSON ilə zənginləşdir."""
    print('  [i] Elmi/kontekstual kriminalistika analizi...', file=sys.stderr)
    img_meta = None
    try:
        from extractors.image_extractor import ImageExtractor
        img_meta = ImageExtractor().extract(filepath)
    except Exception:
        pass

    vision_ml = None
    try:
        from analyzers.vision_ml_analyzer import analyze_vision_ml
        vision_ml = analyze_vision_ml(filepath)
    except Exception as e:
        print(f'  [!] Vision (forensics enrich): {e}', file=sys.stderr)

    scientific = analyze_forensic_scientific(
        filepath, img_meta=img_meta, forensics_partial=forensics_result, vision_ml=vision_ml,
    )
    forensics_result['scientific'] = scientific
    forensics_result['unified_report'] = build_unified_forensic_json(
        filepath, img_meta, forensics_result, scientific, vision_ml,
    )
    forensics_result['vision_ml'] = vision_ml

    ur = forensics_result['unified_report']
    summary = forensics_result.get('summary') or {}
    auth_p = (scientific.get('authenticity') or {}).get('is_ai_generated_probability', 0)
    summary['ai_generated_hint'] = auth_p > 0.55
    summary['ai_probability'] = auth_p
    summary['is_manipulated'] = (scientific.get('manipulation') or {}).get('is_manipulated', False)
    summary['estimated_season'] = ur.get('inferred', {}).get('estimated_season_az')
    summary['estimated_time'] = ur.get('inferred', {}).get('estimated_time_of_day_az')
    forensics_result['summary'] = summary
    return forensics_result
