import React from 'react';
import { Sparkles, Image, MapPin, FileText, ArrowRight, AlertTriangle, ScanFace, Car, Cpu } from 'lucide-react';
import LocationPanel from './LocationPanel';

import { UPLOADS_BASE } from '../apiClient';

function uploadsUrl(filename) {
  if (!filename) return null;
  return `${UPLOADS_BASE}/${String(filename).replace(/\\/g, '/').split('/').pop()}`;
}

function MetaBlock({ title, meta }) {
  if (!meta) return null;
  const tags = meta.raw_tags || {};
  const keys = Object.keys(tags);
  const loc = meta.location;
  return (
    <div style={{ flex: 1, minWidth: 200 }}>
      <h4 style={{ fontSize: 12, color: '#94a3b8', margin: '0 0 8px' }}>{title}</h4>
      {loc?.latitude != null && (
        <p style={{ fontSize: 11, color: '#34d399', margin: '0 0 6px' }}>
          GPS: {loc.latitude.toFixed?.(5) ?? loc.latitude}, {loc.longitude.toFixed?.(5) ?? loc.longitude}
        </p>
      )}
      <p style={{ fontSize: 11, color: '#64748b', margin: '0 0 6px' }}>{keys.length} metadata tag</p>
      {keys.length > 0 && (
        <div style={{ maxHeight: 120, overflowY: 'auto', fontSize: 10, color: '#cbd5e1' }}>
          {keys.slice(0, 12).map((k) => (
            <div key={k} style={{ marginBottom: 2 }}>
              <span style={{ color: '#64748b' }}>{k}:</span> {String(tags[k]).slice(0, 60)}
            </div>
          ))}
          {keys.length > 12 && <span style={{ color: '#475569' }}>+{keys.length - 12} daha...</span>}
        </div>
      )}
    </div>
  );
}

