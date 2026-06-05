"""PRNU — kamera sensor noise fingerprint (OpenCV + optional noiseprint)."""

import os
import sys
import hashlib

import numpy as np

CACHE_DIR_NAME = '.prnu_cache'


def _cache_dir(filepath):
    base = os.path.dirname(filepath)
    path = os.path.join(base, CACHE_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def _extract_noise_residual(img_gray):
    """Yüksək keçirən filtr ilə noise residual."""
    import cv2
    blurred = cv2.GaussianBlur(img_gray, (0, 0), 3)
    residual = img_gray.astype(np.float32) - blurred.astype(np.float32)
    return residual


def _fingerprint_vector(residual):
    """Residual-dan kompakt vektor."""
    h, w = residual.shape
    blocks = 8
    bh, bw = h // blocks, w // blocks
    if bh < 1 or bw < 1:
        return residual.flatten()[:512]
    vec = []
    for i in range(blocks):
        for j in range(blocks):
            patch = residual[i * bh:(i + 1) * bh, j * bw:(j + 1) * bw]
            vec.extend([float(np.mean(patch)), float(np.std(patch))])
    return np.array(vec, dtype=np.float32)


def _save_fingerprint(filepath, vec):
    cache = _cache_dir(filepath)
    fid = hashlib.sha256(vec.tobytes()).hexdigest()[:16]
    out = os.path.join(cache, f'{fid}.npy')
    np.save(out, vec)
    return fid, out


def _load_or_compute(filepath):
    import cv2
    img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None, None
    h, w = img.shape[:2]
    if max(h, w) > 1200:
        scale = 1200 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    residual = _extract_noise_residual(img)
    vec = _fingerprint_vector(residual)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec, residual


def _noiseprint_similarity(path_a, path_b):
    try:
        import noiseprint
        # noiseprint API varies; fallback if fails
        return None
    except ImportError:
        return None
    except Exception:
        return None


def _cosine_similarity(v1, v2):
    if v1 is None or v2 is None or len(v1) != len(v2):
        min_len = min(len(v1) if v1 is not None else 0, len(v2) if v2 is not None else 0)
        if min_len < 8:
            return 0.0
        v1 = v1[:min_len]
        v2 = v2[:min_len]
    dot = float(np.dot(v1, v2))
    return max(0.0, min(1.0, dot))


def analyze_prnu_single(filepath):
    vec, _ = _load_or_compute(filepath)
    if vec is None:
        return {'error': 'Şəkil oxuna bilmədi'}
    fid, path = _save_fingerprint(filepath, vec)
    return {
        'status': 'success',
        'fingerprint_id': fid,
        'cache_path': path,
        'message': 'PRNU profili yaradıldı (müqayisə üçün saxlanıldı)',
    }


def compare_prnu(filepath_a, filepath_b):
    np_sim = _noiseprint_similarity(filepath_a, filepath_b)
    v1, _ = _load_or_compute(filepath_a)
    v2, _ = _load_or_compute(filepath_b)
    if v1 is None or v2 is None:
        return {'similarity': 0.0, 'same_camera_likely': False, 'method': 'none'}
    sim = np_sim if np_sim is not None else _cosine_similarity(v1, v2)
    likely = sim >= 0.82
    conf = sim if likely else sim * 0.7
    return {
        'similarity': round(sim, 4),
        'same_camera_likely': likely,
        'confidence': round(conf, 4),
        'method': 'noise_residual' if np_sim is None else 'noiseprint',
        'note': 'Kiçik və ya messencer şəkillərində etibarlılıq aşağı ola bilər.',
    }
