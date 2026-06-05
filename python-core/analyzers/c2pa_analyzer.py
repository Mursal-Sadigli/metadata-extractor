"""C2PA / Content Credentials analizi."""

import os
import sys
import re


def analyze_c2pa(filepath):
    try:
        import c2pa
        reader = c2pa.Reader.from_file(filepath)
        manifest = reader.get_active_manifest()
        if not manifest:
            return {'status': 'not_found', 'c2pa_present': False}

        is_ai = False
        issuer = None
        edit_list = []
        validation_status = 'unknown'

        try:
            json_manifest = manifest.json() if hasattr(manifest, 'json') else str(manifest)
            text = json_manifest if isinstance(json_manifest, str) else str(json_manifest)
            if re.search(r'ai|generat|synthetic|dall|midjourney|firefly', text, re.I):
                is_ai = True
            if 'issuer' in text.lower():
                m = re.search(r'"issuer"[^"]*"([^"]+)"', text)
                if m:
                    issuer = m.group(1)
        except Exception:
            pass

        try:
            validation_status = 'valid' if reader.validate() else 'invalid'
        except Exception:
            validation_status = 'unknown'

        return {
            'status': 'found',
            'c2pa_present': True,
            'is_ai_generated': is_ai,
            'issuer': issuer,
            'edit_list': edit_list[:10],
            'validation_status': validation_status,
        }
    except ImportError:
        return _analyze_c2pa_raw(filepath)
    except Exception as e:
        raw = _analyze_c2pa_raw(filepath)
        if raw.get('c2pa_present'):
            return raw
        return {'status': 'not_found', 'c2pa_present': False, 'detail': str(e)}


def _analyze_c2pa_raw(filepath):
    """SDK yoxdursa faylda c2pa/jumbf axtarışı."""
    try:
        with open(filepath, 'rb') as f:
            data = f.read(min(2_000_000, os.path.getsize(filepath)))
        if b'c2pa' in data.lower() or b'jumbf' in data.lower() or b'contentcredentials' in data.lower():
            is_ai = b'ai.generated' in data.lower() or b'synthetic' in data.lower()
            return {
                'status': 'found',
                'c2pa_present': True,
                'is_ai_generated': is_ai,
                'issuer': None,
                'edit_list': [],
                'validation_status': 'unknown',
                'note': 'Raw byte scan (c2pa-python tam yoxlanmadı)',
            }
    except Exception:
        pass
    return {'status': 'not_found', 'c2pa_present': False}
