"""
Computer Vision & ML — insan sayı, emosiya/yaş/cins, COCO obyektlər,
brend/loqo, OCR, sənəd növü, Places/CLIP səhnə, GIF/video hərəkət.
"""

import os
import re
import sys
import tempfile
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from utils.artifact_utils import path_to_filename

# ── Age / Gender (OpenCV DNN) ──
AGE_PROTO_URL = (
    'https://raw.githubusercontent.com/spmallick/learnopencv/master/'
    'AgeGender/age_deploy.prototxt'
)
AGE_MODEL_URL = (
    'https://raw.githubusercontent.com/spmallick/learnopencv/master/'
    'AgeGender/age_net.caffemodel'
)
GENDER_PROTO_URL = (
    'https://raw.githubusercontent.com/spmallick/learnopencv/master/'
    'AgeGender/gender_deploy.prototxt'
)
GENDER_MODEL_URL = (
    'https://raw.githubusercontent.com/spmallick/learnopencv/master/'
    'AgeGender/gender_net.caffemodel'
)
FER_ONNX_URLS = [
    'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/'
    'facial_expression_recognition/facial_expression_recognition_mobilefacenet_2022july.onnx',
    'https://github.com/opencv/opencv_zoo/raw/main/models/'
    'facial_expression_recognition/facial_expression_recognition_mobilefacenet_2022july.onnx',
]

AGE_BUCKETS = ['0-2', '4-6', '8-12', '15-20', '25-32', '38-43', '48-53', '60+']
AGE_BUCKETS_AZ = {
    '0-2': '0-2 yaş', '4-6': '4-6 yaş', '8-12': '8-12 yaş', '15-20': '15-20 yaş',
    '25-32': '25-32 yaş', '38-43': '38-43 yaş', '48-53': '48-53 yaş', '60+': '60+ yaş',
}
GENDER_AZ = {'Male': 'Kişi', 'Female': 'Qadın', 'Unknown': 'Müəyyən deyil'}

EMOTION_LABELS = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']
EMOTION_AZ = {
    'angry': 'Qəzəbli (Angry)',
    'disgust': 'İstənməz (Disgust)',
    'fear': 'Qorxu (Fear)',
    'happy': 'Xoşbəxt (Happy)',
    'neutral': 'Neytral (Neutral)',
    'sad': 'Kədərli (Sad)',
    'surprise': 'Təəccüblü (Surprised)',
}

PLACE_PROMPTS = [
    ('restaurant', 'restoran / yemək yeri'),
    ('office', 'ofis / iş yeri'),
    ('park', 'park / bağ'),
    ('beach', 'çimərlik / sahilyanı'),
    ('street', 'küçə / şəhər'),
    ('home', 'ev / mənzil'),
    ('shop', 'mağaza / ticarət'),
    ('hospital', 'xəstəxana / klinika'),
    ('school', 'məktəb / universitet'),
    ('airport', 'hava limanı'),
    ('stadium', 'stadion / idman'),
    ('forest', 'meşə / təbiət'),
    ('mountain', 'dağ / landşaft'),
    ('indoor', 'daxili məkan'),
    ('outdoor', 'açıq hava'),
]

