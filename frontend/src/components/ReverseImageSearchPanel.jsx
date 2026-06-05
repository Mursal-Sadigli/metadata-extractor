import React, { useState, useEffect, useMemo } from 'react';
import {
  Search,
  ExternalLink,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Key,
  Globe,
  Image as ImageIcon,
} from 'lucide-react';
import { api } from '../apiClient';
import WebImageTimelinePanel from './WebImageTimelinePanel';
import {
  buildPortalSearchLinks,
  isFetchableImageUrl,
  resolveSearchImageUrl,
} from '../utils/portalImageSearch';

const PROVIDER_COLORS = {
  tineye: '#a78bfa',
  google_vision: '#60a5fa',
  google_lens: '#34d399',
  google_lens_serpapi: '#34d399',
  bing: '#f472b6',
  bing_visual: '#f472b6',
};

const STATUS_ICON = {
  ok: CheckCircle2,
  error: AlertCircle,
  needs_api_key: Key,
  needs_public_url: Globe,
};

function pickSearchUrl(ris, searchImageUrl, imageUrl) {
  const fromApi = ris?.search_image_url || ris?.public_image_url;
  if (isFetchableImageUrl(fromApi)) return fromApi;
  if (isFetchableImageUrl(searchImageUrl)) return searchImageUrl;
  if (isFetchableImageUrl(imageUrl)) return imageUrl;
  return null;
}

