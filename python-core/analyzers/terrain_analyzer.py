import cv2
import numpy as np
import os
import sys

def extract_skyline_and_terrain(filepath, output_dir=None):
    """
    Şəkildəki dağ və ya bina siluetlərini (skyline) çıxarır və 
    xüsusiyyətlərini (SIFT keypoints) yadda saxlayır.
    Bu xüsusiyyətlər gələcəkdə peyk bazası (Satellite Matching) ilə kəsişdirilə bilər.
    """
    try:
        if not output_dir:
            output_dir = os.path.dirname(filepath)
            
        terrain_filename = os.path.join(output_dir, f"terrain_{os.path.basename(filepath)}")
        
        img = cv2.imread(filepath)
        if img is None:
            return {"error": "Şəkli oxumaq mümkün olmadı"}
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 1. Edge Detection (Canny) - Siluetləri çıxarmaq
        edges = cv2.Canny(gray, 50, 150)
        
        # 2. SIFT Keypoints (Dağ və obyekt relyefinin xüsusi nöqtələri)
        sift = cv2.SIFT_create()
        keypoints, descriptors = sift.detectAndCompute(gray, None)
        
        # Xüsusiyyətləri vizuallaşdırmaq (nəticəni görmək üçün)
        img_with_edges = cv2.addWeighted(gray, 0.7, edges, 0.3, 0)
        img_with_kp = cv2.drawKeypoints(img_with_edges, keypoints, None, color=(0,255,0), flags=0)
        
        cv2.imwrite(terrain_filename, img_with_kp)
        
        # SIFT nöqtələrinin xülasəsi
        num_keypoints = len(keypoints) if keypoints is not None else 0
        
        return {
            "status": "success",
            "terrain_image_path": terrain_filename,
            "sift_keypoints_found": num_keypoints,
            "message": "Bu konturlar peyk axtarış bazasına göndərilə bilər."
        }
    except Exception as e:
        print(f"  [!] Terrain Analysis Error: {e}", file=sys.stderr)
        return {"error": str(e)}