BRAND_PATTERNS: List[Tuple[str, List[str]]] = [
    ('Nike', [r'\bnike\b', r'\bswoosh\b']),
    ('Adidas', [r'\badidas\b', r'\bthree\s*stripes\b']),
    ('Apple', [r'\bapple\b', r'\biphone\b', r'\bipad\b', r'\bmacbook\b']),
    ('Samsung', [r'\bsamsung\b', r'\bgalaxy\b']),
    ('Google', [r'\bgoogle\b', r'\bandroid\b', r'\bpixel\b']),
    ('Microsoft', [r'\bmicrosoft\b', r'\bwindows\b', r'\bxbox\b']),
    ('Coca-Cola', [r'\bcoca[\s-]?cola\b', r'\bcoke\b']),
    ('Pepsi', [r'\bpepsi\b']),
    ('McDonald\'s', [r"\bmcdonald'?s?\b", r'\bmcd\b']),
    ('BMW', [r'\bbmw\b', r'\bm\s*power\b']),
    ('Mercedes-Benz', [r'\bmercedes\b', r'\bbenz\b']),
    ('Audi', [r'\baudi\b']),
    ('Toyota', [r'\btoyota\b']),
    ('Instagram', [r'\binstagram\b', r'\big\b']),
    ('Facebook', [r'\bfacebook\b', r'\bmeta\b']),
    ('TikTok', [r'\btiktok\b']),
    ('Twitter/X', [r'\btwitter\b', r'\bx\.com\b']),
    ('Starbucks', [r'\bstarbucks\b']),
    ('Amazon', [r'\bamazon\b']),
    ('Visa', [r'\bvisa\b']),
    ('Mastercard', [r'\bmastercard\b']),
    ('Shell', [r'\bshell\b']),
    ('BP', [r'\bbp\b']),
    ('Red Bull', [r'\bred\s*bull\b']),
    ('Heineken', [r'\bheineken\b']),
]

CLIP_BRAND_PROMPTS = [
    'Nike logo', 'Apple logo', 'Coca-Cola logo', 'BMW logo', 'Mercedes logo',
    'Instagram logo', 'McDonald\'s logo', 'Adidas logo', 'Google logo',
]

DOCUMENT_TYPES = {
    'passport': {
        'label_az': 'Pasport (Passport)',
        'patterns': [
            r'\bpassport\b', r'\bpasport\b', r'\brepublic\b.*\bpassport\b',
            r'\bP<[A-Z]{3}', r'\bMRZ\b', r'\bdate of birth\b', r'\bnationality\b',
        ],
        'weight': 1.0,
    },
    'visa': {
        'label_az': 'Viza (Visa)',
        'patterns': [
            r'\bvisa\b', r'\bentry\b', r'\bimmigrant\b', r'\bnonimmigrant\b',
            r'\bschengen\b', r'\bvalid until\b',
        ],
        'weight': 1.0,
    },
    'id_card': {
        'label_az': 'Şəxsiyyət vəsiqəsi (ID Card)',
        'patterns': [
            r'\bid\s*card\b', r'\bidentity\b', r'\bşəxsiyyət\b', r'\bvesiq',
            r'\bfin\b', r'\bserial\s*no\b', r'\bpersonal\s*no\b',
        ],
        'weight': 0.95,
    },
    'invoice': {
        'label_az': 'Faktura (Invoice)',
        'patterns': [
            r'\binvoice\b', r'\bfaktura\b', r'\bbill\b', r'\btotal\b', r'\bamount\b',
            r'\bvat\b', r'\bədv\b', r'\bsubtotal\b', r'\bqty\b',
        ],
        'weight': 0.85,
    },
    'contract': {
        'label_az': 'Müqavilə (Contract)',
        'patterns': [
            r'\bcontract\b', r'\bmüqavil', r'\bagreement\b', r'\bterms\b',
            r'\bparties\b', r'\bsignature\b', r'\bimza\b',
        ],
        'weight': 0.85,
    },
    'driver_license': {
        'label_az': 'Sürücülük vəsiqəsi',
        'patterns': [r'\bdriver\b', r'\blicense\b', r'\bdl\b', r'\bsürücü\b'],
        'weight': 0.9,
    },
}

_age_net = None
_gender_net = None
_fer_model = None
_clip_model = None
_clip_processor = None


def _light_vision_enabled() -> bool:
    """Render / aşağı RAM: CLIP, EasyOCR və ağır YOLO World söndürülür."""
    val = os.environ.get('LIGHT_VISION', '').strip().lower()
    if val in ('0', 'false', 'no'):
        return False
    if val in ('1', 'true', 'yes'):
        return True
    return os.environ.get('RENDER', '').strip().lower() in ('true', '1')


def _models_dir():
    return os.path.join(os.path.dirname(__file__), '..', 'models')


def _download(url: str, dest: str):
    if os.path.isfile(dest) and os.path.getsize(dest) > 1000:
        return
    print(f'  [i] Model yüklənir: {os.path.basename(dest)}...', file=sys.stderr)
    urllib.request.urlretrieve(url, dest)


