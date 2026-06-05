"""Yüngül CLI — Lokasiya analizi (/api/analyze location), main.py + OCR/carving yükləmədən."""

import argparse
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def _light_location() -> bool:
    if os.environ.get('LIGHT_LOCATION', '').strip().lower() in ('0', 'false', 'no'):
        return False
    if os.environ.get('LIGHT_LOCATION', '').strip().lower() in ('1', 'true', 'yes'):
        return True
    return os.environ.get('RENDER', '').strip().lower() in ('true', '1')


def _light_geoparse_inference(result: dict, web_texts: list, extra_texts=None) -> dict:
    from analyzers.geolocation_analyzer import infer_region_hints
    from analyzers.geoparsing_engine import full_geoparse_from_texts, cluster_candidates, fuse_candidate_scores

    texts = []
    for v in (result.get('description') or {}).values():
        if v:
            texts.append(str(v))
    texts.extend(web_texts or [])
    if extra_texts:
        texts.extend(str(t).strip() for t in extra_texts if t and str(t).strip())
    texts = list(dict.fromkeys(t for t in texts if t and t.strip()))

    regional = infer_region_hints(texts)
    geoparse = full_geoparse_from_texts(texts, regional)
    candidates = []
    for coord in geoparse.get('extracted_coordinates') or []:
        lat = coord.get('latitude')
        lon = coord.get('longitude')
        if lat is None or lon is None:
            continue
        candidates.append({
            'latitude': lat,
            'longitude': lon,
            'source': coord.get('source') or 'geoparse',
            'confidence': float(coord.get('confidence', 0.5)),
            'fusion_score': float(coord.get('confidence', 0.5)),
            'label': coord.get('label') or 'Geoparsing',
        })
    if candidates:
        candidates = cluster_candidates(candidates, km_threshold=1.8)
        candidates = fuse_candidate_scores(candidates, geoparse.get('country_bias'))

    return {
        'candidates': candidates,
        'geoparsing': geoparse,
        'methods_used': ['web_text', 'geoparse_light'],
        'limitations': 'Yüngül rejim: OCR, file carving və tam geoparsing deaktiv.',
    }


def run_location(filepath: str, extra_text=None) -> dict:
    from utils.file_detector import detect_file_type
    from extractors.image_extractor import ImageExtractor
    from analyzers.location_resolver import resolve_image_location
    from analyzers.geo_analyzer import analyze_location

    file_info = detect_file_type(filepath)
    file_type = file_info.get('type')
    if file_type != 'image':
        return {
            'file_info': file_info,
            'type': file_type,
            'error': 'Lokasiya analizi əsasən şəkil faylları üçündür.',
        }

    result = ImageExtractor().extract(filepath)
    light = _light_location()
    extra_texts = [extra_text] if extra_text else None
    file_carving_ml = None
    carved_metadata = None
    web_cands = []
    web_texts = []

    try:
        from analyzers.web_image_location import gather_web_location_hints
        web_texts, web_cands = gather_web_location_hints(filepath, result)
    except Exception as e:
        print(f'  [!] Web lokasiya: {e}', file=sys.stderr)

    merged_texts = list(extra_texts or []) + list(web_texts or [])

    if light:
        inference = _light_geoparse_inference(result, web_texts, extra_texts)
    else:
        from analyzers.file_carving_ml import analyze_file_carving_ml
        from analyzers.carved_metadata_analyzer import analyze_carved_metadata
        from analyzers.geolocation_analyzer import analyze_advanced_geolocation

        file_carving_ml = analyze_file_carving_ml(filepath)
        inference = analyze_advanced_geolocation(
            filepath, result, extra_texts=merged_texts or None,
        )
        carved_metadata = analyze_carved_metadata(filepath)

    location, location_inference, loc_warnings = resolve_image_location(
        filepath,
        result.get('location'),
        carving=file_carving_ml,
        inference=inference,
        extra_texts=merged_texts or None,
        web_candidates=web_cands,
    )
    if loc_warnings:
        result['warnings'] = (result.get('warnings') or []) + loc_warnings

    if location:
        lat = location.get('latitude')
        lon = location.get('longitude')
        if lat is not None and lon is not None:
            geo = analyze_location(lat, lon)
            if geo:
                location['address'] = geo
            if not light and result.get('exif') and result['exif'].get('datetime'):
                dt = (
                    result['exif']['datetime'].get('original')
                    or result['exif']['datetime'].get('modified')
                    or result['exif']['datetime'].get('inferred_from_filename')
                )
                if dt:
                    try:
                        from analyzers.astronomy_analyzer import analyze_sun_position
                        astro = analyze_sun_position(lat, lon, dt)
                        if astro and 'error' not in astro:
                            location['astronomy'] = astro
                    except Exception:
                        pass
            try:
                from analyzers.reverse_weather_analyzer import analyze_reverse_weather
                rw = analyze_reverse_weather(filepath, result, lat, lon, None)
                if rw and rw.get('status') != 'no_coordinates':
                    location['reverse_weather'] = rw
            except Exception as e:
                print(f'  [!] Reverse weather: {e}', file=sys.stderr)

    payload = {
        'file_info': result.get('file_info') or file_info,
        'type': result.get('type') or file_type,
        'location': location,
        'location_inference': location_inference,
        'carved_metadata': carved_metadata,
        'file_carving_ml': file_carving_ml,
        'warnings': result.get('warnings'),
    }
    if light:
        payload['light_mode'] = True
        payload['note_az'] = (
            'Render yüngül lokasiya: EXIF GPS, veb mənbə, geoparsing. '
            'OCR və File Carving 4.0 lokal serverdə aktivdir.'
        )
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path')
    parser.add_argument('--text')
    args = parser.parse_args()

    if not os.path.isfile(args.path):
        print(json.dumps({'error': 'Fayl tapılmadı'}, ensure_ascii=False))
        sys.exit(1)

    try:
        payload = run_location(args.path, extra_text=args.text)
    except Exception as e:
        print(json.dumps({'error': f'Lokasiya xətası: {e}'}, ensure_ascii=False))
        sys.exit(1)

    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)


if __name__ == '__main__':
    main()
