import os
import sys
import tempfile
from datetime import datetime
import re
import platform

try:
    import instaloader
    INSTALOADER_AVAILABLE = True
except ImportError:
    INSTALOADER_AVAILABLE = False

from analyzers.ai_analyzer import analyze_image_ai
from analyzers.terrain_analyzer import extract_skyline_and_terrain

def estimate_account_age(ig_id):
    """
    İnstagram ID-sinin böyüklüyünə görə hesabın yaradılma ilini (təxmini) qaytarır.
    """
    try:
        ig_id = int(ig_id)
        if ig_id < 10000000: return "2010 - 2011 (Çox Köhnə Hesab)"
        if ig_id < 200000000: return "2012 - 2013"
        if ig_id < 1000000000: return "2014 - 2015"
        if ig_id < 5000000000: return "2016 - 2018"
        if ig_id < 30000000000: return "2019 - 2021"
        return "2022+ (Nisbətən Yeni Hesab)"
    except:
        return "Bilinmir"

def guess_device_from_text(text):
    """
    Mətn və həştəqlərə əsasən cihaz təxmini.
    """
    if not text: return None
    text = text.lower()
    if re.search(r'(shotoniphone|iphone|apple)', text): return "Apple iPhone"
    if re.search(r'(shotonsamsung|samsung|galaxy|s2[0-9]ultra)', text): return "Samsung Galaxy"
    if re.search(r'(pixel|teampixel)', text): return "Google Pixel"
    if re.search(r'(canon|nikon|sonyalpha)', text): return "Peşəkar Kamera (DSLR/Mirrorless)"
    return None

