"""
Kriminalistik şəkil bərpası — AI Super Resolution, deblur, üz və nömrə nişanı ROI.
"""

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

_MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models', 'sr')
_SR_MODELS = {
    'fsrcnn_x2': (
        'https://github.com/opencv/opencv_extra/raw/master/testdata/dnn/FSRCNN_x2.pb',
        'fsrcnn',
        2,
    ),
    'edsr_x4': (
        'https://github.com/Saafke/EDSR_Tensorflow/raw/master/models/EDSR_x4.pb',
        'edsr',
        4,
    ),
}


def _ensure_sr_model(name: str = 'fsrcnn_x2') -> Optional[str]:
    os.makedirs(_MODELS_DIR, exist_ok=True)
    info = _SR_MODELS.get(name)
    if not info:
        return None
    path = os.path.join(_MODELS_DIR, f'{name}.pb')
    if os.path.isfile(path) and os.path.getsize(path) > 10000:
        return path
    try:
        import requests
        print(f'  [i] SR model yüklənir: {name}...', file=sys.stderr)
        r = requests.get(info[0], timeout=120)
        r.raise_for_status()
        with open(path, 'wb') as f:
            f.write(r.content)
        return path
    except Exception as e:
        print(f'  [!] SR model yüklənmədi ({name}): {e}', file=sys.stderr)
        return None


def _dnn_super_resolution(img: np.ndarray, model_name: str = 'fsrcnn_x2') -> Tuple[Optional[np.ndarray], str]:
    path = _ensure_sr_model(model_name)
    if not path:
        return None, ''
    _, algo, scale = _SR_MODELS[model_name]
    try:
        sr = cv2.dnn_superres.DnnSuperResImpl_create()
        sr.readModel(path)
        sr.setModel(algo, scale)
        up = sr.upsample(img)
        return up, f'ai_sr_{algo}_x{scale}'
    except Exception as e:
        print(f'  [!] DNN SR: {e}', file=sys.stderr)
        return None, ''


def _detail_enhance(img: np.ndarray) -> np.ndarray:
    try:
        return cv2.detailEnhance(img, sigma_s=12, sigma_r=0.12)
    except Exception:
        return img


def _deblur_forensic(img: np.ndarray, blur_score: float) -> Tuple[np.ndarray, str]:
    """Bulanıqlığa görə adaptiv deblur / kəskinləşdirmə."""
    out = img.copy()
    if blur_score < 80:
        strength = 1.8
        sigma = 0.8
    elif blur_score < 150:
        strength = 1.4
        sigma = 1.0
    else:
        return _detail_enhance(out), 'detail_enhance'

    blurred = cv2.GaussianBlur(out, (0, 0), sigma)
    sharp = cv2.addWeighted(out, 1.0 + strength, blurred, -strength, 0)
    sharp = _detail_enhance(sharp)
    try:
        sharp = cv2.edgePreservingFilter(sharp, flags=1, sigma_s=40, sigma_r=0.35)
    except Exception:
        pass
    return sharp, 'forensic_deblur'


def _clahe_lab(img: np.ndarray, clip: float = 2.8) -> np.ndarray:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def _detect_faces(img: np.ndarray) -> List[Tuple[int, int, int, int]]:
    boxes: List[Tuple[int, int, int, int]] = []
    try:
        import mediapipe as mp
        mp_face = mp.solutions.face_detection
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        with mp_face.FaceDetection(model_selection=1, min_detection_confidence=0.35) as fd:
            res = fd.process(rgb)
            if res.detections:
                h, w = img.shape[:2]
                for det in res.detections:
                    bb = det.location_data.relative_bounding_box
                    x = int(bb.xmin * w)
                    y = int(bb.ymin * h)
                    bw = int(bb.width * w)
                    bh = int(bb.height * h)
                    boxes.append((x, y, bw, bh))
        if boxes:
            return boxes
    except Exception:
        pass

    try:
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.15, 5, minSize=(24, 24))
        for (x, y, w, h) in faces:
            boxes.append((int(x), int(y), int(w), int(h)))
    except Exception:
        pass
    return boxes


