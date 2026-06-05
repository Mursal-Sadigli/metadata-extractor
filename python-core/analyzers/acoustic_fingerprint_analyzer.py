"""Akustik spektr analizi və barmaq izi (Acoustic Fingerprinting)."""

import hashlib
import os
import struct
import subprocess
import sys
import tempfile
import wave
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def _ffmpeg_available() -> bool:
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def extract_audio_wav(source_path: str, max_duration_sec: float = 90.0) -> Tuple[Optional[str], List[str]]:
    """Video/audio faylından müvəqqəti mono WAV çıxarır."""
    warnings = []
    if not _ffmpeg_available():
        return None, ['FFmpeg tapılmadı — akustik analiz məhdudlaşır.']

    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    tmp.close()
    out_path = tmp.name
    cmd = [
        'ffmpeg', '-y', '-i', source_path,
        '-vn', '-acodec', 'pcm_s16le', '-ar', '22050', '-ac', '1',
        '-t', str(max_duration_sec),
        out_path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=120)
        if proc.returncode != 0 or not os.path.isfile(out_path) or os.path.getsize(out_path) < 44:
            warnings.append('Audio track çıxarılmadı və ya səssiz fayldır.')
            try:
                os.unlink(out_path)
            except OSError:
                pass
            return None, warnings
        return out_path, warnings
    except Exception as e:
        warnings.append(str(e))
        try:
            os.unlink(out_path)
        except OSError:
            pass
        return None, warnings


def _read_wav_mono(path: str, max_samples: int = 2_000_000) -> Tuple[Optional[np.ndarray], int]:
    try:
        with wave.open(path, 'rb') as w:
            ch = w.getnchannels()
            sr = w.getframerate()
            n = w.getnframes()
            raw = w.readframes(min(n, max_samples))
        if ch == 2:
            samples = struct.unpack(f'<{len(raw)//2}h', raw)
            arr = np.array(samples[::2], dtype=np.float32) / 32768.0
        else:
            arr = np.array(struct.unpack(f'<{len(raw)//2}h', raw), dtype=np.float32) / 32768.0
        return arr, sr
    except Exception:
        return None, 0


def _frequency_profile(samples: np.ndarray, sample_rate: int) -> Dict[str, Any]:
    if samples is None or len(samples) < 512 or sample_rate <= 0:
        return {'error': 'Kifayət qədər audio nümunə yoxdur'}

    n = min(len(samples), sample_rate * 30)
    seg = samples[:n]
    if len(seg) < 2048:
        seg = np.pad(seg, (0, 2048 - len(seg)))

    spectrum = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freqs = np.fft.rfftfreq(len(seg), 1.0 / sample_rate)
    mag = spectrum[: len(freqs)]
    total = float(np.sum(mag)) + 1e-12

    bands = [
        ('sub_bass', 20, 60),
        ('bass', 60, 250),
        ('low_mid', 250, 500),
        ('mid', 500, 2000),
        ('high_mid', 2000, 6000),
        ('treble', 6000, 12000),
        ('air', 12000, sample_rate / 2),
    ]
    band_energy = {}
    for name, lo, hi in bands:
        mask = (freqs >= lo) & (freqs < hi)
        band_energy[name] = round(float(np.sum(mag[mask]) / total) * 100, 2)

    peak_idx = int(np.argmax(mag[1:]) + 1) if len(mag) > 1 else 0
    dominant_hz = round(float(freqs[peak_idx]), 1)
    centroid = round(float(np.sum(freqs * mag) / total), 1)
    rolloff_idx = np.searchsorted(np.cumsum(mag) / total, 0.85)
    rolloff_hz = round(float(freqs[min(rolloff_idx, len(freqs) - 1)]), 1)

    zcr = float(np.mean(np.abs(np.diff(np.sign(seg)))) / 2)

    return {
        'dominant_frequency_hz': dominant_hz,
        'spectral_centroid_hz': centroid,
        'spectral_rolloff_hz': rolloff_hz,
        'zero_crossing_rate': round(zcr, 4),
        'band_energy_percent': band_energy,
        'estimated_pitch_class': _pitch_class(dominant_hz),
    }


