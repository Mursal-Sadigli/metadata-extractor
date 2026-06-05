"""
AI Analyzer

Mətn oxuma (OCR) və obyekt aşkarlama funksiyaları.
"""
import cv2
import easyocr
import numpy as np
import os
import sys

_reader = None

def get_reader():
    global _reader
    if _reader is None:
        print("  [i] İlk dəfə OCR modelləri yüklənir, gözləyin...", file=sys.stderr)
        # verbose=False disables the "Using CPU" print which breaks JSON
        _reader = easyocr.Reader(['az', 'en', 'tr'], gpu=False, verbose=False)
    return _reader

def get_object_detector():
    """MobileNet SSD modelini yükləyir və hazırlayır."""
    import urllib.request
    
    model_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(model_dir, exist_ok=True)
    
    prototxt_path = os.path.join(model_dir, 'MobileNetSSD_deploy.prototxt')
    caffemodel_path = os.path.join(model_dir, 'MobileNetSSD_deploy.caffemodel')
    
    if not os.path.exists(prototxt_path):
        print("  [i] Object Detection konfiqurasiyası yüklənir...", file=sys.stderr)
        urllib.request.urlretrieve("https://raw.githubusercontent.com/djmv/MobilNet_SSD_opencv/master/MobileNetSSD_deploy.prototxt", prototxt_path)
        
    if not os.path.exists(caffemodel_path):
        print("  [i] Object Detection modeli yüklənir (təxm. 22MB)...", file=sys.stderr)
        urllib.request.urlretrieve("https://raw.githubusercontent.com/djmv/MobilNet_SSD_opencv/master/MobileNetSSD_deploy.caffemodel", caffemodel_path)
        
    net = cv2.dnn.readNetFromCaffe(prototxt_path, caffemodel_path)
    return net

CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]

def detect_objects(filepath):
    """
    Şəkildəki obyektləri (Landmark/Brand OSINT əsası) tapır.
    """
    result = []
    try:
        net = get_object_detector()
        img = cv2.imread(filepath)
        if img is None:
            return result
            
        (h, w) = img.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 0.007843, (300, 300), 127.5)
        net.setInput(blob)
        detections = net.forward()
        
        for i in np.arange(0, detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.5:
                idx = int(detections[0, 0, i, 1])
                if idx < len(CLASSES):
                    label = CLASSES[idx]
                    result.append({"object": label, "confidence": float(confidence)})
    except Exception as e:
        print(f"  [!] Object Detection Error: {e}", file=sys.stderr)
        
    return result

def analyze_image_ai(filepath):
    """Şəkli AI ilə analiz edir: mətn oxuma və obyekt aşkarlama."""
    result = {
        'extracted_text': []
    }
    
    if not os.path.exists(filepath):
        return result
        
    print("  [i] AI Analizi aparılır...", file=sys.stderr)

    # 1. Mətn Oxuma (OCR)
    try:
        reader = get_reader()
        text_results = reader.readtext(filepath, detail=0)
        valid_texts = [t for t in text_results if len(t.strip()) > 2]
        if valid_texts:
            result['extracted_text'] = valid_texts
            print(f"  [i] Tapılan mətn sətirləri: {len(valid_texts)}", file=sys.stderr)
    except Exception as e:
        print(f"  [!] OCR xətası: {e}", file=sys.stderr)
        
    # 2. Object Detection (Landmark/Brand/General)
    objects = detect_objects(filepath)
    if objects:
        result['detected_objects'] = objects
        print(f"  [i] Tapılan obyektlər: {len(objects)}", file=sys.stderr)
        
    return result
