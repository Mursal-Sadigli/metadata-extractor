import React, { useState } from 'react';
import { Box, ScanSearch } from 'lucide-react';
import VideoTrackingPanel from './VideoTrackingPanel';

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
  'Bina və struktur': '#f97316',
  'Dirək və infra': '#eab308',
  'Yol və mühit': '#64748b',
  Digər: '#9ca3af',
};

function uploadsUrl(filename) {
  if (!filename) return null;
  const base = String(filename).replace(/\\/g, '/').split('/').pop();
  return `${UPLOADS_BASE}/${base}`;
}

function ObjectOverlay({ src, objects, onZoom }) {
  const [dims, setDims] = useState({ w: 0, h: 0 });
  if (!src) return null;

  return (
    <div style={{ position: 'relative', flex: 1, minWidth: 260 }}>
      <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6, textAlign: 'center' }}>
        Obyekt qutuları (canlı)
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
        onClick={() => onZoom?.(src, 'Obyektlər')}
      >
        <img
          src={src}
          alt="Obyekt skanı"
          style={{ width: '100%', height: 280, objectFit: 'contain', borderRadius: 4, display: 'block' }}
          onLoad={(e) => setDims({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
        />
        {dims.w > 0 && objects?.length > 0 && (
          <svg
            style={{
              position: 'absolute',
              left: 8,
              top: 8,
              width: 'calc(100% - 16px)',
              height: 280,
              pointerEvents: 'none',
            }}
            viewBox={`0 0 ${dims.w} ${dims.h}`}
            preserveAspectRatio="xMidYMid meet"
          >
            {objects.map((o) => {
              const b = o.bbox;
              if (!b) return null;
              const color = CATEGORY_COLORS[o.category] || CATEGORY_COLORS.Digər;
              return (
                <g key={o.id}>
                  <rect
                    x={b.x}
                    y={b.y}
                    width={b.w}
                    height={b.h}
                    fill="none"
                    stroke={color}
                    strokeWidth={Math.max(2, dims.w / 400)}
                    rx={2}
                  />
                  <text
                    x={b.x + 4}
                    y={Math.max(b.y + 14, 14)}
                    fill={color}
                    fontSize={Math.max(10, dims.w / 70)}
                    fontWeight="700"
                  >
                    {o.class_name_az}
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

export default function ObjectDetectionPanel({ data, originalUrl }) {
  const [lightbox, setLightbox] = useState(null);
  if (!data) return null;

  if (data.video_tracking) {
    return <VideoTrackingPanel tracking={data.video_tracking} originalUrl={originalUrl} mode="objects" />;
  }

  const od = data.object_detection || data;
  const objects = od.objects || [];
  const summary = od.summary || {};
  const previewSrc = uploadsUrl(od.preview_filename) || uploadsUrl(data.artifacts?.find((a) => String(a).startsWith('objects_')));
  const originalSrc = originalUrl || uploadsUrl(data.original_filename);

  if (od.error && od.status === 'error') {
    return (
      <div style={{ background: '#1e293b', borderRadius: 16, padding: 20, border: '1px solid rgba(239,68,68,0.3)' }}>
        <p style={{ color: '#f87171', margin: 0, fontSize: 13 }}>{od.error}</p>
      </div>
    );
  }

  return (
    <div
      style={{
        background: '#1e293b',
        borderRadius: 16,
        padding: 20,
        border: '1px solid rgba(59,130,246,0.35)',
        boxShadow: '0 0 15px rgba(59,130,246,0.08)',
      }}
      className="cyber-panel"
    >
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
        <div style={{ background: 'rgba(59,130,246,0.2)', padding: 6, borderRadius: 8 }}>
          <Box style={{ width: 16, height: 16, color: '#60a5fa' }} />
        </div>
        <h2 style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
          Obyekt aşkarlanması (YOLO + bina tanıma)
        </h2>
        <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 700, color: objects.length ? '#60a5fa' : '#64748b' }}>
          {od.total_objects ?? objects.length} obyekt · {od.unique_classes ?? 0} sinif
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

      <p style={{ fontSize: 11, color: '#64748b', margin: '0 0 14px' }}>
        <ScanSearch style={{ width: 12, height: 12, display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
        {od.model || 'YOLOv8m'} · {od.dataset || 'COCO + World (güclü)'}
        {od.detectors?.length ? ` · ${od.detectors.join(' + ')}` : ''}
        {od.settings?.tiled ? ' · parça skan' : ''}
      </p>

      {od.note && (
        <p style={{ fontSize: 11, color: '#94a3b8', margin: '0 0 14px', lineHeight: 1.5 }}>{od.note}</p>
      )}

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 18 }}>
        {previewSrc && objects.length > 0 && (
          <div style={{ flex: 1, minWidth: 260 }}>
            <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6, textAlign: 'center' }}>İşarələnmiş önizləmə</div>
            <div
              style={{ background: '#0f172a', padding: 8, borderRadius: 10, border: '1px solid #334155', cursor: 'pointer' }}
              onClick={() => setLightbox({ src: previewSrc, label: 'Obyektlər' })}
            >
              <img src={previewSrc} alt="" style={{ width: '100%', height: 280, objectFit: 'contain', borderRadius: 4 }} />
            </div>
          </div>
        )}
        {originalSrc && objects.length > 0 && (
          <ObjectOverlay src={originalSrc} objects={objects} onZoom={(src, label) => setLightbox({ src, label })} />
        )}
      </div>

      {Object.keys(summary.by_category || {}).length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: 13, color: '#94a3b8', marginBottom: 8 }}>Kateqoriyalar üzrə</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {Object.entries(summary.by_category).map(([cat, count]) => (
              <span
                key={cat}
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  padding: '4px 10px',
                  borderRadius: 20,
                  border: `1px solid ${CATEGORY_COLORS[cat] || '#64748b'}55`,
                  color: CATEGORY_COLORS[cat] || '#cbd5e1',
                  background: `${CATEGORY_COLORS[cat] || '#64748b'}15`,
                }}
              >
                {cat}: {count}
              </span>
            ))}
          </div>
        </div>
      )}

      {Object.keys(summary.by_class || {}).length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: 13, color: '#94a3b8', marginBottom: 8 }}>Siniflər üzrə say</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {Object.entries(summary.by_class).map(([cls, count]) => (
              <span key={cls} style={{ fontSize: 11, color: '#cbd5e1', background: '#0f172a', padding: '4px 8px', borderRadius: 6, border: '1px solid #334155' }}>
                {cls} ×{count}
              </span>
            ))}
          </div>
        </div>
      )}

      {objects.length > 0 && (
        <div>
          <h3 style={{ fontSize: 13, color: '#94a3b8', marginBottom: 8 }}>Tapılan obyektlər</h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ color: '#64748b', textAlign: 'left' }}>
                  <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>#</th>
                  <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>Sinif</th>
                  <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>Kateqoriya</th>
                  <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>Etibar</th>
                  <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>Sahə %</th>
                  <th style={{ padding: '6px 8px', borderBottom: '1px solid #334155' }}>BBox</th>
                </tr>
              </thead>
              <tbody>
                {objects.map((o) => (
                  <tr key={o.id} style={{ color: '#e2e8f0' }}>
                    <td style={{ padding: 8, borderBottom: '1px solid #1e293b' }}>{o.id}</td>
                    <td style={{ padding: 8, borderBottom: '1px solid #1e293b' }}>
                      <span style={{ color: CATEGORY_COLORS[o.category] || '#e2e8f0' }}>{o.class_name_az}</span>
                      <div style={{ fontSize: 10, color: '#64748b' }}>{o.class_name}</div>
                    </td>
                    <td style={{ padding: 8, borderBottom: '1px solid #1e293b' }}>{o.category}</td>
                    <td style={{ padding: 8, borderBottom: '1px solid #1e293b' }}>{Math.round((o.confidence || 0) * 100)}%</td>
                    <td style={{ padding: 8, borderBottom: '1px solid #1e293b' }}>{o.area_percent}%</td>
                    <td style={{ padding: 8, borderBottom: '1px solid #1e293b', fontFamily: 'monospace', fontSize: 11 }}>
                      {o.bbox?.x},{o.bbox?.y} {o.bbox?.w}×{o.bbox?.h}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!objects.length && (
        <p style={{ fontSize: 12, color: '#64748b', fontStyle: 'italic', margin: 0 }}>
          Heç bir obyekt tapılmadı. Etibar həddini azaldın və ya daha aydın şəkil yükləyin.
        </p>
      )}
    </div>
  );
}
