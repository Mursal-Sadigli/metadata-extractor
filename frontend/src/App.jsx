import React, { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { UploadCloud, Camera, MapPin, ShieldAlert, Globe, Download, Loader2, ArrowLeft, Terminal, FileText, AlertCircle, GitCompare, Archive, Link2, ScanFace, Box, Brain, Sparkles, Music, Film } from 'lucide-react';
import 'leaflet/dist/leaflet.css';
import { api, API_BASE, getAuthToken, normalizeUploadResponse } from './apiClient';
import AdminLogin from './components/AdminLogin';

import ForensicsPanel from './components/ForensicsPanel';
import OsintPanel from './components/OsintPanel';
import ReverseImageSearchPanel from './components/ReverseImageSearchPanel';
import ComparePanel from './components/ComparePanel';
import ArchiveResultsPanel from './components/ArchiveResultsPanel';
import SocialMetaPanel from './components/SocialMetaPanel';
import LocationPanel from './components/LocationPanel';
import ProgramTracesPanel from './components/ProgramTracesPanel';
import InternalStructurePanel from './components/InternalStructurePanel';
import FacePrivacyPanel from './components/FacePrivacyPanel';
import ObjectDetectionPanel from './components/ObjectDetectionPanel';
import VisionMLPanel from './components/VisionMLPanel';
import RestoreAnalyzePanel from './components/RestoreAnalyzePanel';
import MediaMetadataPanel from './components/MediaMetadataPanel';
import CaptureDatePanel from './components/CaptureDatePanel';
import PropagationAnalysisPanel from './components/PropagationAnalysisPanel';
import { exportToPDF } from './exportUtils';
import './CyberTheme.css';

function buildMetadataEntries(exifData) {
  const entries = [];
  const seen = new Set();
  const push = (label, value, maxLen = 220) => {
    const str = value == null ? '' : String(value);
    if (!str || str.length > maxLen) return;
    const dedupe = `${label}:${str}`;
    if (seen.has(dedupe)) return;
    seen.add(dedupe);
    entries.push({ key: label, value: str });
  };

  const exif = exifData?.exif;
  if (exif?.image) {
    const img = exif.image;
    if (img.width && img.height) push('Ölçü', `${img.width} × ${img.height} px`);
    if (img.format) push('Format', img.format);
    if (img.mode) push('Rəng rejimi', img.mode);
  }
  if (exif?.camera) {
    Object.entries(exif.camera).forEach(([k, v]) => push(k, v));
  }
  if (exifData?.software_traces?.primary_application) {
    push('Proqram (aşkarlanmış)', exifData.software_traces.primary_application);
  }
  const cap = exifData?.capture_date;
  if (cap?.status === 'success') {
    push('Çəkiliş — gün', cap.calendar_az?.gun ?? cap.day);
    push('Çəkiliş — ay', cap.calendar_az?.ay ?? cap.month);
    push('Çəkiliş — il', cap.calendar_az?.il ?? cap.year);
    if (cap.iso_datetime) push('Çəkiliş — tam vaxt', cap.iso_datetime);
    if (cap.source_label_az) push('Tarix mənbəyi', cap.source_label_az);
    if (cap.wayback_note_az) push('Wayback qeydi', cap.wayback_note_az, 400);
    if (cap.wayback_url) push('Wayback snapshot', cap.wayback_url, 500);
  }
  if (exif?.datetime) {
    Object.entries(exif.datetime).forEach(([k, v]) => {
      const label = k === 'inferred_from_filename' ? 'Təxmini vaxt (fayl adı)' : k;
      push(label, v);
    });
  }
  if (exif?.settings) {
    Object.entries(exif.settings).forEach(([k, v]) => push(k, v));
  }
  if (exifData?.raw_tags) {
    Object.entries(exifData.raw_tags).forEach(([key, value]) => {
      if (String(value).length > 100) return;
      push(key.replace('Image ', '').replace('EXIF ', ''), value);
    });
  }
  if (exifData?.file_info) {
    push('Fayl ölçüsü', exifData.file_info.size_human);
  }
  const web = exifData?.web_metadata;
  if (web?.domain) push('Mənbə domeni', web.domain);
  if (web?.source_url) push('Orijinal URL', web.source_url, 500);
  if (web?.resolved_url && web.resolved_url !== web.source_url) {
    push('Həll olunmuş URL', web.resolved_url, 500);
  }
  if (web?.page_url) push('Mənbə səhifə', web.page_url, 500);
  if (web?.source_kind === 'google') push('Mənbə tipi', 'Google şəkil');
  if (web?.summary_az) push('Xülasə', web.summary_az, 400);
  if (web?.hashes?.md5) push('MD5', web.hashes.md5);
  if (web?.hashes?.sha256) push('SHA256', web.hashes.sha256);
  const dl = web?.technical?.download;
  if (dl?.content_type) push('Content-Type', dl.content_type);
  if (dl?.content_length) push('Fayl ölçüsü (bayt)', dl.content_length);
  if (dl?.downloaded_at) push('Yüklənmə vaxtı', dl.downloaded_at);
  if (web?.technical?.http_headers?.['Last-Modified']) {
    push('HTTP Last-Modified', web.technical.http_headers['Last-Modified']);
  }
  if (web?.technical?.google_cdn?.cdn_max_edge) {
    push('Google CDN kənar', `${web.technical.google_cdn.cdn_max_edge}px`);
  }
  const prop = exifData?.image_propagation;
  if (prop?.image_hash) push('image_hash', prop.image_hash);
  if (prop?.global_first_seen_display_az) push('İlk internet izi', prop.global_first_seen_display_az);
  if (prop?.occurrences?.[0]) {
    const o = prop.occurrences[0];
    if (o.first_seen) push('first_seen', o.first_seen);
    if (o.source) push('source', o.source);
    if (o.confidence != null) push('confidence', `${Math.round(o.confidence * 100)}%`);
  }
  if (web?.page?.og_title) push('Səhifə başlığı', web.page.og_title);
  if (web?.page?.og_description) push('Səhifə təsviri', web.page.og_description.slice(0, 150));
  if (web?.page?.published) push('Dərc tarixi', web.page.published);
  if (web?.technical?.jpeg_markers) push('JPEG blokları', web.technical.jpeg_markers.join(', '));
  if (web?.embedded) {
    Object.entries(web.embedded).slice(0, 24).forEach(([k, v]) => push(k, v));
  }
  if (exifData?.description) {
    Object.entries(exifData.description).forEach(([k, v]) => push(k, v));
  }
  const rr = exifData?.residual_recovery;
  if (rr?.summary_az) push('Qalıq bərpa', rr.summary_az, 400);
  if (rr?.recovery_score != null) push('Bərpa skoru', `${rr.recovery_score}/100`);
  if (rr?.sources_used?.length) push('Bərpa mənbələri', rr.sources_used.join(', '));
  if (rr?.best_gps_source) push('GPS mənbə (bərpa)', rr.best_gps_source);
  if (rr?.recovered_tag_count) push('Bərpa tag sayı', rr.recovered_tag_count);
  if (exifData?.location?.inferred && exifData?.location?.label) {
    push('Bərpa GPS', exifData.location.label);
    if (exifData.location.display) push('Koordinat', exifData.location.display);
  }
  const webPage = exifData?.web_metadata?.page;
  if (webPage?.page_title) push('Səhifə başlıq', webPage.page_title);
  if (webPage?.og_title) push('Səhifə OG', webPage.og_title);
  return entries;
}

const metaTagStyle = {
  background: '#0f172a',
  padding: '8px 10px',
  borderRadius: '8px',
  border: '1px solid #293548',
};

/* ───────── Stillər ───────── */
const styles = {
  page: {
    minHeight: '100vh',
    background: '#0f172a',
    color: '#f1f5f9',
    padding: '24px 32px 60px',
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    transition: 'all 0.3s ease'
  },
  container: {
    maxWidth: '1100px',
    margin: '0 auto',
  },
  header: {
    textAlign: 'center',
    paddingTop: '32px',
    marginBottom: '32px',
    position: 'relative'
  },
  h1: {
    fontSize: '36px',
    fontWeight: '800',
    background: 'linear-gradient(135deg, #60a5fa, #818cf8, #a78bfa)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    margin: '0 0 10px',
  },
  subtitle: {
    fontSize: '15px',
    color: '#94a3b8',
    margin: 0,
    maxWidth: '600px',
    marginLeft: 'auto',
    marginRight: 'auto',
    lineHeight: '1.5',
  },
  errorBox: {
    background: 'rgba(239,68,68,0.1)',
    border: '1px solid rgba(239,68,68,0.3)',
    borderRadius: '12px',
    padding: '12px 16px',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    color: '#f87171',
    maxWidth: '600px',
    margin: '0 auto 20px',
    fontSize: '14px',
  },
  dropzone: (isDragActive, uploading) => ({
    border: `2px dashed ${isDragActive ? '#818cf8' : '#334155'}`,
    borderRadius: '20px',
    padding: '64px 32px',
    textAlign: 'center',
    cursor: uploading ? 'not-allowed' : 'pointer',
    transition: 'all 0.3s',
    maxWidth: '680px',
    margin: '0 auto',
    background: isDragActive ? 'rgba(129,140,248,0.08)' : 'rgba(30,41,59,0.5)',
    opacity: uploading ? 0.6 : 1,
  }),
  toolbar: {
    display: 'flex',
    alignItems: 'center',
    gap: '14px',
    background: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '14px',
    padding: '10px 18px',
    marginBottom: '20px',
    flexWrap: 'wrap',
  },
  thumbnail: {
    width: '48px',
    height: '48px',
    borderRadius: '8px',
    overflow: 'hidden',
    border: '2px solid #475569',
    flexShrink: 0,
    background: '#000',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  },
  thumbImg: {
    width: '48px',
    height: '48px',
    objectFit: 'cover',
    display: 'block',
  },
  fileInfo: {
    flex: '1',
    minWidth: '0',
  },
  fileName: {
    fontSize: '13px',
    color: '#e2e8f0',
    fontWeight: '600',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  btnGroup: {
    display: 'flex',
    gap: '6px',
    flexShrink: 0,
    flexWrap: 'wrap'
  },
  actionBtn: (isActive, color) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    padding: '6px 12px',
    borderRadius: '8px',
    fontSize: '12px',
    fontWeight: '600',
    border: isActive ? `1px solid ${color}` : '1px solid #475569',
    background: isActive ? `${color}22` : '#0f172a',
    color: isActive ? color : '#cbd5e1',
    cursor: isActive ? 'default' : 'pointer',
    transition: 'all 0.2s',
    whiteSpace: 'nowrap',
  }),
  iconBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    padding: '6px 10px',
    borderRadius: '8px',
    fontSize: '11px',
    fontWeight: '500',
    border: '1px solid #334155',
    background: 'transparent',
    color: '#94a3b8',
    cursor: 'pointer',
    flexShrink: 0,
    whiteSpace: 'nowrap',
  },
  card: (borderColor) => ({
    background: '#1e293b',
    borderRadius: '14px',
    padding: '20px',
    border: `1px solid ${borderColor}`,
    marginBottom: '16px',
  })
};

