import React, { useState } from 'react';
import { Film, MapPin, Users, AlertTriangle, Clock, ScanFace } from 'lucide-react';

import { UPLOADS_BASE } from '../apiClient';

const CATEGORY_COLORS = {
  İnsan: '#ec4899',
  Nəqliyyat: '#3b82f6',
  Heyvan: '#22c55e',
  Mebel: '#a855f7',
  Elektronika: '#22d3ee',
  'Məişət texnikası': '#fbbf24',
  'Kəskin əşya': '#ef4444',
  Bitki: '#4ade80',
  İnfrastruktur: '#94a3b8',
  Əşya: '#cbd5e1',
  Digər: '#9ca3af',
};

function uploadsUrl(filename) {
  if (!filename) return null;
  const base = String(filename).replace(/\\/g, '/').split('/').pop();
  return `${UPLOADS_BASE}/${base}`;
}

function fmtCoord(v) {
  if (v == null || Number.isNaN(Number(v))) return '—';
  return Number(v).toFixed(5);
}

export default function VideoTrackingPanel({ tracking, originalUrl, mode = 'objects' }) {
  const [lightbox, setLightbox] = useState(null);
  if (!tracking) return null;

  if (tracking.status === 'error') {
    return (
      <div style={{ background: '#1e293b', borderRadius: 16, padding: 20, border: '1px solid rgba(239,68,68,0.3)' }}>
        <p style={{ color: '#f87171', margin: 0, fontSize: 13 }}>{tracking.error}</p>
      </div>
    );
  }

  const tracks = tracking.tracks || [];
  const faceClusters = tracking.face_clusters || [];
  const video = tracking.video || {};
  const loc = tracking.location || {};
  const previewSrc = uploadsUrl(tracking.artifacts?.preview_image);
  const title = mode === 'faces' ? 'Video üz izləmə və re-id' : 'Video obyekt izləmə (MOT)';
  const accent = mode === 'faces' ? '#22d3ee' : '#60a5fa';

  return (
    <div
      style={{
        background: '#1e293b',
        borderRadius: 16,
        padding: 20,
        border: `1px solid ${accent}55`,
        boxShadow: `0 0 15px ${accent}14`,
      }}
      className="cyber-panel"
    >
      {lightbox && (
        <div
          onClick={() => setLightbox(null)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.85)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 24,
          }}
        >
          <img src={lightbox} alt="Önizləmə" style={{ maxWidth: '95%', maxHeight: '90%', objectFit: 'contain' }} />
        </div>
      )}

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginBottom: 16,
          paddingBottom: 12,
          borderBottom: '1px solid #334155',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ background: `${accent}33`, padding: 6, borderRadius: 8 }}>
          <Film style={{ width: 16, height: 16, color: accent }} />
        </div>
        <h2 style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>{title}</h2>
        <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 700, color: accent }}>
          {tracking.unique_tracks ?? tracks.length} track · {tracking.tracker?.toUpperCase() || 'MOT'}
        </span>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 14, fontSize: 11, color: '#94a3b8' }}>
        <span>Müddət: {video.duration_sec ?? '—'}s</span>
        <span>FPS: {video.fps ?? '—'}</span>
        <span>Nümunə: {video.sample_fps ?? 2} FPS</span>
        <span>İşlənmiş kadr: {video.frames_processed ?? 0}</span>
        {tracking.anonymized && (
          <span style={{ color: '#fbbf24' }}>Anonim rejim (blur sonrası izləmə)</span>
        )}
        {tracking.face_reid_enabled && (
          <span style={{ color: '#22d3ee' }}>SFace re-id aktiv</span>
        )}
      </div>

      {tracking.note && (
        <p style={{ fontSize: 11, color: '#64748b', margin: '0 0 14px', lineHeight: 1.5 }}>{tracking.note}</p>
      )}

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 18 }}>
        {previewSrc && (
          <div style={{ flex: 1, minWidth: 260 }}>
            <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6, textAlign: 'center' }}>
              Annotasiyalı son kadr
            </div>
            <div
              style={{
                background: '#0f172a',
                padding: 8,
                borderRadius: 10,
                border: '1px solid #334155',
                cursor: 'pointer',
              }}
              onClick={() => setLightbox(previewSrc)}
            >
              <img
                src={previewSrc}
                alt="Track önizləmə"
                style={{ width: '100%', height: 260, objectFit: 'contain', borderRadius: 4 }}
              />
            </div>
          </div>
        )}
        {originalUrl && !previewSrc && (
          <div style={{ flex: 1, minWidth: 200 }}>
            <video
              src={originalUrl}
              controls
              style={{ width: '100%', maxHeight: 260, borderRadius: 8, background: '#0f172a' }}
            />
          </div>
        )}
      </div>

      {(loc.latitude != null || loc.longitude != null) && (
        <div
          style={{
            background: '#0f172a',
            padding: 12,
            borderRadius: 10,
            border: '1px solid #334155',
            marginBottom: 16,
          }}
        >
          <h3 style={{ fontSize: 13, color: '#94a3b8', margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
            <MapPin style={{ width: 14, height: 14 }} /> Video lokasiyası (ffprobe)
          </h3>
          <p style={{ margin: 0, fontSize: 12, color: '#cbd5e1' }}>
            {fmtCoord(loc.latitude)}, {fmtCoord(loc.longitude)}
            {loc.creation_time ? ` · ${loc.creation_time}` : ''}
          </p>
          <p style={{ margin: '6px 0 0', fontSize: 11, color: '#64748b' }}>
            Statik video GPS — bütün tracklər eyni koordinat kontekstində.
          </p>
        </div>
      )}

      <div style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 13, color: '#94a3b8', margin: '0 0 10px', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Clock style={{ width: 14, height: 14 }} /> Obyekt track cədvəli
        </h3>
        {tracks.length === 0 ? (
          <p style={{ fontSize: 12, color: '#64748b', margin: 0 }}>Track tapılmadı (COCO sinifləri və ya etibar həddi).</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ color: '#64748b', textAlign: 'left' }}>
                  <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>ID</th>
                  <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>Sinif</th>
                  <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>Vaxt aralığı</th>
                  <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>Kadr</th>
                  <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>Xülasə</th>
                </tr>
              </thead>
              <tbody>
                {tracks.map((t) => {
                  const color = CATEGORY_COLORS[t.category] || CATEGORY_COLORS.Digər;
                  return (
                    <tr key={t.track_id} style={{ borderBottom: '1px solid #1e293b' }}>
                      <td style={{ padding: '8px', color: '#e2e8f0', fontWeight: 700 }}>#{t.track_id}</td>
                      <td style={{ padding: '8px', color }}>{t.class_name_az}</td>
                      <td style={{ padding: '8px', color: '#cbd5e1' }}>
                        {t.first_seen_fmt} – {t.last_seen_fmt}
                      </td>
                      <td style={{ padding: '8px', color: '#94a3b8' }}>{t.frame_count}</td>
                      <td style={{ padding: '8px', color: '#94a3b8', fontSize: 11 }}>{t.summary_az}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {mode === 'faces' && (
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: 13, color: '#94a3b8', margin: '0 0 10px', display: 'flex', alignItems: 'center', gap: 6 }}>
            <ScanFace style={{ width: 14, height: 14 }} /> Üz klasterləri (re-id)
          </h3>
          {faceClusters.length === 0 ? (
            <p style={{ fontSize: 12, color: '#64748b', margin: 0 }}>
              {tracking.anonymized
                ? 'Anonim rejimdə üz re-id söndürülüb — yalnız insan obyekti track.'
                : 'Üz klasteri tapılmadı və ya kifayət qədər nümunə yoxdur.'}
            </p>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10 }}>
              {faceClusters.map((cl) => (
                <div
                  key={cl.cluster_id}
                  style={{
                    background: '#0f172a',
                    padding: 12,
                    borderRadius: 10,
                    border: '1px solid #334155',
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#22d3ee', marginBottom: 6 }}>
                    Klaster #{cl.cluster_id}
                  </div>
                  <p style={{ margin: '0 0 6px', fontSize: 12, color: '#cbd5e1' }}>{cl.summary_az}</p>
                  <p style={{ margin: 0, fontSize: 11, color: '#64748b' }}>
                    {cl.face_count} nümunə · track ID: {(cl.linked_track_ids || []).join(', ') || '—'}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {(tracking.warnings || []).length > 0 && (
        <div
          style={{
            marginTop: 12,
            padding: 12,
            borderRadius: 10,
            background: 'rgba(251,191,36,0.08)',
            border: '1px solid rgba(251,191,36,0.25)',
          }}
        >
          {(tracking.warnings || []).map((w, i) => (
            <p key={i} style={{ margin: i ? '6px 0 0' : 0, fontSize: 11, color: '#fbbf24', display: 'flex', gap: 6 }}>
              <AlertTriangle style={{ width: 12, height: 12, flexShrink: 0, marginTop: 2 }} />
              {w}
            </p>
          ))}
        </div>
      )}

      <footer style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid #334155', fontSize: 10, color: '#64748b' }}>
        <Users style={{ width: 11, height: 11, display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
        Yalnız icazəli şəxslər və rəsmi araşdırma məqsədilə istifadə edin.
      </footer>
    </div>
  );
}
