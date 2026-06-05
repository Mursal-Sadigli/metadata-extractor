import os


def analyze_weather(latitude, longitude, date_string=None):
    """Geriyə uyğunluq — tam analiz reverse_weather moduluna yönləndirilir."""
    from analyzers.reverse_weather_analyzer import analyze_reverse_weather
    rw = analyze_reverse_weather(
        filepath=None,
        latitude=latitude,
        longitude=longitude,
        datetime_raw=date_string,
    )
    legacy = rw.get('weather_legacy')
    if legacy:
        return legacy
    return {'error': rw.get('error', 'Hava məlumatı alınmadı')}


def analyze_osint(filepath, result_dict=None):
    """
    OSINT paneli üçün xüsusi analiz.
    Burada `result_dict` əvvəlki EXIF analizindən gələn datadır.
    """
    result = {}
    
    if result_dict and "location" in result_dict and result_dict["location"]:
        loc = result_dict["location"]
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        
        from analyzers.reverse_weather_analyzer import analyze_reverse_weather
        rw = analyze_reverse_weather(filepath, result_dict, lat, lon, None)
        if rw:
            result["reverse_weather"] = rw
            if rw.get("weather_legacy"):
                result["weather"] = rw["weather_legacy"]
            elif rw.get("historical", {}).get("daily_summary"):
                d = rw["historical"]["daily_summary"]
                result["weather"] = {
                    "date": d.get("date"),
                    "max_temp_c": d.get("max_temp_c"),
                    "min_temp_c": d.get("min_temp_c"),
                    "precipitation_mm": d.get("precipitation_mm"),
                    "weather_code": d.get("weather_code"),
                    "description": d.get("description_az"),
                }

    if filepath:
        try:
            from analyzers.reverse_image_search_analyzer import analyze_reverse_image_search
            public_url = None
            fn = os.path.basename(filepath) if filepath else None
            ris = analyze_reverse_image_search(filepath, public_url, fn)
            if ris:
                result['reverse_image_search'] = ris
        except Exception as e:
            result['reverse_image_search'] = {
                'module': 'reverse_image_search',
                'status': 'error',
                'error': str(e),
            }

    return result
