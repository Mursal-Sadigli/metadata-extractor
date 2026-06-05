"""
Audio Metadata Extractor

tinytag kitabxanasından istifadə edərək Audio fayllarından metadata çıxarır.
"""

from tinytag import TinyTag
from extractors.base import BaseExtractor

class AudioExtractor(BaseExtractor):
    """Audio fayllarından metadata çıxaran extractor."""

    def extract(self, filepath):
        """
        Audio faylından metadata çıxar.
        """
        result = {
            'file_info': self.get_file_info(filepath),
            'type': 'audio',
            'audio_info': None
        }
        try:
            tag = TinyTag.get(filepath)
            audio_data = {
                'title': tag.title,
                'artist': tag.artist,
                'album': tag.album,
                'albumartist': tag.albumartist,
                'genre': tag.genre,
                'year': tag.year,
                'track': tag.track,
                'track_total': tag.track_total,
                'duration': tag.duration,
                'bitrate': tag.bitrate,
                'samplerate': tag.samplerate,
                'filesize': tag.filesize,
                'channels': tag.channels,
                'comment': tag.comment
            }
            # None olan dəyərləri təmizlə
            result['audio_info'] = {k: v for k, v in audio_data.items() if v is not None and str(v).strip() != ""}
        except Exception as e:
            print(f"  [!] Audio oxuma xətası: {e}")
        return result