export default function RestoreAnalyzePanel({ data, originalUrl }) {
  if (!data) return null;

  const ra = data.restore_analyze || data;
  if (ra.status === 'error') {
    return (
      <div style={{ background: '#1e293b', borderRadius: 16, padding: 20, border: '1px solid rgba(239,68,68,0.3)' }}>
        <p style={{ color: '#f87171', margin: 0 }}>{ra.error}</p>
      </div>
    );
  }

  const rest = ra.restoration || {};
  const before = rest.before || {};
  const after = rest.after || {};
  const restoredUrl = uploadsUrl(rest.restored_filename);
  const comparison = ra.metadata_comparison || {};
  const locationPayload = {
    location: ra.location,
    location_inference: ra.location_inference,
    carved_metadata: ra.carved_metadata,
    file_carving_ml: ra.file_carving_ml,
  };

  return (
    <div
      style={{
        background: '#1e293b',
        borderRadius: 16,
        padding: 20,
        border: '1px solid rgba(52,211,153,0.25)',
        marginBottom: 16,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, paddingBottom: 12, borderBottom: '1px solid #334155' }}>
        <div style={{ background: 'rgba(52,211,153,0.15)', padding: 8, borderRadius: 10 }}>
          <Sparkles style={{ width: 18, height: 18, color: '#34d399' }} />
        </div>
        <div>
          <h2 style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>Forensic AI Bərpa + Metadata & Lokasiya</h2>
          <p style={{ fontSize: 11, color: '#64748b', margin: '4px 0 0' }}>{rest.summary_az}</p>
        </div>
      </div>

      {ra.note && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', background: '#0f172a', padding: 10, borderRadius: 8, marginBottom: 16, fontSize: 11, color: '#94a3b8' }}>
          <AlertTriangle style={{ width: 14, height: 14, color: '#fbbf24', flexShrink: 0, marginTop: 1 }} />
          {ra.note}
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 16, alignItems: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6 }}>Orijinal</div>
          <img
            src={originalUrl}
            alt="Orijinal"
            style={{ maxWidth: 220, maxHeight: 160, borderRadius: 8, border: '1px solid #334155', objectFit: 'contain' }}
          />
          <div style={{ fontSize: 10, color: '#475569', marginTop: 4 }}>
            Blur {before.blur_score} · {before.width}×{before.height}
          </div>
        </div>
        <ArrowRight style={{ width: 20, height: 20, color: '#34d399' }} />
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 11, color: '#34d399', marginBottom: 6 }}>Bərpa edilmiş</div>
          {restoredUrl ? (
            <img
              src={restoredUrl}
              alt="Bərpa"
              style={{ maxWidth: 220, maxHeight: 160, borderRadius: 8, border: '1px solid rgba(52,211,153,0.4)', objectFit: 'contain' }}
            />
          ) : (
            <div style={{ width: 220, height: 120, background: '#0f172a', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Image style={{ color: '#475569' }} />
            </div>
          )}
          <div style={{ fontSize: 10, color: '#34d399', marginTop: 4 }}>
            Blur {after.blur_score} · {after.width}×{after.height}
          </div>
        </div>
      </div>

      {rest.forensic_enhancement && (
        <div style={{ background: '#0f172a', padding: 12, borderRadius: 10, border: '1px solid rgba(52,211,153,0.35)', marginBottom: 16 }}>
          <h3 style={{ fontSize: 13, color: '#34d399', margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Cpu style={{ width: 14, height: 14 }} />
            Kriminalistik AI Enhancement
          </h3>
          <p style={{ fontSize: 11, color: '#94a3b8', margin: '0 0 10px', lineHeight: 1.5 }}>
            {rest.forensic_enhancement.summary_az || rest.forensic_enhancement.pipeline}
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            <span style={badgeStyle}>
              <ScanFace style={{ width: 12, height: 12 }} /> Üz: {rest.forensic_enhancement.face_count ?? 0}
            </span>
            <span style={badgeStyle}>
              <Car style={{ width: 12, height: 12 }} /> Nömrə adayı: {rest.forensic_enhancement.plate_candidate_count ?? 0}
            </span>
            {rest.forensic_enhancement.sr_model_attempted && (
              <span style={badgeStyle}>SR: {rest.forensic_enhancement.sr_model_attempted}</span>
            )}
          </div>
          {(rest.forensic_enhancement.targets_enhanced || []).length > 0 && (
            <ul style={{ margin: '10px 0 0', paddingLeft: 18, fontSize: 11, color: '#cbd5e1' }}>
              {rest.forensic_enhancement.targets_enhanced.map((t, i) => (
                <li key={i}>{t.label_az} — {t.enhancement}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
        {(rest.steps_applied || []).map((s) => (
          <span key={s} style={{ fontSize: 10, padding: '3px 8px', borderRadius: 6, background: '#0f172a', color: '#34d399', border: '1px solid #334155' }}>
            {s}
          </span>
        ))}
        {rest.exif_preserved && (
          <span style={{ fontSize: 10, padding: '3px 8px', borderRadius: 6, background: '#0f172a', color: '#60a5fa', border: '1px solid #334155' }}>
            EXIF saxlanıldı
          </span>
        )}
      </div>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16, padding: 12, background: '#0f172a', borderRadius: 10 }}>
        <FileText style={{ width: 16, height: 16, color: '#60a5fa', flexShrink: 0 }} />
        <MetaBlock title="Orijinal metadata" meta={ra.original_metadata} />
        <MetaBlock title="Bərpa sonrası metadata" meta={ra.restored_metadata} />
      </div>

      {comparison.summary_az && (
        <p style={{ fontSize: 12, color: '#94a3b8', margin: '0 0 16px' }}>
          Müqayisə: {comparison.summary_az}
        </p>
      )}

      {comparison.ocr_improvement?.new_text_lines?.length > 0 && (
        <div style={{ marginBottom: 16, fontSize: 11, color: '#cbd5e1' }}>
          <strong style={{ color: '#a78bfa' }}>OCR təkmilləşməsi:</strong>
          <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
            {comparison.ocr_improvement.new_text_lines.slice(0, 8).map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      <div style={{ borderTop: '1px solid #334155', paddingTop: 16 }}>
        <h3 style={{ fontSize: 13, color: '#f87171', margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 6 }}>
          <MapPin style={{ width: 14, height: 14 }} />
          Lokasiya (bərpa sonrası prioritet)
        </h3>
        <LocationPanel data={locationPayload} />
      </div>
    </div>
  );
}

const badgeStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  fontSize: 10,
  padding: '4px 10px',
  borderRadius: 6,
  background: '#1e293b',
  color: '#a7f3d0',
  border: '1px solid #334155',
};