def _get_age_gender_nets():
    global _age_net, _gender_net
    if _age_net is None:
        mdir = _models_dir()
        os.makedirs(mdir, exist_ok=True)
        age_p = os.path.join(mdir, 'age_deploy.prototxt')
        age_m = os.path.join(mdir, 'age_net.caffemodel')
        gen_p = os.path.join(mdir, 'gender_deploy.prototxt')
        gen_m = os.path.join(mdir, 'gender_net.caffemodel')
        for u, p in [
            (AGE_PROTO_URL, age_p), (AGE_MODEL_URL, age_m),
            (GENDER_PROTO_URL, gen_p), (GENDER_MODEL_URL, gen_m),
        ]:
            _download(u, p)
        _age_net = cv2.dnn.readNet(age_m, age_p)
        _gender_net = cv2.dnn.readNet(gen_m, gen_p)
    return _age_net, _gender_net


def _get_fer_model():
    global _fer_model
    if _fer_model is None:
        mdir = _models_dir()
        os.makedirs(mdir, exist_ok=True)
        path = os.path.join(mdir, 'fer_mobilefacenet_2022july.onnx')
        if not os.path.isfile(path) or os.path.getsize(path) < 10000:
            for url in FER_ONNX_URLS:
                try:
                    _download(url, path)
                    break
                except Exception:
                    continue
        if os.path.isfile(path):
            _fer_model = cv2.FaceRecognizerSF.create(path, '')
    return _fer_model


def _get_clip():
    global _clip_model, _clip_processor
    if _light_vision_enabled():
        return None, None
    if _clip_model is None:
        try:
            from transformers import CLIPModel, CLIPProcessor
            _clip_processor = CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')
            _clip_model = CLIPModel.from_pretrained('openai/clip-vit-base-patch32')
            _clip_model.eval()
        except Exception as e:
            print(f'  [!] CLIP yüklənmədi: {e}', file=sys.stderr)
    return _clip_model, _clip_processor


def _crop_face_bgr(img: np.ndarray, bbox: Dict) -> Optional[np.ndarray]:
    h, w = img.shape[:2]
    x, y, bw, bh = bbox['x'], bbox['y'], bbox['w'], bbox['h']
    pad = int(max(bw, bh) * 0.15)
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(w, x + bw + pad)
    y2 = min(h, y + bh + pad)
    crop = img[y1:y2, x1:x2]
    return crop if crop.size > 0 else None


def _predict_age_gender(face_bgr: np.ndarray) -> Tuple[str, str, float, float]:
    """Yaş bucket və cins (OpenCV DNN)."""
    if _light_vision_enabled():
        return '—', 'Unknown', 0.0, 0.0
    try:
        age_net, gender_net = _get_age_gender_nets()
        blob = cv2.dnn.blobFromImage(
            face_bgr, 1.0, (227, 227),
            (78.4263377603, 87.7689143744, 114.895847746), swapRB=False,
        )
        age_net.setInput(blob)
        age_probs = age_net.forward()[0]
        age_idx = int(age_probs.argmax())
        age_bucket = AGE_BUCKETS[min(age_idx, len(AGE_BUCKETS) - 1)]
        age_conf = float(age_probs[age_idx])

        gender_net.setInput(blob)
        gender_probs = gender_net.forward()[0]
        gender_idx = int(gender_probs.argmax())
        gender = 'Male' if gender_idx == 0 else 'Female'
        gender_conf = float(gender_probs[gender_idx])
        return age_bucket, gender, age_conf, gender_conf
    except Exception as e:
        print(f'  [!] Yaş/cins: {e}', file=sys.stderr)
        return '—', 'Unknown', 0.0, 0.0


