import React, { useState } from 'react';
import { Layers, Grid3X3, Repeat, FileWarning, Database, ChevronDown, ChevronUp } from 'lucide-react';

const PROFILE_LABELS = {
  exif: 'EXIF',
  xmp: 'XMP',
  iptc: 'IPTC',
  icc: 'ICC Profile',
};

const PROFILE_COLORS = {
  exif: '#60a5fa',
  xmp: '#a78bfa',
  iptc: '#fbbf24',
  icc: '#34d399',
};

function CountBadge({ label, count, color = '#94a3b8' }) {
  if (!count) return null;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '3px 8px',
        borderRadius: 6,
        background: '#0f172a',
        border: `1px solid ${color}44`,
        fontSize: 11,
        color,
        fontWeight: 600,
      }}
    >
      {label}: {count}
    </span>
  );
}

export default function InternalStructurePanel({ data }) {
  const [showSegments, setShowSegments] = useState(false);
  if (!data || data.status === 'error') return null;

  const segments = data.segments || {};
  const counts = segments.counts || {};
  const mosaic = data.mosaic || {};
  const loop = data.loop;
  const profiles = data.metadata_profiles || {};
  const embedded = data.embedded_findings || [];

  return (
    <div
      style={{
        marginTop: 16,
        paddingTop: 16,
        borderTop: '1px solid #334155',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <div style={{ background: 'rgba(129,140,248,0.2)', padding: 6, borderRadius: 8 }}>
          <Layers style={{ width: 14, height: 14, color: '#818cf8' }} />
        </div>
        <h3 style={{ fontSize: 14, fontWeight: 700, color: '#e2e8f0', margin: 0 }}>
          Daxili Struktur (Forensic)
        </h3>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: '#64748b' }}>
          {data.format} · {(data.file_size_bytes || 0).toLocaleString()} byte
        </span>
      </div>

      {(data.summary_az || []).map((line, i) => (
        <p key={i} style={{ margin: '0 0 4px', fontSize: 11, color: '#94a3b8', lineHeight: 1.45 }}>
          {line}
        </p>
      ))}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, margin: '12px 0' }}>
        {Object.entries(counts).map(([k, v]) => (
          <CountBadge key={k} label={k} count={v} color="#818cf8" />
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10, marginBottom: 14 }}>
        <div style={{ background: '#0f172a', padding: 12, borderRadius: 10, border: '1px solid #334155' }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Grid3X3 style={{ width: 12, height: 12 }} /> Mozaik / Tile
          </div>
          <p style={{ margin: 0, fontSize: 12, color: mosaic.detected ? '#fbbf24' : '#cbd5e1', lineHeight: 1.45 }}>
            {mosaic.summary_az || '—'}
          </p>
        </div>

        <div style={{ background: '#0f172a', padding: 12, borderRadius: 10, border: '1px solid #334155' }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Repeat style={{ width: 12, height: 12 }} /> Döngə limiti (loop)
          </div>
          <p style={{ margin: 0, fontSize: 12, color: '#cbd5e1' }}>
            {loop ? (
              <>
                {loop.format || 'Animasiya'}: <strong>{loop.max_repeats ?? '—'}</strong>
                {loop.infinite_loop && <span style={{ color: '#22d3ee', marginLeft: 6 }}>∞</span>}
              </>
            ) : (
              'Statik şəkil — loop yoxdur (GIF/APNG/WebP anim deyil)'
            )}
          </p>
        </div>
      </div>

      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Database style={{ width: 12, height: 12 }} /> Metadata profilləri
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 8 }}>
          {Object.entries(profiles).map(([key, prof]) => (
            <div
              key={key}
              style={{
                background: '#0f172a',
                padding: 10,
                borderRadius: 8,
                border: `1px solid ${prof.present ? PROFILE_COLORS[key] + '55' : '#334155'}`,
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 700, color: prof.present ? PROFILE_COLORS[key] : '#64748b' }}>
                {PROFILE_LABELS[key] || key.toUpperCase()}
              </div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                {prof.present ? `Var · ${prof.size_bytes || '?'} byte` : 'Yoxdur'}
              </div>
              {prof.locations?.length > 0 && (
                <div style={{ fontSize: 10, color: '#64748b', marginTop: 4, lineHeight: 1.35 }}>
                  {prof.locations.slice(0, 2).join('; ')}
                  {prof.locations.length > 2 ? ` (+${prof.locations.length - 2})` : ''}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {embedded.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
            <FileWarning style={{ width: 12, height: 12, color: '#fbbf24' }} /> Gömülü fayl / trailing data
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {embedded.map((e, i) => (
              <div
                key={i}
                style={{
                  background: '#0f172a',
                  padding: '8px 10px',
                  borderRadius: 8,
                  border: `1px solid ${e.risk === 'high' ? 'rgba(239,68,68,0.35)' : 'rgba(251,191,36,0.25)'}`,
                  fontSize: 11,
                  color: '#cbd5e1',
                }}
              >
                {e.description_az}
                {e.estimated_size_bytes ? ` · ~${e.estimated_size_bytes.toLocaleString()} byte` : ''}
                {e.mime_hint ? ` · ${e.mime_hint}` : ''}
              </div>
            ))}
          </div>
          <p style={{ fontSize: 10, color: '#64748b', margin: '8px 0 0' }}>
            OSINT panelində steganografiya bölməsində də göstərilir.
          </p>
        </div>
      )}

      {(segments.details || []).length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setShowSegments(!showSegments)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 10px',
              borderRadius: 8,
              border: '1px solid #334155',
              background: 'transparent',
              color: '#94a3b8',
              fontSize: 11,
              cursor: 'pointer',
            }}
          >
            {showSegments ? <ChevronUp style={{ width: 12, height: 12 }} /> : <ChevronDown style={{ width: 12, height: 12 }} />}
            Chunk/segment cədvəli ({segments.total_segments || segments.total_chunks || 0})
          </button>
          {showSegments && (
            <div style={{ marginTop: 8, maxHeight: 220, overflowY: 'auto', fontSize: 10, color: '#94a3b8' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: '#64748b' }}>
                    <th style={{ padding: '4px 6px', borderBottom: '1px solid #334155' }}>Tip</th>
                    <th style={{ padding: '4px 6px', borderBottom: '1px solid #334155' }}>Offset</th>
                    <th style={{ padding: '4px 6px', borderBottom: '1px solid #334155' }}>Ölçü</th>
                    <th style={{ padding: '4px 6px', borderBottom: '1px solid #334155' }}>Qeyd</th>
                  </tr>
                </thead>
                <tbody>
                  {(segments.details || []).map((s, i) => (
                    <tr key={i}>
                      <td style={{ padding: '4px 6px', borderBottom: '1px solid #1e293b', color: '#cbd5e1' }}>
                        {s.name || s.type}
                      </td>
                      <td style={{ padding: '4px 6px', borderBottom: '1px solid #1e293b' }}>{s.offset}</td>
                      <td style={{ padding: '4px 6px', borderBottom: '1px solid #1e293b' }}>
                        {s.payload_size ?? s.length ?? '—'}
                      </td>
                      <td style={{ padding: '4px 6px', borderBottom: '1px solid #1e293b' }}>
                        {s.contains || s.extra?.contains || s.note || ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {(data.warnings || []).length > 0 && (
        <div style={{ marginTop: 12 }}>
          {(data.warnings || []).map((w, i) => (
            <p key={i} style={{ margin: '4px 0 0', fontSize: 11, color: '#fbbf24' }}>
              {w}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
