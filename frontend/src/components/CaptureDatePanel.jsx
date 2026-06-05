import React from 'react';
import { Calendar, Clock, Info, Globe, ExternalLink } from 'lucide-react';

const DATE_TYPE_STYLE = {
  capture: { title: 'Kamera çəkiliş tarixi', color: '#34d399', border: 'rgba(52,211,153,0.4)' },
  first_seen: { title: 'İlk internet izi', color: '#60a5fa', border: 'rgba(96,165,250,0.45)' },
  wayback: { title: 'İlk internet izi (Wayback)', color: '#38bdf8', border: 'rgba(56,189,248,0.45)' },
  platform: { title: 'Platforma tarixi', color: '#fbbf24', border: 'rgba(251,191,36,0.4)' },
  published: { title: 'Veb / dərc tarixi', color: '#a78bfa', border: 'rgba(167,139,250,0.4)' },
};

export default function CaptureDatePanel({ captureDate }) {
  if (!captureDate) return null;

  const cd = captureDate;
  const cal = cd.calendar_az;
  const isOk = cd.status === 'success';
  const dt = cd.date_type || 'unknown';
  const styleKey = cd.source === 'wayback_earliest' ? 'wayback' : dt;
  const style = DATE_TYPE_STYLE[styleKey] || { title: cd.date_type_title_az || 'Çəkiliş tarixi', color: '#94a3b8', border: 'rgba(100,116,139,0.35)' };

  return (
    <div
      style={{
        background: isOk ? `${style.color}18` : 'rgba(100,116,139,0.15)',
        border: `1px solid ${isOk ? style.border : 'rgba(100,116,139,0.35)'}`,
        borderRadius: 12,
        padding: 14,
        marginBottom: 14,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: isOk ? 12 : 8 }}>
        {dt === 'first_seen' || cd.source === 'wayback_earliest' ? (
          <Globe style={{ width: 18, height: 18, color: style.color }} />
        ) : (
          <Calendar style={{ width: 18, height: 18, color: style.color }} />
        )}
        <h3 style={{ fontSize: 14, fontWeight: 700, color: style.color, margin: 0 }}>
          {cd.date_type_title_az || style.title}
        </h3>
        {isOk && cd.confidence_percent != null && (
          <span style={{ fontSize: 10, color: '#64748b', marginLeft: 'auto' }}>
            etibar {cd.confidence_percent}%
          </span>
        )}
      </div>

      {isOk && cal ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'baseline' }}>
          <div
            style={{
              background: '#0f172a',
              borderRadius: 10,
              padding: '12px 18px',
              border: `1px solid ${style.border}`,
              minWidth: 72,
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: 28, fontWeight: 800, color: '#f1f5f9', lineHeight: 1 }}>{cal.gun}</div>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>gün</div>
          </div>
          <div
            style={{
              background: '#0f172a',
              borderRadius: 10,
              padding: '12px 18px',
              border: `1px solid ${style.border}`,
              flex: 1,
              minWidth: 120,
            }}
          >
            <div style={{ fontSize: 20, fontWeight: 700, color: '#a7f3d0', textTransform: 'capitalize' }}>
              {cal.ay}
            </div>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>ay</div>
          </div>
          <div
            style={{
              background: '#0f172a',
              borderRadius: 10,
              padding: '12px 18px',
              border: `1px solid ${style.border}`,
              minWidth: 80,
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: 28, fontWeight: 800, color: '#f1f5f9', lineHeight: 1 }}>{cal.il}</div>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>il</div>
          </div>
        </div>
      ) : (
        <p style={{ fontSize: 12, color: '#94a3b8', margin: 0, lineHeight: 1.5 }}>
          {cd.message_az}
        </p>
      )}

      {isOk && (
        <>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              marginTop: 12,
              fontSize: 12,
              color: '#cbd5e1',
            }}
          >
            <Clock style={{ width: 13, height: 13, color: style.color }} />
            <span>{cd.display_az}</span>
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 6,
              marginTop: 8,
              fontSize: 11,
              color: '#64748b',
            }}
          >
            <Info style={{ width: 12, height: 12, flexShrink: 0, marginTop: 2 }} />
            <span>{cd.source_label_az}</span>
          </div>
          {cd.wayback_note_az && (
            <p style={{ fontSize: 11, color: '#7dd3fc', margin: '8px 0 0', lineHeight: 1.45 }}>
              {cd.wayback_note_az}
            </p>
          )}
          {cd.tineye_note_az && (
            <p style={{ fontSize: 11, color: '#93c5fd', margin: '8px 0 0', lineHeight: 1.45 }}>
              {cd.tineye_note_az}
            </p>
          )}
          {cd.wayback_url && (
            <a
              href={cd.wayback_url}
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                marginTop: 8,
                fontSize: 11,
                color: '#38bdf8',
                textDecoration: 'none',
              }}
            >
              Wayback snapshot <ExternalLink style={{ width: 10, height: 10 }} />
            </a>
          )}
          {cd.platform_misread_az && (
            <p style={{ fontSize: 10, color: '#fbbf24', margin: '6px 0 0', lineHeight: 1.4 }}>
              {cd.platform_misread_az}
            </p>
          )}
          {cd.warning_az && (
            <p style={{ fontSize: 10, color: '#f87171', margin: '6px 0 0', lineHeight: 1.4 }}>
              {cd.warning_az}
            </p>
          )}
          {(cd.alternatives || []).length > 0 && (
            <div style={{ marginTop: 10, fontSize: 10, color: '#475569' }}>
              Alternativ:{' '}
              {cd.alternatives.map((a, i) => (
                <span key={i}>
                  {i > 0 ? ' · ' : ''}
                  {a.display_az} ({a.source_label_az})
                </span>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
