import React from 'react';
import { Link2, ExternalLink, Hash, MapPin, Smartphone, BarChart3, Shield, AlertTriangle } from 'lucide-react';

import { UPLOADS_BASE as UPLOADS } from '../apiClient';

const PLATFORM_LABELS = {
  tiktok: 'TikTok',
  instagram: 'Instagram',
  twitter: 'X (Twitter)',
  facebook: 'Facebook',
  youtube: 'YouTube',
  social: 'Sosial',
};

function Row({ label, value, mono }) {
  if (value == null || value === '') return null;
  return (
    <p style={{ margin: '4px 0', fontSize: 13, color: '#cbd5e1' }}>
      <strong style={{ color: '#94a3b8' }}>{label}:</strong>{' '}
      <span style={mono ? { fontFamily: 'monospace', fontSize: 12, wordBreak: 'break-all' } : {}}>{value}</span>
    </p>
  );
}

function Section({ title, icon: Icon, children }) {
  return (
    <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid #334155' }}>
      <h3 style={{ fontSize: 13, color: '#94a3b8', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
        {Icon && <Icon style={{ width: 14, height: 14 }} />}
        {title}
      </h3>
      {children}
    </div>
  );
}

export default function SocialMetaPanel({ data }) {
  if (!data) return null;

  const payload = data.social_meta || data;
  const err = payload.error || data.error;

  if (payload.status === 'error' || (err && !payload.platform)) {
    return (
      <div style={{ background: '#1e293b', padding: 16, borderRadius: 12, color: '#ef4444', fontSize: 13 }}>
        {err || 'Sosial metadata alınmadı'}
      </div>
    );
  }

  const ids = payload.unique_ids || {};
  const loc = payload.location || {};
  const dev = payload.device || {};
  const eng = payload.engagement || {};
  const media = payload.media || {};
  const platformLabel = PLATFORM_LABELS[payload.platform] || payload.platform || '—';
  const confidencePct = payload.confidence != null ? Math.round(payload.confidence * 100) : null;

  return (
    <div
      style={{
        background: '#1e293b',
        borderRadius: 16,
        padding: 20,
        border: '1px solid rgba(99,102,241,0.3)',
      }}
      className="cyber-panel"
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Link2 style={{ width: 16, height: 16, color: '#818cf8' }} />
          <h2 style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
            Sosial Media Metadata — {platformLabel}
          </h2>
        </div>
        {confidencePct != null && (
          <span style={{ fontSize: 12, color: confidencePct >= 60 ? '#10b981' : '#fbbf24', fontWeight: 700 }}>
            Etibar: {confidencePct}%
          </span>
        )}
      </div>

      <div style={{ fontSize: 13, color: '#cbd5e1' }}>
        <Row label="Giriş növü" value={payload.content_type === 'profile' ? 'Instagram profil' : payload.input_type === 'file' ? 'Yüklənmiş fayl' : 'Post URL'} />
        <Row label="Başlıq" value={payload.title} />
        <Row label="Müəllif" value={payload.author?.name || ids.uploader_id} />
        <Row label="Yüklənmə tarixi" value={payload.upload_date} />

        {ids.webpage_url && (
          <a href={ids.webpage_url} target="_blank" rel="noreferrer" style={{ color: '#818cf8', display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 6, fontSize: 12 }}>
            Orijinal link <ExternalLink style={{ width: 12, height: 12 }} />
          </a>
        )}

        {(ids.content_id || ids.uploader_id || ids.shortcode) && (
          <Section title="Unikal ID-lər" icon={Hash}>
            <div style={{ background: '#0f172a', padding: 12, borderRadius: 10, border: '1px solid #334155' }}>
              <Row label="Content ID" value={ids.content_id} mono />
              <Row label="Shortcode" value={ids.shortcode} mono />
              <Row label="Uploader ID" value={ids.uploader_id} mono />
              <Row label="Channel ID" value={ids.channel_id} mono />
              <Row label="Display ID" value={ids.display_id} mono />
            </div>
          </Section>
        )}

        {(loc.latitude != null || loc.place_name) && (
          <Section title="Lokasiya" icon={MapPin}>
            <div style={{ background: '#0f172a', padding: 12, borderRadius: 10, border: '1px solid #334155' }}>
              {loc.latitude != null && (
                <p style={{ margin: '0 0 4px', color: '#10b981' }}>
                  GPS: {loc.latitude}, {loc.longitude}
                </p>
              )}
              <Row label="Yer adı" value={loc.place_name} />
              <Row label="Mənbə" value={loc.source !== 'none' ? loc.source : null} />
            </div>
          </Section>
        )}

        {(dev.make || dev.model || dev.software || dev.os) && (
          <Section title="Cihaz / proqram" icon={Smartphone}>
            <div style={{ background: '#0f172a', padding: 12, borderRadius: 10, border: '1px solid #334155' }}>
              <Row label="İstehsalçı" value={dev.make} />
              <Row label="Model" value={dev.model} />
              <Row label="Proqram" value={dev.software} />
              <Row label="OS" value={dev.os} />
              <Row label="Mənbə" value={dev.source !== 'none' ? dev.source : null} />
            </div>
          </Section>
        )}

        {(eng.followers != null || eng.following != null) && (
          <Section title="Profil statistikası" icon={BarChart3}>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 12 }}>
              {eng.followers != null && <span><strong style={{ color: '#94a3b8' }}>İzləyici:</strong> {eng.followers.toLocaleString()}</span>}
              {eng.following != null && <span><strong style={{ color: '#94a3b8' }}>İzlənilən:</strong> {eng.following.toLocaleString()}</span>}
            </div>
          </Section>
        )}

        {(eng.views != null || eng.likes != null || eng.comments != null) && (
          <Section title="Statistika" icon={BarChart3}>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 12 }}>
              {eng.views != null && <span><strong style={{ color: '#94a3b8' }}>Baxış:</strong> {eng.views.toLocaleString()}</span>}
              {eng.likes != null && <span><strong style={{ color: '#94a3b8' }}>Bəyənmə:</strong> {eng.likes.toLocaleString()}</span>}
              {eng.comments != null && <span><strong style={{ color: '#94a3b8' }}>Şərh:</strong> {eng.comments.toLocaleString()}</span>}
            </div>
          </Section>
        )}

        {(media.duration_sec || media.width) && (
          <Section title="Media" icon={BarChart3}>
            <Row label="Müddət" value={media.duration_sec != null ? `${media.duration_sec}s` : null} />
            <Row label="Ölçü" value={media.width && media.height ? `${media.width}×${media.height}` : null} />
          </Section>
        )}

        {payload.description && (
          <p style={{ margin: '12px 0 0', color: '#94a3b8', fontSize: 12, lineHeight: 1.5 }}>{payload.description}</p>
        )}

        {payload.sources?.length > 0 && (
          <Section title="Mənbələr" icon={Shield}>
            <p style={{ margin: 0, fontSize: 11, color: '#64748b' }}>{payload.sources.join(' · ')}</p>
          </Section>
        )}

        {payload.warnings?.length > 0 && (
          <Section title="Xəbərdarlıqlar" icon={AlertTriangle}>
            {payload.warnings.map((w, i) => (
              <p key={i} style={{ margin: '4px 0', fontSize: 11, color: '#fbbf24', lineHeight: 1.45 }}>{w}</p>
            ))}
          </Section>
        )}

        {payload.thumbnail_file && (
          <img
            src={`${UPLOADS}/${payload.thumbnail_file}`}
            alt="thumbnail"
            style={{ maxWidth: 200, borderRadius: 8, marginTop: 12 }}
          />
        )}
        {payload.thumbnail_location?.latitude != null && (
          <p style={{ margin: '8px 0 0', color: '#10b981', fontSize: 12 }}>
            Thumbnail GPS: {payload.thumbnail_location.latitude}, {payload.thumbnail_location.longitude}
          </p>
        )}
      </div>
    </div>
  );
}
