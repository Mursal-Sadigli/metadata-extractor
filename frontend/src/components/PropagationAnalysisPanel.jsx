import React, { useState } from 'react';
import { History, Globe, Layers, ExternalLink, Loader2, RefreshCw } from 'lucide-react';
import { api } from '../apiClient';
import { buildPortalSearchLinks, resolveSearchImageUrl } from '../utils/portalImageSearch';

const VARIANT_COLORS = {
  url_params: '#60a5fa',
  path_resize: '#a78bfa',
  similar_or_crop: '#fbbf24',
  exact_match: '#34d399',
};

export default function PropagationAnalysisPanel({
  propagation,
  filename,
  imageUrl,
  uploadMeta,
  onUpdate,
}) {
  const [local, setLocal] = useState(propagation || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const data = local || propagation;
  if (!data && !filename) return null;

  const searchUrl = resolveSearchImageUrl(uploadMeta) || (
    imageUrl?.startsWith('http') && !/localhost|127\.0\.0\.1/i.test(imageUrl) ? imageUrl : undefined
  );

  const runFull = async () => {
    if (!filename) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.post(
        '/api/propagation-analysis',
        {
          filename,
          public_image_url: searchUrl,
        },
        { timeout: 240000 },
      );
      setLocal(res.data);
      if (onUpdate) onUpdate(res.data);
    } catch (e) {
      setError(e.response?.data?.error || 'Tam yayılma analizi uğursuz oldu.');
    } finally {
      setLoading(false);
    }
  };

  if (!data) {
    return (
      <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid #334155' }}>
        <button
          type="button"
          onClick={runFull}
          disabled={loading || !filename}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 14px',
            borderRadius: 8,
            border: 'none',
            background: '#7c3aed',
            color: '#fff',
            fontSize: 12,
            fontWeight: 600,
            cursor: loading ? 'wait' : 'pointer',
          }}
        >
          {loading ? <Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} /> : <History style={{ width: 14, height: 14 }} />}
          Tarix və yayılma analizi
        </button>
        {error && <p style={{ color: '#f87171', fontSize: 12, marginTop: 8 }}>{error}</p>}
      </div>
    );
  }

  const wbImg = data.wayback?.image || [];
  const pages = data.page_indexing || [];
  const variants = data.variants || [];
  const occ = data.occurrences || [];

  return (
    <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid #334155' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        <History style={{ width: 16, height: 16, color: '#a78bfa' }} />
        <h3 style={{ fontSize: 13, color: '#a78bfa', margin: 0, flex: 1 }}>Tarix və yayılma analizi</h3>
        {filename && (
          <button
            type="button"
            onClick={runFull}
            disabled={loading}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              padding: '6px 10px',
              fontSize: 10,
              borderRadius: 6,
              border: '1px solid #475569',
              background: '#0f172a',
              color: '#94a3b8',
              cursor: loading ? 'wait' : 'pointer',
            }}
          >
            {loading ? <Loader2 style={{ width: 12, height: 12 }} /> : <RefreshCw style={{ width: 12, height: 12 }} />}
            Tam analiz (+ tərs axtarış)
          </button>
        )}
      </div>

      {data.summary_az && (
        <p style={{ fontSize: 12, color: '#cbd5e1', margin: '0 0 12px', lineHeight: 1.5 }}>{data.summary_az}</p>
      )}
      {(data.cdn_warning?.message_az || data.cdn_only_note_az) && (
        <p style={{
          fontSize: 11,
          color: '#fbbf24',
          margin: '0 0 12px',
          padding: '10px 12px',
          background: 'rgba(251,191,36,0.08)',
          borderRadius: 8,
          border: '1px solid rgba(251,191,36,0.25)',
          lineHeight: 1.5,
        }}>
          {data.cdn_warning?.message_az || data.cdn_only_note_az}
        </p>
      )}
      {error && <p style={{ color: '#f87171', fontSize: 11, margin: '0 0 8px' }}>{error}</p>}

      {data.global_first_seen_display_az && (
        <div style={{
          background: 'rgba(167,139,250,0.12)',
          border: '1px solid rgba(167,139,250,0.35)',
          borderRadius: 10,
          padding: 12,
          marginBottom: 12,
        }}>
          <div style={{ fontSize: 11, color: '#94a3b8' }}>Ən erkən ümumi iz</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#e2e8f0' }}>{data.global_first_seen_display_az}</div>
          {data.image_hash && (
            <div style={{ fontSize: 10, color: '#64748b', marginTop: 6, wordBreak: 'break-all' }}>
              image_hash: {data.image_hash}
            </div>
          )}
        </div>
      )}

      {wbImg.length > 0 && (
        <section style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#60a5fa', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Globe style={{ width: 12, height: 12 }} />
            Wayback — şəkil URL ilk snapshot
          </div>
          {wbImg.map((w, i) => (
            <div key={i} style={{ fontSize: 11, padding: '8px 10px', background: '#0f172a', borderRadius: 8, marginBottom: 6, border: '1px solid #334155' }}>
              <div style={{ color: '#e2e8f0', fontWeight: 600 }}>
                {w.first_snapshot_display_az || w.first_snapshot || '—'}
                {w.snapshot_count > 0 && <span style={{ color: '#64748b', fontWeight: 400 }}> · {w.snapshot_count} snapshot</span>}
              </div>
              <div style={{ color: '#64748b', marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis' }}>{w.url}</div>
              {w.wayback_url && (
                <a href={w.wayback_url} target="_blank" rel="noreferrer" style={{ fontSize: 10, color: '#60a5fa', marginTop: 4, display: 'inline-flex', gap: 4, alignItems: 'center' }}>
                  Wayback snapshot <ExternalLink style={{ width: 10, height: 10 }} />
                </a>
              )}
            </div>
          ))}
        </section>
      )}

      {pages.length > 0 && (
        <section style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#34d399', marginBottom: 8 }}>
            Səhifə ilk indekslənmə (Wayback + metadata)
          </div>
          <div style={{ maxHeight: 160, overflowY: 'auto' }}>
            {pages.map((p, i) => (
              <div key={i} style={{ fontSize: 11, padding: '8px 10px', background: '#0f172a', borderRadius: 8, marginBottom: 6, border: '1px solid #334155' }}>
                <div style={{ color: '#a7f3d0', fontWeight: 600 }}>
                  {p.first_seen_display_az || p.first_seen || '—'}
                  <span style={{ color: '#64748b', fontWeight: 400 }}> · etibar {Math.round((p.confidence || 0) * 100)}%</span>
                </div>
                <div style={{ color: '#64748b', marginTop: 2 }}>{p.domain}</div>
                {p.wayback_url && (
                  <a href={p.wayback_url} target="_blank" rel="noreferrer" style={{ fontSize: 10, color: '#60a5fa' }}>Wayback</a>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {variants.length > 0 && (
        <section style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#fbbf24', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Layers style={{ width: 12, height: 12 }} />
            Variantlar / kəsilmiş / ölçü ({variants.length})
          </div>
          <div style={{ maxHeight: 200, overflowY: 'auto' }}>
            {variants.slice(0, 12).map((v, i) => (
              <div key={i} style={{ fontSize: 10, padding: '8px', background: '#0f172a', borderRadius: 8, marginBottom: 6, border: '1px solid #334155' }}>
                <span style={{ color: VARIANT_COLORS[v.variant_type] || '#94a3b8', fontWeight: 600 }}>
                  {v.variant_type_az || v.variant_type}
                </span>
                {v.dimensions_hint && <span style={{ color: '#64748b' }}> · {v.dimensions_hint}</span>}
                <span style={{ color: '#475569' }}> · {v.source}</span>
                {v.page_url && (
                  <a href={v.page_url} target="_blank" rel="noreferrer" style={{ display: 'block', color: '#64748b', marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {v.page_url}
                  </a>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {occ.length > 0 && (
        <section>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', marginBottom: 8 }}>Vahid cədvəl (metadata)</div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', fontSize: 10, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ color: '#64748b', textAlign: 'left' }}>
                  <th style={{ padding: 4 }}>first_seen</th>
                  <th style={{ padding: 4 }}>source</th>
                  <th style={{ padding: 4 }}>conf.</th>
                </tr>
              </thead>
              <tbody>
                {occ.slice(0, 8).map((o, i) => (
                  <tr key={i} style={{ borderTop: '1px solid #1e293b' }}>
                    <td style={{ padding: 4, color: '#e2e8f0' }}>{o.first_seen || '—'}</td>
                    <td style={{ padding: 4, color: '#94a3b8' }}>{o.source}</td>
                    <td style={{ padding: 4, color: '#64748b' }}>{Math.round((o.confidence || 0) * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {((data.manual_reverse_portals?.length ? data.manual_reverse_portals : buildPortalSearchLinks(searchUrl))).length > 0 && (
        <section style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', marginBottom: 8 }}>
            Pulsuz tərs axtarış (veb — API/billing yox)
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {(data.manual_reverse_portals?.length ? data.manual_reverse_portals : buildPortalSearchLinks(searchUrl)).filter((p) => p.search_url).map((p) => (
              <a
                key={p.id}
                href={p.search_url}
                target="_blank"
                rel="noreferrer"
                style={{
                  fontSize: 10,
                  padding: '6px 10px',
                  borderRadius: 6,
                  background: '#1e293b',
                  color: '#93c5fd',
                  border: '1px solid #334155',
                }}
              >
                {p.name}
              </a>
            ))}
          </div>
        </section>
      )}

      {data.limitations_az && (
        <p style={{ fontSize: 10, color: '#475569', margin: '10px 0 0', lineHeight: 1.4 }}>{data.limitations_az}</p>
      )}
    </div>
  );
}
