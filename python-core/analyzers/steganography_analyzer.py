"""Steganografiya analizi — yalnız şəkil (LSB, DCT heuristika, gizli mətn)."""

import math
import os
import sys

import numpy as np

RISK_AZ = {'low': 'aşağı', 'medium': 'orta', 'high': 'yüksək'}


def _file_entropy(data):
    if not data:
        return 0.0
    freq = {}
    for b in data:
        freq[b] = freq.get(b, 0) + 1
    ent = 0.0
    ln = len(data)
    for c in freq.values():
        p = c / ln
        ent -= p * math.log2(p)
    return ent


def _lsb_chi_square(rgb):
    """RGB LSB paylanmasına əsasən şübhə."""
    try:
        flat = rgb.flatten()
        if len(flat) < 1000:
            return 'low', 10
        lsb = flat & 1
        ratio = float(np.mean(lsb))
        deviation = abs(ratio - 0.5)
        if deviation < 0.02:
            return 'medium', 45
        if deviation < 0.05:
            return 'low', 20
        return 'high', min(85, int(50 + deviation * 400))
    except Exception:
        return 'low', 0


def _jpeg_dct_heuristic(filepath):
    """
    JPEG/şəkil üçün 8x8 DCT AC əmsallarının anomaliyası (sadə stego şübhəsi).
    """
    try:
        import cv2
        gray = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
        if gray is None or gray.shape[0] < 16 or gray.shape[1] < 16:
            return 'low', 0

        h, w = gray.shape
        h8, w8 = h - h % 8, w - w % 8
        gray = gray[:h8, :w8].astype(np.float32)

        ac_vars = []
        for y in range(0, h8, 8):
            for x in range(0, w8, 8):
                block = gray[y:y + 8, x:x + 8]
                dct = cv2.dct(block)
                ac = dct.copy()
                ac[0, 0] = 0
                ac_vars.append(float(np.var(ac)))

        if len(ac_vars) < 16:
            return 'low', 0

        mean_v = float(np.mean(ac_vars))
        std_v = float(np.std(ac_vars))
        cv_ratio = std_v / (mean_v + 1e-6)

        if cv_ratio > 1.8:
            return 'medium', 50
        if cv_ratio > 2.5:
            return 'high', 68
        return 'low', 15
    except Exception as e:
        return 'low', 0


def _risk_from_score(score):
    if score < 25:
        return 'low'
    if score < 55:
        return 'medium'
    return 'high'


def analyze_steganography(filepath):
    """Şəkildə gizlədilmiş məlumat üçün steganografiya analizi."""
    findings = []
    methods = []
    stego_score = 0

    if not os.path.isfile(filepath):
        return {
            'status': 'error',
            'error': 'Fayl tapılmadı',
            'media_type': 'image',
            'stego_score': 0,
            'suspicious': False,
        }

    ext = os.path.splitext(filepath)[1].lower()

    try:
        from PIL import Image
        img = Image.open(filepath).convert('RGB')
        arr = np.array(img)
        suspicion, lsb_score = _lsb_chi_square(arr)
        stego_score = max(stego_score, lsb_score)
        methods.append('LSB (chi-square)')
        findings.append(f'LSB paylanması: {RISK_AZ.get(suspicion, suspicion)} şübhə')
    except Exception as e:
        findings.append(f'LSB analizi uğursuz: {e}')

    if ext in ('.jpg', '.jpeg', '.png', '.webp', '.bmp'):
        dct_susp, dct_score = _jpeg_dct_heuristic(filepath)
        if dct_score > 0:
            stego_score = max(stego_score, dct_score)
            methods.append('DCT (8x8 heuristika)')
            findings.append(f'DCT əmsal anomaliyası: {RISK_AZ.get(dct_susp, dct_susp)} şübhə')

    trailing = 0
    hidden_preview = None
    try:
        with open(filepath, 'rb') as f:
            raw = f.read()
        if raw[:2] == b'\xff\xd8':
            end = raw.rfind(b'\xff\xd9')
            if end > 0 and end + 2 < len(raw):
                trailing = len(raw) - end - 2
                if trailing > 32:
                    stego_score = max(stego_score, min(90, 40 + trailing // 100))
                    methods.append('JPEG trailing data')
                    findings.append(f'JPEG sonrası {trailing} əlavə byte')
                    tail = raw[-200:]
                    try:
                        text = tail.decode('utf-8', errors='ignore')
                        printable = ''.join(c for c in text if c.isprintable())
                        if len(printable) > 8:
                            hidden_preview = printable[:80]
                    except Exception:
                        pass
        elif ext == '.png' and b'IEND' in raw:
            idx = raw.rfind(b'IEND')
            if idx > 0 and idx + 8 < len(raw):
                trailing = len(raw) - idx - 8
                if trailing > 32:
                    stego_score = max(stego_score, min(85, 35 + trailing // 80))
                    methods.append('PNG trailing data')
                    findings.append(f'PNG IEND sonrası {trailing} əlavə byte')

        ent = _file_entropy(raw[-4096:] if len(raw) > 4096 else raw)
        if ent > 7.5 and trailing > 0:
            findings.append(f'Yüksək entropy ({ent:.2f})')
            stego_score = max(stego_score, 55)
    except Exception as e:
        findings.append(f'Fayl oxuma: {e}')

    try:
        from stegano import lsb
        secret = lsb.reveal(filepath)
        if secret and len(secret.strip()) > 2:
            stego_score = max(stego_score, 75)
            hidden_preview = secret.strip()[:120]
            methods.append('stegano LSB decode')
            findings.append('LSB decode: gizli mətn tapıldı')
    except Exception:
        pass

    lsb_suspicion = _risk_from_score(stego_score)
    risk_az = RISK_AZ.get(lsb_suspicion, lsb_suspicion)

    return {
        'status': 'success',
        'media_type': 'image',
        'stego_score': min(100, stego_score),
        'lsb_suspicion': lsb_suspicion,
        'risk_level': lsb_suspicion,
        'risk_level_az': risk_az,
        'suspicious': stego_score >= 55,
        'methods': methods,
        'trailing_bytes': trailing,
        'findings': findings,
        'hidden_message_preview': hidden_preview,
    }