def _predict_emotion(face_bgr: np.ndarray) -> Tuple[str, float]:
    """FER+ ONNX — emosiya."""
    if _light_vision_enabled():
        return 'neutral', 0.0
    try:
        fer = _get_fer_model()
        if fer is None:
            return 'neutral', 0.0
        rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        # FER model expects aligned face — resize center crop
        size = 112
        resized = cv2.resize(rgb, (size, size))
        # Simple blob for emotion ONNX (mobilefacenet fer uses feature + classifier internally via FaceRecognizerSF)
        # opencv zoo FER is used differently — use direct ONNX if FaceRecognizerSF fails
        blob = cv2.dnn.blobFromImage(resized, 1.0 / 255, (size, size), (0, 0, 0), swapRB=True)
        # Fallback: heuristic from ONNX via cv2.dnn
        mdir = _models_dir()
        onnx_path = os.path.join(mdir, 'fer_mobilefacenet_2022july.onnx')
        if os.path.isfile(onnx_path):
            net = cv2.dnn.readNetFromONNX(onnx_path)
            net.setInput(blob)
            out = net.forward()
            if out.size > 0:
                flat = out.flatten()
                if len(flat) >= len(EMOTION_LABELS):
                    idx = int(np.argmax(flat[:len(EMOTION_LABELS)]))
                    conf = float(flat[idx])
                    return EMOTION_LABELS[idx], conf
    except Exception as e:
        print(f'  [!] Emosiya: {e}', file=sys.stderr)
    return 'neutral', 0.0


def _analyze_people(img_path: str, img_bgr: np.ndarray) -> Dict[str, Any]:
    from analyzers.face_privacy_analyzer import detect_faces
    from analyzers.object_detection_analyzer import detect_objects

    face_res = detect_faces(img_path)
    faces = face_res.get('faces') or []
    yolo = detect_objects(img_path, conf_threshold=0.15)
    yolo_persons = [o for o in (yolo.get('objects') or []) if o.get('class_name') == 'person']

    person_instances = []
    for i, face in enumerate(faces):
        bbox = face.get('bbox') or {}
        crop = _crop_face_bgr(img_bgr, bbox)
        entry = {
            'id': i + 1,
            'bbox': bbox,
            'detectors': face.get('detectors'),
            'confidence': face.get('confidence'),
        }
        if crop is not None and crop.shape[0] >= 20 and crop.shape[1] >= 20:
            age_bucket, gender, age_conf, gender_conf = _predict_age_gender(crop)
            emotion, emo_conf = _predict_emotion(crop)
            entry['age'] = {
                'bucket': age_bucket,
                'label_az': AGE_BUCKETS_AZ.get(age_bucket, age_bucket),
                'range_az': _age_to_range_az(age_bucket),
                'confidence': round(age_conf, 3),
            }
            entry['gender'] = {
                'value': gender,
                'label_az': GENDER_AZ.get(gender, 'Müəyyən deyil'),
                'confidence': round(gender_conf, 3),
            }
            entry['emotion'] = {
                'value': emotion,
                'label_az': EMOTION_AZ.get(emotion, emotion),
                'confidence': round(float(emo_conf), 3),
            }
        else:
            entry['age'] = {'label_az': 'Müəyyən deyil'}
            entry['gender'] = {'label_az': 'Müəyyən deyil'}
            entry['emotion'] = {'label_az': 'Müəyyən deyil'}
        person_instances.append(entry)

    face_count = len(faces)
    yolo_count = len(yolo_persons)
    best_count = max(face_count, yolo_count)

    return {
        'face_detection_count': face_count,
        'yolo_person_count': yolo_count,
        'person_count': best_count,
        'count_method': 'face+yolo' if face_count != yolo_count else 'unified',
        'summary_az': (
            f'{best_count} insan (üz: {face_count}, YOLO person: {yolo_count})'
            if best_count else 'İnsan tapılmadı'
        ),
        'persons': person_instances,
        'emotion_summary': _summarize_emotions(person_instances),
        'age_summary': _summarize_ages(person_instances),
        'gender_summary': _summarize_genders(person_instances),
    }


def _age_to_range_az(bucket: str) -> str:
    mapping = {
        '25-32': '25-35 arası (təxmini)',
        '38-43': '35-45 arası (təxmini)',
        '15-20': '15-25 arası (təxmini)',
        '48-53': '45-55 arası (təxmini)',
    }
    return mapping.get(bucket, AGE_BUCKETS_AZ.get(bucket, bucket))


