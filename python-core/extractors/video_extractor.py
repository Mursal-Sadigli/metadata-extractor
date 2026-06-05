"""Video metadata və frame çıxarışı (FFmpeg / OpenCV fallback)."""

import json
import os
import subprocess
import sys

from extractors.base import BaseExtractor
from extractors.image_extractor import ImageExtractor
from utils.artifact_utils import path_to_filename


def _ffmpeg_available():
    try:
        subprocess.run(['ffprobe', '-version'], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


class VideoExtractor(BaseExtractor):
    def extract(self, filepath, num_frames=3):
        result = {
            'file_info': self.get_file_info(filepath),
            'type': 'video',
            'container': None,
            'audio': None,
            'frames': [],
            'warnings': [],
        }
        output_dir = os.path.dirname(filepath)
        base = os.path.splitext(os.path.basename(filepath))[0]

        if _ffmpeg_available():
            result['container'] = self._ffprobe(filepath)
            result['frames'] = self._extract_frames_ffmpeg(filepath, output_dir, base, num_frames)
        else:
            result['warnings'].append('FFmpeg tapılmadı — yalnız OpenCV ilə bir frame çıxarılır.')
            result['frames'] = self._extract_frame_opencv(filepath, output_dir, base)

        img_ext = ImageExtractor()
        for fr in result['frames']:
            fp = fr.get('path')
            if fp and os.path.isfile(fp):
                meta = img_ext.extract(fp)
                fr['exif'] = meta.get('exif')
                fr['location'] = meta.get('location')
                fr['filename'] = path_to_filename(fp)

        return result

    def _ffprobe(self, filepath):
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', filepath,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                return {'error': proc.stderr or 'ffprobe failed'}
            data = json.loads(proc.stdout)
            fmt = data.get('format', {})
            streams = data.get('streams', [])
            video_s = next((s for s in streams if s.get('codec_type') == 'video'), {})
            audio_s = next((s for s in streams if s.get('codec_type') == 'audio'), {})
            return {
                'duration_sec': float(fmt.get('duration', 0) or 0),
                'size_bytes': int(fmt.get('size', 0) or 0),
                'format_name': fmt.get('format_name'),
                'tags': fmt.get('tags', {}),
                'video_codec': video_s.get('codec_name'),
                'width': video_s.get('width'),
                'height': video_s.get('height'),
                'audio_codec': audio_s.get('codec_name'),
            }
        except Exception as e:
            return {'error': str(e)}

    def _extract_frames_ffmpeg(self, filepath, output_dir, base, num_frames):
        duration = 1.0
        try:
            probe = self._ffprobe(filepath)
            duration = max(0.1, float(probe.get('duration_sec', 1)))
        except Exception:
            pass

        frames = []
        points = [0.05]
        if num_frames >= 2:
            points.append(0.5)
        if num_frames >= 3:
            points.append(0.92)

        for i, pct in enumerate(points[:num_frames]):
            t = duration * pct
            out_name = f'frame_{i}_{base}.jpg'
            out_path = os.path.join(output_dir, out_name)
            cmd = [
                'ffmpeg', '-y', '-ss', str(t), '-i', filepath,
                '-frames:v', '1', '-q:v', '2', out_path,
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=45)
                if os.path.isfile(out_path):
                    frames.append({
                        'index': i,
                        'timestamp_sec': round(t, 2),
                        'path': out_path,
                        'filename': out_name,
                    })
            except Exception as e:
                print(f'  [!] frame {i}: {e}', file=sys.stderr)
        return frames

    def _extract_frame_opencv(self, filepath, output_dir, base):
        try:
            import cv2
            cap = cv2.VideoCapture(filepath)
            ok, frame = cap.read()
            cap.release()
            if not ok:
                return []
            out_name = f'frame_0_{base}.jpg'
            out_path = os.path.join(output_dir, out_name)
            cv2.imwrite(out_path, frame)
            return [{'index': 0, 'timestamp_sec': 0, 'path': out_path, 'filename': out_name}]
        except Exception as e:
            print(f'  [!] OpenCV video: {e}', file=sys.stderr)
            return []
