"""
Document Metadata Extractor

python-docx kitabxanasından istifadə edərək DOCX fayllarından metadata çıxarır.
"""

from docx import Document
from extractors.base import BaseExtractor

class DocumentExtractor(BaseExtractor):
    """DOCX sənədlərindən metadata çıxaran extractor."""

    def extract(self, filepath):
        """
        DOCX faylından metadata çıxar.
        """
        result = {
            'file_info': self.get_file_info(filepath),
            'type': 'document',
            'document_info': None
        }
        
        # Yalnız .docx fayllarını dəstəkləyirik
        if not filepath.lower().endswith('.docx'):
            return result
            
        try:
            doc = Document(filepath)
            prop = doc.core_properties
            
            doc_data = {
                'author': prop.author,
                'category': prop.category,
                'comments': prop.comments,
                'content_status': prop.content_status,
                'created': str(prop.created) if prop.created else None,
                'identifier': prop.identifier,
                'keywords': prop.keywords,
                'language': prop.language,
                'last_modified_by': prop.last_modified_by,
                'last_printed': str(prop.last_printed) if prop.last_printed else None,
                'modified': str(prop.modified) if prop.modified else None,
                'revision': prop.revision,
                'subject': prop.subject,
                'title': prop.title,
                'version': prop.version
            }
            # None və boş olan dəyərləri təmizlə
            result['document_info'] = {k: v for k, v in doc_data.items() if v is not None and str(v).strip() != ""}
        except Exception as e:
            print(f"  [!] Document oxuma xətası: {e}")
            
        return result
