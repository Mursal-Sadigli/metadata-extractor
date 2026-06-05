"""İki şəkil müqayisəsi — EXIF, GPS, pHash, PRNU."""

import math
import sys

from extractors.image_extractor import ImageExtractor
from analyzers.prnu_analyzer import compare_prnu


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _visual_similarity(path_a, path_b):
    try:
        import imagehash
        from PIL import Image
        h1 = imagehash.phash(Image.open(path_a))
        h2 = imagehash.phash(Image.open(path_b))
        diff = h1 - h2
        pct = max(0, 100 - diff * 100 / 64)
        return round(pct, 1), diff
    except Exception as e:
        print(f'  [!] pHash: {e}', file=sys.stderr)
        return None, None


def compare_images(filepath_a, filepath_b):
    ext = ImageExtractor()
    ra = ext.extract(filepath_a)
    rb = ext.extract(filepath_b)

    signals = []
    overall_score = 0
    weights = 0

    cam_a = (ra.get('exif') or {}).get('camera') or {}
    cam_b = (rb.get('exif') or {}).get('camera') or {}
    if cam_a and cam_b:
        same_make = cam_a.get('make') == cam_b.get('make') and cam_a.get('make')
        same_model = cam_a.get('model') == cam_b.get('model') and cam_a.get('model')
        if same_make and same_model:
            signals.append({'type': 'exif_camera', 'match': True, 'detail': f"{cam_a.get('make')} {cam_a.get('model')}"})
            overall_score += 25
        else:
            signals.append({'type': 'exif_camera', 'match': False, 'detail': 'Fərqli kamera metadata'})
        weights += 25

    loc_a = ra.get('location')
    loc_b = rb.get('location')
    if loc_a and loc_b and loc_a.get('latitude') is not None:
        dist = _haversine_m(
            loc_a['latitude'], loc_a['longitude'],
            loc_b['latitude'], loc_b['longitude'],
        )
        same_place = dist < 50
        signals.append({
            'type': 'gps',
            'match': same_place,
            'distance_m': round(dist, 1),
            'detail': f'Məsafə: {dist:.0f} m',
        })
        overall_score += 30 if same_place else 5
        weights += 30

    vis_pct, hash_diff = _visual_similarity(filepath_a, filepath_b)
    if vis_pct is not None:
        signals.append({
            'type': 'visual_phash',
            'match': vis_pct >= 85,
            'similarity_percent': vis_pct,
            'hash_difference': int(hash_diff) if hash_diff is not None else None,
        })
        overall_score += int(vis_pct * 0.25)
        weights += 25

    prnu = compare_prnu(filepath_a, filepath_b)
    signals.append({
        'type': 'prnu',
        'match': prnu.get('same_camera_likely', False),
        'similarity': prnu.get('similarity'),
        'confidence': prnu.get('confidence'),
        'detail': prnu.get('note'),
    })
    if prnu.get('same_camera_likely'):
        overall_score += 20
    weights += 20

    confidence_pct = round(100 * overall_score / weights, 1) if weights else 0

    same_camera = any(s['type'] == 'prnu' and s.get('match') for s in signals)
    same_place = any(s['type'] == 'gps' and s.get('match') for s in signals)
    same_scene = vis_pct is not None and vis_pct >= 90

    return {
        'file_a': ra.get('file_info'),
        'file_b': rb.get('file_info'),
        'signals': signals,
        'summary': {
            'confidence_percent': confidence_pct,
            'same_camera_likely': same_camera,
            'same_location_likely': same_place,
            'same_scene_likely': same_scene,
            'verdict': _verdict(same_camera, same_place, same_scene, confidence_pct),
        },
        'prnu': prnu,
    }


def _verdict(same_camera, same_place, same_scene, conf):
    if same_place and (same_camera or same_scene):
        return 'Yüksək ehtimalla eyni yer və/və ya eyni cihaz'
    if same_scene:
        return 'Vizual olaraq çox oxşar (eyni səhnə ola bilər)'
    if same_camera:
        return 'Eyni kamera sensor izi (eyni cihaz ehtimalı)'
    if conf < 25:
        return 'Əlaqə zəif və ya fərqli mənbə'
    return 'Qismən oxşarlıq — əlavə sübut lazımdır'
