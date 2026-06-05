"""
Üz aşkarlama və anonimləşdirmə (precision-first).

YuNet + MediaPipe konsensusu; demografiya yoxdur.
"""

import os
import sys
import urllib.request

import cv2
import numpy as np

from utils.artifact_utils import path_to_filename

YUNET_MODEL_NAME = 'face_detection_yunet_2023mar.onnx'
YUNET_URLS = [
    'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/'
    'face_detection_yunet/face_detection_yunet_2023mar.onnx',
    'https://github.com/opencv/opencv_zoo/raw/main/models/'
    'face_detection_yunet/face_detection_yunet_2023mar.onnx',
]

MAX_FACES = 20
MIN_IMAGE_SIDE = 64
MIN_AREA_RATIO = 0.0025
MIN_AREA_HAAR = 0.0035
MIN_AREA_SINGLE = 0.004
MIN_FACE_PX = 40
MIN_ASPECT = 0.55
MAX_ASPECT = 1.75
IOU_CLUSTER = 0.32
CONF_MIN = 0.72
YUNET_SCORE_THRESHOLD = 0.6

_yunet_detector = None


def _models_dir():
    return os.path.join(os.path.dirname(__file__), '..', 'models')


def _ensure_yunet_model():
    model_dir = _models_dir()
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, YUNET_MODEL_NAME)
    if not os.path.exists(model_path) or os.path.getsize(model_path) < 10000:
        print('  [i] YuNet üz modeli yüklənir...', file=sys.stderr)
        last_err = None
        for url in YUNET_URLS:
            try:
                urllib.request.urlretrieve(url, model_path)
                if os.path.getsize(model_path) >= 10000:
                    break
            except Exception as e:
                last_err = e
        if not os.path.exists(model_path) or os.path.getsize(model_path) < 10000:
            raise RuntimeError(f'YuNet modeli yüklənmədi: {last_err}')
    return model_path


def _get_yunet():
    global _yunet_detector
    if _yunet_detector is None:
        model_path = _ensure_yunet_model()
        _yunet_detector = cv2.FaceDetectorYN.create(
            model_path,
            '',
            (320, 320),
            score_threshold=YUNET_SCORE_THRESHOLD,
            nms_threshold=0.3,
            top_k=5000,
        )
    return _yunet_detector


def _bbox_iou(a, b):
    ax, ay, aw, ah = a['x'], a['y'], a['w'], a['h']
    bx, by, bw, bh = b['x'], b['y'], b['w'], b['h']
    x1 = max(ax, bx)
    y1 = max(ay, by)
    x2 = min(ax + aw, bx + bw)
    y2 = min(ay + ah, by + bh)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def _clamp_bbox(x, y, w, h, img_w, img_h):
    x = max(0, int(x))
    y = max(0, int(y))
    w = max(1, min(int(w), img_w - x))
    h = max(1, min(int(h), img_h - y))
    return x, y, w, h


def _detect_yunet(img, img_w, img_h):
    detector = _get_yunet()
    detector.setInputSize((img_w, img_h))
    _, faces = detector.detect(img)
    results = []
    if faces is None:
        return results
    img_area = max(img_w * img_h, 1)
    for row in faces:
        if len(row) < 15:
            continue
        x, y, w, h = float(row[0]), float(row[1]), float(row[2]), float(row[3])
        score = float(row[14])
        x, y, w, h = _clamp_bbox(x, y, w, h, img_w, img_h)
        landmarks = {
            'right_eye': [round(float(row[4]), 1), round(float(row[5]), 1)],
            'left_eye': [round(float(row[6]), 1), round(float(row[7]), 1)],
            'nose': [round(float(row[8]), 1), round(float(row[9]), 1)],
            'mouth_right': [round(float(row[10]), 1), round(float(row[11]), 1)],
            'mouth_left': [round(float(row[12]), 1), round(float(row[13]), 1)],
        }
        results.append({
            'source': 'yunet',
            'bbox': {'x': x, 'y': y, 'w': w, 'h': h},
            'confidence': round(score, 4),
            'area_percent': round((w * h) / img_area * 100, 3),
            'landmarks': landmarks,
        })
    return results


