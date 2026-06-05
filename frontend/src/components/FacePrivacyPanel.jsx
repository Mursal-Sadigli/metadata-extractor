import React, { useState } from 'react';
import { ScanFace, Shield, Image as ImageIcon, Loader2, User, Film } from 'lucide-react';
import VideoTrackingPanel from './VideoTrackingPanel';

import { UPLOADS_BASE } from '../apiClient';

const CIRCLE_COLORS = ['#22d3ee', '#a78bfa', '#34d399', '#fbbf24', '#f472b6'];

function uploadsUrl(filename) {
  if (!filename) return null;
  const base = String(filename).replace(/\\/g, '/').split('/').pop();
  return `${UPLOADS_BASE}/${base}`;
}

function bboxToCircle(b) {
  if (!b) return null;
  const cx = b.x + b.w / 2;
  const cy = b.y + b.h / 2;
  const radius = (Math.max(b.w, b.h) / 2) * 1.08;
  return { cx, cy, radius };
}

function FaceOverlay({ src, faces, onZoom }) {
  const [dims, setDims] = useState({ w: 0, h: 0 });
  if (!src) return null;

  const strokeW = dims.w > 0 ? Math.max(2, dims.w / 350) : 2;

  return (
    <div style={{ position: 'relative', flex: 1, minWidth: 240 }}>
      <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6, textAlign: 'center' }}>
        Üz dairələri (canlı overlay)
      </div>
      <div
        style={{
          background: '#0f172a',
          padding: 8,
          borderRadius: 10,
          border: '1px solid #334155',
          cursor: 'pointer',
          position: 'relative',
        }}
        onClick={() => onZoom?.(src, 'Üz skanı')}
      >
        <img
          src={src}
          alt="Üz skanı"
          style={{ width: '100%', height: 260, objectFit: 'contain', borderRadius: 4, display: 'block' }}
          onLoad={(e) => setDims({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
        />
        {dims.w > 0 && faces?.length > 0 && (
          <svg
            style={{
              position: 'absolute',
              left: 8,
              top: 8,
              width: 'calc(100% - 16px)',
              height: 260,
              pointerEvents: 'none',
            }}
            viewBox={`0 0 ${dims.w} ${dims.h}`}
            preserveAspectRatio="xMidYMid meet"
          >
            {faces.map((f, idx) => {
              const c = f.circle || bboxToCircle(f.bbox);
              if (!c) return null;
              const color = CIRCLE_COLORS[idx % CIRCLE_COLORS.length];
              const labelY = Math.max(c.radius + 14, c.cy - c.radius - 8);
              return (
                <g key={f.id}>
                  <circle
                    cx={c.cx}
                    cy={c.cy}
                    r={c.radius}
                    fill="none"
                    stroke={color}
                    strokeWidth={strokeW}
                    strokeDasharray={f.info?.multi_detector ? '0' : '6 4'}
                  />
                  <circle cx={c.cx} cy={c.cy} r={4} fill={color} />
                  <text
                    x={c.cx}
                    y={labelY}
                    textAnchor="middle"
                    fill={color}
                    fontSize={Math.max(12, dims.w / 55)}
                    fontWeight="700"
                  >
                    Üz #{f.id}
                  </text>
                </g>
              );
            })}
          </svg>
        )}
      </div>
    </div>
  );
}

function FaceInfoCard({ face, color }) {
  const info = face.info || {};
  const conf = info.confidence_percent ?? Math.round((face.confidence || 0) * 100);

  return (
    <div
      style={{
        background: '#0f172a',
        borderRadius: 10,
        border: `1px solid ${color}44`,
        padding: '12px 14px',
        borderLeft: `3px solid ${color}`,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: '50%',
            border: `2px solid ${color}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 13,
            fontWeight: 800,
            color,
          }}
        >
          {face.id}
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9' }}>Üz #{face.id}</div>
          <div style={{ fontSize: 11, color: color }}>Etibar: {info.reliability || '—'} ({conf}%)</div>
        </div>
      </div>
      <dl style={{ margin: 0, fontSize: 12, color: '#cbd5e1', display: 'grid', gap: 6 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <dt style={{ color: '#64748b', margin: 0 }}>Baxış bucağı</dt>
          <dd style={{ margin: 0, textAlign: 'right' }}>{info.orientation || '—'}</dd>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <dt style={{ color: '#64748b', margin: 0 }}>Şəkildə yeri</dt>
          <dd style={{ margin: 0, textAlign: 'right', maxWidth: '55%' }}>{info.position || '—'}</dd>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <dt style={{ color: '#64748b', margin: 0 }}>Ölçü</dt>
          <dd style={{ margin: 0 }}>{info.size_pixels || `${face.bbox?.w}×${face.bbox?.h} px`}</dd>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <dt style={{ color: '#64748b', margin: 0 }}>Sahə</dt>
          <dd style={{ margin: 0 }}>{info.area_percent ?? face.area_percent}% şəkil</dd>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <dt style={{ color: '#64748b', margin: 0 }}>Mərkəz</dt>
          <dd style={{ margin: 0, fontFamily: 'monospace' }}>
            ({face.center?.x ?? '—'}, {face.center?.y ?? '—'})
          </dd>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <dt style={{ color: '#64748b', margin: 0 }}>Dairə radiusu</dt>
          <dd style={{ margin: 0 }}>{face.circle?.radius ?? '—'} px</dd>
        </div>
        <div>
          <dt style={{ color: '#64748b', margin: '0 0 4px' }}>Detektorlar</dt>
          <dd style={{ margin: 0, lineHeight: 1.4 }}>{info.detectors_label || face.detectors}</dd>
        </div>
        {face.info?.multi_detector && (
          <p style={{ margin: 0, fontSize: 11, color: '#34d399' }}>✓ Bir neçə detektor təsdiqləyib</p>
        )}
      </dl>
    </div>
  );
}

export default function FacePrivacyPanel({
  data,
  originalUrl,
  onAnonymize,
  loadingAnonymize,
  anonymizeOptions,
  onAnonymizeOptionsChange,
}) {
  const [lightbox, setLightbox] = useState(null);

  if (!data) return null;

  if (data.video_tracking) {
    return (
      <>
        <VideoTrackingPanel tracking={data.video_tracking} originalUrl={originalUrl} mode="faces" />
        {onAnonymize && (
          <div
            style={{
              background: '#0f172a',
              padding: 14,
              borderRadius: 10,
              border: '1px solid #334155',
              marginTop: 12,
            }}
          >
            <h3 style={{ fontSize: 13, color: '#94a3b8', margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Film style={{ width: 14, height: 14 }} /> Video anonim rejim
            </h3>
            <p style={{ fontSize: 11, color: '#64748b', margin: '0 0 10px', lineHeight: 1.5 }}>
              Aktiv olanda üz re-id söndürülür; izləmə blur edilmiş kadrlarda aparılır (yalnız insan obyekti track).
            </p>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#e2e8f0', marginBottom: 10 }}>
              <input
                type="checkbox"
                checked={anonymizeOptions?.enabled ?? false}
                onChange={(e) => onAnonymizeOptionsChange?.({ ...anonymizeOptions, enabled: e.target.checked })}
              />
              Anonim rejim (blur sonrası izləmə)
            </label>
            {anonymizeOptions?.enabled && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', marginBottom: 12 }}>
                <select
                  value={anonymizeOptions.method || 'blur'}
                  onChange={(e) => onAnonymizeOptionsChange?.({ ...anonymizeOptions, method: e.target.value })}
                  style={{
                    background: '#1e293b',
                    color: '#e2e8f0',
                    border: '1px solid #334155',
                    borderRadius: 6,
                    padding: '6px 10px',
                    fontSize: 12,
                  }}
                >
                  <option value="blur">Blur (Gaussian)</option>
                  <option value="pixelate">Pixelate</option>
                </select>
                <label style={{ fontSize: 12, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 8 }}>
                  Güc: {anonymizeOptions.strength ?? 3}
                  <input
                    type="range"
                    min={1}
                    max={5}
                    value={anonymizeOptions.strength ?? 3}
                    onChange={(e) =>
                      onAnonymizeOptionsChange?.({ ...anonymizeOptions, strength: Number(e.target.value) })
                    }
                  />
                </label>
              </div>
            )}
            <button
              type="button"
              onClick={() => onAnonymize(anonymizeOptions)}
              disabled={loadingAnonymize || !anonymizeOptions?.enabled}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 14px',
                borderRadius: 8,
                border: '1px solid rgba(34,211,238,0.4)',
                background: 'rgba(34,211,238,0.15)',
                color: '#22d3ee',
                fontSize: 12,
                fontWeight: 600,
                cursor: loadingAnonymize || !anonymizeOptions?.enabled ? 'not-allowed' : 'pointer',
                opacity: loadingAnonymize || !anonymizeOptions?.enabled ? 0.5 : 1,
              }}
            >
              {loadingAnonymize ? (
                <Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} />
              ) : (
                <ScanFace style={{ width: 14, height: 14 }} />
              )}
              Anonim video izləməni yenidən işə sal
            </button>
          </div>
        )}
      </>
    );
  }

  const fp = data.face_privacy || data;
  const faces = fp.faces || [];
  const anon = data.anonymization;
  const originalSrc = originalUrl || uploadsUrl(data.original_filename);
  const previewSrc = uploadsUrl(fp.preview_filename) || uploadsUrl(data.artifacts?.find((a) => String(a).startsWith('faces_')));
  const anonSrc = uploadsUrl(anon?.anonymized_filename);

  if (fp.error && fp.status === 'error') {
    return (
      <div
        style={{
          background: '#1e293b',
          borderRadius: '16px',
          padding: '20px',
          border: '1px solid rgba(239,68,68,0.3)',
        }}
        className="cyber-panel"
      >
        <p style={{ color: '#f87171', margin: 0, fontSize: 13 }}>{fp.error}</p>
      </div>
    );
  }

  return (
    <div
      style={{
        background: '#1e293b',
        borderRadius: '16px',
        padding: '20px',
        border: '1px solid rgba(34,211,238,0.3)',
        boxShadow: '0 0 15px rgba(34,211,238,0.08)',
      }}
      className="cyber-panel"
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          marginBottom: '16px',
          paddingBottom: '12px',
          borderBottom: '1px solid #334155',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ background: 'rgba(34,211,238,0.2)', padding: '6px', borderRadius: '8px' }}>
          <ScanFace style={{ width: '16px', height: '16px', color: '#22d3ee' }} />
        </div>
        <h2 style={{ fontSize: '15px', fontWeight: '700', color: '#f1f5f9', margin: 0 }}>
          Üz tanıma və anonimləşdirmə
        </h2>
        <span
          style={{
            marginLeft: 'auto',
            fontSize: 11,
            fontWeight: 700,
            color: faces.length ? '#22d3ee' : '#64748b',
          }}
        >
          {faces.length} üz tapıldı
        </span>
      </div>

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
          <img src={lightbox.src} alt={lightbox.label} style={{ maxWidth: '95%', maxHeight: '90%', objectFit: 'contain' }} />
        </div>
      )}

      {fp.note && !faces.length && (
        <p style={{ fontSize: 12, color: '#94a3b8', margin: '0 0 14px', lineHeight: 1.5, fontStyle: 'italic' }}>
          {fp.note}
        </p>
      )}

      {fp.strict_mode && (
        <p style={{ fontSize: 11, color: '#64748b', margin: '0 0 14px' }}>
          <Shield style={{ width: 12, height: 12, display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
          YuNet + MediaPipe + Haar — üzlər dairə ilə işarələnir.
        </p>
      )}

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 20 }}>
        {previewSrc && faces.length > 0 ? (
          <div style={{ flex: 1, minWidth: 240 }}>
            <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6, textAlign: 'center' }}>
              İşarələnmiş önizləmə (server)
            </div>
            <div
              style={{
                background: '#0f172a',
                padding: 8,
                borderRadius: 10,
                border: '1px solid #334155',
                cursor: 'pointer',
              }}
              onClick={() => setLightbox({ src: previewSrc, label: 'Üz dairələri' })}
            >
              <img
                src={previewSrc}
                alt="Üz dairələri"
                style={{ width: '100%', height: 260, objectFit: 'contain', borderRadius: 4 }}
              />
            </div>
          </div>
        ) : null}
        {originalSrc && faces.length > 0 && (
          <FaceOverlay src={originalSrc} faces={faces} onZoom={(src, label) => setLightbox({ src, label })} />
        )}
        {originalSrc && !faces.length && (
          <div style={{ flex: 1, minWidth: 200 }}>
            <img src={originalSrc} alt="" style={{ width: '100%', maxHeight: 260, objectFit: 'contain', borderRadius: 8 }} />
          </div>
        )}
        {anonSrc && (
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6, textAlign: 'center' }}>Anonimləşdirilmiş</div>
            <div
              style={{
                background: '#0f172a',
                padding: 8,
                borderRadius: 10,
                border: '1px solid #334155',
                cursor: 'pointer',
              }}
              onClick={() => setLightbox({ src: anonSrc, label: 'Anonim' })}
            >
              <img
                src={anonSrc}
                alt="Anonim"
                style={{ width: '100%', height: 260, objectFit: 'contain', borderRadius: 4 }}
              />
            </div>
          </div>
        )}
      </div>

      {faces.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <h3
            style={{
              fontSize: 13,
              color: '#94a3b8',
              marginBottom: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <User style={{ width: 14, height: 14 }} /> Tapılan üzlər haqqında
          </h3>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
              gap: 12,
            }}
          >
            {faces.map((f, idx) => (
              <FaceInfoCard key={f.id} face={f} color={CIRCLE_COLORS[idx % CIRCLE_COLORS.length]} />
            ))}
          </div>
        </div>
      )}

      {fp.file_metadata_hints?.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: 13, color: '#94a3b8', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
            <ImageIcon style={{ width: 14, height: 14 }} /> Fayl metadata ipucları
          </h3>
          {fp.file_metadata_hints
            .filter((h) => h.field !== '_error')
            .map((h, i) => (
              <div
                key={i}
                style={{
                  background: '#0f172a',
                  padding: '8px 10px',
                  borderRadius: 8,
                  border: '1px solid #334155',
                  fontSize: 12,
                  marginBottom: 6,
                  color: '#cbd5e1',
                }}
              >
                <strong style={{ color: '#94a3b8' }}>{h.field}:</strong> {h.value}
              </div>
            ))}
        </div>
      )}

      {onAnonymize && faces.length > 0 && !anonSrc && (
        <div
          style={{
            background: '#0f172a',
            padding: 14,
            borderRadius: 10,
            border: '1px solid #334155',
          }}
        >
          <h3 style={{ fontSize: 13, color: '#94a3b8', margin: '0 0 10px' }}>Anonimləşdirmə</h3>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#e2e8f0', marginBottom: 10 }}>
            <input
              type="checkbox"
              checked={anonymizeOptions?.enabled ?? false}
              onChange={(e) => onAnonymizeOptionsChange?.({ ...anonymizeOptions, enabled: e.target.checked })}
            />
            Blur / pixelate tətbiq et (dairə ətrafı daxil)
          </label>
          {anonymizeOptions?.enabled && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', marginBottom: 12 }}>
              <select
                value={anonymizeOptions.method || 'blur'}
                onChange={(e) => onAnonymizeOptionsChange?.({ ...anonymizeOptions, method: e.target.value })}
                style={{
                  background: '#1e293b',
                  color: '#e2e8f0',
                  border: '1px solid #334155',
                  borderRadius: 6,
                  padding: '6px 10px',
                  fontSize: 12,
                }}
              >
                <option value="blur">Blur (Gaussian)</option>
                <option value="pixelate">Pixelate</option>
              </select>
              <label style={{ fontSize: 12, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 8 }}>
                Güc: {anonymizeOptions.strength ?? 3}
                <input
                  type="range"
                  min={1}
                  max={5}
                  value={anonymizeOptions.strength ?? 3}
                  onChange={(e) =>
                    onAnonymizeOptionsChange?.({ ...anonymizeOptions, strength: Number(e.target.value) })
                  }
                />
              </label>
            </div>
          )}
          <button
            type="button"
            onClick={() => onAnonymize(anonymizeOptions)}
            disabled={loadingAnonymize || !anonymizeOptions?.enabled}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 14px',
              borderRadius: 8,
              border: '1px solid rgba(34,211,238,0.4)',
              background: 'rgba(34,211,238,0.15)',
              color: '#22d3ee',
              fontSize: 12,
              fontWeight: 600,
              cursor: loadingAnonymize || !anonymizeOptions?.enabled ? 'not-allowed' : 'pointer',
              opacity: loadingAnonymize || !anonymizeOptions?.enabled ? 0.5 : 1,
            }}
          >
            {loadingAnonymize ? (
              <Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} />
            ) : (
              <ScanFace style={{ width: 14, height: 14 }} />
            )}
            Anonimləşdirilmiş şəkil yarat
          </button>
        </div>
      )}

      {anon?.status === 'success' && (
        <p style={{ fontSize: 12, color: '#10b981', margin: '12px 0 0' }}>
          {anon.faces_anonymized} üz anonimləşdirildi ({anon.method}, güc {anon.strength}).
        </p>
      )}
    </div>
  );
}
