import React from 'react';
import { GitCompare } from 'lucide-react';

export default function ComparePanel({ data }) {
  if (!data) return null;
  const summary = data.summary || {};

  return (
    <div style={{
      background: '#1e293b', borderRadius: '16px', padding: '20px',
      border: '1px solid rgba(168,85,247,0.3)',
    }} className="cyber-panel">
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px', paddingBottom: '12px', borderBottom: '1px solid #334155' }}>
        <GitCompare style={{ width: '16px', height: '16px', color: '#a855f7' }} />
        <h2 style={{ fontSize: '15px', fontWeight: '700', color: '#f1f5f9', margin: 0 }}>İki Şəkil Müqayisəsi</h2>
        <span style={{ marginLeft: 'auto', fontSize: '12px', color: '#a855f7', fontWeight: 700 }}>
          {summary.confidence_percent ?? 0}% etibar
        </span>
      </div>

      <p style={{ fontSize: '14px', color: '#e2e8f0', fontWeight: 600, margin: '0 0 16px' }}>{summary.verdict}</p>

      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '16px', fontSize: '12px' }}>
        <span style={{ color: summary.same_camera_likely ? '#10b981' : '#64748b' }}>Eyni kamera: {summary.same_camera_likely ? 'Bəli' : 'Xeyr'}</span>
        <span style={{ color: summary.same_location_likely ? '#10b981' : '#64748b' }}>Eyni yer: {summary.same_location_likely ? 'Bəli' : 'Xeyr'}</span>
        <span style={{ color: summary.same_scene_likely ? '#10b981' : '#64748b' }}>Eyni səhnə: {summary.same_scene_likely ? 'Bəli' : 'Xeyr'}</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {(data.signals || []).map((s, i) => (
          <div key={i} style={{ background: '#0f172a', padding: '10px', borderRadius: '8px', border: '1px solid #334155', fontSize: '12px' }}>
            <strong style={{ color: s.match ? '#10b981' : '#94a3b8' }}>{s.type}</strong>
            {' — '}
            <span style={{ color: '#cbd5e1' }}>{s.detail || (s.match ? 'Uyğun' : 'Uyğunsuz')}</span>
            {s.similarity_percent != null && <span style={{ color: '#64748b' }}> ({s.similarity_percent}% vizual)</span>}
            {s.similarity != null && s.type === 'prnu' && <span style={{ color: '#64748b' }}> (PRNU: {(s.similarity * 100).toFixed(0)}%)</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