MP_FACE_MODEL_FULL = 'blaze_face_full_range.tflite'
MP_FACE_MODEL_SHORT = 'blaze_face_short_range.tflite'
MP_FACE_URLS = {
    MP_FACE_MODEL_FULL: (
        'https://storage.googleapis.com/mediapipe-models/face_detector/'
        'blaze_face_full_range/float16/1/blaze_face_full_range.tflite'
    ),
    MP_FACE_MODEL_SHORT: (
        'https://storage.googleapis.com/mediapipe-models/face_detector/'
        'blaze_face_short_range/float16/1/blaze_face_short_range.tflite'
    ),
}

_mp_detectors = {}


def _ensure_mediapipe_model(model_name):
    model_dir = _models_dir()
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, model_name)
    if not os.path.exists(model_path) or os.path.getsize(model_path) < 10000:
        print(f'  [i] MediaPipe modeli yüklənir: {model_name}...', file=sys.stderr)
        urllib.request.urlretrieve(MP_FACE_URLS[model_name], model_path)
    return model_path


def _get_mediapipe_detector(model_name):
    if model_name not in _mp_detectors:
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        model_path = _ensure_mediapipe_model(model_name)
        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceDetectorOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            min_detection_confidence=0.5,
        )
        _mp_detectors[model_name] = vision.FaceDetector.create_from_options(options)
    return _mp_detectors[model_name]


def _detect_mediapipe_model(img_rgb, img_w, img_h, model_name, source_tag):
    results = []
    img_area = max(img_w * img_h, 1)
    try:
        import mediapipe as mp

        detector = _get_mediapipe_detector(model_name)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
        det = detector.detect(mp_image)
        if not det.detections:
            return results
        for d in det.detections:
            score = float(d.categories[0].score) if d.categories else 0.0
            box = d.bounding_box
            x, y, w, h = _clamp_bbox(
                int(box.origin_x), int(box.origin_y),
                int(box.width), int(box.height),
                img_w, img_h,
            )
            results.append({
                'source': source_tag,
                'bbox': {'x': x, 'y': y, 'w': w, 'h': h},
                'confidence': round(score, 4),
                'area_percent': round((w * h) / img_area * 100, 3),
                'landmarks': None,
            })
    except Exception:
        pass
    return results


def _detect_mediapipe(img_rgb, img_w, img_h):
    try:
        import mediapipe as mp  # noqa: F401
    except ImportError:
        return [], 'mediapipe quraşdırılmayıb'

    results = []
    results.extend(_detect_mediapipe_model(
        img_rgb, img_w, img_h, MP_FACE_MODEL_FULL, 'mediapipe_full',
    ))
    results.extend(_detect_mediapipe_model(
        img_rgb, img_w, img_h, MP_FACE_MODEL_SHORT, 'mediapipe_short',
    ))
    return results, None


