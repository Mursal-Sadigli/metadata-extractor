import math
from datetime import datetime
import pytz

try:
    from pysolar.solar import get_altitude, get_azimuth
    PYSOLAR_AVAILABLE = True
except ImportError:
    PYSOLAR_AVAILABLE = False

def parse_exif_date(date_str):
    """
    EXIF tarix formatını (YYYY:MM:DD HH:MM:SS) datetime obyektinə çevirir.
    Əgər saat qurşağı yoxdursa, UTC kimi qəbul edir.
    """
    try:
        if not date_str:
            return None
        dt = datetime.strptime(date_str.strip(), "%Y:%m:%d %H:%M:%S")
        return dt.replace(tzinfo=pytz.UTC)
    except Exception:
        return None

def analyze_sun_position(latitude, longitude, date_str):
    """
    Verilmiş tarix, saat və koordinatlara əsasən günəşin bucağını (altitude) və azimutunu (azimuth) hesablayır.
    Bu, şəkildəki kölgələrin düşmə bucağı ilə uyğunluğunu yoxlamaq üçün OSINT-də istifadə olunur.
    """
    if not PYSOLAR_AVAILABLE:
        return {"error": "pysolar library not installed"}
        
    dt = parse_exif_date(date_str)
    if not dt:
        return {"error": "Invalid or missing datetime"}
        
    try:
        altitude = get_altitude(latitude, longitude, dt)
        azimuth = get_azimuth(latitude, longitude, dt)
        
        return {
            "datetime_utc": str(dt),
            "sun_altitude_degrees": round(altitude, 2),
            "sun_azimuth_degrees": round(azimuth, 2),
            "shadow_direction": "North" if azimuth > 90 and azimuth < 270 else "South", # sadələşdirilmiş
            "notes": "Şəkildəki kölgə uzunluğu günəş bucağı (altitude) ilə tərs mütənasib olmalıdır."
        }
    except Exception as e:
        return {"error": str(e)}

def estimate_sun_angle_from_shadow(object_height, shadow_length):
    """
    İstifadəçinin vizual olaraq ölçdüyü obyektin hündürlüyü və kölgə uzunluğuna əsasən 
    günəşin düşmə bucağını (altitude) hesablayır.
    """
    if shadow_length <= 0:
        return None
        
    angle_rad = math.atan(object_height / shadow_length)
    angle_deg = math.degrees(angle_rad)
    return round(angle_deg, 2)

