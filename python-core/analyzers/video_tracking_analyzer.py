"""
Video Multi-Object Tracking — ByteTrack/BoT-SORT + üz re-id (SFace) + anonim rejim.
"""

import os
import re
import sys
import tempfile
import urllib.request

import cv2
import numpy as np

from utils.artifact_utils import path_to_filename
from analyzers.object_detection_analyzer import (
    get_yolo_model,
    COCO_LABELS_AZ,
    _class_category,
    CATEGORY_COLORS_BGR,
)

SFACE_MODEL = 'face_recognition_sface_2021dec.onnx'
SFACE_URLS = [
    'https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/'
    'face_recognition_sface/face_recognition_sface_2021dec.onnx',
    'https://github.com/opencv/opencv_zoo/raw/main/models/'
    'face_recognition_sface/face_recognition_sface_2021dec.onnx',
]
REID_COSINE_THRESHOLD = 0.363
LEGAL_WARNING = 'Yalnız icazəli şəxslər və rəsmi araşdırma məqsədilə istifadə edin.'

_sface_recognizer = None


def _models_dir():
    return os.path.join(os.path.dirname(__file__), '..', 'models')


def _ensure_sface_model():
    model_dir = _models_dir()
    os.makedirs(model_dir, exist_ok=True)
    path = os.path.join(model_dir, SFACE_MODEL)
    if os.path.isfile(path) and os.path.getsize(path) > 10000:
        return path
    print('  [i] SFace re-id modeli yüklənir...', file=sys.stderr)
    for url in SFACE_URLS:
        try:
            urllib.request.urlretrieve(url, path)
            if os.path.getsize(path) > 10000:
                return path
        except Exception:
            continue
    raise RuntimeError('SFace modeli yüklənmədi')


def _get_sface():
    global _sface_recognizer
    if _sface_recognizer is None:
        path = _ensure_sface_model()
        _sface_recognizer = cv2.FaceRecognizerSF.create(path, '')
    return _sface_recognizer