def _detect_haar(img, img_w, img_h):
    """Frontal + profil Haar — YuNet/MediaPipe çatışmayanda əlavə tutma."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img_area = max(img_w * img_h, 1)
    min_side = max(MIN_FACE_PX, min(img_w, img_h) // 14)
    results = []

    cascades = (
        ('haar_frontal', 'haarcascade_frontalface_default.xml', 1.08, 5),
        ('haar_profile', 'haarcascade_profileface.xml', 1.12, 5),
    )
    for source, filename, scale, neighbors in cascades:
        path = cv2.data.haarcascades + filename
        cascade = cv2.CascadeClassifier(path)
        if cascade.empty():
            continue
        found = cascade.detectMultiScale(
            gray,
            scaleFactor=scale,
            minNeighbors=neighbors,
            minSize=(min_side, min_side),
        )
        for (x, y, w, h) in found:
            x, y, w, h = _clamp_bbox(x, y, w, h, img_w, img_h)
            area_pct = (w * h) / img_area * 100
            if area_pct < MIN_AREA_HAAR * 100:
                continue
            if not _aspect_ok(w, h):
                continue
            results.append({
                'source': source,
                'bbox': {'x': x, 'y': y, 'w': w, 'h': h},
                'confidence': 0.78 if source == 'haar_frontal' else 0.74,
                'area_percent': round(area_pct, 3),
                'landmarks': None,
            })
    return results


def _aspect_ok(w, h):
    if h <= 0:
        return False
    ratio = w / h
    return MIN_ASPECT <= ratio <= MAX_ASPECT


def _landmarks_valid(landmarks, bbox):
    """YuNet landmark-ları üzə uyğundursa True (kiçik FP-ləri kəsir)."""
    if not landmarks or not bbox:
        return False
    try:
        re = landmarks.get('right_eye')
        le = landmarks.get('left_eye')
        nose = landmarks.get('nose')
        if not re or not le or not nose:
            return False
        x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
        if w < 20 or h < 20:
            return False

        def _inside(px, py):
            return x <= px <= x + w and y <= py <= y + h

        if not all(_inside(p[0], p[1]) for p in (re, le, nose)):
            return False
        eye_dist = ((re[0] - le[0]) ** 2 + (re[1] - le[1]) ** 2) ** 0.5
        if eye_dist < w * 0.15 or eye_dist > w * 0.85:
            return False
        return True
    except (TypeError, KeyError, IndexError):
        return False


def _should_merge_into_cluster(cand, cluster):
    """Kiçik YuNet FP-lərini real üz klasterlərinə zorla birləşdirmir."""
    iou = _bbox_iou(cand['bbox'], cluster['bbox'])
    if iou < IOU_CLUSTER:
        return False
    cluster_max_area = max(m['area_percent'] for m in cluster['members'])
    if cand['source'] == 'yunet' and cand['area_percent'] < cluster_max_area * 0.4:
        if not _landmarks_valid(cand.get('landmarks'), cand['bbox']):
            return False
    if cluster['members'][0]['source'] == 'yunet' and cluster_max_area < cand['area_percent'] * 0.4:
        if not _landmarks_valid(cluster['members'][0].get('landmarks'), cluster['bbox']):
            return False
    return True


def _pick_cluster_bbox(members):
    """Ən etibarlı bbox — kiçik yüksək-skor YuNet FP deyil, real üz ölçüsü."""
    haar_mp = [
        m for m in members
        if m['source'].startswith('haar') or m['source'].startswith('mediapipe')
    ]
    pool = haar_mp if haar_mp else members
    best = max(pool, key=lambda m: m['area_percent'] * m['confidence'])
    return dict(best['bbox'])


def _cluster_candidates(candidates):
    """IoU ilə detektor nəticələrini klasterləşdir."""
    sorted_cands = sorted(
        candidates,
        key=lambda c: (-c['area_percent'], -c['confidence']),
    )
    clusters = []
    for cand in sorted_cands:
        placed = False
        for cluster in clusters:
            if _should_merge_into_cluster(cand, cluster):
                cluster['members'].append(cand)
                cluster['bbox'] = _pick_cluster_bbox(cluster['members'])
                placed = True
                break
        if not placed:
            clusters.append({'members': [cand], 'bbox': dict(cand['bbox'])})
    return clusters


def _cluster_sources(members):
    return sorted({m['source'] for m in members})


def _score_cluster(cluster):
    """Klaster üçün qəbul qərarı və birləşmiş metadata."""
    members = cluster['members']
    sources = _cluster_sources(members)
    n_sources = len(sources)

    bbox = _pick_cluster_bbox(members)
    w, h = bbox['w'], bbox['h']
    area_pct = max(m['area_percent'] for m in members)
    confs = [m['confidence'] for m in members]
    avg_conf = sum(confs) / len(confs)
    landmarks = None
    for m in members:
        if m.get('landmarks'):
            landmarks = m['landmarks']
            break

    yunet_conf = next((m['confidence'] for m in members if m['source'] == 'yunet'), None)
    mp_conf = max(
        (m['confidence'] for m in members if m['source'].startswith('mediapipe')),
        default=None,
    )
    haar_conf = max(
        (m['confidence'] for m in members if m['source'].startswith('haar')),
        default=None,
    )

    if w < MIN_FACE_PX or h < MIN_FACE_PX:
        return None
    if not _aspect_ok(w, h):
        return None

    # Çox kiçik yeganə YuNet FP (ekran/loqotip)
    if (
        n_sources == 1
        and sources[0] == 'yunet'
        and area_pct < MIN_AREA_SINGLE * 100
        and not _landmarks_valid(landmarks, bbox)
    ):
        return None

    accept = False
    detectors_label = '+'.join(sources)

    if n_sources >= 2 and area_pct >= MIN_AREA_RATIO * 100 and avg_conf >= CONF_MIN:
        accept = True
    elif any(s.startswith('mediapipe') for s in sources) and area_pct >= MIN_AREA_SINGLE * 100:
        mp_only = [m for m in members if m['source'].startswith('mediapipe')]
        if max(m['confidence'] for m in mp_only) >= 0.55:
            accept = True
    elif 'yunet' in sources and yunet_conf and yunet_conf >= 0.82:
        if area_pct >= MIN_AREA_SINGLE * 100 or _landmarks_valid(landmarks, bbox):
            accept = True
    elif any(s.startswith('haar') for s in sources) and area_pct >= MIN_AREA_HAAR * 100:
        if n_sources >= 2 or area_pct >= MIN_AREA_SINGLE * 100 or w >= 48:
            accept = True
            avg_conf = max(avg_conf, haar_conf or 0.76)

    if not accept:
        return None

    return {
        'detectors': detectors_label,
        'confidence': round(min(0.99, avg_conf), 4),
        'bbox': bbox,
        'area_percent': round(area_pct, 3),
        'landmarks': landmarks,
        'yunet_confidence': yunet_conf,
        'mediapipe_confidence': mp_conf,
        'source_count': n_sources,
    }


def _fuse_detections(yunet_faces, mp_faces, haar_faces, img_area):
    """Çox detektorlu klaster füsionu — real üzlər üçün daha yüksək tutma."""
    all_cands = list(yunet_faces) + list(mp_faces) + list(haar_faces)
    if not all_cands:
        return []

    clusters = _cluster_candidates(all_cands)
    accepted = []
    for cluster in clusters:
        scored = _score_cluster(cluster)
        if scored and scored['confidence'] >= CONF_MIN:
            accepted.append(scored)

    accepted.sort(key=lambda x: (-x.get('source_count', 1), -x['confidence']))

    # Landşaft FP: hamısı minikdirsə və 4+ klaster — at
    if len(accepted) >= 4 and all(f['area_percent'] < 0.35 for f in accepted):
        accepted = [f for f in accepted if f['area_percent'] >= 0.35]

    deduped = []
    for cand in accepted:
        if any(_bbox_iou(cand['bbox'], d['bbox']) >= 0.45 for d in deduped):
            continue
        deduped.append(cand)
        if len(deduped) >= MAX_FACES:
            break

    return deduped


def _bbox_to_circle(bbox, padding=1.08):
    """BBox-dan üz dairəsi (mərkəz + radius)."""
    x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
    cx = x + w / 2
    cy = y + h / 2
    radius = max(w, h) / 2 * padding
    return {
        'cx': round(cx, 1),
        'cy': round(cy, 1),
        'radius': round(radius, 1),
    }


def _detector_label_az(detectors_str):
    labels = []
    d = detectors_str or ''
    if 'yunet' in d:
        labels.append('YuNet (dərin öyrənmə)')
    if 'mediapipe' in d:
        labels.append('MediaPipe BlazeFace')
    if 'haar_frontal' in d:
        labels.append('Haar frontal')
    if 'haar_profile' in d:
        labels.append('Haar profil')
    return ', '.join(labels) if labels else detectors_str


def _enrich_face(face, img_w, img_h):
    """UI və hesabat üçün üz haqqında əlavə metadata."""
    b = face['bbox']
    face['circle'] = _bbox_to_circle(b)
    cx = face['circle']['cx']
    cy = face['circle']['cy']

    conf_pct = round((face.get('confidence') or 0) * 100)
    if conf_pct >= 88 or face.get('source_count', 1) >= 2:
        reliability = 'yüksək'
    elif conf_pct >= 74:
        reliability = 'orta'
    else:
        reliability = 'aşağı'

    det = face.get('detectors', '')
    if 'haar_profile' in det and 'haar_frontal' not in det.split('+'):
        orientation = 'profil görünüşü'
    elif 'haar_frontal' in det:
        orientation = 'frontal (üzə qarşı)'
    elif 'yunet' in det:
        orientation = 'frontal (YuNet)'
    else:
        orientation = 'müəyyən edilməyib'

    rel_x = cx / max(img_w, 1)
    if rel_x < 0.33:
        position = 'şəklin sol tərəfi'
    elif rel_x > 0.66:
        position = 'şəklin sağ tərəfi'
    else:
        position = 'şəklin mərkəzi'

    vert = cy / max(img_h, 1)
    if vert < 0.33:
        position += ', yuxarı hissə'
    elif vert > 0.66:
        position += ', aşağı hissə'

    face['info'] = {
        'reliability': reliability,
        'confidence_percent': conf_pct,
        'orientation': orientation,
        'position': position,
        'size_pixels': f"{b['w']}×{b['h']} px",
        'area_percent': face.get('area_percent'),
        'detectors_label': _detector_label_az(det),
        'multi_detector': (face.get('source_count') or 1) >= 2,
        'center': {'x': cx, 'y': cy},
    }
    face['center'] = {'x': cx, 'y': cy}
    return face


def _finalize_faces(deduped, img_w, img_h):
    for i, face in enumerate(deduped):
        face['id'] = i + 1
        _enrich_face(face, img_w, img_h)
    return deduped


def _draw_faces_preview(filepath, faces):
    """Üzləri dairə ilə işarələnmiş önizləmə şəkli yaradır."""
    if not faces:
        return None
    img = cv2.imread(filepath)
    if img is None:
        return None

    out = img.copy()
    for f in faces:
        c = f.get('circle') or _bbox_to_circle(f['bbox'])
        cx, cy, r = int(c['cx']), int(c['cy']), int(c['radius'])
        cv2.circle(out, (cx, cy), r, (238, 211, 34), 3, lineType=cv2.LINE_AA)
        cv2.circle(out, (cx, cy), 3, (238, 211, 34), -1, lineType=cv2.LINE_AA)
        label = f"#{f['id']}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        tx = max(0, cx - tw // 2)
        ty = max(th + 4, cy - r - 6)
        cv2.rectangle(out, (tx - 2, ty - th - 4), (tx + tw + 2, ty + 2), (15, 23, 42), -1)
        cv2.putText(
            out, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
            (238, 211, 34), 2, cv2.LINE_AA,
        )

    out_dir = os.path.dirname(os.path.abspath(filepath))
    base = os.path.basename(filepath)
    name, _ext = os.path.splitext(base)
    out_path = os.path.join(out_dir, f'faces_{name}.jpg')
    cv2.imwrite(out_path, out, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    return path_to_filename(out_path)


def _extract_file_metadata_hints(filepath):
    hints = []
    try:
        from extractors.image_extractor import ImageExtractor
        meta = ImageExtractor().extract(filepath)
        desc = meta.get('description') or {}
        for key in ('XPSubject', 'Subject', 'ImageDescription', 'XPTitle', 'XPKeywords'):
            val = desc.get(key)
            if val and str(val).strip():
                hints.append({'field': key, 'value': str(val).strip()[:300]})
        raw = meta.get('raw_tags') or {}
        for tag, val in raw.items():
            tl = tag.lower()
            if any(k in tl for k in ('subject', 'person', 'creator', 'artist')):
                sv = str(val).strip()
                if sv and len(sv) < 300:
                    hints.append({'field': tag, 'value': sv})
    except Exception as e:
        hints.append({'field': '_error', 'value': str(e)})
    return hints


def detect_faces(filepath):
    """Şəkildə üzləri precision-first rejimində aşkar edir."""
    if not os.path.isfile(filepath):
        return {
            'status': 'error',
            'error': 'Fayl tapılmadı',
            'faces': [],
            'total_faces': 0,
            'strict_mode': True,
        }

    img = cv2.imread(filepath)
    if img is None:
        return {
            'status': 'error',
            'error': 'Şəkil oxunmadı',
            'faces': [],
            'total_faces': 0,
            'strict_mode': True,
        }

    img_h, img_w = img.shape[:2]
    if img_w < MIN_IMAGE_SIDE or img_h < MIN_IMAGE_SIDE:
        return {
            'status': 'error',
            'error': f'Şəkil çox kiçikdir (min {MIN_IMAGE_SIDE}px)',
            'faces': [],
            'total_faces': 0,
            'strict_mode': True,
            'image_size': {'width': img_w, 'height': img_h},
        }

    img_area = img_w * img_h
    yunet_raw = _detect_yunet(img, img_w, img_h)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mp_raw, mp_err = _detect_mediapipe(img_rgb, img_w, img_h)
    haar_raw = _detect_haar(img, img_w, img_h)

    faces = _finalize_faces(
        _fuse_detections(yunet_raw, mp_raw, haar_raw, img_area),
        img_w, img_h,
    )

    preview_filename = None
    if faces:
        preview_filename = _draw_faces_preview(filepath, faces)

    note = None
    if not faces:
        total_raw = len(yunet_raw) + len(mp_raw) + len(haar_raw)
        if total_raw == 0:
            note = (
                'Heç bir detektor üz tapmadı. Şəkil keyfiyyəti, bucaq və ya '
                'üzün çox kiçik/örtülü olması səbəb ola bilər.'
            )
        else:
            note = (
                'Detektorlar region tapdı, lakin etibarlı üz kimi təsdiqlənmədi. '
                'Şübhəli və ya çox kiçik regionlar süzülür.'
            )

    return {
        'status': 'success',
        'strict_mode': True,
        'image_size': {'width': img_w, 'height': img_h},
        'total_faces': len(faces),
        'faces': faces,
        'preview_filename': preview_filename,
        'file_metadata_hints': _extract_file_metadata_hints(filepath),
        'detector_versions': {
            'yunet': YUNET_MODEL_NAME,
            'mediapipe': f'{MP_FACE_MODEL_FULL}+{MP_FACE_MODEL_SHORT}',
            'haar': 'frontal+profile',
        },
        'raw_counts': {
            'yunet_candidates': len(yunet_raw),
            'mediapipe_candidates': len(mp_raw),
            'haar_candidates': len(haar_raw),
        },
        'note': note,
        'warnings': [mp_err] if mp_err else [],
    }


def _padded_region(bbox, img_w, img_h, padding_ratio=0.18):
    x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
    pad_w = int(w * padding_ratio)
    pad_h = int(h * padding_ratio)
    x1 = max(0, x - pad_w)
    y1 = max(0, y - pad_h)
    x2 = min(img_w, x + w + pad_w)
    y2 = min(img_h, y + h + pad_h)
    return x1, y1, x2, y2


def anonymize_faces(filepath, faces, method='blur', strength=3, padding=0.18):
    """Üz regionlarını blur və ya pixelate edir; yeni fayl yaradır."""
    if not faces:
        return {'status': 'skipped', 'message': 'Anonimləşdirmə üçün üz yoxdur'}

    img = cv2.imread(filepath)
    if img is None:
        return {'status': 'error', 'message': 'Şəkil oxunmadı'}

    img_h, img_w = img.shape[:2]
    strength = max(1, min(5, int(strength)))
    padding = max(0.05, min(0.35, float(padding)))

    out = img.copy()
    method = (method or 'blur').lower()

    for face in faces:
        x1, y1, x2, y2 = _padded_region(face['bbox'], img_w, img_h, padding)
        roi = out[y1:y2, x1:x2]
        if roi.size == 0:
            continue
        rh, rw = roi.shape[:2]
        if method == 'pixelate':
            block = max(8, min(32, 8 + strength * 4))
            small = cv2.resize(
                roi,
                (max(1, rw // block), max(1, rh // block)),
                interpolation=cv2.INTER_LINEAR,
            )
            out[y1:y2, x1:x2] = cv2.resize(
                small, (rw, rh), interpolation=cv2.INTER_NEAREST
            )
        else:
            k = strength * 6 + 1
            if k % 2 == 0:
                k += 1
            blurred = cv2.GaussianBlur(roi, (k, k), 0)
            out[y1:y2, x1:x2] = blurred

    out_dir = os.path.dirname(os.path.abspath(filepath))
    base = os.path.basename(filepath)
    name, _ext = os.path.splitext(base)
    out_path = os.path.join(out_dir, f'anon_{name}.jpg')
    cv2.imwrite(out_path, out, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

    return {
        'status': 'success',
        'method': method,
        'strength': strength,
        'padding': padding,
        'faces_anonymized': len(faces),
        'anonymized_path': out_path,
        'anonymized_filename': path_to_filename(out_path),
    }


def analyze_face_privacy(
    filepath,
    anonymize=False,
    method='blur',
    strength=3,
    padding=0.18,
):
    """Üz skanı + istəyə bağlı anonimləşdirmə."""
    detection = detect_faces(filepath)
    result = {
        'original_filename': path_to_filename(filepath),
        'face_privacy': detection,
        'artifacts': [],
    }

    if detection.get('status') != 'success':
        result['face_privacy']['total_faces'] = 0
        result['face_privacy'].setdefault('faces', [])
        return result

    preview_fn = detection.get('preview_filename')
    if preview_fn:
        result['artifacts'].append(preview_fn)

    if anonymize and detection.get('faces'):
        anon = anonymize_faces(
            filepath,
            detection['faces'],
            method=method,
            strength=strength,
            padding=padding,
        )
        result['anonymization'] = anon
        fn = anon.get('anonymized_filename')
        if fn:
            result['artifacts'].append(fn)

    return result
