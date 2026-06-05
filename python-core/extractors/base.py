"""
Baza Extractor — Abstract Base Class

Bütün extractor-lar bu sinifdən miras alır.
"""

import os
from abc import ABC, abstractmethod
from datetime import datetime


class BaseExtractor(ABC):
    """
    Bütün metadata extractor-lar üçün abstract base class.

    Hər extractor extract() metodunu implementasiya etməlidir.
    Ortaq fayl metadata-sı bu sinifdə toplanır.
    """

    def get_file_info(self, filepath):
        """
        Ortaq fayl məlumatlarını topla (bütün fayl tipləri üçün).

        Args:
            filepath: Fayl yolu

        Returns:
            dict: Fayl haqqında əsas məlumatlar
        """
        stat = os.stat(filepath)

        return {
            'filename': os.path.basename(filepath),
            'filepath': os.path.abspath(filepath),
            'size_bytes': stat.st_size,
            'size_human': self._human_readable_size(stat.st_size),
            'created': self._timestamp_to_iso(stat.st_ctime),
            'modified': self._timestamp_to_iso(stat.st_mtime),
            'extension': os.path.splitext(filepath)[1].lower(),
        }

    @abstractmethod
    def extract(self, filepath):
        """
        Fayldan metadata çıxar.

        Args:
            filepath: Fayl yolu

        Returns:
            dict: Çıxarılmış metadata
        """
        pass

    @staticmethod
    def _human_readable_size(size_bytes):
        """Baytları oxunaqlı formata çevir (KB, MB, GB)."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

    @staticmethod
    def _timestamp_to_iso(timestamp):
        """Unix timestamp-ı ISO formatına çevir."""
        try:
            return datetime.fromtimestamp(timestamp).isoformat()
        except (OSError, ValueError):
            return None