def _summarize_emotions(persons: List[Dict]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for p in persons:
        emo = (p.get('emotion') or {}).get('value')
        if emo:
            label = EMOTION_AZ.get(emo, emo)
            out[label] = out.get(label, 0) + 1
    return out


def _summarize_ages(persons: List[Dict]) -> List[str]:
    return list({
        (p.get('age') or {}).get('range_az') or (p.get('age') or {}).get('label_az')
        for p in persons
        if (p.get('age') or {}).get('label_az') and (p.get('age') or {}).get('label_az') != 'Müəyyən deyil'
    })


def _summarize_genders(persons: List[Dict]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for p in persons:
        g = (p.get('gender') or {}).get('label_az', 'Müəyyən deyil')
        out[g] = out.get(g, 0) + 1
    return out


def _analyze_ocr(img_path: str) -> Dict[str, Any]:
    if _light_vision_enabled():
        return {
            'status': 'skipped',
            'reason': 'Yüngül rejim (server RAM)',
            'lines': [],
            'words': [],
            'full_text': '',
            'word_count': 0,
            'line_count': 0,
        }
    from analyzers.ai_analyzer import get_reader
    lines = []
    words = []
    try:
        reader = get_reader()
        results = reader.readtext(img_path, detail=1, paragraph=False)
        for item in results:
            if len(item) < 3:
                continue
            bbox, text, conf = item[0], str(item[1]).strip(), float(item[2])
            if len(text) < 1:
                continue
            lines.append({'text': text, 'confidence': round(conf, 3), 'bbox': bbox})
            for w in re.findall(r'[\w\u0400-\u04FF\u0590-\u05FF\u0600-\u06FF\u00C0-\u024F\'\-\.]+', text):
                if len(w) >= 2:
                    words.append({'word': w, 'confidence': round(conf, 3), 'source_line': text})
    except Exception as e:
        print(f'  [!] OCR: {e}', file=sys.stderr)
        return {'status': 'error', 'error': str(e), 'lines': [], 'words': []}

    full_text = ' '.join(l['text'] for l in lines)
    return {
        'status': 'success',
        'line_count': len(lines),
        'word_count': len(words),
        'lines': lines,
        'words': words,
        'full_text': full_text,
        'addresses_hints': _extract_address_hints(lines),
    }


def _extract_address_hints(lines: List[Dict]) -> List[str]:
    hints = []
    for ln in lines:
        t = ln['text']
        if re.search(r'\b(st|street|küç|prospekt|bulvar|avenue|ave|road|rd|baku|bakı|azərbaycan)\b', t, re.I):
            hints.append(t)
        elif re.search(r'\d{1,4}\s+[A-Za-z\u00C0-\u024F]{3,}', t):
            hints.append(t)
    return hints[:15]


def _detect_brands(ocr: Dict[str, Any], img_path: str) -> Dict[str, Any]:
    text = (ocr.get('full_text') or '').lower()
    found = []
    for brand, patterns in BRAND_PATTERNS:
        for pat in patterns:
            if re.search(pat, text, re.I):
                found.append({
                    'brand': brand,
                    'method': 'OCR',
                    'confidence': 0.82,
                    'evidence': pat,
                })
                break

    clip_brands = _clip_brand_detect(img_path)
    seen = {f['brand'] for f in found}
    for b in clip_brands:
        if b['brand'] not in seen:
            found.append(b)

    found.sort(key=lambda x: -x.get('confidence', 0))
    return {
        'count': len(found),
        'brands': found[:20],
        'summary_az': ', '.join(b['brand'] for b in found[:8]) if found else 'Marka/loqo tapılmadı',
    }


def _clip_brand_detect(img_path: str) -> List[Dict]:
    model, processor = _get_clip()
    if model is None or processor is None:
        return []
    try:
        import torch
        from PIL import Image
        img = Image.open(img_path).convert('RGB')
        inputs = processor(text=CLIP_BRAND_PROMPTS, images=img, return_tensors='pt', padding=True)
        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits_per_image.softmax(dim=1)[0]
        results = []
        for i, prompt in enumerate(CLIP_BRAND_PROMPTS):
            score = float(logits[i])
            if score > 0.22:
                brand = prompt.replace(' logo', '')
                results.append({
                    'brand': brand,
                    'method': 'CLIP',
                    'confidence': round(score, 3),
                    'evidence': prompt,
                })
        results.sort(key=lambda x: -x['confidence'])
        return results[:5]
    except Exception as e:
        print(f'  [!] CLIP brend: {e}', file=sys.stderr)
        return []


def _detect_documents(ocr: Dict[str, Any]) -> Dict[str, Any]:
    text = ocr.get('full_text') or ''
    scores = []
    for doc_id, cfg in DOCUMENT_TYPES.items():
        hits = []
        score = 0.0
        for pat in cfg['patterns']:
            if re.search(pat, text, re.I):
                hits.append(pat)
                score += cfg['weight']
        if hits:
            scores.append({
                'type': doc_id,
                'label_az': cfg['label_az'],
                'score': round(score, 2),
                'matched_patterns': len(hits),
                'confidence': min(0.95, 0.45 + score * 0.15),
            })
    scores.sort(key=lambda x: -x['score'])
    top = scores[0] if scores else None
    return {
        'detected': bool(scores),
        'primary': top,
        'candidates': scores[:5],
        'summary_az': top['label_az'] if top else 'Sənəd növü aşkar edilmədi',
    }


def _analyze_scene(img_path: str) -> Dict[str, Any]:
    model, processor = _get_clip()
    if model is None:
        return {'status': 'skipped', 'reason': 'CLIP modeli yüklənmədi'}
    try:
        import torch
        from PIL import Image
        prompts = [f'a photo of a {p[0]}' for p in PLACE_PROMPTS]
        labels_en = [p[0] for p in PLACE_PROMPTS]
        labels_az = [p[1] for p in PLACE_PROMPTS]
        img = Image.open(img_path).convert('RGB')
        inputs = processor(text=prompts, images=img, return_tensors='pt', padding=True)
        with torch.no_grad():
            outputs = model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1)[0]
        ranked = sorted(
            zip(labels_en, labels_az, [float(p) for p in probs]),
            key=lambda x: -x[2],
        )
        top = ranked[0]
        return {
            'status': 'success',
            'method': 'CLIP (Places365 tipli)',
            'primary': {
                'place_en': top[0],
                'place_az': top[1],
                'confidence': round(top[2], 3),
            },
            'top_places': [
                {'place_en': en, 'place_az': az, 'confidence': round(conf, 3)}
                for en, az, conf in ranked[:5]
            ],
            'summary_az': f'{top[1]} ({round(top[2] * 100)}%)',
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def _extract_frames_for_motion(filepath: str, max_frames: int = 24) -> List[np.ndarray]:
    ext = os.path.splitext(filepath)[1].lower()
    frames = []
    if ext == '.gif':
        try:
            from PIL import Image, ImageSequence
            with Image.open(filepath) as im:
                for i, frame in enumerate(ImageSequence.Iterator(im)):
                    if i >= max_frames:
                        break
                    arr = np.array(frame.convert('RGB'))
                    frames.append(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
        except Exception as e:
            print(f'  [!] GIF frame: {e}', file=sys.stderr)
    elif ext in ('.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v'):
        cap = cv2.VideoCapture(filepath)
        if not cap.isOpened():
            return frames
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        step = max(1, total // max_frames) if total > 0 else 1
        idx = 0
        grabbed = 0
        while grabbed < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % step == 0:
                frames.append(frame)
                grabbed += 1
            idx += 1
        cap.release()
    return frames


def _analyze_motion(filepath: str) -> Dict[str, Any]:
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in ('.gif', '.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v'):
        return {
            'applicable': False,
            'summary_az': 'Statik şəkil — hərəkət analizi tətbiq edilmir',
        }

    frames = _extract_frames_for_motion(filepath)
    if len(frames) < 2:
        return {
            'applicable': True,
            'motion_detected': False,
            'summary_az': 'Kadr yetərli deyil — hərəkət ölçülə bilmədi',
        }

    diffs = []
    flow_mags = []
    blur_vars = []
    prev_gray = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)

    for i in range(1, len(frames)):
        gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
        diffs.append(float(np.mean(cv2.absdiff(prev_gray, gray))))
        blur_vars.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0,
        )
        mag = float(np.mean(np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)))
        flow_mags.append(mag)
        prev_gray = gray

    mean_diff = float(np.mean(diffs))
    mean_flow = float(np.mean(flow_mags))
    blur_std = float(np.std(blur_vars))

    motion_detected = mean_diff > 4.0 or mean_flow > 0.8
    blur_motion = blur_std > 80 and mean_diff > 8

    if mean_diff > 25 or mean_flow > 3:
        level = 'yüksək'
    elif mean_diff > 10 or mean_flow > 1.5:
        level = 'orta'
    elif motion_detected:
        level = 'aşağı'
    else:
        level = 'statik'

    return {
        'applicable': True,
        'media_type': 'gif' if ext == '.gif' else 'video',
        'frames_analyzed': len(frames),
        'motion_detected': motion_detected,
        'motion_blur_hint': blur_motion,
        'mean_frame_diff': round(mean_diff, 2),
        'mean_optical_flow': round(mean_flow, 3),
        'blur_variance_std': round(blur_std, 1),
        'motion_level': level,
        'summary_az': (
            f'Hərəkət: {level} (frame diff={mean_diff:.1f}, optical flow={mean_flow:.2f})'
            + (' · blur/motion izi' if blur_motion else '')
        ),
    }


def _draw_vision_preview(img_bgr: np.ndarray, people: Dict, objects: Dict, out_path: str) -> Optional[str]:
    out = img_bgr.copy()
    for obj in (objects.get('objects') or [])[:80]:
        if obj.get('class_name') == 'person':
            continue
        b = obj.get('bbox') or {}
        x, y, w, h = int(b.get('x', 0)), int(b.get('y', 0)), int(b.get('w', 0)), int(b.get('h', 0))
        cv2.rectangle(out, (x, y), (x + w, y + h), (59, 130, 246), 2)
        cv2.putText(out, obj.get('class_name_az', '')[:12], (x, max(y - 4, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (59, 130, 246), 1, cv2.LINE_AA)

    for p in (people.get('persons') or []):
        b = p.get('bbox') or {}
        x, y, w, h = int(b.get('x', 0)), int(b.get('y', 0)), int(b.get('w', 0)), int(b.get('h', 0))
        emo = (p.get('emotion') or {}).get('label_az', '')[:8]
        cv2.rectangle(out, (x, y), (x + w, y + h), (34, 211, 238), 2)
        cv2.putText(out, emo, (x, y + h + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (34, 211, 238), 1, cv2.LINE_AA)

    cv2.imwrite(out_path, out, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    return path_to_filename(out_path)


def analyze_vision_ml(filepath: str, conf_threshold: float = 0.15) -> Dict[str, Any]:
    """Tam Computer Vision & ML analizi."""
    if not os.path.isfile(filepath):
        return {'status': 'error', 'error': 'Fayl tapılmadı'}

    ext = os.path.splitext(filepath)[1].lower()
    is_static_image = ext in (
        '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.heic', '.heif',
    )
    is_video = ext in ('.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v')

    if not is_static_image and not is_video:
        return {'status': 'error', 'error': 'Computer Vision yalnız şəkil/GIF/video üçündür.'}

    light = _light_vision_enabled()
    print(
        f'  [i] Computer Vision & ML analizi...'
        + (' (yüngül rejim)' if light else ''),
        file=sys.stderr,
    )

    analysis_path = filepath
    if is_video:
        from extractors.video_extractor import VideoExtractor
        vr = VideoExtractor().extract(filepath, num_frames=3)
        frames = vr.get('frames') or []
        if frames and os.path.isfile(frames[0].get('path', '')):
            analysis_path = frames[0]['path']

    img_bgr = cv2.imread(analysis_path)
    if img_bgr is None and not is_video:
        return {'status': 'error', 'error': 'Şəkil oxunmadı'}

    result: Dict[str, Any] = {
        'status': 'success',
        'analysis_source': os.path.basename(analysis_path),
        'light_mode': light,
        'models': {
            'faces': 'YuNet+MediaPipe+Haar',
            'objects': 'YOLOv8n COCO' if light else 'YOLOv8m COCO + World',
            'age_gender': 'deaktiv (yüngül)' if light else 'OpenCV DNN (Levi)',
            'emotion': 'deaktiv (yüngül)' if light else 'FER+ MobileFaceNet',
            'ocr': 'deaktiv (yüngül)' if light else 'EasyOCR (az/en/tr)',
            'scene': 'deaktiv (yüngül)' if light else 'CLIP ViT-B/32',
            'brands': 'OCR + CLIP' if not light else 'deaktiv (yüngül)',
        },
    }

    if img_bgr is not None:
        result['people'] = _analyze_people(analysis_path, img_bgr)
        from analyzers.object_detection_analyzer import detect_objects
        result['objects_coco'] = detect_objects(analysis_path, conf_threshold=conf_threshold)
        result['ocr'] = _analyze_ocr(analysis_path)
        result['brands_logos'] = (
            {'count': 0, 'brands': [], 'summary_az': 'Yüngül rejim — deaktiv'}
            if light else _detect_brands(result['ocr'], analysis_path)
        )
        result['documents'] = (
            {'detected': False, 'summary_az': 'Yüngül rejim — deaktiv'}
            if light else _detect_documents(result['ocr'])
        )
        result['scene'] = (
            {'status': 'skipped', 'reason': 'Yüngül rejim (server RAM)'}
            if light else _analyze_scene(analysis_path)
        )

        out_dir = os.path.dirname(os.path.abspath(filepath))
        base = os.path.splitext(os.path.basename(filepath))[0]
        preview_path = os.path.join(out_dir, f'vision_preview_{base}.jpg')
        pf = _draw_vision_preview(img_bgr, result['people'], result['objects_coco'], preview_path)
        if pf:
            result['preview_filename'] = pf
    else:
        result['people'] = {'person_count': 0, 'summary_az': 'Kadr oxunmadı'}
        result['objects_coco'] = {'objects': [], 'total_objects': 0}
        result['ocr'] = {'words': [], 'lines': []}
        result['brands_logos'] = {'brands': []}
        result['documents'] = {'detected': False}
        result['scene'] = {'status': 'skipped'}

    result['motion'] = _analyze_motion(filepath)

    result['summary_az'] = _build_summary(result)
    if light:
        result['note'] = (
            'Render yüngül rejim: üz + əsas obyekt aşkarlanması. '
            'Tam CLIP/OCR/EasyOCR üçün lokal server istifadə edin.'
        )
    else:
        result['note'] = (
            'Yaş/cins/emosiya təxminidir — hüquqi identifikasiya üçün istifadə etməyin. '
            'COCO 80 sinif; brend aşkarlanması OCR+CLIP heuristikasidir.'
        )
    return result


def _build_summary(result: Dict) -> List[str]:
    lines = []
    p = result.get('people') or {}
    lines.append(p.get('summary_az', ''))
    oc = result.get('objects_coco') or {}
    if oc.get('total_objects'):
        classes = list((oc.get('summary') or {}).get('by_class', {}).keys())[:6]
        lines.append(f"Obyektlər ({oc['total_objects']}): {', '.join(classes)}")
    sc = result.get('scene') or {}
    if sc.get('primary'):
        lines.append(f"Məkan: {sc.get('summary_az')}")
    br = result.get('brands_logos') or {}
    if br.get('count'):
        lines.append(f"Markalar: {br.get('summary_az')}")
    doc = result.get('documents') or {}
    if doc.get('detected'):
        lines.append(f"Sənəd: {doc.get('summary_az')}")
    ocr = result.get('ocr') or {}
    if ocr.get('word_count'):
        lines.append(f"OCR: {ocr['word_count']} söz, {ocr.get('line_count', 0)} sətir")
    mot = result.get('motion') or {}
    if mot.get('applicable'):
        lines.append(mot.get('summary_az', ''))
    return [l for l in lines if l]