def analyze_instagram_profile(username, max_posts=5):
    """
    İnstagram kəşfiyyat modulu (OSINT).
    Profildəki bioqrafiya, izləyici məlumatları, son postların şəkilləri
    və bu şəkillər üzərində AI vizual analizi (Lokasiya, Obyekt, OCR, Face) edir.
    """
    username = username.strip().lstrip('@')
    
    if not INSTALOADER_AVAILABLE:
        return {"error": "instaloader quraşdırılmayıb. Quraşdırmaq üçün: pip install instaloader"}
        
    print(f"  [i] İnstagram OSINT başlayır: @{username}", file=sys.stderr)
    result = {
        "target": username,
        "profile": {},
        "posts": []
    }
    
    # Instaloader obyekti yarat
    L = instaloader.Instaloader(
        download_pictures=True, 
        download_videos=False, 
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        quiet=True
    )
    
    try:
        # Önceki oturumu yükleyelim (varsa)
        # İnstaloader hepsinde ~/.instaloader dizinini kullanır
        # Windows'ta: C:\Users\username\.instaloader\session-USERNAME
        # Linux/Mac'ta: ~/.instaloader/session-USERNAME
        
        session_dir = os.path.expanduser('~/.instaloader')
        
        session_loaded = False
        
        try:
            if os.path.exists(session_dir):
                # Kaydedilen session dosyalarını bul
                for f in os.listdir(session_dir):
                    if f.startswith('session-'):
                        session_file = os.path.join(session_dir, f)
                        try:
                            L.load_session_from_file(session_file)
                            print(f"  [i] Oturum yüklendi: {f}", file=sys.stderr)
                            session_loaded = True
                            break
                        except:
                            pass
        except Exception as e:
            print(f"  [!] Session dizini hatası: {e}", file=sys.stderr)
        
        # Oturum yok, yeni giriş gerekli
        if not session_loaded:
            # Eğer TTY değilse (server ortamı), interaktif giriş yapma
            if not sys.stdin.isatty():
                return {"error": "Session dosyası bulunamadı. Lütfen CLI'dan manuel session oluşturun: instaloader --login username"}
            
            print(f"  [!] Oturum dosyası bulunamadı. İlk kez giriş yapılıyor...", file=sys.stderr)
            
            try:
                print("\n" + "="*50, file=sys.stderr)
                print("  Instagram Hesabınızla Giriş Yapın (OSINT için)", file=sys.stderr)
                print("="*50, file=sys.stderr)
                
                ig_username = input("  Instagram Kullanıcı Adı: ").strip()
                # Şifre görünür olacak şekilde (input yerine)
                ig_password = input("  Şifre: ").strip()
                
                try:
                    L.login(ig_username, ig_password)
                    print(f"  [✓] Başarılı giriş! Oturum kaydediliyor...", file=sys.stderr)
                    
                    # instaloader otomatik olarak session'ı ~/.instaloader/session-USERNAME formatında kaydeder
                    print(f"  [✓] Oturum kaydedildi: ~/.instaloader/session-{ig_username}", file=sys.stderr)
                except instaloader.exceptions.TwoFactorAuthRequiredException:
                    print(f"  [!] İki Faktörlü Doğrulama Gerekli", file=sys.stderr)
                    print(f"  İnstagram hesabınızda 2FA etkinleştirilmiş.", file=sys.stderr)
                    print(f"  ", file=sys.stderr)
                    print(f"  Çözüm: İnstaloader Session dosyasını manuel olarak oluşturmalısınız:", file=sys.stderr)
                    print(f"  1. instaloader -u {ig_username} profil_adi", file=sys.stderr)
                    print(f"  2. 2FA kodunu terminal-da girin", file=sys.stderr)
                    print(f"  3. Oturum ~/.instaloader/session dosyasına kaydedilecektir", file=sys.stderr)
                    return {"error": f"2FA etkinleştirilmiş - Manuel session kurulumu gerekli"}
                except Exception as login_err:
                    return {"error": f"Giriş başarısız: {login_err}"}
            except (EOFError, KeyboardInterrupt):
                # stdin kapalıysa - server ortamı
                return {"error": "Session dosyası bulunamadı ve interaktif giriş yapılamadı. Lütfen CLI'dan manuel session oluşturun: instaloader --login your_username"}
        
        # Profil bilgilerini al
        profile = instaloader.Profile.from_username(L.context, username)
        
        # Profil Məlumatları
        result["profile"] = {
            "id": profile.userid,
            "estimated_creation": estimate_account_age(profile.userid),
            "full_name": profile.full_name,
            "biography": profile.biography,
            "followers": profile.followers,
            "followees": profile.followees,
            "risk_ratio": round(profile.followees / max(profile.followers, 1), 2),
            "is_private": profile.is_private,
            "is_verified": profile.is_verified,
            "profile_pic_url": profile.profile_pic_url,
            "external_url": profile.external_url
        }
        
        if profile.is_private:
            result["error"] = "Bu hesab gizlidir. İcazə olmadan postlara daxil olmaq mümkün deyil."
            return result
            
        print(f"  [i] Postlar çəkilir (Max {max_posts})...", file=sys.stderr)
        
        # Temp qovluq yarat
        temp_dir = tempfile.mkdtemp(prefix="ig_osint_")
        L.dirname_pattern = temp_dir
        
        post_count = 0
        for post in profile.get_posts():
            if post_count >= max_posts:
                break
                
            post_data = {
                "date": str(post.date_utc),
                "caption": post.caption or "",
                "hashtags": post.caption_hashtags,
                "tagged_users": post.tagged_users,
                "location": post.location.name if post.location else None,
                "url": post.url,
                "likes": post.likes,
                "ai_analysis": {}
            }
            
            # Şəkli endir və analiz et
            print(f"  [i] Post endirilir və analiz edilir: {post.date_utc}", file=sys.stderr)
            try:
                L.download_post(post, target=temp_dir)
                # İndi yüklənmiş faylı tap
                for f in os.listdir(temp_dir):
                    if f.endswith(".jpg") and "UTC" in f:
                        img_path = os.path.join(temp_dir, f)
                        
                        # 1. AI Analizi (OCR + Object Detection)
                        ai_res = analyze_image_ai(img_path)
                        if ai_res:
                            post_data["ai_analysis"]["objects_and_text"] = ai_res
                            
                        # 2. Terrain Analizi (Skyline/Mountain OSINT)
                        terr_res = extract_skyline_and_terrain(img_path)
                        if terr_res.get("status") == "success":
                            post_data["ai_analysis"]["terrain_keypoints"] = terr_res.get("sift_keypoints_found", 0)
                            
                        # Faylı sil ki, növbəti postla qarışmasın
                        os.remove(img_path)
            except Exception as e:
                print(f"  [!] Post analizində xəta: {e}", file=sys.stderr)
                
            # Cihaz təxmini
            device_guess = guess_device_from_text(post_data["caption"])
            if not device_guess and post_data["hashtags"]:
                device_guess = guess_device_from_text(" ".join(post_data["hashtags"]))
            if device_guess:
                post_data["estimated_device"] = device_guess
                
            result["posts"].append(post_data)
            post_count += 1
            
        # Davranış Analizi (Ən aktiv saatlar)
        if result["posts"]:
            hours = [datetime.strptime(p["date"], "%Y-%m-%d %H:%M:%S").hour for p in result["posts"]]
            avg_hour = sum(hours) / len(hours)
            
            time_str = "Gecə" if avg_hour < 6 else "Səhər" if avg_hour < 12 else "Günorta" if avg_hour < 18 else "Axşam"
            
            result["behavior_analysis"] = {
                "average_post_hour": round(avg_hour, 1),
                "most_active_time_of_day": time_str,
                "notes": f"İstifadəçi əsasən {time_str} saatlarında post paylaşır."
            }
            
        print("  [OK] İnstagram kəşfiyyatı bitdi.", file=sys.stderr)
        return result
        
    except instaloader.exceptions.ProfileNotExistsException:
        return {"error": f"Hesap tapılmadı: {username}"}
    except Exception as e:
        print(f"  [!] İnstagram OSINT xətası: {e}", file=sys.stderr)
        return {"error": str(e)}
