"""
Şəkil Metadata Extractor

EXIF, GPS, kamera məlumatları, çəkiliş parametrləri və thumbnail çıxarma.
exifread + Pillow istifadə edir.
"""

import os
import re
import sys

import exifread
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

from extractors.base import BaseExtractor
from utils.gps_converter import dms_to_decimal, format_coordinates

IFD_GPS = 0x8825

WHATSAPP_FILENAME_DT = re.compile(
    r'WhatsApp[_\s-]?Image[_\s-]?(\d{4})[_\s-](\d{2})[_\s-](\d{2})[_\s-]at[_\s-](\d{2})\.(\d{2})\.(\d{2})',
    re.IGNORECASE,
)


class ImageExtractor(BaseExtractor):
    """Şəkil fayllarından EXIF metadata çıxaran extractor."""

    # Əsas EXIF tag-ları və onların oxunaqlı adları
    CAMERA_TAGS = {
        'Image Make': 'make',
        'Image Model': 'model',
        'EXIF LensModel': 'lens',
        'EXIF LensMake': 'lens_make',
        'Image Software': 'software',
    }

    SETTINGS_TAGS = {
        'EXIF ISOSpeedRatings': 'iso',
        'EXIF FNumber': 'aperture',
        'EXIF ExposureTime': 'shutter_speed',
        'EXIF FocalLength': 'focal_length',
        'EXIF FocalLengthIn35mmFilm': 'focal_length_35mm',
        'EXIF Flash': 'flash',
        'EXIF ExposureProgram': 'exposure_program',
        'EXIF MeteringMode': 'metering_mode',
        'EXIF WhiteBalance': 'white_balance',
        'EXIF ExposureBiasValue': 'exposure_bias',
        'EXIF DigitalZoomRatio': 'digital_zoom',
    }

    DATETIME_TAGS = {
        'EXIF DateTimeOriginal': 'original',
        'EXIF DateTimeDigitized': 'digitized',
        'Image DateTime': 'modified',
    }

    IMAGE_TAGS = {
        'EXIF ExifImageWidth': 'width',
        'EXIF ExifImageLength': 'height',
        'Image Orientation': 'orientation',
        'EXIF ColorSpace': 'color_space',
        'Image XResolution': 'x_resolution',
        'Image YResolution': 'y_resolution',
    }

    def extract(self, filepath):
        """
        Şəkil faylından bütün metadata-nı çıxar.

        Args:
            filepath: Şəkil faylının yolu

        Returns:
            dict: Çıxarılmış metadata (file_info, exif, location, raw_tags)
        """
        result = {
            'file_info': self.get_file_info(filepath),
            'type': 'image',
            'exif': None,
            'location': None,
            'description': None,
        }

        ext = os.path.splitext(filepath)[1].lower()

        # Live Photo: eyni adlı .mov
        mov_sidecar = os.path.splitext(filepath)[0] + '.mov'
        if os.path.isfile(mov_sidecar):
            result['live_photo'] = {'mov_path': mov_sidecar, 'mov_filename': os.path.basename(mov_sidecar)}

        # EXIF tag-larını oxu (exifread)
        try:
            with open(filepath, 'rb') as f:
                tags = exifread.process_file(f, details=True)
        except Exception as e:
            print(f"  [!] EXIF oxuma xətası: {e}", file=sys.stderr)
            tags = {}

        pillow_exif, pillow_location, pillow_raw = self._extract_with_pillow(filepath)

        if not tags:
            print(f"  [i] exifread ilə EXIF tapılmadı: {os.path.basename(filepath)}", file=sys.stderr)
            result['exif'] = pillow_exif or self._get_pillow_info(filepath)
            result['location'] = pillow_location
            if pillow_raw:
                result['raw_tags'] = pillow_raw
            return self._finalize_image_result(result, filepath)

        # EXIF datasını strukturlaşdır
        result['exif'] = {
            'camera': self._extract_group(tags, self.CAMERA_TAGS),
            'settings': self._extract_settings(tags),
            'datetime': self._extract_group(tags, self.DATETIME_TAGS),
            'image': self._extract_image_info(tags, filepath),
        }

        # GPS məlumatlarını çıxar
        result['location'] = self._extract_gps(tags)

        # Təsvir/caption çıxar (dil analizi üçün)
        result['description'] = self._extract_description(tags)

        # Bütün raw tag-ları da saxla
        result['raw_tags'] = {
            str(k): str(v) for k, v in tags.items()
            if not k.startswith('Thumbnail')
            and not k.startswith('JPEGThumbnail')
            and not k.startswith('EXIF MakerNote')
        }

        # exifread GPS tapmasa, Pillow ilə yenidən yoxla
        if not result['location'] and pillow_location:
            result['location'] = pillow_location

        if pillow_exif:
            result['exif'] = self._merge_exif(result['exif'], pillow_exif)

        if pillow_raw:
            merged_raw = dict(pillow_raw)
            merged_raw.update(result.get('raw_tags') or {})
            result['raw_tags'] = merged_raw

        if ext == '.png':
            xmp_tags = self._extract_png_xmp(filepath)
            if xmp_tags:
                merged = dict(xmp_tags)
                merged.update(result.get('raw_tags') or {})
                result['raw_tags'] = merged

        return self._finalize_image_result(result, filepath)

    def _server_light_mode(self) -> bool:
        if os.environ.get('SKIP_HEAVY_ENRICH', '').strip().lower() in ('1', 'true', 'yes'):
            return True
        if os.environ.get('LIGHT_VISION', '').strip().lower() in ('1', 'true', 'yes'):
            return True
        if os.environ.get('LIGHT_OSINT', '').strip().lower() in ('1', 'true', 'yes'):
            return True
        return os.environ.get('RENDER', '').strip().lower() in ('true', '1')

    def _finalize_image_result(self, result, filepath):
        try:
            from analyzers.web_image_metadata import enrich_web_image_metadata
            enrich_web_image_metadata(result, filepath)
        except Exception as e:
            print(f'  [!] Web metadata enrich: {e}', file=sys.stderr)
        if self._server_light_mode():
            result['warnings'] = self._build_warnings(filepath, result)
            result['light_enrich'] = True
            return result
        try:
            from analyzers.residual_metadata_recovery import recover_residual_metadata
            recover_residual_metadata(result, filepath)
        except Exception as e:
            print(f'  [!] Qalıq metadata bərpası: {e}', file=sys.stderr)
        try:
            from analyzers.image_propagation_analyzer import analyze_image_propagation
            analyze_image_propagation(
                filepath, result, include_reverse_search=False, include_free_discovery=True,
            )
        except Exception as e:
            print(f'  [!] Yayılma analizi: {e}', file=sys.stderr)
        try:
            from analyzers.capture_date_analyzer import analyze_capture_date
            analyze_capture_date(result, filepath)
        except Exception as e:
            print(f'  [!] Capture date: {e}', file=sys.stderr)
        result['warnings'] = self._build_warnings(filepath, result)
        return result

    def extract_thumbnail(self, filepath, output_dir):
        """
        Şəkildən thumbnail çıxar və saxla.

        Args:
            filepath: Şəkil faylının yolu
            output_dir: Thumbnail-ın saxlanacağı qovluq

        Returns:
            str: Thumbnail faylının yolu, və ya None
        """
        try:
            with open(filepath, 'rb') as f:
                tags = exifread.process_file(f)

            thumbnail_data = tags.get('JPEGThumbnail')
            if thumbnail_data:
                os.makedirs(output_dir, exist_ok=True)
                basename = os.path.splitext(os.path.basename(filepath))[0]
                thumb_path = os.path.join(output_dir, f"{basename}_thumb.jpg")

                with open(thumb_path, 'wb') as thumb_file:
                    thumb_file.write(thumbnail_data)

                return thumb_path
        except Exception as e:
            print(f"  [!] Thumbnail çıxarma xətası: {e}", file=sys.stderr)

        return None

    def _extract_group(self, tags, tag_map):
        """Tag qrupunu çıxar."""
        result = {}
        for tag_name, key in tag_map.items():
            if tag_name in tags:
                value = str(tags[tag_name])
                if value and value != '0':
                    result[key] = value
        return result if result else None

    def _extract_settings(self, tags):
        """Çəkiliş parametrlərini çıxar və formatla."""
        settings = {}

        for tag_name, key in self.SETTINGS_TAGS.items():
            if tag_name in tags:
                value = tags[tag_name]
                str_value = str(value)

                if key == 'aperture':
                    # FNumber-ı f/X.X formatına çevir
                    try:
                        if hasattr(value.values[0], 'num'):
                            ratio = value.values[0]
                            f_num = ratio.num / ratio.den if ratio.den else 0
                            settings[key] = f"f/{f_num:.1f}"
                        else:
                            settings[key] = f"f/{str_value}"
                    except (IndexError, AttributeError):
                        settings[key] = str_value

                elif key == 'shutter_speed':
                    # Ekspozisiya vaxtını formatla
                    settings[key] = str_value

                elif key == 'focal_length':
                    # Fokus uzunluğunu mm ilə göstər
                    try:
                        if hasattr(value.values[0], 'num'):
                            ratio = value.values[0]
                            fl = ratio.num / ratio.den if ratio.den else 0
                            settings[key] = f"{fl:.1f}mm"
                        else:
                            settings[key] = f"{str_value}mm"
                    except (IndexError, AttributeError):
                        settings[key] = str_value

                elif key == 'iso':
                    settings[key] = int(str_value) if str_value.isdigit() else str_value

                else:
                    settings[key] = str_value

        return settings if settings else None

    def _extract_image_info(self, tags, filepath):
        """Şəkil ölçüsü və parametrləri."""
        info = self._extract_group(tags, self.IMAGE_TAGS) or {}

        # Əgər EXIF-də ölçü yoxdursa, Pillow ilə al
        if 'width' not in info or 'height' not in info:
            try:
                with Image.open(filepath) as img:
                    info['width'] = img.width
                    info['height'] = img.height
                    info['mode'] = img.mode
                    info['format'] = img.format
            except Exception:
                pass

        return info if info else None

    def _extract_gps(self, tags):
        """GPS koordinatlarını çıxar."""
        gps_lat = tags.get('GPS GPSLatitude')
        gps_lat_ref = tags.get('GPS GPSLatitudeRef')
        gps_lon = tags.get('GPS GPSLongitude')
        gps_lon_ref = tags.get('GPS GPSLongitudeRef')

        if not all([gps_lat, gps_lat_ref, gps_lon, gps_lon_ref]):
            return None

        latitude = dms_to_decimal(gps_lat.values, gps_lat_ref)
        longitude = dms_to_decimal(gps_lon.values, gps_lon_ref)

        if latitude is None or longitude is None:
            return None

        from utils.coordinate_validator import apply_sanitized_to_location
        location = apply_sanitized_to_location(
            format_coordinates(latitude, longitude), source='exif',
        )
        if not location:
            return None

        # Əlavə GPS məlumatları
        gps_alt = tags.get('GPS GPSAltitude')
        if gps_alt:
            try:
                if hasattr(gps_alt.values[0], 'num'):
                    ratio = gps_alt.values[0]
                    alt = ratio.num / ratio.den if ratio.den else 0
                    location['altitude_m'] = round(alt, 1)
                else:
                    location['altitude_m'] = float(str(gps_alt))
            except (IndexError, AttributeError, ValueError):
                pass

        gps_timestamp = tags.get('GPS GPSTimeStamp')
        gps_date = tags.get('GPS GPSDate')
        if gps_timestamp:
            location['gps_timestamp'] = str(gps_timestamp)
        if gps_date:
            location['gps_date'] = str(gps_date)

        return location

    def _extract_description(self, tags):
        """
        Təsvir/caption mətnini çıxar (dil analizi üçün).

        IPTC və EXIF description tag-larını yoxlayır.
        """
        description_tags = [
            'Image ImageDescription',
            'EXIF UserComment',
            'Image XPComment',
            'Image XPTitle',
            'Image XPSubject',
            'Image XPKeywords',
        ]

        descriptions = {}
        for tag in description_tags:
            if tag in tags:
                value = str(tags[tag]).strip()
                if value and value not in ('0', '', 'None'):
                    key = tag.split(' ', 1)[1] if ' ' in tag else tag
                    descriptions[key] = value

        return descriptions if descriptions else None

    def _extract_png_xmp(self, filepath):
        """PNG daxilindəki XMP və EXIF blokları."""
        tags = {}
        try:
            with open(filepath, 'rb') as f:
                raw = f.read(min(500000, os.path.getsize(filepath)))
            text = raw.decode('utf-8', errors='ignore')
            if 'xmp' in text.lower() or 'xpacket' in text.lower():
                for m in re.finditer(r'<([a-zA-Z0-9]+):([a-zA-Z0-9]+)[^>]*>([^<]{1,200})</', text):
                    key = f'XMP_{m.group(1)}_{m.group(2)}'
                    if key not in tags:
                        tags[key] = m.group(3).strip()
        except OSError:
            pass
        try:
            with Image.open(filepath) as img:
                exif = img.getexif()
                if exif:
                    for tag_id, value in exif.items():
                        name = TAGS.get(tag_id, str(tag_id))
                        tags[f'PNG_{name}'] = str(value)[:200]
        except Exception:
            pass
        return tags if tags else None

    def _get_pillow_info(self, filepath):
        """EXIF olmayan şəkillərdən Pillow ilə əsas məlumatları al."""
        try:
            with Image.open(filepath) as img:
                return {
                    'camera': None,
                    'settings': None,
                    'datetime': None,
                    'image': {
                        'width': img.width,
                        'height': img.height,
                        'mode': img.mode,
                        'format': img.format,
                    }
                }
        except Exception:
            return None

    def _extract_with_pillow(self, filepath):
        """Pillow getexif() ilə EXIF/GPS (exifread boş qaldıqda və ya GPS itirdikdə)."""
        try:
            with Image.open(filepath) as img:
                exif = img.getexif()
                if not exif:
                    return None, None, None

                raw_tags = {}
                camera = {}
                settings = {}
                datetime_info = {}
                image_info = {
                    'width': img.width,
                    'height': img.height,
                    'mode': img.mode,
                    'format': img.format,
                }

                pillow_to_exifread = {
                    'Make': ('Image Make', 'make'),
                    'Model': ('Image Model', 'model'),
                    'LensModel': ('EXIF LensModel', 'lens'),
                    'Software': ('Image Software', 'software'),
                    'DateTimeOriginal': ('EXIF DateTimeOriginal', 'original'),
                    'DateTimeDigitized': ('EXIF DateTimeDigitized', 'digitized'),
                    'DateTime': ('Image DateTime', 'modified'),
                    'ISOSpeedRatings': ('EXIF ISOSpeedRatings', 'iso'),
                    'FNumber': ('EXIF FNumber', 'aperture'),
                    'ExposureTime': ('EXIF ExposureTime', 'shutter_speed'),
                    'FocalLength': ('EXIF FocalLength', 'focal_length'),
                    'Orientation': ('Image Orientation', 'orientation'),
                }

                for tag_id, value in exif.items():
                    if tag_id == IFD_GPS:
                        continue
                    tag_name = TAGS.get(tag_id, str(tag_id))
                    formatted = self._format_pillow_value(value)
                    raw_tags[tag_name] = formatted

                    if tag_name in ('Make', 'Model', 'LensModel', 'Software'):
                        camera[pillow_to_exifread[tag_name][1]] = formatted
                    elif tag_name in ('DateTimeOriginal', 'DateTimeDigitized', 'DateTime'):
                        key = pillow_to_exifread[tag_name][1]
                        datetime_info[key] = formatted
                    elif tag_name in ('ISOSpeedRatings', 'FNumber', 'ExposureTime', 'FocalLength'):
                        settings[pillow_to_exifread[tag_name][1]] = formatted

                location = None
                try:
                    gps_ifd = exif.get_ifd(IFD_GPS)
                except Exception:
                    gps_ifd = None

                if gps_ifd:
                    location = self._extract_gps_from_pillow_ifd(gps_ifd)
                    for gps_tag_id, gps_value in gps_ifd.items():
                        gps_name = GPSTAGS.get(gps_tag_id, str(gps_tag_id))
                        raw_tags[f'GPS {gps_name}'] = self._format_pillow_value(gps_value)

                structured = {
                    'camera': camera or None,
                    'settings': settings or None,
                    'datetime': datetime_info or None,
                    'image': image_info,
                    'source': 'pillow',
                }
                return structured, location, raw_tags or None
        except Exception as e:
            print(f"  [!] Pillow EXIF oxuma xətası: {e}", file=sys.stderr)
            return None, None, None

    def _format_pillow_value(self, value):
        if isinstance(value, bytes):
            try:
                return value.decode('utf-8', errors='replace').strip('\x00')
            except Exception:
                return value.hex()
        if isinstance(value, tuple):
            parts = []
            for item in value:
                if hasattr(item, 'numerator') and hasattr(item, 'denominator'):
                    den = item.denominator or 1
                    parts.append(str(round(item.numerator / den, 6)))
                else:
                    parts.append(str(item))
            return ', '.join(parts)
        return str(value)

    def _extract_gps_from_pillow_ifd(self, gps_ifd):
        """Pillow GPS IFD-dən koordinat çıxar."""
        lat = gps_ifd.get(2)
        lat_ref = gps_ifd.get(1)
        lon = gps_ifd.get(4)
        lon_ref = gps_ifd.get(3)

        if not all([lat, lat_ref, lon, lon_ref]):
            return None

        def coord_to_decimal(parts, ref):
            ref_str = ref.decode() if isinstance(ref, bytes) else str(ref)
            decimals = []
            for part in parts:
                if hasattr(part, 'numerator') and hasattr(part, 'denominator'):
                    den = part.denominator or 1
                    decimals.append(part.numerator / den)
                else:
                    decimals.append(float(part))
            if len(decimals) < 3:
                return None
            value = decimals[0] + (decimals[1] / 60.0) + (decimals[2] / 3600.0)
            if ref_str in ('S', 'W'):
                value = -value
            return round(value, 6)

        latitude = coord_to_decimal(lat, lat_ref)
        longitude = coord_to_decimal(lon, lon_ref)
        if latitude is None or longitude is None:
            return None
        from utils.coordinate_validator import apply_sanitized_to_location
        return apply_sanitized_to_location(
            format_coordinates(latitude, longitude), source='exif',
        )

    def _merge_exif(self, primary, secondary):
        """İki EXIF strukturunu birləşdir (boş sahələri doldur)."""
        if not primary:
            return secondary
        if not secondary:
            return primary
        merged = dict(primary)
        for key in ('camera', 'settings', 'datetime', 'image'):
            if not merged.get(key) and secondary.get(key):
                merged[key] = secondary[key]
            elif merged.get(key) and secondary.get(key):
                if isinstance(merged[key], dict):
                    combined = dict(secondary[key])
                    combined.update(merged[key])
                    merged[key] = combined
        if secondary.get('source'):
            merged['source'] = secondary['source']
        return merged

    def _infer_datetime_from_filename(self, filepath):
        """WhatsApp fayl adından təxmini tarix/vaxt."""
        basename = os.path.basename(filepath)
        match = WHATSAPP_FILENAME_DT.search(basename)
        if not match:
            return None
        y, mo, d, h, mi, s = match.groups()
        return f"{y}:{mo}:{d} {h}:{mi}:{s}"

    def _build_warnings(self, filepath, result):
        """İstifadəçiyə göstəriləcək xəbərdarlıqlar."""
        warnings = []
        basename = os.path.basename(filepath).lower()
        has_gps = bool(result.get('location'))
        raw_count = len(result.get('raw_tags') or {})
        exif = result.get('exif') or {}
        has_camera = bool(exif.get('camera'))
        has_datetime = bool(exif.get('datetime'))

        if 'whatsapp' in basename:
            warnings.append(
                'WhatsApp şəkilləri adətən GPS və EXIF məlumatını silir. '
                'Orijinal kamera faylını yükləyin.'
            )
        elif 'telegram' in basename or 'instagram' in basename:
            warnings.append(
                'Mesajlaşma/sosial şəbəkə vasitəsilə göndərilmiş şəkillərdə metadata çox vaxt silinir.'
            )

        web = result.get('web_metadata') or {}
        richness = result.get('metadata_richness')
        field_count = web.get('field_count', 0)

        residual = result.get('residual_recovery') or {}
        if not has_gps and not has_camera and raw_count == 0:
            if residual.get('status') == 'success' or field_count >= 3 or web.get('has_embedded_blocks'):
                warnings.append(
                    'Kamera EXIF/GPS silinib. Qalıq bərpa + veb metadata aşağıda göstərilir.'
                )
            else:
                warnings.append(
                    'Əlavə metadata məhduddur. Orijinal fayl və ya məqalə URL (imgref) daha çox verə bilər.'
                )
        elif not has_gps and not has_camera and (field_count >= 2 or web.get('source_url') or residual):
            if not any('qalıq' in w.lower() or 'internet' in w.lower() or 'veb' in w.lower() for w in warnings):
                warnings.append(
                    'GPS/kamera EXIF yoxdur; qalıq bərpa və veb metadata əlavə edilib.'
                )

        inferred = self._infer_datetime_from_filename(filepath)
        if inferred and not has_datetime:
            if not exif.get('datetime'):
                if result.get('exif') is None:
                    result['exif'] = self._get_pillow_info(filepath) or {}
                result['exif']['datetime'] = {'inferred_from_filename': inferred}
            warnings.append(
                f'EXIF tarix yoxdur; fayl adından təxmini vaxt: {inferred.replace(":", "-", 2)}'
            )

        return warnings if warnings else None
