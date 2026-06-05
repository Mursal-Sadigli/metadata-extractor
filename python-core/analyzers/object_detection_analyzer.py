"""
COCO + YOLO-World obyekt aşkarlanması — çoxlu bina/obyekt, yüksək dəqiqlik.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from utils.artifact_utils import path_to_filename

MODEL_NAME = os.environ.get('YOLO_MODEL', 'yolov8m.pt')
WORLD_MODEL_NAME = os.environ.get('YOLO_WORLD_MODEL', 'yolov8m-worldv2.pt')
USE_WORLD = os.environ.get('YOLO_WORLD', '1').strip().lower() not in ('0', 'false', 'no')
USE_TILED = os.environ.get('YOLO_TILED', '1').strip().lower() not in ('0', 'false', 'no')
USE_MULTISCALE = os.environ.get('YOLO_MULTISCALE', '1').strip().lower() not in ('0', 'false', 'no')
SCENE_ONLY = os.environ.get('YOLO_SCENE_ONLY', '1').strip().lower() not in ('0', 'false', 'no')

CONF_DEFAULT = 0.15
IOU_DEFAULT = 0.35
IMGSZ_PRIMARY = 1280
IMGSZ_SECONDARY = 960
TILE_SIZE = 512
TILE_OVERLAP = 0.32
MAX_DETECTIONS = 500
MERGE_IOU_SAME = 0.48
MERGE_IOU_STRUCTURE_DUP = 0.72

_yolo_model = None
_world_model = None

COCO_CLASSES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat', 'dog',
    'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella',
    'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball', 'kite',
    'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket', 'bottle',
    'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich',
    'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
    'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
    'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book',
    'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush',
]

OPEN_VOCAB_CLASSES = [
    'building', 'house', 'apartment building', 'office building', 'skyscraper', 'high-rise building',
    'tower', 'church', 'mosque', 'school building', 'hospital', 'factory', 'warehouse', 'barn',
    'roof', 'window', 'door', 'balcony', 'wall', 'chimney', 'bridge', 'ruins',
    'tree', 'palm tree', 'pine tree', 'oak tree', 'bush', 'shrub', 'grass', 'forest', 'flower',
    'utility pole', 'telephone pole', 'electric pole', 'street light', 'lamp post', 'light pole',
    'traffic light', 'traffic sign', 'road sign', 'billboard', 'sign', 'bus stop', 'fence', 'gate',
    'bench', 'mailbox', 'fire hydrant', 'parking meter', 'power line',
    'car', 'sedan', 'suv', 'truck', 'pickup truck', 'bus', 'minibus', 'van', 'taxi',
    'motorcycle', 'scooter', 'bicycle', 'ambulance', 'police car', 'train', 'tram',
    'airplane', 'helicopter', 'boat', 'ship',
    'person', 'man', 'woman', 'child', 'pedestrian', 'people',
    'dog', 'cat', 'bird', 'horse', 'cow',
    'road', 'street', 'sidewalk', 'crosswalk', 'parking lot',
]

COCO_LABELS_AZ = {
    'person': 'İnsan', 'bicycle': 'Velosiped', 'car': 'Avtomobil', 'motorcycle': 'Motosikl',
    'airplane': 'Təyyarə', 'bus': 'Avtobus', 'train': 'Qatar', 'truck': 'Yük maşını',
    'boat': 'Gəmi/qayıq', 'traffic light': 'Svetafor', 'fire hydrant': 'Yanğın hidrantı',
    'stop sign': 'Stop işarəsi', 'parking meter': 'Parkomat', 'bench': 'Skameyka',
    'bird': 'Quş', 'cat': 'Pişik', 'dog': 'İt', 'horse': 'At', 'sheep': 'Qoyun',
    'cow': 'İnək', 'elephant': 'Fil', 'bear': 'Ayı', 'zebra': 'Zebra', 'giraffe': 'Zürafə',
    'backpack': 'Sırt çantası', 'umbrella': 'Çətir', 'handbag': 'Çanta', 'tie': 'Qalstuk',
    'suitcase': 'Çamadan', 'bottle': 'Şüşə', 'wine glass': 'Şərab stəkanı', 'cup': 'Fincan',
    'fork': 'Çəngəl', 'knife': 'Bıçaq', 'spoon': 'Qaşıq', 'bowl': 'Qabaq',
    'chair': 'Stul', 'couch': 'Divan', 'potted plant': 'Bitki (saksı)', 'bed': 'Yataq',
    'dining table': 'Yemək masası', 'toilet': 'Tualet', 'tv': 'Televizor', 'laptop': 'Noutbuk',
    'mouse': 'Siçan', 'remote': 'Pult', 'keyboard': 'Klaviatura', 'cell phone': 'Mobil telefon',
    'microwave': 'Mikrodalğalı soba', 'oven': 'Soba', 'refrigerator': 'Soyuducu',
    'book': 'Kitab', 'clock': 'Saat', 'vase': 'Vaza', 'scissors': 'Qayçı',
}

WORLD_LABELS_AZ = {
    'building': 'Bina', 'house': 'Ev', 'apartment building': 'Yaşayış binası',
    'office building': 'Ofis binası', 'skyscraper': 'Göydələn', 'high-rise building': 'Hündür bina',
    'tower': 'Qüllə', 'church': 'Kilsə', 'mosque': 'Məscid', 'school building': 'Məktəb',
    'hospital': 'Xəstəxana', 'factory': 'Zavod', 'warehouse': 'Anbar', 'barn': 'Anbar',
    'roof': 'Dam', 'window': 'Pəncərə', 'door': 'Qapı', 'balcony': 'Balkon', 'wall': 'Divar',
    'chimney': 'Baca', 'bridge': 'Körpü', 'ruins': 'Xarabalıq',
    'tree': 'Ağac', 'palm tree': 'Palma', 'pine tree': 'Şam ağacı', 'oak tree': 'Palıd ağacı',
    'bush': 'Kol', 'shrub': 'Kol', 'grass': 'Ot', 'forest': 'Meşə', 'flower': 'Gül',
    'utility pole': 'Dirək (kommunikasiya)', 'telephone pole': 'Telefon dirəyi',
    'electric pole': 'Elektrik dirəyi', 'street light': 'Küçə işığı', 'lamp post': 'İşıq dirəyi',
    'light pole': 'İşıq dirəyi', 'traffic light': 'Svetafor', 'traffic sign': 'Yol işarəsi',
    'road sign': 'Yol işarəsi', 'billboard': 'Reklam lövhəsi', 'sign': 'İşarə',
    'bus stop': 'Avtobus dayanacağı', 'fence': 'Hasar', 'gate': 'Qapı (hasar)',
    'bench': 'Skameyka', 'mailbox': 'Poçt qutusu', 'fire hydrant': 'Yanğın hidrantı',
    'parking meter': 'Parkomat', 'power line': 'Elektrik xətti',
    'car': 'Avtomobil', 'sedan': 'Sedan', 'suv': 'SUV', 'truck': 'Yük maşını',
    'pickup truck': 'Pikap', 'bus': 'Avtobus', 'minibus': 'Minibus', 'van': 'Furqon',
    'taxi': 'Taksi', 'motorcycle': 'Motosikl', 'scooter': 'Skuter', 'bicycle': 'Velosiped',
    'ambulance': 'Təcili yardım', 'police car': 'Polis maşını', 'train': 'Qatar', 'tram': 'Tramvay',
    'airplane': 'Təyyarə', 'helicopter': 'Helikopter', 'boat': 'Gəmi', 'ship': 'Gəmi',
    'person': 'İnsan', 'man': 'Kişi', 'woman': 'Qadın', 'child': 'Uşaq', 'pedestrian': 'Piyada',
    'people': 'İnsanlar', 'umbrella': 'Çətir', 'chair': 'Stul', 'table': 'Masa',
    'laptop': 'Noutbuk', 'cell phone': 'Telefon', 'backpack': 'Sırt çantası', 'handbag': 'Çanta',
    'dog': 'İt', 'cat': 'Pişik', 'bird': 'Quş', 'horse': 'At', 'cow': 'İnək',
    'road': 'Yol', 'street': 'Küçə', 'sidewalk': 'Səki', 'crosswalk': 'Piyada keçidi',
    'parking lot': 'Parkinq',
}

STRUCTURE_CLASSES = frozenset({
    'building', 'house', 'apartment building', 'office building', 'skyscraper',
    'high-rise building', 'tower', 'church', 'mosque', 'school building', 'hospital',
    'factory', 'warehouse', 'barn', 'roof', 'window', 'door', 'balcony', 'wall', 'chimney', 'ruins',
})

POLE_CLASSES = frozenset({
    'utility pole', 'telephone pole', 'electric pole', 'street light', 'lamp post',
    'light pole', 'traffic light', 'fire hydrant', 'parking meter', 'power line',
})

# Mənzərə/OSINT: qalstuk, yemək, ev əşyası və s. göstərilmir
EXCLUDED_CLASSES = frozenset({
    'tie', 'handbag', 'suitcase', 'backpack', 'umbrella',
    'fork', 'knife', 'spoon', 'bowl', 'cup', 'wine glass', 'bottle',
    'banana', 'apple', 'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake',
    'toothbrush', 'hair drier', 'scissors', 'teddy bear', 'book', 'clock', 'vase', 'remote', 'mouse',
    'keyboard', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'bed', 'dining table', 'toilet',
    'tv', 'laptop', 'cell phone', 'couch', 'chair', 'table',
    'frisbee', 'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove',
    'skateboard', 'surfboard', 'tennis racket',
    'window', 'door', 'balcony', 'chimney', 'roof', 'wall',
})

SCENE_CATEGORIES = frozenset({
    'İnsan', 'Nəqliyyat', 'Heyvan', 'Bitki',
    'Bina və struktur', 'Dirək və infra', 'Yol və mühit',
})

ALWAYS_ALLOWED_CLASSES = frozenset({
    'person', 'man', 'woman', 'child', 'pedestrian', 'people',
    'bench', 'potted plant',
})

CATEGORY_AZ = {
    'person': 'İnsan',
    'bicycle': 'Nəqliyyat', 'car': 'Nəqliyyat', 'motorcycle': 'Nəqliyyat',
    'airplane': 'Nəqliyyat', 'bus': 'Nəqliyyat', 'train': 'Nəqliyyat',
    'truck': 'Nəqliyyat', 'boat': 'Nəqliyyat', 'van': 'Nəqliyyat', 'helicopter': 'Nəqliyyat',
    'bird': 'Heyvan', 'cat': 'Heyvan', 'dog': 'Heyvan',
    'chair': 'Mebel', 'couch': 'Mebel', 'bed': 'Mebel', 'dining table': 'Mebel',
    'bench': 'Mebel', 'table': 'Mebel', 'potted plant': 'Bitki', 'tree': 'Bitki',
    'palm tree': 'Bitki', 'bush': 'Bitki',
    'laptop': 'Elektronika', 'tv': 'Elektronika', 'cell phone': 'Elektronika',
    'building': 'Bina və struktur', 'house': 'Bina və struktur', 'skyscraper': 'Bina və struktur',
    'tower': 'Bina və struktur', 'church': 'Bina və struktur', 'mosque': 'Bina və struktur',
    'bridge': 'Bina və struktur', 'factory': 'Bina və struktur', 'barn': 'Bina və struktur',
    'roof': 'Bina və struktur', 'window': 'Bina və struktur', 'door': 'Bina və struktur',
    'wall': 'Bina və struktur',
    'traffic light': 'Dirək və infra', 'fire hydrant': 'Dirək və infra',
    'stop sign': 'Dirək və infra', 'parking meter': 'Dirək və infra', 'sign': 'Dirək və infra',
    'billboard': 'Dirək və infra', 'street light': 'Dirək və infra', 'lamp post': 'Dirək və infra',
    'fence': 'Dirək və infra',
    'utility pole': 'Dirək və infra', 'telephone pole': 'Dirək və infra',
    'electric pole': 'Dirək və infra', 'light pole': 'Dirək və infra',
    'traffic sign': 'Dirək və infra', 'road sign': 'Dirək və infra', 'power line': 'Dirək və infra',
    'road': 'Yol və mühit', 'street': 'Yol və mühit', 'sidewalk': 'Yol və mühit',
    'crosswalk': 'Yol və mühit', 'parking lot': 'Yol və mühit',
    'sedan': 'Nəqliyyat', 'suv': 'Nəqliyyat', 'pickup truck': 'Nəqliyyat',
    'minibus': 'Nəqliyyat', 'taxi': 'Nəqliyyat', 'scooter': 'Nəqliyyat',
    'ambulance': 'Nəqliyyat', 'police car': 'Nəqliyyat', 'tram': 'Nəqliyyat', 'ship': 'Nəqliyyat',
    'man': 'İnsan', 'woman': 'İnsan', 'child': 'İnsan', 'pedestrian': 'İnsan', 'people': 'İnsan',
    'pine tree': 'Bitki', 'oak tree': 'Bitki', 'shrub': 'Bitki', 'grass': 'Bitki', 'forest': 'Bitki',
    'flower': 'Bitki',
}

CATEGORY_COLORS_BGR = {
    'İnsan': (236, 72, 153),
    'Nəqliyyat': (59, 130, 246),
    'Heyvan': (34, 197, 94),
    'Mebel': (168, 85, 247),
    'Elektronika': (34, 211, 238),
    'Bitki': (74, 222, 128),
    'Bina və struktur': (249, 115, 22),
    'Dirək və infra': (234, 179, 8),
    'Yol və mühit': (100, 116, 139),
    'İnfrastruktur': (148, 163, 184),
    'Əşya': (203, 213, 225),
    'Digər': (156, 163, 175),
}


def _models_dir():
    return os.path.join(os.path.dirname(__file__), '..', 'models')


def _load_yolo(weights: str):
    from ultralytics import YOLO
    model_dir = _models_dir()
    os.makedirs(model_dir, exist_ok=True)
    local = os.path.join(model_dir, os.path.basename(weights))
    if os.path.isfile(local):
        return YOLO(local)
    m = YOLO(weights)
    try:
        import shutil
        src = getattr(m, 'ckpt_path', None) or weights
        if os.path.isfile(src) and not os.path.isfile(local):
            shutil.copy2(src, local)
    except Exception:
        pass
    return m


def get_yolo_model():
    global _yolo_model
    if _yolo_model is not None:
        return _yolo_model
    print(f'  [i] YOLO (COCO) yüklənir: {MODEL_NAME}...', file=sys.stderr)
    _yolo_model = _load_yolo(MODEL_NAME)
    return _yolo_model


def _get_yolo_model():
    return get_yolo_model()


def get_world_model():
    global _world_model
    if _world_model is not None:
        return _world_model
    if not USE_WORLD:
        return None
    try:
        print(f'  [i] YOLO-World yüklənir: {WORLD_MODEL_NAME}...', file=sys.stderr)
        _world_model = _load_yolo(WORLD_MODEL_NAME)
        _world_model.set_classes(OPEN_VOCAB_CLASSES)
    except Exception as e:
        print(f'  [!] YOLO-World yüklənmədi: {e}', file=sys.stderr)
        _world_model = None
    return _world_model


def _class_label_az(class_name: str, source: str = 'coco') -> str:
    if source == 'world':
        return WORLD_LABELS_AZ.get(class_name, class_name.replace('_', ' ').title())
    return COCO_LABELS_AZ.get(class_name, class_name.replace('_', ' ').title())


def _class_category(class_name: str) -> str:
    if class_name in STRUCTURE_CLASSES:
        return 'Bina və struktur'
    if class_name in POLE_CLASSES:
        return 'Dirək və infra'
    if class_name in CATEGORY_AZ:
        return CATEGORY_AZ[class_name]
    return 'Digər'


def _is_scene_relevant(class_name: str, category: str) -> bool:
    """Kiçik/ev əşyaları (qalstuk, çəngəl və s.) süzülür."""
    if not SCENE_ONLY:
        return True
    if class_name in EXCLUDED_CLASSES:
        return False
    if class_name in ALWAYS_ALLOWED_CLASSES:
        return True
    return category in SCENE_CATEGORIES


def _bbox_from_xyxy(xyxy, img_w: int, img_h: int, offset_x: int = 0, offset_y: int = 0) -> Dict[str, int]:
    x1, y1, x2, y2 = [int(v) for v in xyxy]
    x1 += offset_x
    y1 += offset_y
    x2 += offset_x
    y2 += offset_y
    x1 = max(0, min(x1, img_w - 1))
    y1 = max(0, min(y1, img_h - 1))
    x2 = max(x1 + 1, min(x2, img_w))
    y2 = max(y1 + 1, min(y2, img_h))
    w, h = x2 - x1, y2 - y1
    return {'x': x1, 'y': y1, 'w': w, 'h': h}


def _bbox_iou(a: Dict[str, int], b: Dict[str, int]) -> float:
    ax2, ay2 = a['x'] + a['w'], a['y'] + a['h']
    bx2, by2 = b['x'] + b['w'], b['y'] + b['h']
    ix1, iy1 = max(a['x'], b['x']), max(a['y'], b['y'])
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    union = a['w'] * a['h'] + b['w'] * b['h'] - inter
    return inter / union if union > 0 else 0.0


def _make_object(
    *,
    class_name: str,
    confidence: float,
    bbox: Dict[str, int],
    img_area: int,
    source: str,
    cls_id: int = -1,
) -> Dict[str, Any]:
    area_pct = round(bbox['w'] * bbox['h'] / img_area * 100, 3)
    return {
        'class_id': cls_id,
        'class_name': class_name,
        'class_name_az': _class_label_az(class_name, source),
        'category': _class_category(class_name),
        'confidence': round(confidence, 4),
        'bbox': bbox,
        'area_percent': area_pct,
        'center': {
            'x': round(bbox['x'] + bbox['w'] / 2, 1),
            'y': round(bbox['y'] + bbox['h'] / 2, 1),
        },
        'detector': source,
    }


def _boxes_from_result(result, img_w: int, img_h: int, names: Dict, source: str, offset_x: int = 0, offset_y: int = 0) -> List[Dict[str, Any]]:
    img_area = max(img_w * img_h, 1)
    out: List[Dict[str, Any]] = []
    if result.boxes is None:
        return out
    for box in result.boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        name = names.get(cls_id, f'class_{cls_id}')
        if isinstance(name, str):
            class_name = name.lower().strip()
        else:
            class_name = str(name)
        bbox = _bbox_from_xyxy(box.xyxy[0].tolist(), img_w, img_h, offset_x, offset_y)
        if bbox['w'] < 4 or bbox['h'] < 4:
            continue
        cat = _class_category(class_name)
        if not _is_scene_relevant(class_name, cat):
            continue
        out.append(_make_object(
            class_name=class_name,
            confidence=conf,
            bbox=bbox,
            img_area=img_area,
            source=source,
            cls_id=cls_id,
        ))
    return out


def _predict_image(model, img_bgr: np.ndarray, conf: float, iou: float, imgsz: int) -> List[Any]:
    return model.predict(
        source=img_bgr,
        conf=conf,
        iou=iou,
        verbose=False,
        max_det=MAX_DETECTIONS,
        imgsz=imgsz,
    )


def _detect_coco_full(model, img_bgr: np.ndarray, img_w: int, img_h: int, conf: float, iou: float, imgsz: int) -> List[Dict[str, Any]]:
    names = model.names if hasattr(model, 'names') else {}
    objects: List[Dict[str, Any]] = []
    for result in _predict_image(model, img_bgr, conf, iou, imgsz):
        objects.extend(_boxes_from_result(result, img_w, img_h, names, 'coco'))
    return objects


def _detect_tiled(
    model,
    img_bgr: np.ndarray,
    img_w: int,
    img_h: int,
    conf: float,
    iou: float,
    imgsz: int,
    source_tag: str = 'tile',
) -> List[Dict[str, Any]]:
    """Kiçik obyektlər (dirək, ağac, uzaq avtomobil) üçün sıx parça skanı."""
    names = model.names if hasattr(model, 'names') else {}
    step = max(64, int(TILE_SIZE * (1 - TILE_OVERLAP)))
    objects: List[Dict[str, Any]] = []
    for y0 in range(0, img_h, step):
        for x0 in range(0, img_w, step):
            y1 = min(y0 + TILE_SIZE, img_h)
            x1 = min(x0 + TILE_SIZE, img_w)
            if y1 - y0 < 40 or x1 - x0 < 40:
                continue
            crop = img_bgr[y0:y1, x0:x1]
            tile_imgsz = min(imgsz, max(y1 - y0, x1 - x0, 320))
            try:
                for result in _predict_image(model, crop, conf, iou, tile_imgsz):
                    objects.extend(_boxes_from_result(
                        result, img_w, img_h, names, source_tag, x0, y0,
                    ))
            except Exception:
                continue
    return objects


def _detect_world(model, img_bgr: np.ndarray, img_w: int, img_h: int, conf: float, iou: float, imgsz: int) -> List[Dict[str, Any]]:
    names = model.names if hasattr(model, 'names') else {}
    objects: List[Dict[str, Any]] = []
    wconf = max(0.10, conf - 0.04)
    try:
        for result in _predict_image(model, img_bgr, wconf, iou, imgsz):
            objects.extend(_boxes_from_result(result, img_w, img_h, names, 'world'))
    except Exception as e:
        print(f'  [!] YOLO-World predict: {e}', file=sys.stderr)
    return objects


def _should_merge(a: Dict[str, Any], b: Dict[str, Any], iou: float) -> bool:
    """Yalnız eyni obyektin təkrar deteksiyası birləşsin; 4-5 ayrı bina ayrı qalsın."""
    if iou < MERGE_IOU_SAME:
        return False
    if a['class_name'] == b['class_name']:
        return True
    if a['class_name'] in STRUCTURE_CLASSES and b['class_name'] in STRUCTURE_CLASSES:
        return iou >= MERGE_IOU_STRUCTURE_DUP
    if a['class_name'] in POLE_CLASSES and b['class_name'] in POLE_CLASSES:
        return iou >= MERGE_IOU_STRUCTURE_DUP
    return False


def _merge_objects(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = sorted(candidates, key=lambda o: -o['confidence'])
    merged: List[Dict[str, Any]] = []
    for obj in candidates:
        replaced = False
        for i, kept in enumerate(merged):
            iou = _bbox_iou(obj['bbox'], kept['bbox'])
            if not _should_merge(obj, kept, iou):
                continue
            if obj['confidence'] > kept['confidence']:
                merged[i] = obj
            replaced = True
            break
        if not replaced:
            merged.append(obj)
    return merged


def _needs_tiled(img_w: int, img_h: int) -> bool:
    return USE_TILED and max(img_w, img_h) > 720


def detect_objects(
    filepath: str,
    conf_threshold: float = CONF_DEFAULT,
    iou_threshold: float = IOU_DEFAULT,
    imgsz: int = IMGSZ_PRIMARY,
) -> Dict[str, Any]:
    """COCO + YOLO-World + çoxölçülü + parça skanı — ağac, dirək, bina, insan, avtomobil."""
    if not os.path.isfile(filepath):
        return {'status': 'error', 'error': 'Fayl tapılmadı', 'objects': [], 'total_objects': 0}

    img = cv2.imread(filepath)
    if img is None:
        return {'status': 'error', 'error': 'Şəkil oxunmadı', 'objects': [], 'total_objects': 0}

    img_h, img_w = img.shape[:2]
    conf = max(0.08, min(0.9, float(conf_threshold)))
    iou = max(0.2, min(0.7, float(iou_threshold)))
    imgsz = max(640, min(1920, int(imgsz)))

    all_candidates: List[Dict[str, Any]] = []
    detectors_used: List[str] = []

    try:
        coco = get_yolo_model()
        scales = [imgsz]
        if USE_MULTISCALE and imgsz >= IMGSZ_PRIMARY:
            scales.append(IMGSZ_SECONDARY)

        for si, scale in enumerate(scales):
            c = max(0.10, conf - (0.02 if si else 0))
            all_candidates.extend(_detect_coco_full(coco, img, img_w, img_h, c, iou, scale))
        detectors_used.append('coco')
        if len(scales) > 1:
            detectors_used.append('multiscale')

        if _needs_tiled(img_w, img_h):
            tc = max(0.10, conf - 0.05)
            all_candidates.extend(_detect_tiled(coco, img, img_w, img_h, tc, iou, IMGSZ_PRIMARY, 'coco_tile'))
            detectors_used.append('coco_tile')

        world = get_world_model()
        if world is not None:
            all_candidates.extend(_detect_world(world, img, img_w, img_h, conf, iou, IMGSZ_PRIMARY))
            detectors_used.append('world')
            if _needs_tiled(img_w, img_h):
                all_candidates.extend(_detect_tiled(
                    world, img, img_w, img_h, max(0.08, conf - 0.06), iou,
                    IMGSZ_PRIMARY, 'world_tile',
                ))
                detectors_used.append('world_tile')
    except ImportError as e:
        return {'status': 'error', 'error': str(e), 'objects': [], 'total_objects': 0}
    except Exception as e:
        print(f'  [!] Obyekt aşkarlanması: {e}', file=sys.stderr)
        return {'status': 'error', 'error': str(e), 'objects': [], 'total_objects': 0}

    objects = _merge_objects(all_candidates)
    objects = [o for o in objects if _is_scene_relevant(o['class_name'], o['category'])]
    objects.sort(key=lambda o: (-o['confidence'], -o.get('area_percent', 0)))
    for i, obj in enumerate(objects):
        obj['id'] = i + 1

    by_class: Dict[str, int] = {}
    by_category: Dict[str, int] = {}
    for obj in objects:
        key = obj['class_name_az']
        by_class[key] = by_class.get(key, 0) + 1
        cat = obj['category']
        by_category[cat] = by_category.get(cat, 0) + 1

    model_label = MODEL_NAME.replace('.pt', '')
    world_label = WORLD_MODEL_NAME.replace('.pt', '') if 'world' in detectors_used else None

    return {
        'status': 'success',
        'model': model_label,
        'world_model': world_label,
        'dataset': 'COCO 80 + YOLO-World (bina/ev və s.)',
        'detectors': detectors_used,
        'image_size': {'width': img_w, 'height': img_h},
        'total_objects': len(objects),
        'unique_classes': len({o['class_name'] for o in objects}),
        'objects': objects,
        'summary': {
            'by_class': by_class,
            'by_category': by_category,
            'class_list': sorted({o['class_name'] for o in objects}),
        },
        'settings': {
            'confidence': conf,
            'iou': iou,
            'imgsz': imgsz,
            'tiled': _needs_tiled(img_w, img_h),
            'scene_only': SCENE_ONLY,
        },
        'note': (
            f'{model_label} + YOLO-World — mənzərə obyektləri (insan, nəqliyyat, bina, ağac, dirək). '
            'Qalstuk və ev əşyaları süzülür.'
        ),
    }


def _draw_objects_preview(filepath: str, objects: List[Dict[str, Any]]) -> Optional[str]:
    if not objects:
        return None
    img = cv2.imread(filepath)
    if img is None:
        return None

    out = img.copy()
    for obj in objects:
        b = obj['bbox']
        cat = obj.get('category', 'Digər')
        color = CATEGORY_COLORS_BGR.get(cat, CATEGORY_COLORS_BGR['Digər'])
        x, y, w, h = b['x'], b['y'], b['w'], b['h']
        cv2.rectangle(out, (x, y), (x + w, y + h), color, 2, lineType=cv2.LINE_AA)
        label = f"#{obj['id']} {obj['class_name_az']} {int(obj['confidence']*100)}%"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        ty = max(y - 4, th + 4)
        cv2.rectangle(out, (x, ty - th - 4), (x + tw + 4, ty + 2), (15, 23, 42), -1)
        cv2.putText(out, label, (x + 2, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

    out_dir = os.path.dirname(os.path.abspath(filepath))
    base = os.path.basename(filepath)
    name, _ext = os.path.splitext(base)
    out_path = os.path.join(out_dir, f'objects_{name}.jpg')
    cv2.imwrite(out_path, out, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    return path_to_filename(out_path)


def analyze_object_detection(filepath: str, conf_threshold: float = CONF_DEFAULT) -> Dict[str, Any]:
    detection = detect_objects(filepath, conf_threshold=conf_threshold)
    result = {
        'original_filename': path_to_filename(filepath),
        'object_detection': detection,
        'artifacts': [],
    }
    if detection.get('status') == 'success' and detection.get('objects'):
        preview = _draw_objects_preview(filepath, detection['objects'])
        if preview:
            detection['preview_filename'] = preview
            result['artifacts'].append(preview)
    return result
