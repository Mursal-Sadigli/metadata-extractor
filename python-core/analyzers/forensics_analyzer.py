import os
import sys
from PIL import Image, ImageChops, ImageEnhance
import warnings

from utils.artifact_utils import path_to_filename, ela_manipulation_score

warnings.filterwarnings("ignore")


def generate_ela(filepath, output_dir=None):
    """Error Level Analysis (ELA)."""
    try:
        original = Image.open(filepath).convert('RGB')
        if not output_dir:
            output_dir = os.path.dirname(filepath)
        temp_filename = os.path.join(output_dir, f"temp_{os.path.basename(filepath)}")
        ela_filename = os.path.join(output_dir, f"ela_{os.path.basename(filepath)}.png")
        original.save(temp_filename, 'JPEG', quality=90)
        compressed = Image.open(temp_filename)
        ela_image = ImageChops.difference(original, compressed)
        extrema = ela_image.getextrema()
        max_diff = max([ex[1] for ex in extrema])
        if max_diff == 0:
            max_diff = 1
        scale = 255.0 / max_diff
        ela_image = ImageEnhance.Brightness(ela_image).enhance(scale)
        ela_image.save(ela_filename)
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        return {
            "status": "success",
            "ela_image_path": ela_filename,
            "max_difference": max_diff,
        }
    except Exception as e:
        print(f"  [!] ELA Error: {e}", file=sys.stderr)
        return {"status": "error", "message": str(e)}


def enhance_reflections(filepath, output_dir=None):
    """CLAHE + sharpening — kölgə/yansıma detalları."""
    try:
        import cv2
        import numpy as np
        if not output_dir:
            output_dir = os.path.dirname(filepath)
        enhanced_filename = os.path.join(output_dir, f"enhanced_{os.path.basename(filepath)}")
        img = cv2.imread(filepath)
        if img is None:
            return {"error": "Şəkli oxumaq mümkün olmadı"}
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        enhanced_lab = cv2.merge((cl, a, b))
        enhanced_img = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
        gaussian = cv2.GaussianBlur(enhanced_img, (0, 0), 3.0)
        enhanced_img = cv2.addWeighted(enhanced_img, 1.5, gaussian, -0.5, 0)
        cv2.imwrite(enhanced_filename, enhanced_img)
        return {"status": "success", "enhanced_image_path": enhanced_filename}
    except Exception as e:
        print(f"  [!] Reflection Enhancement Error: {e}", file=sys.stderr)
        return {"error": str(e)}


def generate_caption(filepath):
    """BLIP image captioning."""
    try:
        from transformers import BlipProcessor, BlipForConditionalGeneration
        import torch

        print("  [i] Image Captioning modeli yüklənir...", file=sys.stderr)
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        raw_image = Image.open(filepath).convert('RGB')
        inputs = processor(raw_image, return_tensors="pt")
        out = model.generate(**inputs, max_new_tokens=50)
        caption = processor.decode(out[0], skip_special_tokens=True)
        return {"caption": caption}
    except Exception as e:
        print(f"  [!] Caption Error: {e}", file=sys.stderr)
        return {"error": str(e)}


def _build_forensics_summary(result):
    """Ümumi kriminalistika xülasəsi."""
    summary = {
        "manipulation_risk": "low",
        "manipulation_score": 0,
        "metadata_recovery": "none",
        "ai_generated_hint": False,
    }
    ela = result.get("ela") or {}
    if ela.get("risk_level"):
        summary["manipulation_risk"] = ela["risk_level"]
        summary["manipulation_score"] = ela.get("manipulation_score", 0)

    carved = result.get("carved_metadata") or {}
    if carved.get("recovery_score", 0) >= 40:
        summary["metadata_recovery"] = "high"
    elif carved.get("recovery_score", 0) >= 15:
        summary["metadata_recovery"] = "medium"
    elif carved.get("carved_blocks_found", 0) > 0:
        summary["metadata_recovery"] = "low"

    c2pa = result.get("c2pa") or {}
    if c2pa.get("ai_generated") or c2pa.get("status") == "ai_likely":
        summary["ai_generated_hint"] = True

    stego = result.get("steganography") or {}
    if stego.get("suspicious") or (stego.get("risk_score", 0) or 0) > 60:
        if summary["manipulation_risk"] == "low":
            summary["manipulation_risk"] = "medium"

    return summary


def analyze_forensics(filepath):
    """Kriminalistika paneli üçün bütün analizlər."""
    result = {
        "original_filename": path_to_filename(filepath),
        "artifacts": [],
    }

    print("  [i] Kriminalistika analizi başlayır...", file=sys.stderr)

    ela_result = generate_ela(filepath)
    if ela_result.get("status") == "success":
        score, risk = ela_manipulation_score(ela_result["max_difference"])
        ela_fn = path_to_filename(ela_result["ela_image_path"])
        result["ela"] = {
            "filename": ela_fn,
            "max_difference": ela_result["max_difference"],
            "manipulation_score": score,
            "risk_level": risk,
        }
        if ela_fn:
            result["artifacts"].append(ela_fn)

    enh_result = enhance_reflections(filepath)
    if enh_result.get("status") == "success":
        enh_fn = path_to_filename(enh_result["enhanced_image_path"])
        result["enhanced_reflection"] = {"filename": enh_fn}
        if enh_fn:
            result["artifacts"].append(enh_fn)

    try:
        from analyzers.steganography_analyzer import analyze_steganography
        result["steganography"] = analyze_steganography(filepath)
    except Exception as e:
        result["steganography"] = {"error": str(e)}

    try:
        from analyzers.c2pa_analyzer import analyze_c2pa
        result["c2pa"] = analyze_c2pa(filepath)
    except Exception as e:
        result["c2pa"] = {"status": "error", "message": str(e)}

    try:
        from analyzers.prnu_analyzer import analyze_prnu_single
        result["prnu"] = analyze_prnu_single(filepath)
    except Exception as e:
        result["prnu"] = {"error": str(e)}

    try:
        from analyzers.carved_metadata_analyzer import analyze_carved_metadata
        result["carved_metadata"] = analyze_carved_metadata(filepath)
    except Exception as e:
        result["carved_metadata"] = {"status": "error", "message": str(e)}

    cap_result = generate_caption(filepath)
    if cap_result.get("caption"):
        result["caption"] = cap_result["caption"]

    try:
        from analyzers.software_trace_analyzer import analyze_software_traces
        from extractors.image_extractor import ImageExtractor
        img_meta = ImageExtractor().extract(filepath)
        result["software_traces"] = analyze_software_traces(filepath, img_meta)
    except Exception as e:
        result["software_traces"] = {"error": str(e), "summary": "Proqram izi analizi uğursuz oldu.", "traces": []}

    result["summary"] = _build_forensics_summary(result)

    try:
        from analyzers.forensic_scientific_analyzer import enrich_forensics_report
        result = enrich_forensics_report(filepath, result)
    except Exception as e:
        print(f'  [!] Elmi kriminalistika: {e}', file=sys.stderr)
        result['scientific_error'] = str(e)

    return result
