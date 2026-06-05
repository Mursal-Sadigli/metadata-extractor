"""
Zəiflənmiş şəkil bərpası — denoise, kontrast, kəskinləşdirmə, upscaling;
bərpa sonrası metadata + lokasiya analizi.
"""

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from utils.artifact_utils import path_to_filename


def _assess_degradation(img: np.ndarray) -> Dict[str, Any]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    noise_est = float(np.std(gray.astype(np.float32) - cv2.GaussianBlur(gray, (0, 0), 3).astype(np.float32)))

    blur_level = 'aşağı'
    if lap_var < 50:
        blur_level = 'yüksək'
    elif lap_var < 120:
        blur_level = 'orta'

    noise_level = 'aşağı'
    if noise_est > 12:
        noise_level = 'yüksək'
    elif noise_est > 6:
        noise_level = 'orta'

    low_res = w < 800 or h < 600
    needs_restore = lap_var < 150 or noise_est > 7 or low_res

    return {
        'width': w,
        'height': h,
        'blur_score': round(lap_var, 2),
        'blur_level_az': blur_level,
        'noise_std': round(noise_est, 2),
        'noise_level_az': noise_level,
        'low_resolution': low_res,
        'needs_restoration': needs_restore,
        'summary_az': (
            f'Blur: {blur_level} (skor {lap_var:.0f}), səs-küy: {noise_level}, '
            f'ölçü {w}×{h}' + (' — bərpa tövsiyə olunur' if needs_restore else '')
        ),
    }


def _apply_clahe_bgr(img: np.ndarray, clip: float = 2.5) -> np.ndarray:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def _unsharp_mask(img: np.ndarray, sigma: float = 1.2, strength: float = 1.4) -> np.ndarray:
    blurred = cv2.GaussianBlur(img, (0, 0), sigma)
    return cv2.addWeighted(img, 1.0 + strength, blurred, -strength, 0)


def _restore_image(img: np.ndarray, assessment: Dict) -> Tuple[np.ndarray, List[str], Dict[str, Any]]:
    """Kriminalistik AI bərpa (SR + deblur + üz/nömrə ROI)."""
    from analyzers.forensic_image_enhancement import apply_forensic_enhancement

    try:
        out, steps, forensic_meta = apply_forensic_enhancement(img, assessment)
        return out, steps, forensic_meta
    except Exception as e:
        print(f'  [!] Forensic enhancement fallback: {e}', file=sys.stderr)
        steps: List[str] = []
        out = img.copy()
        if assessment.get('noise_std', 0) > 5:
            out = cv2.bilateralFilter(out, 9, 75, 75)
            steps.append('bilateral_denoise')
        out = _apply_clahe_bgr(out)
        steps.append('clahe_fallback')
        out = _unsharp_mask(out)
        steps.append('sharpen_fallback')
        return out, steps, {'fallback': True, 'error': str(e)}