export default function ReverseImageSearchPanel({
  data,
  filename,
  imageUrl,
  searchImageUrl,
  uploadMeta,
  embedded = true,
}) {
  const [localData, setLocalData] = useState(data || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const resolvedFromMeta = useMemo(
    () => searchImageUrl || resolveSearchImageUrl(uploadMeta),
    [searchImageUrl, uploadMeta],
  );

  useEffect(() => {
    if (data) setLocalData(data);
  }, [data]);

  const ris = localData || data;
  const effectiveSearchUrl = pickSearchUrl(ris, resolvedFromMeta, imageUrl);

  const portalLinks = useMemo(() => {
    if (ris?.portal_links?.length) {
      return ris.portal_links.filter((l) => l.search_url && l.method !== 'info');
    }
    return buildPortalSearchLinks(effectiveSearchUrl);
  }, [ris?.portal_links, effectiveSearchUrl]);

  const runSearch = async () => {
    if (!filename) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.post('/api/reverse-image-search', {
        filename,
        public_image_url: effectiveSearchUrl || undefined,
      }, { timeout: 180000 });
      setLocalData(res.data);
    } catch (e) {
      setError(e.response?.data?.error || 'Tərs şəkil axtarışı uğursuz oldu.');
    } finally {
      setLoading(false);
    }
  };

  if (!ris && !filename) return null;

  return (
    <div style={embedded ? { marginTop: 0 } : {}}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        marginBottom: 12,
        flexWrap: 'wrap',
      }}>
        <h3 style={{
          fontSize: 13,
          color: '#94a3b8',
          margin: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          flex: 1,
        }}>
          <Search style={{ width: 14, height: 14 }} />
          Canlı Şəkil Kəşfiyyatı (Tərs Axtarış)
        </h3>
        {filename && (
          <button
            type="button"
            onClick={runSearch}
            disabled={loading}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 14px',
              borderRadius: 8,
              border: 'none',
              background: '#059669',
              color: '#fff',
              fontSize: 12,
              fontWeight: 600,
              cursor: loading ? 'wait' : 'pointer',
            }}
          >
            {loading ? (
              <Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} />
            ) : (
              <Search style={{ width: 14, height: 14 }} />
            )}
            {ris ? 'Yenidən axtar' : 'Axtarışı başlat'}
          </button>
        )}
      </div>

      {error && <p style={{ fontSize: 12, color: '#f87171', margin: '0 0 10px' }}>{error}</p>}

      {effectiveSearchUrl && (
        <p style={{ fontSize: 10, color: '#64748b', margin: '0 0 10px', wordBreak: 'break-all' }}>
          Tərs axtarış URL: {effectiveSearchUrl}
        </p>
      )}

      {!effectiveSearchUrl && !ris && !loading && (
        <p style={{ fontSize: 12, color: '#fbbf24', margin: '0 0 10px', lineHeight: 1.5 }}>
          Portal avtomatik axtarışı üçün şəkli birbaşa şəkil linkindən yükləyin (məs. .jpg/.webp URL) və ya PUBLIC_APP_URL (ngrok) təyin edin.
        </p>
      )}

      {!ris && !loading && effectiveSearchUrl && (
        <p style={{ fontSize: 12, color: '#64748b', fontStyle: 'italic', margin: '0 0 10px' }}>
          Aşağıdakı portallara klik edəndə həmin şəkil URL ilə avtomatik axtarış açılır. API axtarışı üçün «Axtarışı başlat».
        </p>
      )}

      {portalLinks.length > 0 && (
        <div style={{ marginBottom: ris ? 14 : 0 }}>
          <h4 style={{ fontSize: 12, color: '#94a3b8', margin: '0 0 8px' }}>Portal axtarışları (URL ilə avtomatik)</h4>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {portalLinks.map((link) => (
              <a
                key={link.id}
                href={link.search_url}
                target="_blank"
                rel="noreferrer"
                title={link.note_az}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '8px 12px',
                  borderRadius: 8,
                  background: link.privacy_warning ? 'rgba(251,191,36,0.08)' : '#0f172a',
                  border: `1px solid ${link.privacy_warning ? 'rgba(251,191,36,0.35)' : '#334155'}`,
                  color: '#cbd5e1',
                  fontSize: 12,
                  textDecoration: 'none',
                }}
              >
                {link.name}
                <ExternalLink style={{ width: 12, height: 12 }} />
              </a>
            ))}
          </div>
          {portalLinks.some((l) => l.privacy_warning) && (
            <p style={{ fontSize: 10, color: '#fbbf24', margin: '8px 0 0' }}>
              PimEyes URL ilə avtomatik açmır; digər portallar (Lens, TinEye, Yandex) birbaşa bu şəkil linki ilə axtarır.
            </p>
          )}
        </div>
      )}

      {ris && (
        <>
          {ris.summary_az && (
            <p style={{ fontSize: 12, color: '#cbd5e1', margin: '0 0 12px', lineHeight: 1.5 }}>
              {ris.summary_az}
            </p>
          )}

          {ris.providers?.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
              {ris.providers.map((p) => {
                const Icon = STATUS_ICON[p.status] || AlertCircle;
                const color = p.status === 'ok' ? '#10b981' : p.status === 'needs_api_key' ? '#fbbf24' : '#94a3b8';
                return (
                  <div
                    key={p.id}
                    style={{
                      background: '#0f172a',
                      border: '1px solid #334155',
                      borderRadius: 8,
                      padding: '8px 12px',
                      fontSize: 11,
                      minWidth: 140,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#e2e8f0', fontWeight: 600 }}>
                      <Icon style={{ width: 12, height: 12, color }} />
                      {p.name}
                    </div>
                    <div style={{ color: '#64748b', marginTop: 4 }}>
                      {p.status === 'ok' && `${p.match_count || 0} uyğunluq`}
                      {p.status === 'needs_api_key' && 'API açarı lazım'}
                      {p.status === 'needs_public_url' && 'İctimai URL lazım'}
                      {p.status === 'error' && (p.error || 'Xəta').slice(0, 60)}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {ris.matches?.length > 0 ? (
            <div style={{ marginBottom: 14 }}>
              <h4 style={{ fontSize: 12, color: '#10b981', margin: '0 0 8px' }}>
                Tapıntılar ({ris.total_matches || ris.matches.length})
              </h4>
              <div style={{ maxHeight: 280, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
                {ris.matches.map((m, i) => (
                  <a
                    key={i}
                    href={m.page_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      display: 'flex',
                      gap: 10,
                      alignItems: 'flex-start',
                      padding: '10px 12px',
                      background: '#0f172a',
                      borderRadius: 8,
                      border: '1px solid #334155',
                      textDecoration: 'none',
                      color: 'inherit',
                    }}
                  >
                    {m.image_url ? (
                      <img
                        src={m.image_url}
                        alt=""
                        style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 6, flexShrink: 0 }}
                        onError={(e) => { e.target.style.display = 'none'; }}
                      />
                    ) : (
                      <div style={{
                        width: 48, height: 48, background: '#1e293b', borderRadius: 6,
                        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                      }}>
                        <ImageIcon style={{ width: 20, height: 20, color: '#475569' }} />
                      </div>
                    )}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {m.title || m.domain}
                      </div>
                      <div style={{ fontSize: 10, color: '#64748b', marginTop: 2 }}>
                        <span style={{
                          color: PROVIDER_COLORS[m.provider] || '#94a3b8',
                          fontWeight: 600,
                          marginRight: 6,
                        }}>
                          {m.provider}
                        </span>
                        {m.domain}
                        {m.score != null && ` · ${Math.round(m.score)}%`}
                        {m.match_type && ` · ${m.match_type}`}
                      </div>
                    </div>
                    <ExternalLink style={{ width: 14, height: 14, color: '#60a5fa', flexShrink: 0 }} />
                  </a>
                ))}
              </div>
            </div>
          ) : (
            <p style={{ fontSize: 12, color: '#64748b', marginBottom: 14 }}>
              API ilə birbaşa uyğunluq tapılmadı. Yuxarıdakı portal linklərindən istifadə edin.
            </p>
          )}

          {ris.web_timeline && (
            <WebImageTimelinePanel timeline={ris.web_timeline} />
          )}

          {ris.setup_hints_az?.length > 0 && (
            <details style={{ marginTop: 12, fontSize: 11, color: '#64748b' }}>
              <summary style={{ cursor: 'pointer', color: '#94a3b8' }}>API konfiqurasiyası (.env)</summary>
              <ul style={{ margin: '8px 0 0', paddingLeft: 18, lineHeight: 1.6 }}>
                {ris.setup_hints_az.map((h, i) => (
                  <li key={i}>{h}</li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </div>
  );
}
