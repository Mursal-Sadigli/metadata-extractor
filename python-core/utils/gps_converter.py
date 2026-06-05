"""
GPS Koordinat Çevirici

EXIF GPS formatından (degrees/minutes/seconds) decimal degrees-ə çevirmə.
"""

from utils.coordinate_validator import normalize_hemisphere_ref


def dms_to_decimal(dms_values, ref):
    """
    DMS (Degrees, Minutes, Seconds) formatını decimal degrees-ə çevir.

    Args:
        dms_values: EXIF GPS tag dəyərləri [degrees, minutes, seconds]
                    Hər dəyər exifread.utils.Ratio və ya adi rəqəm ola bilər.
        ref: İstiqamət referansı ('N', 'S', 'E', 'W')

    Returns:
        float: Decimal degrees dəyəri
    """
    try:
        # exifread Ratio obyektlərini float-a çevir
        degrees = _ratio_to_float(dms_values[0])
        minutes = _ratio_to_float(dms_values[1])
        seconds = _ratio_to_float(dms_values[2])

        # Decimal degrees hesabla
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)

        # Cənub və ya Qərb istiqamətində mənfi et
        ref_n = normalize_hemisphere_ref(ref)
        if ref_n in ('S', 'W'):
            decimal = -decimal

        return round(decimal, 6)
    except (IndexError, TypeError, ZeroDivisionError) as e:
        print(f"  [!] GPS çevirmə xətası: {e}")
        return None


def _ratio_to_float(value):
    """
    exifread Ratio obyektini və ya digər rəqəm tiplərini float-a çevir.

    Args:
        value: Ratio, int, float, və ya str

    Returns:
        float: Çevrilmiş dəyər
    """
    if hasattr(value, 'num') and hasattr(value, 'den'):
        # exifread Ratio obyekti
        if value.den == 0:
            return 0.0
        return float(value.num) / float(value.den)
    elif isinstance(value, (int, float)):
        return float(value)
    else:
        # String ola bilər, float-a çevirməyə çalış
        return float(str(value))


def format_coordinates(latitude, longitude):
    """
    Koordinatları oxunaqlı formata çevir.

    Args:
        latitude: Enlik (float)
        longitude: Uzunluq (float)

    Returns:
        dict: Formatlanmış koordinat məlumatları
    """
    if latitude is None or longitude is None:
        return None

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None

    lat_dir = 'N' if latitude >= 0 else 'S'
    lon_dir = 'E' if longitude >= 0 else 'W'

    return {
        'latitude': latitude,
        'longitude': longitude,
        'display': f"{abs(latitude):.6f}°{lat_dir}, {abs(longitude):.6f}°{lon_dir}",
        'map_url': f"https://maps.google.com/maps?q={latitude},{longitude}",
        'osm_url': f"https://www.openstreetmap.org/?mlat={latitude}&mlon={longitude}#map=16/{latitude}/{longitude}",
    }


def decimal_to_dms_display(latitude, longitude):
    """Decimal koordinatları DMS formatında göstərir."""
    def one(val, pos, neg):
        direction = pos if val >= 0 else neg
        av = abs(val)
        d = int(av)
        m = int((av - d) * 60)
        s = round((av - d - m / 60) * 3600, 2)
        return f"{d}°{m}'{s}\"{direction}"

    try:
        return {
            'latitude_dms': one(float(latitude), 'N', 'S'),
            'longitude_dms': one(float(longitude), 'E', 'W'),
        }
    except (TypeError, ValueError):
        return None
