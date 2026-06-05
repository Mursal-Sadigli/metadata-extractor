"""
Fayl Tipi Aşkarlayıcı

MIME type detection və uyğun extractor-a yönləndirmə.
"""

import os

# python-magic mövcud deyilsə fallback olaraq extension-a bax
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False

# Dəstəklənən MIME tipləri və onlara uyğun extractor adları
MIME_MAP = {
    # Şəkillər
    'image/jpeg': 'image',
    'image/png': 'image',
    'image/tiff': 'image',
    'image/webp': 'image',
    'image/gif': 'image',
    'image/bmp': 'image',
    'image/heic': 'image',
    'image/heif': 'image',
    'image/x-canon-cr2': 'image',
    'image/x-nikon-nef': 'image',
    'image/x-sony-arw': 'image',

    # PDF
    'application/pdf': 'pdf',

    # Audio
    'audio/mpeg': 'audio',
    'audio/mp3': 'audio',
    'audio/flac': 'audio',
    'audio/ogg': 'audio',
    'audio/wav': 'audio',
    'audio/x-wav': 'audio',
    'audio/aac': 'audio',
    'audio/mp4': 'audio',
    'audio/x-m4a': 'audio',

    # Video
    'video/mp4': 'video',
    'video/quicktime': 'video',
    'video/webm': 'video',
    'video/x-matroska': 'video',
    'video/x-msvideo': 'video',

    # Sənədlər
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'document',
    'application/msword': 'document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'document',
    'application/vnd.ms-excel': 'document',
}

# Extension əsaslı fallback xəritəsi
EXTENSION_MAP = {
    # Şəkillər
    '.jpg': 'image', '.jpeg': 'image', '.png': 'image',
    '.tiff': 'image', '.tif': 'image', '.webp': 'image',
    '.gif': 'image', '.bmp': 'image', '.heic': 'image',
    '.heif': 'image', '.cr2': 'image', '.nef': 'image',
    '.arw': 'image', '.raw': 'image', '.dng': 'image',

    # Video
    '.mp4': 'video', '.mov': 'video', '.webm': 'video',
    '.mkv': 'video', '.avi': 'video', '.m4v': 'video',

    # PDF
    '.pdf': 'pdf',

    # Audio
    '.mp3': 'audio', '.flac': 'audio', '.ogg': 'audio',
    '.wav': 'audio', '.aac': 'audio', '.m4a': 'audio',
    '.wma': 'audio',

    # Sənədlər
    '.docx': 'document', '.doc': 'document',
    '.xlsx': 'document', '.xls': 'document',
}


def detect_file_type(filepath):
    """
    Faylın tipini aşkarla.

    Args:
        filepath: Fayl yolu

    Returns:
        dict: {
            'type': 'image'|'pdf'|'audio'|'document'|'unknown',
            'mime_type': 'image/jpeg',
            'method': 'magic'|'extension'
        }
    """
    result = {
        'type': 'unknown',
        'mime_type': None,
        'method': None
    }

    # Əvvəlcə python-magic ilə cəhd et
    if HAS_MAGIC:
        try:
            mime = magic.from_file(filepath, mime=True)
            result['mime_type'] = mime
            result['method'] = 'magic'

            if mime in MIME_MAP:
                result['type'] = MIME_MAP[mime]
                return result
        except Exception:
            pass

    # Fallback: fayl uzantısına bax
    ext = os.path.splitext(filepath)[1].lower()
    if ext in EXTENSION_MAP:
        result['type'] = EXTENSION_MAP[ext]
        result['method'] = 'extension'
        if result['mime_type'] is None:
            result['mime_type'] = f"detected-by-extension/{ext.lstrip('.')}"

    return result


def get_supported_extensions():
    """Dəstəklənən bütün fayl uzantılarını qaytarır."""
    return list(EXTENSION_MAP.keys())


def is_supported_file(filepath):
    """Faylın dəstəklənib-dəstəklənmədiyini yoxla."""
    file_info = detect_file_type(filepath)
    return file_info['type'] != 'unknown'


def scan_directory(directory, recursive=False):
    """
    Qovluqdakı dəstəklənən faylları skan et.

    Args:
        directory: Qovluq yolu
        recursive: Alt qovluqlara da bax

    Returns:
        list: Dəstəklənən faylların yolları
    """
    supported_files = []

    if recursive:
        for root, dirs, files in os.walk(directory):
            for filename in files:
                filepath = os.path.join(root, filename)
                if is_supported_file(filepath):
                    supported_files.append(filepath)
    else:
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath) and is_supported_file(filepath):
                supported_files.append(filepath)

    return sorted(supported_files)