def _copy_exif_to_restored(original_path: str, restored_path: str) -> bool:
    try:
        from PIL import Image
        with Image.open(original_path) as orig:
            exif_bytes = orig.info.get('exif')
        if not exif_bytes:
            return False
        restored = cv2.imread(restored_path)
        if restored is None:
            return False
        rgb = cv2.cvtColor(restored, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        pil.save(restored_path, 'JPEG', quality=95, exif=exif_bytes)
        return True
    except Exception as e:
        print(f'  [!] EXIF köçürmə: {e}', file=sys.stderr)
        return False


def _run_location_pipeline(filepath: str, img_meta: Dict, extra_texts=None) -> Dict[str, Any]:
    """main.py location axını — bərpa edilmiş fayl üzərində."""
    from analyzers.geo_analyzer import analyze_location
    from analyzers.astronomy_analyzer import analyze_sun_position
    from analyzers.file_carving_ml import analyze_file_carving_ml
    from analyzers.location_resolver import resolve_image_location
    from analyzers.carved_metadata_analyzer import analyze_carved_metadata

    file_carving_ml = analyze_file_carving_ml(filepath)
    carved_metadata = analyze_carved_metadata(filepath)
    location, location_inference, _loc_warnings = resolve_image_location(
        filepath,
        img_meta.get('location'),
        carving=file_carving_ml,
        extra_texts=extra_texts,
    )

    if location and location.get('latitude') is not None:
        geo = analyze_location(location['latitude'], location['longitude'])
        if geo:
            location['address'] = geo
        exif = img_meta.get('exif') or {}
        dt_info = exif.get('datetime') or {}
        dt = dt_info.get('original') or dt_info.get('modified') or dt_info.get('inferred_from_filename')
        if dt:
            astro = analyze_sun_position(location['latitude'], location['longitude'], dt)
            if astro and 'error' not in astro:
                location['astronomy'] = astro

    return {
        'location': location,
        'location_inference': location_inference,
        'carved_metadata': carved_metadata,
        'file_carving_ml': file_carving_ml,
    }


def _compare_metadata(original_meta: Dict, restored_meta: Dict) -> Dict[str, Any]:
    orig_tags = set((original_meta.get('raw_tags') or {}).keys())
    rest_tags = set((restored_meta.get('raw_tags') or {}).keys())
    new_tags = rest_tags - orig_tags
    orig_gps = original_meta.get('location') is not None
    rest_gps = restored_meta.get('location') is not None

    gains = []
    if not orig_gps and rest_gps:
        gains.append('Bərpa sonrası GPS/metadata oxunması yaxşılaşdı')
    if len(new_tags) > len(orig_tags):
        gains.append(f'{len(new_tags) - len(orig_tags)} əlavə metadata tag')
    if not gains:
        gains.append('Metadata eyni qaldı — bərpa vizual/OCR/geoparsing üçündür')

    return {
        'original_tag_count': len(orig_tags),
        'restored_tag_count': len(rest_tags),
        'new_tags': sorted(new_tags)[:20],
        'gps_recovered': not orig_gps and rest_gps,
        'summary_az': '; '.join(gains),
    }


def analyze_restore_and_metadata(
    filepath: str,
    extra_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Zəiflənmiş şəkili bərpa et, sonra metadata + lokasiya analiz et.
    Orijinal və bərpa edilmiş nəticələri müqayisə edir.
    """
    if not os.path.isfile(filepath):
        return {'status': 'error', 'error': 'Fayl tapılmadı'}

    img = cv2.imread(filepath)
    if img is None:
        return {'status': 'error', 'error': 'Şəkil oxunmadı'}

    print('  [i] Şəkil bərpası və metadata/lokasiya analizi...', file=sys.stderr)

    from extractors.image_extractor import ImageExtractor

    original_meta = ImageExtractor().extract(filepath)
    assessment = _assess_degradation(img)
    restored_img, steps, forensic_meta = _restore_image(img, assessment)

    out_dir = os.path.dirname(os.path.abspath(filepath))
    base = os.path.splitext(os.path.basename(filepath))[0]
    restored_path = os.path.join(out_dir, f'restored_{base}.jpg')
    cv2.imwrite(restored_path, restored_img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    exif_copied = _copy_exif_to_restored(filepath, restored_path)

    post_assessment = _assess_degradation(restored_img)
    restored_filename = path_to_filename(restored_path)

    restored_meta = ImageExtractor().extract(restored_path)
    extra_texts = [extra_text] if extra_text else None

    loc_original = _run_location_pipeline(filepath, original_meta, extra_texts)
    loc_restored = _run_location_pipeline(restored_path, restored_meta, extra_texts)

    ocr_gain = None
    try:
        from analyzers.ai_analyzer import analyze_image_ai
        ocr_orig = analyze_image_ai(filepath).get('extracted_text') or []
        ocr_rest = analyze_image_ai(restored_path).get('extracted_text') or []
        new_lines = [t for t in ocr_rest if t not in ocr_orig]
        if new_lines:
            ocr_gain = {'new_text_lines': new_lines[:15], 'count': len(new_lines)}
    except Exception:
        pass

    comparison = _compare_metadata(original_meta, restored_meta)
    if ocr_gain:
        comparison['ocr_improvement'] = ocr_gain
        comparison['summary_az'] += f'; OCR: +{ocr_gain["count"]} yeni sətir'

    primary_location = loc_restored.get('location') or loc_original.get('location')
    primary_inference = loc_restored.get('location_inference') or loc_original.get('location_inference')

    return {
        'status': 'success',
        'restoration': {
            'steps_applied': steps,
            'forensic_enhancement': forensic_meta,
            'exif_preserved': exif_copied,
            'restored_filename': restored_filename,
            'restored_path': restored_path,
            'before': assessment,
            'after': post_assessment,
            'quality_delta': {
                'blur_score': round(post_assessment['blur_score'] - assessment['blur_score'], 2),
                'noise_std': round(post_assessment['noise_std'] - assessment['noise_std'], 2),
            },
            'summary_az': (
                (forensic_meta.get('summary_az') or '')
                + f' Blur {assessment["blur_score"]:.0f} → {post_assessment["blur_score"]:.0f}.'
            ).strip(),
        },
        'original_metadata': {
            'exif': original_meta.get('exif'),
            'raw_tags': original_meta.get('raw_tags'),
            'location': original_meta.get('location'),
            'warnings': original_meta.get('warnings'),
        },
        'restored_metadata': {
            'exif': restored_meta.get('exif'),
            'raw_tags': restored_meta.get('raw_tags'),
            'location': restored_meta.get('location'),
            'warnings': restored_meta.get('warnings'),
        },
        'metadata_comparison': comparison,
        'location': primary_location,
        'location_inference': primary_inference,
        'location_original': loc_original,
        'location_restored': loc_restored,
        'carved_metadata': loc_restored.get('carved_metadata') or loc_original.get('carved_metadata'),
        'file_carving_ml': loc_restored.get('file_carving_ml') or loc_original.get('file_carving_ml'),
        'note': (
            'Kriminalistik AI bərpa: OpenCV DNN Super Resolution, deblur, üz və nömrə nişanı ROI netləşdirmə. '
            'Silinmiş EXIF/GPS bərpa olunmur — carving və geoparsing ilə əlavə iz axtarılır.'
        ),
    }
