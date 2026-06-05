# Metadata Extractor

Paylaşılmış fotoların EXIF datası, GPS koordinatlarından lokasiya (check-in), mətndən dil analizi və digər fayl (PDF, Audio, DOCX) metadata-larını çıxaran Python CLI aləti. Alət həm lokal fayllar, həm də sosial media URL-ləri ilə işləyə bilir. Nəticələr layihə qovluğundakı `results/` direktoriyasında JSON formatında saxlanılır.

## Quraşdırılma

Əvvəlcə lazımi kitabxanaları quraşdırın:

```bash
pip install -r requirements.txt
```

> **Qeyd:** Windows istifadəçiləri üçün `python-magic-bin` quraşdırılmışdır. Linux və ya macOS istifadə edirsinizsə, `requirements.txt`-dən bu paketi silib əvəzinə sisteminizin paket meneceri ilə `libmagic` yükləyə və `pip install python-magic` edə bilərsiniz.

## İstifadə

```bash
# Tək fayl analizi
python main.py photo.jpg

# URL-dən yükləyib analiz et
python main.py https://example.com/photo.jpg

# Instagram profiline OSINT analizi
python main.py --instagram @cristiano --max-posts 5

# Qovluqdakı bütün faylları skan et (rekursiv)
python main.py ./photos/ --recursive

# Yalnız GPS məlumatını çıxar
python main.py photo.jpg --gps-only

# URL-dən faylı yüklə, analiz et və faylı kompüterdə saxla (avtomatik silmə)
python main.py https://example.com/photo.jpg --keep

# Dil analizi üçün əlavə mətn təqdim et
python main.py photo.jpg --text "Bu şəkil Bakıda çəkilib"
```

## Instagram OSINT Entegrasyonu

### Necə işləyir?
Sistem, **İnstagram anti-bot bloklama** sorununu aşmak üçün sizin kişisel hesabınız aracılığıyla oturum açmaktadır. Bu sayede istənilən ictimai profilin verilerini çekebilir.

### ⚠️ ÖNEMLİ: İki Faktörlü Doğrulama (2FA)

Eğer Instagram hesabınızda **2FA etkinleştirilmişse**, şu adımları izleyin:

1. **Manual session oluşturun:**
```bash
instaloader -u sizin_instagram_kullanici_adi hedef_profili_adi
```

2. **İki Faktörlü Kod Girin:**
   - Terminal-da 2FA kodunu girin
   - Sistem oturum dosyasını otomatik olarak kaydedecektir

3. **Sonra bu sistem ile kullanabilirsiniz:**
```bash
python main.py --instagram @hedef_profil --max-posts 5
```

### Kurulum (2FA Yok)

**İlk kez çalıştırma:**
```bash
python main.py --instagram @hedef_profil --max-posts 5
```

Sistem şunu soracak:
```
Instagram Kullanıcı Adı: sizin_instagram_kullanici_adi
Şifre: (yazarken görünecek)
```

**Oturum kaydediliyor:**
- Verileriniz `~/.instaloader/session` dosyasında güvenli şekilde kaydedilir
- Sonraki çalışmalarda bu oturum otomatik olarak yüklenecektir

### Neden Kişisel Hesap Gerekli?

1. **Instagram 403 Bloklaması:** Instagram anonim bot isteklerini bloklar
2. **Real User Session:** Gerçek bir hesaptan gelen istekler normal kabul edilir  
3. **OSINT Amaçlı:** Herhangi bir ictimai profilin açık verilerini çekebilirsiniz
4. **Güvenli:** Session dosyası yalnızca yerel bilgisayarda saklanır

## Arxitektura və Modullar

Layihə modulyar şəkildə dizayn edilmişdir:

- **Extractors:** Bütün fayllardan metadata çıxaran əsas modullar.
  - `ImageExtractor`: Şəkil faylları üçün (EXIF, Thumbnail)
  - `PdfExtractor`: PDF faylları üçün
  - `AudioExtractor`: MP3, FLAC, OGG kimi səs faylları üçün
  - `DocumentExtractor`: Word sənədləri (DOCX) üçün
- **Analyzers:** Çıxarılmış məlumatların üzərində əlavə emal aparan modullar.
  - `GeoAnalyzer`: GPS koordinatlarını oxunaqlı ünvanlara (şəhər, ölkə) çevirir
  - `LanguageAnalyzer`: Mətndən hansı dildə yazıldığını təxmin edir
- **Downloaders:**
  - `UrlDownloader`: Adi internet linklərindən və ya sosial mediadan (`yt-dlp` vasitəsilə) media fayllarını endirir
- **Reporters:**
  - `JsonReporter`: Nəticələri gözəl formatlanmış JSON şəklində yadda saxlayır
- **Utils:** Köməkçi vasitələr (fayl tipinin təyini, GPS dönüşümləri)
