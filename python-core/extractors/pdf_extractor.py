"""
PDF Metadata Extractor

pypdf kitabxanasından istifadə edərək PDF fayllarından metadata çıxarır.
"""

from pypdf import PdfReader
from extractors.base import BaseExtractor

class PdfExtractor(BaseExtractor):
    """PDF fayllarından metadata çıxaran extractor."""

    def extract(self, filepath):
        """
        PDF faylından metadata çıxar.
        """
        result = {
            'file_info': self.get_file_info(filepath),
            'type': 'pdf',
            'pdf_info': None
        }
        try:
            reader = PdfReader(filepath)
            info = reader.metadata
            pdf_data = {}
            if info:
                pdf_data = {
                    'author': info.author,
                    'creator': info.creator,
                    'producer': info.producer,
                    'subject': info.subject,
                    'title': info.title,
                    'creation_date': str(info.creation_date) if info.creation_date else None,
                    'modification_date': str(info.modification_date) if info.modification_date else None,
                }
            
            pdf_data['pages'] = len(reader.pages)
            pdf_data['is_encrypted'] = reader.is_encrypted
            
            # None olan dəyərləri təmizlə
            result['pdf_info'] = {k: v for k, v in pdf_data.items() if v is not None}
        except Exception as e:
            print(f"  [!] PDF oxuma xətası: {e}")
        return result
