"""
Geo Analyzer — reverse_geocoder və genişləndirilmiş Nominatim.
"""

import sys
import time
from typing import Any, Dict, List, Optional

import requests
import reverse_geocoder as rg

NOMINATIM_SEARCH = 'https://nominatim.openstreetmap.org/search'
NOMINATIM_REVERSE = 'https://nominatim.openstreetmap.org/reverse'
USER_AGENT = 'MetadataExtractor/2.0 (OSINT geoparsing)'


def analyze_location(latitude, longitude):
    """Koordinatları şəhər, rayon və ölkə adına çevir."""
    try:
        results = rg.search((latitude, longitude))
        if results and len(results) > 0:
            res = results[0]
            return {
                'city': res.get('name'),
                'admin1': res.get('admin1'),
                'admin2': res.get('admin2'),
                'country_code': res.get('cc'),
            }
    except Exception as e:
        print(f"  [!] Geo analiz xətası: {e}", file=sys.stderr)
    return None


def nominatim_reverse(latitude, longitude, delay=1.0):
    """OSM reverse geocoding — tam ünvan sətri."""
    full = nominatim_reverse_full(latitude, longitude, delay=delay)
    return full.get('display_name') if full else None


def nominatim_reverse_full(latitude, longitude, delay=1.0) -> Optional[Dict[str, Any]]:
    """Strukturlaşdırılmış reverse geocode."""
    try:
        time.sleep(delay)
        resp = requests.get(
            NOMINATIM_REVERSE,
            params={
                'lat': latitude,
                'lon': longitude,
                'format': 'json',
                'zoom': 18,
                'addressdetails': 1,
            },
            headers={'User-Agent': USER_AGENT},
            timeout=14,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        addr = data.get('address') or {}
        return {
            'display_name': data.get('display_name'),
            'address': {
                'road': addr.get('road') or addr.get('pedestrian'),
                'suburb': addr.get('suburb') or addr.get('neighbourhood'),
                'city': addr.get('city') or addr.get('town') or addr.get('village'),
                'state': addr.get('state'),
                'country': addr.get('country'),
                'country_code': (addr.get('country_code') or '').upper(),
                'postcode': addr.get('postcode'),
            },
            'osm_type': data.get('osm_type'),
            'category': data.get('category'),
        }
    except Exception as e:
        print(f"  [!] Nominatim reverse: {e}", file=sys.stderr)
    return None


def nominatim_search_advanced(
    query: str,
    country_codes: Optional[str] = None,
    structured: Optional[dict] = None,
    limit: int = 5,
    delay: float = 1.05,
) -> List[Dict[str, Any]]:
    """
    Ağıllı forward geocoding — ölkə filtresi və strukturlaşdırılmış ünvan.
    """
    try:
        time.sleep(delay)
        params = {
            'format': 'json',
            'limit': limit,
            'addressdetails': 1,
            'dedupe': 1,
        }

        if structured and structured.get('street') and structured.get('city'):
            params['street'] = structured['street'][:120]
            params['city'] = (structured.get('city') or '')[:80].split(',')[0]
            if structured.get('country'):
                params['country'] = structured['country'][:60]
        else:
            params['q'] = query[:200]

        if country_codes:
            params['countrycodes'] = country_codes.replace('/', ',').lower()[:20]

        resp = requests.get(
            NOMINATIM_SEARCH,
            params=params,
            headers={'User-Agent': USER_AGENT},
            timeout=14,
        )
        if resp.status_code != 200:
            return []

        out = []
        for item in resp.json():
            try:
                lat = float(item['lat'])
                lon = float(item['lon'])
                importance = float(item.get('importance', 0.25))
                addr = item.get('address') or {}
                out.append({
                    'latitude': lat,
                    'longitude': lon,
                    'display_name': item.get('display_name', query)[:160],
                    'importance': importance,
                    'confidence': min(0.4 + importance * 0.45, 0.78),
                    'address': {
                        'city': addr.get('city') or addr.get('town'),
                        'country_code': (addr.get('country_code') or '').upper(),
                        'road': addr.get('road'),
                    },
                    'query': query,
                    'osm_class': item.get('class'),
                    'osm_type': item.get('type'),
                })
            except (KeyError, ValueError, TypeError):
                continue
        return out
    except Exception as e:
        print(f"  [!] Nominatim search: {e}", file=sys.stderr)
        return []
