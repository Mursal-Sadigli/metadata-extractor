import React from 'react';
import { History, ExternalLink, Globe, Pencil, Upload } from 'lucide-react';

const EVENT_STYLE = {
  google_first_archive: { color: '#60a5fa', icon: Globe, label: 'Google arxivində ilk iz' },
  google_match_now: { color: '#34d399', icon: Upload, label: 'Google uyğunluğu (indiki)' },
  site_first_seen: { color: '#a78bfa', icon: Globe, label: 'Saytda ilk görünmə' },
  page_published: { color: '#94a3b8', icon: History, label: 'Səhifə dərc tarixi' },
  page_modified: { color: '#fbbf24', icon: Pencil, label: 'Səhifə redaktəsi' },
  content_modified: { color: '#f87171', icon: Pencil, label: 'Məzmun dəyişib (Wayback)' },
};

export default function WebImageTimelinePanel({ timeline }) {
  if (!timeline || timeline.status === 'error') return null;

  const tl = timeline;
  const events = tl.timeline || [];
  const google = tl.google || {};
  const sites = tl.sites || {};
  const mods = tl.modifications || {};

  if (tl.status === 'no_data' && events.length === 0) {
    return (
      <p style={{ fontSize: 12, color: '#64748b', margin: '12px 0 0' }}>
        {tl.summary_az || 'Veb xronologiya üçün uyğunluq tapılmadı.'}
      </p>
    );
  }

  return (
    <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid #334155' }}>
      <h4 style={{
        fontSize: 13,
        color: '#60a5fa',
        margin: '0 0 10px',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}>
        <History style={{ width: 16, height: 16 }} />
        Veb yayılma xronologiyası (TinEye olmadan)
      </h4>

      {tl.summary_az && (
        <p style={{ fontSize: 12, color: '#cbd5e1', margin: '0 0 12px', lineHeight: 1.5 }}>
          {tl.summary_az}
        </p>
      )}

      {(google.first_archive_display_az || google.match_count > 0) && (
        <div style={{
          background: 'rgba(96,165,250,0.1)',
          border: '1px solid rgba(96,165,250,0.35)',
          borderRadius: 10,
          padding: 12,
          marginBottom: 12,
        }}>
          <div style={{ fontSize: 11, color: '#93c5fd', fontWeight: 600, marginBottom: 6 }}>Google</div>
          {google.first_archive_display_az && (
            <p style={{ fontSize: 13, color: '#e2e8f0', margin: '0 0 6px' }}>
              Arxivdə ilk iz: <strong>{google.first_archive_display_az}</strong>
            </p>
          )}
          {google.match_count > 0 && (
            <p style={{ fontSize: 11, color: '#94a3b8', margin: 0 }}>
              Vision/Lens uyğunluq: {google.match_count} URL
            </p>
          )}
          {google.lens_search_url && (
            <a
              href={google.lens_search_url}
              target="_blank"
              rel="noreferrer"
              style={{ fontSize: 11, color: '#60a5fa', marginTop: 8, display: 'inline-flex', alignItems: 'center', gap: 4 }}
            >
              Google Lens <ExternalLink style={{ width: 11, height: 11 }} />
            </a>
          )}
        </div>
      )}

      {sites.added_after_google?.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: '#a78bfa', fontWeight: 600, marginBottom: 8 }}>
            Google-dan sonra əlavə olunan saytlar
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 160, overflowY: 'auto' }}>
            {sites.added_after_google.map((s, i) => (
              <a
                key={i}
                href={s.page_url}
                target="_blank"
                rel="noreferrer"
                style={{
                  fontSize: 11,
                  padding: '8px 10px',
                  background: '#0f172a',
                  borderRadius: 8,
                  border: '1px solid #334155',
                  color: '#cbd5e1',
                  textDecoration: 'none',
                }}
              >
                <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{s.domain}</span>
                {' · '}
                {s.display_az || s.first_seen}
              </a>
            ))}
          </div>
        </div>
      )}

      {mods.count > 0 && (
        <p style={{ fontSize: 11, color: '#fbbf24', margin: '0 0 10px' }}>
          {mods.count} dəyişiklik / redaktə izi tapıldı (Wayback digest və ya səhifə metadata)
        </p>
      )}

      {events.length > 0 && (
        <div style={{ position: 'relative', paddingLeft: 18, maxHeight: 320, overflowY: 'auto' }}>
          <div style={{
            position: 'absolute',
            left: 5,
            top: 4,
            bottom: 4,
            width: 2,
            background: '#334155',
          }} />
          {events.map((ev, i) => {
            const st = EVENT_STYLE[ev.event_type] || { color: '#94a3b8', icon: History, label: ev.event_type };
            const Icon = st.icon;
            return (
              <div key={i} style={{ position: 'relative', marginBottom: 12, paddingLeft: 12 }}>
                <div style={{
                  position: 'absolute',
                  left: -13,
                  top: 2,
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  background: st.color,
                  border: '2px solid #0f172a',
                }} />
                <div style={{ fontSize: 12, fontWeight: 600, color: st.color }}>{st.label}</div>
                <div style={{ fontSize: 13, color: '#e2e8f0', marginTop: 2 }}>{ev.display_az}</div>
                <div style={{ fontSize: 10, color: '#64748b', marginTop: 4 }}>
                  {ev.domain}
                  {ev.note_az && ` — ${ev.note_az}`}
                </div>
                {ev.wayback_url && (
                  <a
                    href={ev.wayback_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ fontSize: 10, color: '#60a5fa', marginTop: 4, display: 'inline-flex', gap: 4, alignItems: 'center' }}
                  >
                    Wayback snapshot <ExternalLink style={{ width: 10, height: 10 }} />
                  </a>
                )}
                {ev.page_url && !ev.wayback_url && (
                  <a
                    href={ev.page_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ fontSize: 10, color: '#64748b', marginTop: 4, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}
                  >
                    {ev.page_url}
                  </a>
                )}
              </div>
            );
          })}
        </div>
      )}

      {tl.limitations_az && (
        <p style={{ fontSize: 10, color: '#475569', margin: '10px 0 0', lineHeight: 1.4 }}>
          {tl.limitations_az}
        </p>
      )}
    </div>
  );
}