def _pitch_class(hz: float) -> Optional[str]:
    if hz < 50 or hz > 5000:
        return None
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    midi = 12 * np.log2(hz / 440.0) + 69
    return notes[int(round(midi)) % 12]


def _compute_fingerprint(samples: np.ndarray, sample_rate: int) -> Dict[str, Any]:
    """Spektr seqmentlərindən kompakt akustik hash."""
    if samples is None or len(samples) < 4096:
        return {'error': 'Fingerprint üçün audio çox qısadır'}

    hop = sample_rate // 2
    win = sample_rate
    vectors = []
    for start in range(0, min(len(samples) - win, sample_rate * 60), hop):
        chunk = samples[start:start + win] * np.hanning(win)
        spec = np.abs(np.fft.rfft(chunk))
        spec = spec[: min(512, len(spec))]
        spec = spec / (np.max(spec) + 1e-9)
        q = (spec * 255).astype(np.uint8)
        vectors.append(q.tobytes())

    if not vectors:
        return {'error': 'Fingerprint vektoru qurulmadı'}

    digest = hashlib.sha256(b''.join(vectors)).hexdigest()
    preview = '-'.join(digest[i:i + 4] for i in range(0, 24, 4))

    return {
        'algorithm': 'spectral_segment_sha256_v1',
        'hash_hex': digest,
        'hash_preview': preview,
        'segment_count': len(vectors),
        'note_az': 'Eyni hash oxşar akustik məzmunu göstərə bilər; müqayisə üçün istifadə edin.',
    }


def _try_acoustid(filepath: str) -> Optional[Dict[str, Any]]:
    try:
        import acoustid  # pyacoustid + chromaprint fpcalc
        duration, fp_encoded = acoustid.fingerprint(filepath)
        return {
            'engine': 'chromaprint_acoustid',
            'duration_sec': round(float(duration), 2) if duration else None,
            'fingerprint': fp_encoded,
            'note_az': 'MusicBrainz/AcoustID bazası ilə musiqi axtarışı mümkün ola bilər.',
        }
    except Exception:
        return None


def analyze_acoustic(filepath: str, is_video: bool = False) -> Dict[str, Any]:
    wav_path = filepath
    temp_wav = None
    warnings: List[str] = []

    if is_video or not filepath.lower().endswith('.wav'):
        wav_path, w = extract_audio_wav(filepath)
        warnings.extend(w)
        if wav_path and wav_path != filepath:
            temp_wav = wav_path

    if not wav_path:
        return {
            'status': 'skipped',
            'warnings': warnings,
            'summary_az': 'Audio iz analiz edilə bilmədi.',
        }

    samples, sr = _read_wav_mono(wav_path)
    duration_sec = round(len(samples) / sr, 2) if samples is not None and sr else None

    result = {
        'status': 'ok',
        'sample_rate_hz': sr,
        'duration_analyzed_sec': duration_sec,
        'warnings': warnings,
        'frequency_profile': _frequency_profile(samples, sr) if samples is not None else None,
        'acoustic_fingerprint': _compute_fingerprint(samples, sr) if samples is not None else None,
    }

    acoustid = _try_acoustid(wav_path)
    if acoustid:
        result['chromaprint'] = acoustid

    if temp_wav:
        try:
            os.unlink(temp_wav)
        except OSError:
            pass

    fp = (result.get('acoustic_fingerprint') or {}).get('hash_preview', '')
    dom = (result.get('frequency_profile') or {}).get('dominant_frequency_hz')
    result['summary_az'] = (
        f'Akustik profil hazırdır'
        + (f'; dominant ~{dom} Hz' if dom else '')
        + (f'; iz: {fp}' if fp else '')
        + '.'
    )
    print(f'  [i] Akustik fingerprint: {fp or "n/a"}', file=sys.stderr)
    return result