def _fmt_time(sec: float) -> str:
    sec = max(0.0, float(sec))
    m = int(sec // 60)
    s = int(sec % 60)
    return f'{m}:{s:02d}'


def _class_label_az(name):
    return COCO_LABELS_AZ.get(name, name.replace('_', ' ').title())


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


def _video_location(filepath):
    try:
        from extractors.video_extractor import VideoExtractor
        meta = VideoExtractor().extract(filepath, num_frames=1)
        container = meta.get('container') or {}
        tags = container.get('tags') or {}
        loc_raw = tags.get('location') or tags.get('com.apple.quicktime.location.ISO6709')
        lat, lon = None, None
        if loc_raw:
            coords = re.findall(r'[-+]?\d+\.?\d*', str(loc_raw))
            if len(coords) >= 2:
                lat, lon = float(coords[0]), float(coords[1])
        return {
            'latitude': lat,
            'longitude': lon,
            'source': 'ffprobe' if lat is not None else 'none',
            'creation_time': tags.get('creation_time'),
            'duration_sec': container.get('duration_sec'),
        }, meta
    except Exception as e:
        print(f'  [!] Video lokasiya: {e}', file=sys.stderr)
        return {'latitude': None, 'longitude': None, 'source': 'none'}, None


def _anonymize_bgr_frame(bgr, method='blur', strength=3, padding=0.18):
    """Kadr üzünü blur/pixelate — temp fayl vasitəsilə detect_faces."""
    from analyzers.face_privacy_analyzer import detect_faces, _padded_region

    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        tmp_path = tmp.name
    try:
        cv2.imwrite(tmp_path, bgr)
        det = detect_faces(tmp_path)
        faces = det.get('faces') or []
        if not faces:
            return bgr
        out = bgr.copy()
        h, w = out.shape[:2]
        strength = max(1, min(5, int(strength)))
        method = (method or 'blur').lower()
        for face in faces:
            x1, y1, x2, y2 = _padded_region(face['bbox'], w, h, padding)
            roi = out[y1:y2, x1:x2]
            if roi.size == 0:
                continue
            rh, rw = roi.shape[:2]
            if method == 'pixelate':
                block = max(8, min(32, 8 + strength * 4))
                small = cv2.resize(roi, (max(1, rw // block), max(1, rh // block)))
                out[y1:y2, x1:x2] = cv2.resize(small, (rw, rh), interpolation=cv2.INTER_NEAREST)
            else:
                k = strength * 6 + 1
                if k % 2 == 0:
                    k += 1
                out[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 0)
        return out
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _extract_face_embedding(bgr, yunet_detector):
    """YuNet üz → SFace embedding."""
    h, w = bgr.shape[:2]
    yunet_detector.setInputSize((w, h))
    _, faces = yunet_detector.detect(bgr)
    if faces is None or len(faces) == 0:
        return None, None
    face = faces[0]
    try:
        recognizer = _get_sface()
        aligned = recognizer.alignCrop(bgr, face)
        feature = recognizer.feature(aligned)
        bbox = {
            'x': int(face[0]),
            'y': int(face[1]),
            'w': int(face[2]),
            'h': int(face[3]),
        }
        return feature, bbox
    except Exception:
        return None, None


def _cluster_face_embeddings(records):
    """Greedy cosine clustering."""
    recognizer = _get_sface()
    clusters = []
    for rec in records:
        feat = rec['feature']
        best_id = None
        best_sim = -1.0
        for cl in clusters:
            sim = recognizer.match(feat, cl['centroid'], cv2.FaceRecognizerSF_FR_COSINE)
            if sim > best_sim:
                best_sim = sim
                best_id = cl['cluster_id']
        if best_sim >= REID_COSINE_THRESHOLD and best_id is not None:
            cl = next(c for c in clusters if c['cluster_id'] == best_id)
            cl['members'].append(rec)
            cl['centroid'] = (cl['centroid'] + feat) / 2.0
            rec['cluster_id'] = best_id
        else:
            cid = len(clusters) + 1
            clusters.append({'cluster_id': cid, 'centroid': feat.copy(), 'members': [rec]})
            rec['cluster_id'] = cid
    return clusters, records


def _run_mot_on_video(
    filepath,
    tracker='bytetrack',
    conf_threshold=0.35,
    sample_fps=2.0,
    max_duration_sec=120,
    anonymize_first=False,
    anon_method='blur',
    anon_strength=3,
):
    cap = cv2.VideoCapture(filepath)
    if not cap.isOpened():
        return None, 'Video açılmadı'

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = total_frames / fps if fps > 0 else 0
    max_sec = min(duration, max_duration_sec) if duration else max_duration_sec
    stride = max(1, int(round(fps / max(sample_fps, 0.5))))

    tracker_yaml = f'{tracker}.yaml' if not tracker.endswith('.yaml') else tracker
    if tracker_yaml not in ('bytetrack.yaml', 'botsort.yaml'):
        tracker_yaml = 'bytetrack.yaml'

    model = get_yolo_model()
    detections = []
    frame_idx = 0
    processed = 0
    preview_frame = None
    last_frame = None
    last_ts = None

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        ts = frame_idx / fps
        if ts > max_sec:
            break
        if frame_idx % stride != 0:
            frame_idx += 1
            continue

        if anonymize_first:
            frame = _anonymize_bgr_frame(frame, anon_method, anon_strength)

        try:
            results = model.track(
                frame,
                persist=True,
                conf=conf_threshold,
                tracker=tracker_yaml,
                verbose=False,
            )
        except Exception as e:
            cap.release()
            return None, f'Tracking xətası: {e}'

        if results and results[0].boxes is not None and results[0].boxes.id is not None:
            names = model.names
            boxes = results[0].boxes
            for i in range(len(boxes)):
                tid = int(boxes.id[i])
                cls_id = int(boxes.cls[i])
                conf = float(boxes.conf[i])
                x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                class_name = names.get(cls_id, str(cls_id))
                w, h = frame.shape[1], frame.shape[0]
                bbox = {
                    'x': int(max(0, x1)),
                    'y': int(max(0, y1)),
                    'w': int(min(w, x2) - max(0, x1)),
                    'h': int(min(h, y2) - max(0, y1)),
                }
                detections.append({
                    'frame_index': processed,
                    'timestamp_sec': round(ts, 2),
                    'track_id': tid,
                    'class_name': class_name,
                    'class_name_az': _class_label_az(class_name),
                    'category': _class_category(class_name),
                    'confidence': round(conf, 3),
                    'bbox': bbox,
                })

        if preview_frame is None and detections:
            preview_frame = frame.copy()
        last_frame = frame.copy()
        last_ts = ts

        processed += 1
        frame_idx += 1

    cap.release()
    if last_frame is not None:
        last_dets = [d for d in detections if abs(d['timestamp_sec'] - round(last_ts, 2)) < 0.01]
        preview_frame = _draw_tracks_on_frame(last_frame, last_dets)
    return {
        'fps': round(fps, 2),
        'duration_sec': round(duration, 2),
        'sample_fps': sample_fps,
        'frame_stride': stride,
        'frames_processed': processed,
        'detections': detections,
        'preview_frame': preview_frame,
    }, None


def _draw_tracks_on_frame(frame, recent_dets):
    for d in recent_dets:
        b = d['bbox']
        cat = d.get('category', 'Digər')
        color = CATEGORY_COLORS_BGR.get(cat, CATEGORY_COLORS_BGR['Digər'])
        x, y, w, h = b['x'], b['y'], b['w'], b['h']
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        label = f"#{d['track_id']} {d['class_name_az']}"
        cv2.putText(frame, label, (x, max(y - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    return frame


def _aggregate_tracks(detections, location_ctx):
    by_id = {}
    for d in detections:
        tid = d['track_id']
        if tid not in by_id:
            by_id[tid] = {
                'track_id': tid,
                'class_name': d['class_name'],
                'class_name_az': d['class_name_az'],
                'category': d['category'],
                'first_seen_sec': d['timestamp_sec'],
                'last_seen_sec': d['timestamp_sec'],
                'frame_count': 0,
                'confidences': [],
                'bboxes': [],
            }
        t = by_id[tid]
        t['last_seen_sec'] = max(t['last_seen_sec'], d['timestamp_sec'])
        t['first_seen_sec'] = min(t['first_seen_sec'], d['timestamp_sec'])
        t['frame_count'] += 1
        t['confidences'].append(d['confidence'])
        t['bboxes'].append(d['bbox'])

    tracks = []
    for t in by_id.values():
        dur = t['last_seen_sec'] - t['first_seen_sec']
        avg_conf = sum(t['confidences']) / len(t['confidences']) if t['confidences'] else 0
        summary = (
            f"{t['class_name_az']} #{t['track_id']}: "
            f"{_fmt_time(t['first_seen_sec'])} – {_fmt_time(t['last_seen_sec'])} "
            f"({t['frame_count']} kadr)"
        )
        loc_note = None
        if location_ctx.get('latitude') is not None:
            loc_note = (
                f"Video GPS: {location_ctx['latitude']:.5f}, {location_ctx['longitude']:.5f} "
                f"(statik kontekst)"
            )
        tracks.append({
            'track_id': t['track_id'],
            'class_name': t['class_name'],
            'class_name_az': t['class_name_az'],
            'category': t['category'],
            'first_seen_sec': t['first_seen_sec'],
            'last_seen_sec': t['last_seen_sec'],
            'first_seen_fmt': _fmt_time(t['first_seen_sec']),
            'last_seen_fmt': _fmt_time(t['last_seen_sec']),
            'duration_sec': round(dur, 2),
            'frame_count': t['frame_count'],
            'avg_confidence': round(avg_conf, 3),
            'summary_az': summary,
            'location_context': loc_note,
        })
    tracks.sort(key=lambda x: (-x['frame_count'], x['track_id']))
    return tracks


def _face_reid_pass(filepath, detections, sample_fps, max_duration_sec, anonymize_first):
    if anonymize_first:
        return [], ['Anonim rejim: üz re-id söndürülüb (blur sonrası identifikasiya yoxdur).']

    from analyzers.face_privacy_analyzer import _get_yunet

    cap = cv2.VideoCapture(filepath)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    stride = max(1, int(round(fps / max(sample_fps, 0.5))))
    yunet = _get_yunet()

    person_dets = [d for d in detections if d['class_name'] == 'person']
    if not person_dets:
        cap.release()
        return [], []

    target_ts = {round(d['timestamp_sec'], 1) for d in person_dets[::max(1, len(person_dets) // 20 + 1)]}
    records = []
    frame_idx = 0
    max_sec = max_duration_sec

    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        ts = round(frame_idx / fps, 1)
        if frame_idx / fps > max_sec:
            break
        if frame_idx % stride != 0:
            frame_idx += 1
            continue
        if ts not in target_ts:
            frame_idx += 1
            continue

        feat, fbbox = _extract_face_embedding(frame, yunet)
        if feat is not None:
            linked = []
            for d in person_dets:
                if abs(d['timestamp_sec'] - ts) < 0.5 and _bbox_iou(fbbox, d['bbox']) > 0.1:
                    linked.append(d['track_id'])
            records.append({
                'timestamp_sec': ts,
                'feature': feat,
                'linked_track_ids': list(set(linked)),
            })
        frame_idx += 1

    cap.release()
    if not records:
        return [], ['Üz re-id: kifayət qədər üz tapılmadı.']

    clusters, _ = _cluster_face_embeddings(records)
    face_clusters = []
    for cl in clusters:
        members = cl['members']
        tids = set()
        for m in members:
            tids.update(m.get('linked_track_ids') or [])
        times = [m['timestamp_sec'] for m in members]
        face_clusters.append({
            'cluster_id': cl['cluster_id'],
            'face_count': len(members),
            'linked_track_ids': sorted(tids),
            'first_seen_sec': min(times),
            'last_seen_sec': max(times),
            'first_seen_fmt': _fmt_time(min(times)),
            'last_seen_fmt': _fmt_time(max(times)),
            'summary_az': (
                f"Üz klasteri #{cl['cluster_id']}: "
                f"{_fmt_time(min(times))} – {_fmt_time(max(times))} "
                f"({len(members)} nümunə)"
            ),
        })
    return face_clusters, []


def analyze_video_tracking(
    filepath,
    tracker='bytetrack',
    conf_threshold=0.35,
    sample_fps=2.0,
    max_duration_sec=120,
    enable_face_reid=False,
    anonymize_first=False,
    anon_method='blur',
    anon_strength=3,
):
    print('  [i] Video MOT (ByteTrack/BoT-SORT) başlayır...', file=sys.stderr)

    if not os.path.isfile(filepath):
        return {'status': 'error', 'error': 'Fayl tapılmadı'}

    warnings = [LEGAL_WARNING]
    if anonymize_first and enable_face_reid:
        enable_face_reid = False
        warnings.append('Anonim rejim aktiv: üz re-id avtomatik söndürüldü.')

    location_ctx, _video_meta = _video_location(filepath)
    if location_ctx.get('latitude') is None:
        warnings.append('Video konteynerində GPS tapılmadı — lokasiya track konteksti boş qala bilər.')

    mot, err = _run_mot_on_video(
        filepath,
        tracker=tracker,
        conf_threshold=conf_threshold,
        sample_fps=sample_fps,
        max_duration_sec=max_duration_sec,
        anonymize_first=anonymize_first,
        anon_method=anon_method,
        anon_strength=anon_strength,
    )
    if err:
        return {'status': 'error', 'error': err}

    detections = mot['detections']
    tracks = _aggregate_tracks(detections, location_ctx)

    face_clusters = []
    if enable_face_reid:
        try:
            face_clusters, reid_warn = _face_reid_pass(
                filepath, detections, sample_fps, max_duration_sec, anonymize_first,
            )
            warnings.extend(reid_warn)
        except Exception as e:
            warnings.append(f'Üz re-id uğursuz: {e}')
            print(f'  [!] re-id: {e}', file=sys.stderr)

    artifacts = {}
    if mot.get('preview_frame') is not None:
        out_dir = os.path.dirname(os.path.abspath(filepath))
        base = os.path.splitext(os.path.basename(filepath))[0]
        preview_path = os.path.join(out_dir, f'track_preview_{base}.jpg')
        cv2.imwrite(preview_path, mot['preview_frame'], [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        artifacts['preview_image'] = path_to_filename(preview_path)

    return {
        'status': 'success' if tracks else 'no_tracks',
        'tracker': tracker.replace('.yaml', ''),
        'anonymized': bool(anonymize_first),
        'face_reid_enabled': bool(enable_face_reid and not anonymize_first),
        'video': {
            'duration_sec': mot['duration_sec'],
            'fps': mot['fps'],
            'sample_fps': sample_fps,
            'frames_processed': mot['frames_processed'],
            'frame_stride': mot['frame_stride'],
        },
        'location': location_ctx,
        'tracks': tracks,
        'face_clusters': face_clusters,
        'total_detections': len(detections),
        'unique_tracks': len(tracks),
        'artifacts': artifacts,
        'warnings': warnings,
        'note': (
            'COCO 80 sinif. Uzun videolarda sample_fps ilə nümunə kadrlar analiz olunur. '
            'Track ID-lər video daxilində sabitdir, kamera dəyişəndə sıfırlanır.'
        ),
    }
