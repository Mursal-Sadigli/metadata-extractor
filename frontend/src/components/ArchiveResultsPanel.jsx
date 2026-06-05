import React from 'react';
import { Archive, MapPin } from 'lucide-react';

import { UPLOADS_BASE as UPLOADS } from '../apiClient';

export default function ArchiveResultsPanel({ data }) {
  if (!data) return null;

  return (
    <div style={{
      background: '#1e293b', borderRadius: '16px', padding: '20px',
      border: '1px solid rgba(56,189,248,0.3)',
    }} className="cyber-panel">
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
        <Archive style={{ width: '16px', height: '16px', color: '#38bdf8' }} />
        <h2 style={{ fontSize: '15px', fontWeight: '700', color: '#f1f5f9', margin: 0 }}>
          Arxiv Analizi ({data.archive_type || 'unknown'})
        </h2>
        <span style={{ marginLeft: 'auto', fontSize: '12px', color: '#64748b' }}>
          {data.media_count ?? 0} media
        </span>
      </div>

      <div style={{ maxHeight: 400, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {(data.items || []).map((item, i) => (
          <div key={i} style={{ background: '#0f172a', padding: '10px', borderRadius: '8px', border: '1px solid #334155', fontSize: '12px' }}>
            <div style={{ fontWeight: 600, color: '#e2e8f0', marginBottom: '4px' }}>{item.filename}</div>
            {item.has_gps && item.location && (
              <div style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <MapPin style={{ width: '12px', height: '12px' }} />
                GPS: {item.location.latitude?.toFixed(4)}, {item.location.longitude?.toFixed(4)}
              </div>
            )}
            {!item.has_gps && <span style={{ color: '#64748b' }}>GPS yoxdur</span>}
            {item.error && <span style={{ color: '#ef4444' }}>{item.error}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