def _detect_plate_candidates(img: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """Nömrə nişanı üçün düzbucaqlı yüksək kontrast regionlar."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    _, th = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(th, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw < 40 or bh < 12:
            continue
        ar = bw / float(bh)
        if 1.8 <= ar <= 6.5 and bw < w * 0.45 and bh < h * 0.25:
            area = bw * bh
            if area < 8000:
                continue
            roi = gray[y:y + bh, x:x + bw]
            if float(np.std(roi)) < 25:
                continue
            candidates.append((x, y, bw, bh))
    candidates.sort(key=lambda b: b[2] * b[3], reverse=True)
    return candidates[:6]


def _enhance_roi(
    img: np.ndarray,
    bbox: Tuple[int, int, int, int],
    scale: float = 2.0,
    sharp_strength: float = 1.6,
) -> np.ndarray:
    x, y, bw, bh = bbox
    h, w = img.shape[:2]
    pad_x = int(bw * 0.15)
    pad_y = int(bh * 0.15)
    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(w, x + bw + pad_x)
    y2 = min(h, y + bh + pad_y)
    roi = img[y1:y2, x1:x2].copy()
    if roi.size == 0:
        return img

    rh, rw = roi.shape[:2]
    up = cv2.resize(roi, (int(rw * scale), int(rh * scale)), interpolation=cv2.INTER_LANCZOS4)
    blurred = cv2.GaussianBlur(up, (0, 0), 0.9)
    up = cv2.addWeighted(up, 1.0 + sharp_strength, blurred, -sharp_strength, 0)
    up = _clahe_lab(up, clip=3.0)
    down = cv2.resize(up, (x2 - x1, y2 - y1), interpolation=cv2.INTER_AREA)
    out = img.copy()
    out[y1:y2, x1:x2] = down
    return out


def apply_forensic_enhancement(
    img: np.ndarray,
    assessment: Dict[str, Any],
) -> Tuple[np.ndarray, List[str], Dict[str, Any]]:
    """
    Kriminalistik bərpa: AI SR + deblur + üz/nömrə ROI netləşdirmə.
    """
    steps: List[str] = []
    targets: List[Dict[str, Any]] = []
    out = img.copy()
    blur = float(assessment.get('blur_score', 200))
    h, w = out.shape[:2]

    if assessment.get('noise_std', 0) > 5:
        try:
            out = cv2.fastNlMeansDenoisingColored(out, None, 7, 7, 7, 21)
            steps.append('denoise')
        except Exception:
            out = cv2.bilateralFilter(out, 9, 75, 75)
            steps.append('bilateral_denoise')

    out, deb_step = _deblur_forensic(out, blur)
    steps.append(deb_step)

    sr_model = 'edsr_x4' if blur < 120 or max(w, h) < 900 else 'fsrcnn_x2'
    sr_img, sr_step = _dnn_super_resolution(out, sr_model)
    if sr_img is not None and sr_img.shape[0] > 0:
        out = sr_img
        steps.append(sr_step)
    elif blur < 160 or max(w, h) < 1100:
        scale = 2.0 if max(w, h) < 700 else 1.5
        out = cv2.resize(out, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
        steps.append(f'lanczos_upscale_{scale}x')

    faces = _detect_faces(out)
    for i, box in enumerate(faces):
        out = _enhance_roi(out, box, scale=2.0, sharp_strength=1.8)
        targets.append({
            'type': 'face',
            'index': i,
            'bbox': {'x': box[0], 'y': box[1], 'w': box[2], 'h': box[3]},
            'enhancement': 'roi_super_resolution_2x',
            'label_az': 'Üz (uzaq/bulanıq) netləşdirmə',
        })
    if faces:
        steps.append(f'face_roi_x{len(faces)}')

    plates = _detect_plate_candidates(out)
    for i, box in enumerate(plates[:3]):
        out = _enhance_roi(out, box, scale=2.5, sharp_strength=2.2)
        targets.append({
            'type': 'license_plate_candidate',
            'index': i,
            'bbox': {'x': box[0], 'y': box[1], 'w': box[2], 'h': box[3]},
            'enhancement': 'roi_super_resolution_2.5x',
            'label_az': 'Nömrə nişanı adayı netləşdirmə',
        })
    if plates:
        steps.append(f'plate_roi_x{min(3, len(plates))}')

    out = _clahe_lab(out)
    steps.append('clahe_final')

    try:
        out = cv2.edgePreservingFilter(out, flags=2, sigma_s=25, sigma_r=0.4)
        steps.append('edge_preserve')
    except Exception:
        pass

    meta = {
        'module': 'forensic_image_enhancement',
        'pipeline': 'ai_super_resolution + forensic_deblur + roi_targets',
        'sr_model_attempted': sr_model,
        'targets_enhanced': targets,
        'face_count': len(faces),
        'plate_candidate_count': len(plates),
        'summary_az': (
            f'Kriminalistik bərpa: {len(steps)} mərhələ; '
            f'{len(faces)} üz, {min(3, len(plates))} nömrə nişanı adayı netləşdirildi.'
        ),
    }
    return out, steps, meta