function App() {
  const [authed, setAuthed] = useState(() => Boolean(getAuthToken()));
  const [cyberMode, setCyberMode] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [error, setError] = useState(null);

  // States
  const [loadingExif, setLoadingExif] = useState(false);
  const [loadingLocation, setLoadingLocation] = useState(false);
  const [loadingForensics, setLoadingForensics] = useState(false);
  const [loadingOsint, setLoadingOsint] = useState(false);
  const [loadingFacePrivacy, setLoadingFacePrivacy] = useState(false);
  const [loadingFaceAnonymize, setLoadingFaceAnonymize] = useState(false);
  const [loadingObjects, setLoadingObjects] = useState(false);
  const [loadingVision, setLoadingVision] = useState(false);
  const [loadingRestore, setLoadingRestore] = useState(false);

  // Data
  const [exifData, setExifData] = useState(null);
  const [locationData, setLocationData] = useState(null);
  const [forensicsData, setForensicsData] = useState(null);
  const [osintData, setOsintData] = useState(null);
  const [facePrivacyData, setFacePrivacyData] = useState(null);
  const [objectDetectionData, setObjectDetectionData] = useState(null);
  const [visionData, setVisionData] = useState(null);
  const [restoreData, setRestoreData] = useState(null);
  const [faceAnonymizeOptions, setFaceAnonymizeOptions] = useState({
    enabled: false,
    method: 'blur',
    strength: 3,
  });
  const [compareData, setCompareData] = useState(null);
  const [loadingCompare, setLoadingCompare] = useState(false);
  const [archiveData, setArchiveData] = useState(null);
  const [loadingArchive, setLoadingArchive] = useState(false);
  const [socialData, setSocialData] = useState(null);
  const [loadingSocial, setLoadingSocial] = useState(false);
  const [socialUrl, setSocialUrl] = useState('');
  const [loadingUploadUrl, setLoadingUploadUrl] = useState(false);
  const [urlWarnings, setUrlWarnings] = useState([]);
  const [videoFrame, setVideoFrame] = useState(0);

  const isSocialMediaUrl = (u) => /instagram\.com|tiktok\.com|twitter\.com|x\.com|facebook\.com|youtube\.com|youtu\.be|vk\.com/i.test(u || '');
  const isImageUrl = (u) => {
    const s = (u || '').trim();
    if (!s || isSocialMediaUrl(s)) return false;
    if (/imgurl=|googleusercontent|gstatic\.com|ggpht\.com|\/imgres/i.test(s)) return true;
    if (/images\.unsplash\.com|unsplash\.com/i.test(s)) return true;
    if (/\.(jpe?g|png|webp|gif|heic|heif|bmp|avif)(\?|#|$)/i.test(s)) return true;
    if (/\/a\/img\/|\/resize\/|\/media\/|\/images\/|\/photo[-/]|\/hub\//i.test(s)) return true;
    if (/[?&](auto=format|fit=crop|ixlib=|w=\d)/i.test(s)) return true;
    return false;
  };

  const isHttpUrl = (u) => /^https?:\/\/.+/i.test((u || '').trim());

  const cleanupUploads = useCallback(async () => {
    try {
      await api.post('/api/cleanup-uploads');
    } catch (_) { /* ignore */ }
  }, []);

  // Səhifə açılışında və bağlananda müvəqqəti faylları sil (yalnız girişdən sonra)
  useEffect(() => {
    if (!authed) return undefined;
    const onLeave = () => {
      const token = getAuthToken();
      fetch(`${API_BASE}/api/cleanup-uploads`, {
        method: 'POST',
        keepalive: true,
        headers: token ? { 'x-auth-token': token } : {},
      });
    };
    window.addEventListener('beforeunload', onLeave);
    return () => {
      window.removeEventListener('beforeunload', onLeave);
      cleanupUploads();
    };
  }, [authed, cleanupUploads]);

  // Tema tətbiqi
  useEffect(() => {
    if (cyberMode) document.body.classList.add('cyber-theme');
    else document.body.classList.remove('cyber-theme');
  }, [cyberMode]);

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;

    await cleanupUploads();
    setUploading(true);
    setError(null);
    setUrlWarnings([]);
    setUploadedFile(null);
    setExifData(null);
    setLocationData(null);
    setForensicsData(null);
    setOsintData(null);
    setFacePrivacyData(null);
    setObjectDetectionData(null);
    setVisionData(null);
    setRestoreData(null);
    setCompareData(null);
    setArchiveData(null);
    setSocialData(null);
    setVideoFrame(0);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post('/api/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setUploadedFile(normalizeUploadResponse(response.data));
    } catch (err) {
      setError('Fayl yüklənərkən xəta baş verdi.');
    } finally {
      setUploading(false);
    }
  }, [cleanupUploads]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.webp', '.gif', '.heic', '.heif'],
      'video/*': ['.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v'],
      'audio/*': ['.mp3', '.wav', '.flac', '.ogg', '.aac', '.m4a', '.wma'],
      'application/pdf': ['.pdf'],
      'application/zip': ['.zip'],
    },
  });

  const isVideoFile = (name) => /\.(mp4|mov|webm|mkv|avi|m4v)$/i.test(name || '');
  const isAudioFile = (name) => /\.(mp3|wav|flac|ogg|aac|m4a|wma)$/i.test(name || '');
  const isMediaFile = (name) => isVideoFile(name) || isAudioFile(name);

  const runVideoTracking = async ({
    enable_face_reid = false,
    anonymize_first = false,
    method = 'blur',
    strength = 3,
  } = {}) => {
    if (!uploadedFile) return;
    if (enable_face_reid) {
      if (anonymize_first) setLoadingFaceAnonymize(true);
      else setLoadingFacePrivacy(true);
    } else {
      setLoadingObjects(true);
    }
    setError(null);
    try {
      const response = await api.post(
        '/api/video-tracking',
        {
          filename: uploadedFile.filename,
          tracker: 'bytetrack',
          enable_face_reid,
          anonymize_first,
          method,
          strength,
          confidence: 0.35,
          sample_fps: 2,
          max_duration_sec: 120,
        },
        { timeout: 600000 }
      );
      const payload = { ...response.data, video_tracking: response.data.video_tracking };
      if (enable_face_reid) {
        setFacePrivacyData(payload);
        setObjectDetectionData(null);
      } else {
        setObjectDetectionData(payload);
        setFacePrivacyData(null);
      }
    } catch (err) {
      const msg = err.response?.data?.error
        || (err.code === 'ECONNABORTED' ? 'Video izləmə çox uzun çəkdi (10 dəq limit).' : null)
        || 'Video izləmə zamanı xəta baş verdi.';
      setError(msg);
    } finally {
      setLoadingFacePrivacy(false);
      setLoadingFaceAnonymize(false);
      setLoadingObjects(false);
    }
  };

  const analyze = async (type, frameIndex = videoFrame, filenameOverride = null) => {
    const filename = filenameOverride || uploadedFile?.filename;
    if (!filename) return;

    let setLoading, setData;
    if (type === 'exif') { setLoading = setLoadingExif; setData = setExifData; }
    else if (type === 'location') { setLoading = setLoadingLocation; setData = setLocationData; }
    else if (type === 'forensics') { setLoading = setLoadingForensics; setData = setForensicsData; }
    else if (type === 'osint') { setLoading = setLoadingOsint; setData = setOsintData; }

    setLoading(true);
    setError(null);

    try {
      const response = await api.post('/api/analyze', {
        filename,
        type: type,
        video_frame: frameIndex,
      }, { timeout: 300000 });
      setData(response.data);
    } catch (err) {
      const d = err.response?.data;
      let msg = d?.error || `${type.toUpperCase()} analizi zamanı xəta baş verdi.`;
      if (d?.details) msg += ` (${String(d.details).slice(0, 150)})`;
      if (err.code === 'ECONNABORTED') {
        msg = 'Analiz çox uzun çəkdi. Render Free planda ilk sorğu yavaş ola bilər — yenidən cəhd edin.';
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const runFacePrivacy = async (withAnonymize = false, options = faceAnonymizeOptions) => {
    if (!uploadedFile) return;
    const isAnon = Boolean(withAnonymize && options?.enabled);
    if (isVideoFile(uploadedFile.originalName)) {
      return runVideoTracking({
        enable_face_reid: true,
        anonymize_first: isAnon,
        method: options?.method || 'blur',
        strength: options?.strength ?? 3,
      });
    }
    if (isAnon) setLoadingFaceAnonymize(true);
    else setLoadingFacePrivacy(true);
    setError(null);
    try {
      const response = await api.post('/api/face-privacy', {
        filename: uploadedFile.filename,
        anonymize: isAnon,
        method: options?.method || 'blur',
        strength: options?.strength ?? 3,
        video_frame: videoFrame,
      });
      setFacePrivacyData(response.data);
    } catch (err) {
      setError(isAnon ? 'Anonimləşdirmə zamanı xəta baş verdi.' : 'Üz məxfiliyi analizi zamanı xəta baş verdi.');
    } finally {
      setLoadingFacePrivacy(false);
      setLoadingFaceAnonymize(false);
    }
  };

  const runVisionML = async () => {
    if (!uploadedFile) return;
    setLoadingVision(true);
    setError(null);
    try {
      const response = await api.post(
        '/api/vision-ml',
        {
          filename: uploadedFile.filename,
          confidence: 0.16,
          video_frame: videoFrame,
        },
        { timeout: 600000 }
      );
      setVisionData(response.data);
    } catch (err) {
      const msg = err.response?.data?.error
        || (err.code === 'ECONNABORTED' ? 'Computer Vision analizi çox uzun çəkdi.' : null)
        || 'Computer Vision analizi zamanı xəta baş verdi.';
      setError(msg);
    } finally {
      setLoadingVision(false);
    }
  };

  const runRestoreAnalyze = async () => {
    if (!uploadedFile) return;
    setLoadingRestore(true);
    setError(null);
    try {
      const response = await api.post(
        '/api/restore-analyze',
        { filename: uploadedFile.filename },
        { timeout: 600000 }
      );
      setRestoreData(response.data);
    } catch (err) {
      const msg = err.response?.data?.error
        || (err.code === 'ECONNABORTED' ? 'Bərpa analizi çox uzun çəkdi.' : null)
        || 'Bərpa + analiz zamanı xəta baş verdi.';
      setError(msg);
    } finally {
      setLoadingRestore(false);
    }
  };

  const runObjectDetection = async () => {
    if (!uploadedFile) return;
    if (isVideoFile(uploadedFile.originalName)) {
      return runVideoTracking({
        enable_face_reid: false,
        anonymize_first: faceAnonymizeOptions?.enabled ?? false,
        method: faceAnonymizeOptions?.method || 'blur',
        strength: faceAnonymizeOptions?.strength ?? 3,
      });
    }
    setLoadingObjects(true);
    setError(null);
    try {
      const response = await api.post('/api/object-detection', {
        filename: uploadedFile.filename,
        confidence: 0.16,
        video_frame: videoFrame,
      });
      setObjectDetectionData(response.data);
    } catch (err) {
      setError('Obyekt aşkarlanması zamanı xəta baş verdi.');
    } finally {
      setLoadingObjects(false);
    }
  };

  const runCompareSecondFile = async (file) => {
    if (!uploadedFile) return;
    setLoadingCompare(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const up = await api.post('/api/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const cmp = await api.post('/api/compare', {
        filenameA: uploadedFile.filename,
        filenameB: up.data.filename,
      });
      setCompareData(cmp.data);
    } catch (err) {
      setError('Müqayisə zamanı xəta baş verdi.');
    } finally {
      setLoadingCompare(false);
    }
  };

  const onArchiveDrop = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !file.name.endsWith('.zip')) return;
    setLoadingArchive(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.post('/api/analyze-archive', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setArchiveData(res.data);
    } catch (err) {
      setError('Arxiv analizi zamanı xəta baş verdi.');
    } finally {
      setLoadingArchive(false);
    }
  };

  const analyzeSocialFile = async () => {
    if (!uploadedFile) return;
    setLoadingSocial(true);
    setError(null);
    setSocialData(null);
    try {
      const res = await api.post('/api/social-meta', {
        filename: uploadedFile.filename,
        video_frame: videoFrame,
      });
      setSocialData(res.data);
    } catch (err) {
      const d = err.response?.data;
      let msg = d?.error || 'Sosial metadata analizi zamanı xəta baş verdi.';
      if (d?.details) msg += ` (${String(d.details).slice(0, 150)})`;
      if (err.code === 'ECONNABORTED') {
        msg = 'Sosial metadata çox uzun çəkdi — yenidən cəhd edin.';
      }
      setError(msg);
    } finally {
      setLoadingSocial(false);
    }
  };

  const uploadImageFromUrl = async () => {
    const raw = socialUrl.trim();
    if (!raw) return;
    if (isSocialMediaUrl(raw)) {
      setError('Sosial media linki üçün «Link analizi» düyməsini seçin.');
      return;
    }
    if (!isHttpUrl(raw)) {
      setError('Keçərli https:// URL daxil edin.');
      return;
    }
    setLoadingUploadUrl(true);
    await cleanupUploads();
    setError(null);
    setUrlWarnings([]);
    setUploadedFile(null);
    setExifData(null);
    setLocationData(null);
    setForensicsData(null);
    setOsintData(null);
    setFacePrivacyData(null);
    setObjectDetectionData(null);
    setVisionData(null);
    setRestoreData(null);
    setCompareData(null);
    setArchiveData(null);
    setSocialData(null);
    try {
      const res = await api.post(
        '/api/upload-from-url',
        { url: raw },
        { timeout: 240000 }
      );
      setUploadedFile(normalizeUploadResponse(res.data));
      if (res.data.warnings?.length) setUrlWarnings(res.data.warnings);
    } catch (err) {
      const d = err.response?.data;
      let msg = d?.error || err.message || 'Şəkil URL yüklənmədi.';
      if (d?.details) msg += ` (${String(d.details).slice(0, 120)})`;
      if (d?.hint === 'truncated_url' || d?.hint === 'http_404') {
        msg += ' Unsplash/Wikimedia linkləri uzantısız da işləyir; CNET üçün tam .jpg link lazımdır.';
      }
      if (d?.hint === 'google_search_page') {
        msg = (d.error || msg) + ' Şəkilə sağ klik → Copy image address.';
      }
      if (err.code === 'ECONNABORTED') {
        msg = 'Yükləmə çox uzun çəkdi. Backend (node server.js) işləyir?';
      }
      if (err.response?.status === 404 && !d?.error) {
        msg = 'API tapılmadı. Backend-i yenidən başladın (node server.js).';
      }
      setError(msg);
    } finally {
      setLoadingUploadUrl(false);
    }
  };

  const handleUrlSubmit = () => {
    const raw = socialUrl.trim();
    if (!raw) return;
    if (isSocialMediaUrl(raw)) analyzeSocialUrl();
    else if (isHttpUrl(raw)) uploadImageFromUrl();
    else setError('Keçərli https:// URL daxil edin (birbaşa şəkil linki).');
  };

  const analyzeSocialUrl = async () => {
    const raw = socialUrl.trim();
    if (!raw) return;
    if (isImageUrl(raw)) {
      setError(null);
      await uploadImageFromUrl();
      return;
    }
    setLoadingSocial(true);
    setError(null);
    setSocialData(null);
    try {
      const res = await api.post(
        '/api/analyze-url',
        { url: raw },
        { timeout: 180000 }
      );
      if (res.data?.error) {
        setError(res.data.error);
        setSocialData(res.data);
      } else {
        setSocialData(res.data);
      }
    } catch (err) {
      const msg = err.response?.data?.error
        || err.response?.data?.details
        || (err.code === 'ECONNABORTED' ? 'Analiz çox uzun çəkdi (3 dəq limit).' : null)
        || 'URL analizi zamanı xəta baş verdi. Backend və yt-dlp işləyir?';
      setError(typeof msg === 'string' ? msg : 'URL analizi zamanı xəta baş verdi.');
    } finally {
      setLoadingSocial(false);
    }
  };

  const videoFrames = exifData?.video?.frames || locationData?.video?.frames || [];

  const resetUpload = () => {
    cleanupUploads();
    setUploadedFile(null);
    setExifData(null);
    setLocationData(null);
    setForensicsData(null);
    setOsintData(null);
    setFacePrivacyData(null);
    setObjectDetectionData(null);
    setVisionData(null);
    setRestoreData(null);
    setCompareData(null);
    setArchiveData(null);
    setSocialData(null);
    setVideoFrame(0);
    setUrlWarnings([]);
  };

  if (!authed) {
    return <AdminLogin onSuccess={() => setAuthed(true)} />;
  }

  return (
    <div style={styles.page} className={cyberMode ? 'cyber-theme' : ''}>
      <div style={styles.container}>
        
        {/* Header */}
        <div style={styles.header}>
          <button 
            onClick={() => setCyberMode(!cyberMode)}
            style={{position:'absolute', right:0, top:'32px', ...styles.iconBtn, color: cyberMode ? '#00ff41' : '#94a3b8'}}
          >
            <Terminal style={{width:'14px',height:'14px'}} /> {cyberMode ? 'NORMAL MOD' : 'CYBER MOD'}
          </button>
          <h1 style={styles.h1} className={cyberMode ? 'cyber-glitch' : ''}>Intelligent Metadata Extractor</h1>
          <p style={styles.subtitle}>Rəqəmsal Kriminalistika və OSINT Mərkəzi</p>
        </div>

        {error && (
          <div style={styles.errorBox}>
            <AlertCircle style={{width:'18px',height:'18px',flexShrink:0}} />
            <span style={{fontWeight:'500'}}>{error}</span>
          </div>
        )}

        {!uploadedFile && (
          <>
          <div style={{ marginBottom: 16, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              type="url"
              placeholder="Birbaşa şəkil URL (googleusercontent, .jpg, .png…)"
              value={socialUrl}
              onChange={(e) => setSocialUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleUrlSubmit()}
              title={socialUrl.length > 60 ? socialUrl : 'Copy image address — tam URL yapışdırın'}
              style={{
                flex: 1,
                minWidth: 200,
                width: '100%',
                padding: '8px 12px',
                borderRadius: 8,
                border: '1px solid #334155',
                background: '#0f172a',
                color: '#e2e8f0',
                fontSize: 12,
                fontFamily: 'monospace',
              }}
            />
            <button
              onClick={() => uploadImageFromUrl()}
              disabled={loadingUploadUrl || loadingSocial}
              style={styles.iconBtn}
              title="Birbaşa şəkil linki (googleusercontent, .jpg)"
            >
              {loadingUploadUrl ? <Loader2 style={{ width: 12, height: 12, animation: 'spin 1s linear infinite' }} /> : <Camera style={{ width: 12, height: 12 }} />}
              {loadingUploadUrl ? 'Yüklənir…' : 'Şəkil URL'}
            </button>
            <button
              onClick={analyzeSocialUrl}
              disabled={loadingSocial || loadingUploadUrl}
              style={styles.iconBtn}
              title="Yalnız Instagram, TikTok, X, Facebook, YouTube. Şəkil linki avtomatik «Şəkil URL» kimi yüklənir."
            >
              {loadingSocial ? <Loader2 style={{ width: 12, height: 12, animation: 'spin 1s linear infinite' }} /> : <Link2 style={{ width: 12, height: 12 }} />}
              Sosial link
            </button>
            <label style={{ ...styles.iconBtn, cursor: 'pointer' }}>
              {loadingArchive ? <Loader2 style={{ width: 12, height: 12, animation: 'spin 1s linear infinite' }} /> : <Archive style={{ width: 12, height: 12 }} />}
              ZIP arxiv
              <input type="file" accept=".zip" onChange={onArchiveDrop} style={{ display: 'none' }} />
            </label>
          </div>
          {socialData && <div style={{ marginBottom: 16 }}><SocialMetaPanel data={socialData} /></div>}
          {archiveData && <div style={{ marginBottom: 16 }}><ArchiveResultsPanel data={archiveData} /></div>}
          <p style={{ fontSize: 11, color: '#64748b', margin: '0 0 12px', lineHeight: 1.5 }}>
            <strong style={{ color: '#34d399' }}>Şəkil URL</strong> — birbaşa googleusercontent və ya .jpg linki; metadata avtomatik (TinEye yoxdursa Wayback tarixi).
            «Sosial link» — Instagram/TikTok/X.
          </p>
          <div {...getRootProps()} style={styles.dropzone(isDragActive, uploading)}>
            <input {...getInputProps()} />
            <UploadCloud style={{width:'64px',height:'64px',margin:'0 auto 16px',color: isDragActive ? '#818cf8' : '#475569',display:'block'}} />
            {uploading ? (
              <div>
                <Loader2 style={{width:'28px',height:'28px',color:'#818cf8',animation:'spin 1s linear infinite',margin:'0 auto 8px',display:'block'}} />
                <p style={{fontSize:'18px',fontWeight:'700',color:'#818cf8',margin:0}}>Serverə Yüklənir...</p>
              </div>
            ) : (
              <div>
                <p style={{fontSize:'20px',fontWeight:'600',color:'#e2e8f0',margin:'0 0 8px'}}>Faylı bura sürükləyin və ya seçin</p>
                <p style={{fontSize:'14px',color:'#64748b',margin:0}}>Şəkil, Video (mp4/avi), Audio (mp3/wav), PDF, ZIP</p>
              </div>
            )}
          </div>
          </>
        )}

        {uploadedFile && (
          <div id="osint-dashboard">
            {urlWarnings.length > 0 && (
              <div style={{
                background: 'rgba(251,191,36,0.12)',
                border: '1px solid rgba(251,191,36,0.35)',
                borderRadius: 10,
                padding: '10px 14px',
                marginBottom: 12,
                fontSize: 12,
                color: '#fcd34d',
                lineHeight: 1.5,
              }}>
                {urlWarnings.map((w, i) => <div key={i}>{w}</div>)}
                {uploadedFile.source_url && (
                  <div style={{ marginTop: 6, fontSize: 10, color: '#94a3b8', wordBreak: 'break-all' }}>
                    Mənbə: {uploadedFile.source_url}
                  </div>
                )}
              </div>
            )}
            {/* Toolbar */}
            <div style={styles.toolbar} className="cyber-panel">
              <div style={styles.thumbnail}>
                {uploadedFile.originalName.match(/\.(jpeg|jpg|png|webp|gif)$/i) ? (
                  <img src={uploadedFile.url} alt="Preview" style={styles.thumbImg} />
                ) : isVideoFile(uploadedFile.originalName) ? (
                  <Film style={{ color: '#c084fc', width: 28, height: 28 }} />
                ) : isAudioFile(uploadedFile.originalName) ? (
                  <Music style={{ color: '#c084fc', width: 28, height: 28 }} />
                ) : (
                  <FileText style={{color:'#64748b'}} />
                )}
              </div>

              <div style={styles.fileInfo}>
                <div style={styles.fileName}>{uploadedFile.originalName}</div>
                <div style={{fontSize:'11px', color:'#64748b', marginTop:'1px'}}>Analiz üçün hazırdır</div>
              </div>

              <div style={styles.btnGroup}>
                <button onClick={() => analyze('exif')} disabled={loadingExif || exifData} style={styles.actionBtn(exifData, '#60a5fa')} title={isMediaFile(uploadedFile.originalName) ? 'Audio/video: konteyner, tezlik, akustik iz' : 'Şəkil: EXIF və metadata'}>
                  {loadingExif ? <Loader2 style={{width:'13px',height:'13px',animation:'spin 1s linear infinite'}} /> : <Camera style={{width:'13px',height:'13px'}} />}
                  Metadata
                </button>
                <button onClick={() => analyze('location')} disabled={loadingLocation || locationData} style={styles.actionBtn(locationData, '#f87171')} title="GPS, Reverse Weather, Timeline Mapping və File Carving 4.0">
                  {loadingLocation ? <Loader2 style={{width:'13px',height:'13px',animation:'spin 1s linear infinite'}} /> : <MapPin style={{width:'13px',height:'13px'}} />}
                  Lokasiya · Marşrut
                </button>
                {uploadedFile.originalName.match(/\.(jpeg|jpg|png|webp|gif|mp4|mov|webm|mkv|avi|m4v)$/i) && (
                  <button
                    onClick={analyzeSocialFile}
                    disabled={loadingSocial || socialData}
                    style={styles.actionBtn(socialData, '#818cf8')}
                  >
                    {loadingSocial ? <Loader2 style={{width:'13px',height:'13px',animation:'spin 1s linear infinite'}} /> : <Link2 style={{width:'13px',height:'13px'}} />}
                    Sosial metadata
                  </button>
                )}
                
                {/* Yalnız şəkillər üçün xüsusi AI */}
                {uploadedFile.originalName.match(/\.(jpeg|jpg|png|webp|gif|mp4|mov|webm|mkv|avi|m4v)$/i) && (
                  <>
                    <button
                      onClick={runVisionML}
                      disabled={loadingVision || visionData}
                      style={styles.actionBtn(visionData, '#a78bfa')}
                      title="İnsan, emosiya, obyekt, OCR, brend, sənəd, məkan"
                    >
                      {loadingVision ? <Loader2 style={{width:'13px',height:'13px',animation:'spin 1s linear infinite'}} /> : <Brain style={{width:'13px',height:'13px'}} />}
                      AI Vision
                    </button>
                  </>
                )}
                {uploadedFile.originalName.match(/\.(jpeg|jpg|png|webp|gif)$/i) && (
                  <>
                    <button
                      onClick={runRestoreAnalyze}
                      disabled={loadingRestore || restoreData}
                      style={styles.actionBtn(restoreData, '#34d399')}
                      title="AI Super Resolution + deblur, üz/nömrə netləşdirmə, metadata və lokasiya"
                    >
                      {loadingRestore ? <Loader2 style={{width:'13px',height:'13px',animation:'spin 1s linear infinite'}} /> : <Sparkles style={{width:'13px',height:'13px'}} />}
                      Bərpa + Analiz
                    </button>
                    <button onClick={() => analyze('forensics')} disabled={loadingForensics || forensicsData} style={styles.actionBtn(forensicsData, '#eab308')}>
                      {loadingForensics ? <Loader2 style={{width:'13px',height:'13px',animation:'spin 1s linear infinite'}} /> : <ShieldAlert style={{width:'13px',height:'13px'}} />}
                      Kriminalistika
                    </button>
                    <button onClick={() => analyze('osint')} disabled={loadingOsint || osintData} style={styles.actionBtn(osintData, '#10b981')} title="OSINT, tərs şəkil axtarışı, hava, steganografiya">
                      {loadingOsint ? <Loader2 style={{width:'13px',height:'13px',animation:'spin 1s linear infinite'}} /> : <Globe style={{width:'13px',height:'13px'}} />}
                      OSINT
                    </button>
                    <button
                      onClick={() => runFacePrivacy(false)}
                      disabled={loadingFacePrivacy || facePrivacyData}
                      style={styles.actionBtn(facePrivacyData, '#22d3ee')}
                    >
                      {loadingFacePrivacy ? <Loader2 style={{width:'13px',height:'13px',animation:'spin 1s linear infinite'}} /> : <ScanFace style={{width:'13px',height:'13px'}} />}
                      Üz məxfiliyi
                    </button>
                    <button
                      onClick={runObjectDetection}
                      disabled={loadingObjects || objectDetectionData}
                      style={styles.actionBtn(objectDetectionData, '#60a5fa')}
                    >
                      {loadingObjects ? <Loader2 style={{width:'13px',height:'13px',animation:'spin 1s linear infinite'}} /> : <Box style={{width:'13px',height:'13px'}} />}
                      Obyektlər
                    </button>
                  </>
                )}
                {uploadedFile.originalName.match(/\.(mp4|mov|webm|mkv|avi|m4v)$/i) && (
                  <>
                    <button
                      onClick={() => runFacePrivacy(false)}
                      disabled={loadingFacePrivacy || loadingFaceAnonymize || facePrivacyData}
                      style={styles.actionBtn(facePrivacyData, '#22d3ee')}
                      title="Video üz re-id və MOT"
                    >
                      {(loadingFacePrivacy || loadingFaceAnonymize) ? <Loader2 style={{width:'13px',height:'13px',animation:'spin 1s linear infinite'}} /> : <ScanFace style={{width:'13px',height:'13px'}} />}
                      Üz məxfiliyi
                    </button>
                    <button
                      onClick={runObjectDetection}
                      disabled={loadingObjects || objectDetectionData}
                      style={styles.actionBtn(objectDetectionData, '#60a5fa')}
                      title="Video ByteTrack/BoT-SORT izləmə"
                    >
                      {loadingObjects ? <Loader2 style={{width:'13px',height:'13px',animation:'spin 1s linear infinite'}} /> : <Box style={{width:'13px',height:'13px'}} />}
                      Obyektlər
                    </button>
                  </>
                )}
              </div>

              <div style={{display:'flex', gap:'6px'}}>
                <button onClick={() => exportToPDF('osint-dashboard', uploadedFile.originalName)} style={styles.iconBtn}>
                  <Download style={{width:'12px',height:'12px'}} /> PDF Export
                </button>
                <label style={{ ...styles.iconBtn, cursor: 'pointer' }}>
                  {loadingCompare ? <Loader2 style={{ width: 12, height: 12, animation: 'spin 1s linear infinite' }} /> : <GitCompare style={{ width: 12, height: 12 }} />}
                  Müqayisə
                  <input
                    type="file"
                    accept="image/*"
                    style={{ display: 'none' }}
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) runCompareSecondFile(f); e.target.value = ''; }}
                  />
                </label>
                <button onClick={resetUpload} style={styles.iconBtn}>
                  <ArrowLeft style={{width:'12px',height:'12px'}} /> Yeni
                </button>
              </div>
            </div>

            {videoFrames.length > 0 && (
              <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#94a3b8' }}>
                Video frame:
                <select
                  value={videoFrame}
                  onChange={(e) => setVideoFrame(Number(e.target.value))}
                  style={{ background: '#0f172a', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 6, padding: '4px 8px' }}
                >
                  {videoFrames.map((fr) => (
                    <option key={fr.index} value={fr.index}>
                      Frame {fr.index} ({fr.timestamp_sec}s)
                    </option>
                  ))}
                </select>
                <button onClick={() => analyze('exif', videoFrame)} style={styles.iconBtn}>Frame metadata</button>
              </div>
            )}

            {/* NƏTİCƏLƏR */}
            <div className="space-y-5">
              
              {!exifData && !locationData && !forensicsData && !osintData && !facePrivacyData && !objectDetectionData && !visionData && !restoreData && !socialData && (
                <div style={styles.emptyState} className="cyber-panel">
                  <ShieldAlert style={{width:'40px',height:'40px',color:'#475569',margin:'0 auto 12px',display:'block'}} />
                  <p style={{fontSize:'14px', color:'#64748b', margin:'0 0 4px'}}>Yuxarıdakı OSINT düymələrindən birini seçin</p>
                </div>
              )}

              {/* Panellər */}
              {compareData && <ComparePanel data={compareData} />}
              {socialData && <SocialMetaPanel data={socialData} />}
              {forensicsData && (
                <ForensicsPanel
                  data={forensicsData.forensics || forensicsData}
                  originalUrl={uploadedFile.url}
                />
              )}
              {uploadedFile?.originalName?.match(/\.(jpeg|jpg|png|webp|gif|bmp)$/i) && !osintData && (
                <div style={styles.card('rgba(16,185,129,0.25)')} className="cyber-panel">
                  <ReverseImageSearchPanel
                    filename={uploadedFile.filename}
                    imageUrl={uploadedFile.url}
                    uploadMeta={uploadedFile}
                  />
                </div>
              )}
              {osintData && (
                <OsintPanel
                  data={osintData.osint || osintData}
                  imageUrl={uploadedFile.url}
                  uploadMeta={uploadedFile}
                  filename={uploadedFile.filename}
                />
              )}

              {restoreData && (
                <RestoreAnalyzePanel data={restoreData} originalUrl={uploadedFile.url} />
              )}

              {visionData && (
                <VisionMLPanel data={visionData} originalUrl={uploadedFile.url} />
              )}

              {facePrivacyData && (
                <FacePrivacyPanel
                  data={facePrivacyData}
                  originalUrl={uploadedFile.url}
                  onAnonymize={(opts) => runFacePrivacy(true, opts)}
                  loadingAnonymize={loadingFaceAnonymize}
                  anonymizeOptions={faceAnonymizeOptions}
                  onAnonymizeOptionsChange={setFaceAnonymizeOptions}
                />
              )}

              {objectDetectionData && (
                <ObjectDetectionPanel
                  data={objectDetectionData}
                  originalUrl={uploadedFile.url}
                />
              )}

              {exifData?.module === 'media_metadata' && (
                <MediaMetadataPanel data={exifData} />
              )}

              {exifData && exifData.module !== 'media_metadata' && (() => {
                const metaEntries = buildMetadataEntries(exifData);
                return (
                <div style={styles.card('rgba(59,130,246,0.3)')} className="cyber-panel">
                  <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'14px',paddingBottom:'10px',borderBottom:'1px solid #334155'}}>
                    <div style={{background:'rgba(59,130,246,0.2)',padding:'6px',borderRadius:'8px'}}>
                      <FileText style={{width:'15px',height:'15px',color:'#60a5fa'}} />
                    </div>
                    <h2 style={{fontSize:'15px',fontWeight:'700',color:'#f1f5f9',margin:0}}>Rəqəmsal İz (Metadata)</h2>
                  </div>
                  {exifData.warnings?.map((msg, i) => (
                    <p key={i} style={{color:'#fbbf24',fontSize:'12px',margin:'0 0 10px',lineHeight:1.5}}>{msg}</p>
                  ))}
                  {exifData.residual_recovery?.summary_az && (
                    <div style={{
                      background: 'rgba(16,185,129,0.12)',
                      border: '1px solid rgba(52,211,153,0.35)',
                      borderRadius: 10,
                      padding: '10px 12px',
                      marginBottom: 12,
                      fontSize: 12,
                      color: '#a7f3d0',
                      lineHeight: 1.5,
                    }}>
                      <strong style={{ color: '#34d399' }}>Qalıq metadata bərpası</strong>
                      {' — '}{exifData.residual_recovery.summary_az}
                      {exifData.residual_recovery.recovery_score != null && (
                        <span style={{ color: '#94a3b8' }}> (skor: {exifData.residual_recovery.recovery_score}/100)</span>
                      )}
                    </div>
                  )}
                  <CaptureDatePanel captureDate={exifData.capture_date} />
                  {uploadedFile?.originalName?.match(/\.(jpeg|jpg|png|webp|gif|bmp)$/i) && (
                    <PropagationAnalysisPanel
                      propagation={exifData.image_propagation}
                      filename={uploadedFile.filename}
                      imageUrl={uploadedFile.url}
                      uploadMeta={uploadedFile}
                      onUpdate={(prop) => setExifData((prev) => (prev ? { ...prev, image_propagation: prop } : prev))}
                    />
                  )}
                  {metaEntries.length > 0 ? (
                    <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill, minmax(200px, 1fr))',gap:'8px',maxHeight:'300px',overflowY:'auto'}}>
                      {metaEntries.map(({ key, value }) => (
                          <div key={`${key}-${value}`} style={metaTagStyle}>
                            <div style={{fontSize:'10px',color:'#64748b',marginBottom:'2px',wordBreak:'break-word'}}>{key}</div>
                            <div style={{fontSize:'12px',fontWeight:'600',color:'#e2e8f0',wordBreak:'break-word'}}>{value}</div>
                          </div>
                      ))}
                    </div>
                  ) : (
                    <p style={{color:'#64748b',fontStyle:'italic',textAlign:'center',padding:'20px 0',fontSize:'13px'}}>
                      {exifData.web_metadata?.summary_az
                        || 'Əlavə metadata tapılmadı. Başqa format və ya orijinal fayl sınayın.'}
                    </p>
                  )}
                  {exifData.web_metadata?.summary_az && metaEntries.length > 0 && (
                    <p style={{ color: '#94a3b8', fontSize: 11, margin: '10px 0 0', lineHeight: 1.5 }}>
                      {exifData.web_metadata.summary_az}
                    </p>
                  )}
                  <ProgramTracesPanel data={exifData} />
                  <InternalStructurePanel data={exifData.internal_structure} />
                </div>
                );
              })()}

              {locationData && (
                <div style={styles.card('rgba(239,68,68,0.3)')} className="cyber-panel">
                  <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'14px',flexWrap:'wrap'}}>
                    <div style={{display:'flex',alignItems:'center',gap:'8px'}}>
                      <div style={{background:'rgba(239,68,68,0.2)',padding:'6px',borderRadius:'8px'}}>
                        <MapPin style={{width:'15px',height:'15px',color:'#f87171'}} />
                      </div>
                      <h2 style={{fontSize:'15px',fontWeight:'700',color:'#f1f5f9',margin:0}}>Geoparsing, Xəritə & Timeline Mapping</h2>
                    </div>
                    {locationData.location?.address ? (
                      <div style={{marginLeft:'auto',display:'flex',alignItems:'center',gap:'6px',background:'#0f172a',padding:'6px 14px',borderRadius:'10px',border:'1px solid #334155',fontSize:'13px'}}>
                        {locationData.location.inferred && (
                          <span style={{fontSize:'10px',color:'#fbbf24',fontWeight:700}}>TƏXMİNİ</span>
                        )}
                        <span style={{fontWeight:'600',color:'#e2e8f0'}}>{locationData.location.address.city}</span>
                        <span style={{color:'#475569'}}>•</span>
                        <span style={{color:'#94a3b8'}}>{locationData.location.address.country_code}</span>
                      </div>
                    ) : locationData.location?.inferred ? (
                      <span style={{marginLeft:'auto',color:'#fbbf24',fontSize:'12px',fontWeight:600}}>
                        OSINT təxmini ({Math.round((locationData.location.confidence || 0) * 100)}% etibar)
                      </span>
                    ) : (
                      <span style={{marginLeft:'auto',color:'#64748b',fontStyle:'italic',fontSize:'13px'}}>GPS koordinatları tapılmadı</span>
                    )}
                  </div>
                  <LocationPanel
                    data={locationData}
                    currentFilename={uploadedFile?.filename}
                    currentOriginalName={uploadedFile?.originalName}
                  />
                </div>
              )}

            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
