import React, { useState } from 'react';
import {
  Brain, Users, Car, Tag, FileText, MapPin, Activity, ScanSearch, Eye,
} from 'lucide-react';

import { UPLOADS_BASE } from '../apiClient';

function uploadsUrl(filename) {
  if (!filename) return null;
  return `${UPLOADS_BASE}/${String(filename).replace(/\\/g, '/').split('/').pop()}`;
}

function Section({ title, icon: Icon, color, children }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <h3
        style={{
          fontSize: 13,
          color: '#94a3b8',
          margin: '0 0 10px',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <Icon style={{ width: 14, height: 14, color }} />
        {title}
      </h3>
      {children}
    </div>
  );
}

function Chip({ label, color = '#64748b' }) {
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '4px 10px',
        borderRadius: 6,
        background: '#0f172a',
        border: `1px solid ${color}44`,
        fontSize: 11,
        color,
        margin: '2px 4px 2px 0',
      }}
    >
      {label}
    </span>
  );
}

export default function VisionMLPanel({ data, originalUrl }) {
  const [showOcr, setShowOcr] = useState(false);
  if (!data) return null;

  const vm = data.vision_ml || data;
  if (vm.status === 'error') {
    return (
      <div style={{ background: '#1e293b', borderRadius: 16, padding: 20, border: '1px solid rgba(239,68,68,0.3)' }}>
        <p style={{ color: '#f87171', margin: 0 }}>{vm.error}</p>
      </div>
    );
  }

  const people = vm.people || {};
  const objects = vm.objects_coco || {};
  const ocr = vm.ocr || {};
  const brands = vm.brands_logos || {};
  const docs = vm.documents || {};
  const scene = vm.scene || {};
  const motion = vm.motion || {};
  const previewSrc = uploadsUrl(vm.preview_filename) || originalUrl;

  return (
    <div
      style={{
        background: '#1e293b',
        borderRadius: 16,
        padding: 20,
        border: '1px solid rgba(167,139,250,0.35)',
        boxShadow: '0 0 15px rgba(167,139,250,0.08)',
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
        <div style={{ background: 'rgba(167,139,250,0.2)', padding: 6, borderRadius: 8 }}>
          <Brain style={{ width: 16, height: 16, color: '#a78bfa' }} />
        </div>
        <h2 style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
          Computer Vision & ML (AI)
        </h2>
      </div>

      {(vm.summary_az || []).map((line, i) => (
        <p key={i} style={{ margin: '0 0 4px', fontSize: 11, color: '#94a3b8', lineHeight: 1.45 }}>
          {line}
        </p>
      ))}

      {previewSrc && (
        <div style={{ margin: '14px 0' }}>
          <img
            src={previewSrc}
            alt="Vision preview"
            style={{ width: '100%', maxHeight: 280, objectFit: 'contain', borderRadius: 8, background: '#0f172a' }}
          />
        </div>
      )}

      <Section title={`İnsanlar (${people.person_count ?? 0})`} icon={Users} color="#22d3ee">
        <p style={{ margin: '0 0 8px', fontSize: 12, color: '#cbd5e1' }}>{people.summary_az}</p>
        {Object.keys(people.emotion_summary || {}).length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <span style={{ fontSize: 11, color: '#64748b' }}>Emosiyalar: </span>
            {Object.entries(people.emotion_summary).map(([k, v]) => (
              <Chip key={k} label={`${k}: ${v}`} color="#22d3ee" />
            ))}
          </div>
        )}
        {Object.keys(people.gender_summary || {}).length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <span style={{ fontSize: 11, color: '#64748b' }}>Cins: </span>
            {Object.entries(people.gender_summary).map(([k, v]) => (
              <Chip key={k} label={`${k}: ${v}`} color="#a78bfa" />
            ))}
          </div>
        )}
        {(people.persons || []).length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
            {(people.persons || []).map((p) => (
              <div
                key={p.id}
                style={{
                  background: '#0f172a',
                  padding: 10,
                  borderRadius: 8,
                  border: '1px solid #334155',
                  fontSize: 11,
                  color: '#cbd5e1',
                }}
              >
                <strong style={{ color: '#22d3ee' }}>#{p.id}</strong>
                <div>Emosiya: {(p.emotion || {}).label_az || '—'}</div>
                <div>Yaş: {(p.age || {}).range_az || (p.age || {}).label_az || '—'}</div>
                <div>Cins: {(p.gender || {}).label_az || '—'}</div>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title={`COCO obyektlər (${objects.total_objects ?? 0})`} icon={Car} color="#60a5fa">
        {Object.entries((objects.summary || {}).by_class || {}).map(([cls, cnt]) => (
          <Chip key={cls} label={`${cls} ×${cnt}`} color="#60a5fa" />
        ))}
        {!objects.total_objects && (
          <p style={{ margin: 0, fontSize: 12, color: '#64748b' }}>Obyekt tapılmadı</p>
        )}
      </Section>

      <Section title="Markalar / Loqolar" icon={Tag} color="#fbbf24">
        {(brands.brands || []).length > 0 ? (
          (brands.brands || []).map((b, i) => (
            <Chip
              key={i}
              label={`${b.brand} (${b.method}, ${Math.round((b.confidence || 0) * 100)}%)`}
              color="#fbbf24"
            />
          ))
        ) : (
          <p style={{ margin: 0, fontSize: 12, color: '#64748b' }}>{brands.summary_az || 'Tapılmadı'}</p>
        )}
      </Section>

      <Section title="OCR mətn" icon={ScanSearch} color="#34d399">
        <p style={{ margin: '0 0 6px', fontSize: 12, color: '#cbd5e1' }}>
          {ocr.word_count ?? 0} söz · {ocr.line_count ?? 0} sətir
        </p>
        {(ocr.addresses_hints || []).length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <span style={{ fontSize: 11, color: '#64748b' }}>Ünvan ipucları: </span>
            {(ocr.addresses_hints || []).slice(0, 5).map((h, i) => (
              <Chip key={i} label={h} color="#34d399" />
            ))}
          </div>
        )}
        <button
          type="button"
          onClick={() => setShowOcr(!showOcr)}
          style={{
            padding: '4px 10px',
            borderRadius: 6,
            border: '1px solid #334155',
            background: 'transparent',
            color: '#94a3b8',
            fontSize: 11,
            cursor: 'pointer',
          }}
        >
          {showOcr ? 'OCR gizlət' : 'OCR sözlərini göstər'}
        </button>
        {showOcr && (
          <div style={{ marginTop: 8, maxHeight: 160, overflowY: 'auto', fontSize: 11, color: '#94a3b8' }}>
            {(ocr.words || []).slice(0, 80).map((w, i) => (
              <span key={i} style={{ marginRight: 6 }}>{w.word}</span>
            ))}
          </div>
        )}
      </Section>

      <Section title="Sənəd növü" icon={FileText} color="#f472b6">
        <p style={{ margin: 0, fontSize: 12, color: docs.detected ? '#f472b6' : '#64748b' }}>
          {docs.summary_az}
          {docs.primary ? ` (${Math.round((docs.primary.confidence || 0) * 100)}%)` : ''}
        </p>
        {(docs.candidates || []).slice(1, 4).map((c) => (
          <Chip key={c.type} label={c.label_az} color="#64748b" />
        ))}
      </Section>

      <Section title="Məkan tanınması (Places/CLIP)" icon={MapPin} color="#10b981">
        {scene.primary ? (
          <>
            <p style={{ margin: '0 0 6px', fontSize: 13, color: '#10b981', fontWeight: 600 }}>
              {scene.primary.place_az} — {Math.round((scene.primary.confidence || 0) * 100)}%
            </p>
            {(scene.top_places || []).slice(1, 4).map((p) => (
              <Chip key={p.place_en} label={`${p.place_az} ${Math.round(p.confidence * 100)}%`} color="#64748b" />
            ))}
          </>
        ) : (
          <p style={{ margin: 0, fontSize: 12, color: '#64748b' }}>{scene.reason || scene.error || '—'}</p>
        )}
      </Section>

      {motion.applicable && (
        <Section title="Hərəkət (GIF/Video)" icon={Activity} color="#818cf8">
          <p style={{ margin: 0, fontSize: 12, color: motion.motion_detected ? '#818cf8' : '#64748b' }}>
            {motion.summary_az}
          </p>
          {motion.motion_blur_hint && (
            <p style={{ margin: '4px 0 0', fontSize: 11, color: '#fbbf24' }}>
              <Eye style={{ width: 11, height: 11, display: 'inline', verticalAlign: 'middle' }} /> Blur/hərəkət izi aşkar edildi
            </p>
          )}
        </Section>
      )}

      {vm.note && (
        <p style={{ margin: '12px 0 0', fontSize: 10, color: '#64748b', lineHeight: 1.5, borderTop: '1px solid #334155', paddingTop: 10 }}>
          {vm.note}
        </p>
      )}
    </div>
  );
}
