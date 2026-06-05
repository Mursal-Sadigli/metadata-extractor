import React from 'react';
import { Cpu, Monitor, Smartphone, Layers } from 'lucide-react';

const CAT_COLORS = {
  image_editor: '#f472b6',
  camera_device: '#34d399',
  messenger: '#60a5fa',
  office: '#a78bfa',
  pdf: '#fb923c',
  social: '#38bdf8',
  metadata_tool: '#fbbf24',
  binary: '#94a3b8',
};

const CAT_ICONS = {
  camera_device: Smartphone,
  office: Monitor,
  default: Cpu,
};

export default function ProgramTracesPanel({ data, compact = false }) {
  const st = data?.software_traces;
  if (!st) return null;

  const Icon = CAT_ICONS[st.primary_category] || CAT_ICONS.default;
  const color = CAT_COLORS[st.primary_category] || '#94a3b8';

  if (st.error && !st.traces?.length) {
    return (
      <p style={{ color: '#64748b', fontSize: 12, fontStyle: 'italic' }}>{st.summary || st.error}</p>
    );
  }

  return (
    <div style={{ marginTop: compact ? 0 : 12 }}>
      {!compact && (
        <h3 style={{ fontSize: 13, color: '#94a3b8', margin: '0 0 10px', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Layers style={{ width: 14, height: 14 }} /> Agent və proqram izləri
        </h3>
      )}

      {st.primary_application ? (
        <div style={{
          background: '#0f172a', padding: 12, borderRadius: 10,
          border: `1px solid ${color}44`, marginBottom: 10,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <div style={{ background: `${color}22`, padding: 8, borderRadius: 8 }}>
              <Icon style={{ width: 18, height: 18, color }} />
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9' }}>{st.primary_application}</div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                {st.primary_category_label}
                {st.confidence ? ` • ${Math.round(st.confidence * 100)}% etibar` : ''}
              </div>
            </div>
          </div>
          {st.summary && (
            <p style={{ fontSize: 12, color: '#cbd5e1', margin: '10px 0 0', lineHeight: 1.5 }}>{st.summary}</p>
          )}
        </div>
      ) : (
        <p style={{ color: '#64748b', fontSize: 12, marginBottom: 8 }}>{st.summary || 'Proqram izi tapılmadı.'}</p>
      )}

      {st.device_hints?.length > 0 && (
        <div style={{ marginBottom: 10, fontSize: 12 }}>
          <span style={{ color: '#64748b' }}>Cihaz: </span>
          {st.device_hints.map((d, i) => (
            <span key={i} style={{ color: '#34d399', fontWeight: 600, marginRight: 8 }}>{d}</span>
          ))}
        </div>
      )}

      {st.editing_chain?.length > 1 && (
        <div style={{ marginBottom: 10, fontSize: 12, color: '#94a3b8' }}>
          <span style={{ color: '#64748b' }}>Redaktə zənciri: </span>
          {st.editing_chain.join(' → ')}
        </div>
      )}

      {st.traces?.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: compact ? 180 : 280, overflowY: 'auto' }}>
          {st.traces.map((t, i) => (
            <div
              key={`${t.application}-${t.field}-${i}`}
              style={{
                background: '#0f172a', padding: '8px 10px', borderRadius: 8,
                border: '1px solid #334155', fontSize: 11,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                <strong style={{ color: CAT_COLORS[t.category] || '#e2e8f0' }}>{t.application}</strong>
                <span style={{ color: '#64748b' }}>{t.category_label || t.category}</span>
              </div>
              <div style={{ color: '#94a3b8', marginTop: 4 }}>{t.field}</div>
              {t.raw_value && t.raw_value !== t.application && (
                <div style={{ color: '#64748b', marginTop: 2, wordBreak: 'break-word' }}>{t.raw_value}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
