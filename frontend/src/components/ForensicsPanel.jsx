import React, { useState } from 'react';
import {
  ShieldAlert, Image as ImageIcon, ScanLine, Lock, HardDrive, Cpu,
  Sun, Ruler, Cloud, Clock, Users, Fingerprint, AlertTriangle, Brain,
} from 'lucide-react';
import ProgramTracesPanel from './ProgramTracesPanel';

import { UPLOADS_BASE } from '../apiClient';

function uploadsUrl(filename) {
  if (!filename) return null;
  const base = String(filename).replace(/\\/g, '/').split('/').pop();
  return `${UPLOADS_BASE}/${base}`;
}

function ArtifactImage({ filename, label, onZoom }) {
  const src = uploadsUrl(filename);
  if (!src) return null;
  return (
    <div style={{ flex: 1, minWidth: 140 }}>
      <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6, textAlign: 'center' }}>{label}</div>
      <div
        style={{ background: '#0f172a', padding: 8, borderRadius: 10, border: '1px solid #334155', cursor: 'pointer' }}
        onClick={() => onZoom(src, label)}
      >
        <img src={src} alt={label} style={{ width: '100%', height: 160, objectFit: 'contain', borderRadius: 4 }} />
      </div>
    </div>
  );
}

function InfoBlock({ title, icon: Icon, color, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <h3 style={{ fontSize: 13, color: '#94a3b8', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon style={{ width: 14, height: 14, color }} />
        {title}
      </h3>
      <div style={{ background: '#0f172a', padding: 12, borderRadius: 10, border: '1px solid #334155', fontSize: 12, color: '#cbd5e1' }}>
        {children}
      </div>
    </div>
  );
}

function Chip({ label, color = '#64748b' }) {
  return (
    <span style={{
      display: 'inline-block', padding: '3px 8px', borderRadius: 6, margin: '2px 4px 2px 0',
      background: '#1e293b', border: `1px solid ${color}44`, fontSize: 11, color,
    }}>
      {label}
    </span>
  );
}

export default function ForensicsPanel({ data, originalUrl }) {
  const [lightbox, setLightbox] = useState(null);
  const [showJson, setShowJson] = useState(false);
  if (!data) return null;

  const originalFilename = data.original_filename;
  const originalSrc = originalUrl || uploadsUrl(originalFilename);
  const ela = data.ela;
  const enhanced = data.enhanced_reflection;
  const summary = data.summary;
  const sci = data.scientific || {};
  const unified = data.unified_report || {};
  const auth = sci.authenticity || {};
  const manip = sci.manipulation || {};
  const inferred = unified.inferred || {};

  const riskColor = { low: '#10b981', medium: '#fbbf24', high: '#ef4444' };
  const risk = summary?.manipulation_risk || ela?.risk_level || 'low';
  const aiProb = auth.is_ai_generated_probability ?? summary?.ai_probability;

  return (
    <div style={{
      background: '#1e293b', borderRadius: '16px', padding: '20px',
      border: '1px solid rgba(234,179,8,0.3)',
      boxShadow: '0 0 15px rgba(234,179,8,0.08)'
    }} className="cyber-panel">
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px', paddingBottom: '12px', borderBottom: '1px solid #334155', flexWrap: 'wrap' }}>
        <div style={{ background: 'rgba(234,179,8,0.2)', padding: '6px', borderRadius: '8px' }}>
          <ShieldAlert style={{ width: '16px', height: '16px', color: '#eab308' }} />
        </div>
        <h2 style={{ fontSize: '15px', fontWeight: '700', color: '#f1f5f9', margin: 0 }}>
          Kriminalistika & Elmi Analiz
        </h2>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', flexWrap: 'wrap', fontSize: 11, fontWeight: 700 }}>
          {aiProb != null && (
            <span style={{ color: aiProb > 0.55 ? '#fbbf24' : '#10b981' }}>
              AI: {Math.round(aiProb * 100)}%
            </span>
          )}
          <span style={{ color: riskColor[risk] || '#94a3b8' }}>ELA: {risk.toUpperCase()}</span>
          {manip.is_manipulated && <span style={{ color: '#ef4444' }}>MANİPULYASİYA</span>}
        </div>
      </div>

      {lightbox && (
        <div
          onClick={() => setLightbox(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}
        >
          <img src={lightbox.src} alt={lightbox.label} style={{ maxWidth: '95%', maxHeight: '90%', objectFit: 'contain' }} />
        </div>
      )}

      {(inferred.estimated_season_az || inferred.estimated_time_of_day_az) && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 14, fontSize: 11 }}>
          {inferred.estimated_season_az && <Chip label={`Mövsüm: ${inferred.estimated_season_az}`} color="#34d399" />}
          {inferred.estimated_time_of_day_az && <Chip label={`Vaxt: ${inferred.estimated_time_of_day_az}`} color="#60a5fa" />}
          {inferred.sky_weather_az && <Chip label={inferred.sky_weather_az} color="#94a3b8" />}
          {inferred.estimated_year_range && <Chip label={`İl: ${inferred.estimated_year_range}`} color="#a78bfa" />}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>

        {auth.verdict_az && (
          <InfoBlock title="Real foto vs AI / Deepfake" icon={Brain} color="#a78bfa">
            <p style={{ margin: '0 0 8px', fontWeight: 600, color: aiProb > 0.55 ? '#fbbf24' : '#10b981' }}>{auth.verdict_az}</p>
            <p style={{ margin: '0 0 6px' }}>AI ehtimalı: {Math.round((auth.is_ai_generated_probability || 0) * 100)}% · Real: {Math.round((auth.is_real_photo_probability || 0) * 100)}%</p>
            {(auth.signals || []).map((s, i) => (
              <p key={i} style={{ margin: '3px 0', fontSize: 11, color: '#94a3b8' }}>{s}</p>
            ))}
          </InfoBlock>
        )}

        {manip.summary_az && (
          <InfoBlock title="Manipulyasiya (copy-move, splicing, retouch)" icon={AlertTriangle} color="#ef4444">
            <p style={{ margin: '0 0 8px' }}>{manip.summary_az}</p>
            <p style={{ margin: '0 0 6px' }}>Kompozit skor: {manip.composite_score}/100</p>
            {(manip.types_detected || []).map((t) => (
              <Chip key={t} label={t} color="#ef4444" />
            ))}
            {manip.copy_move?.summary_az && (
              <p style={{ margin: '8px 0 0', fontSize: 11, color: '#94a3b8' }}>{manip.copy_move.summary_az}</p>
            )}
          </InfoBlock>
        )}

        {(originalSrc || ela || enhanced) && (
          <div>
            <h3 style={{ fontSize: '13px', color: '#94a3b8', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ScanLine style={{ width: '14px', height: '14px' }} /> Vizual müqayisə (ELA)
            </h3>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {originalSrc && (
                <div style={{ flex: 1, minWidth: 140 }}>
                  <div style={{ fontSize: 10, color: '#64748b', marginBottom: 6, textAlign: 'center' }}>Orijinal</div>
                  <div
                    style={{ background: '#0f172a', padding: 8, borderRadius: 10, border: '1px solid #334155', cursor: 'pointer' }}
                    onClick={() => setLightbox({ src: originalSrc, label: 'Orijinal' })}
                  >
                    <img src={originalSrc} alt="Orijinal" style={{ width: '100%', height: 160, objectFit: 'contain', borderRadius: 4 }} />
                  </div>
                </div>
              )}
              {ela?.filename && (
                <ArtifactImage filename={ela.filename} label="ELA" onZoom={(s, l) => setLightbox({ src: s, label: l })} />
              )}
              {enhanced?.filename && (
                <ArtifactImage filename={enhanced.filename} label="Enhanced" onZoom={(s, l) => setLightbox({ src: s, label: l })} />
              )}
            </div>
            {ela && (
              <div style={{ marginTop: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
                  <span>Manipulyasiya skoru</span>
                  <span>{ela.manipulation_score ?? 0}/100</span>
                </div>
                <div style={{ height: 8, background: '#0f172a', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ width: `${Math.min(100, ela.manipulation_score || 0)}%`, height: '100%', background: riskColor[risk] || '#eab308' }} />
                </div>
              </div>
            )}
          </div>
        )}

        {sci.lighting && (
          <InfoBlock title="Işıq mənbəyi" icon={Sun} color="#fbbf24">
            <p style={{ margin: 0 }}>{sci.lighting.summary_az}</p>
          </InfoBlock>
        )}

        {sci.distance && (
          <InfoBlock title="Kamera–obyekt məsafəsi" icon={Ruler} color="#60a5fa">
            <p style={{ margin: 0 }}>{sci.distance.summary_az}</p>
          </InfoBlock>
        )}

        {sci.shadows && (
          <InfoBlock title="Kölgə analizi" icon={Sun} color="#64748b">
            <p style={{ margin: 0, color: sci.shadows.forgery_hint ? '#fbbf24' : '#cbd5e1' }}>{sci.shadows.summary_az}</p>
          </InfoBlock>
        )}

        {sci.noise_analysis && (
          <InfoBlock title="Səs-küy / sensor (PRNU)" icon={Fingerprint} color="#818cf8">
            <p style={{ margin: '0 0 4px' }}>{sci.noise_analysis.summary_az}</p>
            <p style={{ margin: 0, fontSize: 11, color: '#64748b' }}>{sci.noise_analysis.sensor_hint}</p>
          </InfoBlock>
        )}

        {sci.lens_analysis && (
          <InfoBlock title="Lens (distorsiya, xromatik aberatsiya)" icon={ScanLine} color="#94a3b8">
            <p style={{ margin: 0 }}>{sci.lens_analysis.summary_az}</p>
          </InfoBlock>
        )}

        {sci.contextual_inference && (
          <InfoBlock title="Kontekstual çıxarım" icon={Cloud} color="#34d399">
            <p style={{ margin: 0 }}>{sci.contextual_inference.summary_az}</p>
            {sci.contextual_inference.place_type && (
              <p style={{ margin: '6px 0 0', fontSize: 11, color: '#64748b' }}>Məkan: {sci.contextual_inference.place_type}</p>
            )}
          </InfoBlock>
        )}

        {sci.temporal_inference && (
          <InfoBlock title="Tarixi çıxarım" icon={Clock} color="#a78bfa">
            <p style={{ margin: 0 }}>{sci.temporal_inference.summary_az}</p>
            {(sci.temporal_inference.car_model_year_hints || []).map((c, i) => (
              <Chip key={i} label={`${c.class}: ${c.year_range}`} />
            ))}
          </InfoBlock>
        )}

        {sci.social_inference && (
          <InfoBlock title="Sosial çıxarım" icon={Users} color="#22d3ee">
            <p style={{ margin: 0 }}>{sci.social_inference.summary_az}</p>
            <p style={{ margin: '6px 0 0', fontSize: 11, color: '#64748b' }}>
              {sci.social_inference.face_database_match?.note}
            </p>
          </InfoBlock>
        )}

        {sci.security && (
          <InfoBlock title="Rəqəmsal imza & bütövlük" icon={Lock} color="#10b981">
            <p style={{ margin: '0 0 4px', fontSize: 11, wordBreak: 'break-all' }}>SHA-256: {sci.security.sha256}</p>
            <p style={{ margin: 0, fontSize: 11, color: '#64748b' }}>{sci.security.reencoding_artifacts}</p>
          </InfoBlock>
        )}

        {data.software_traces && (
          <div style={{ background: '#0f172a', padding: 12, borderRadius: 10, border: '1px solid #334155' }}>
            <ProgramTracesPanel data={data} />
          </div>
        )}

        {data.carved_metadata && data.carved_metadata.status !== 'error' && (
          <InfoBlock title="Silinmiş metadata bərpası" icon={HardDrive} color="#a78bfa">
            <p style={{ margin: 0 }}>{data.carved_metadata.summary}</p>
            <p style={{ margin: '6px 0 0' }}>Skor: {data.carved_metadata.recovery_score ?? 0}/100</p>
          </InfoBlock>
        )}

        {data.steganography && !data.steganography.error && (
          <InfoBlock title="Steganografiya & gizli məlumat" icon={Lock} color="#fbbf24">
            <p style={{ margin: '0 0 6px' }}>Skor: {data.steganography.stego_score}/100</p>
            {(data.steganography.findings || []).map((f, i) => (
              <p key={i} style={{ margin: '3px 0', fontSize: 11, color: '#94a3b8' }}>{f}</p>
            ))}
            {data.steganography.hidden_message_preview && (
              <p style={{ margin: '8px 0 0', color: '#fbbf24' }}>Gizli mətn: {data.steganography.hidden_message_preview}</p>
            )}
            {sci.hidden?.jpeg_thumbnail?.found && (
              <p style={{ margin: '8px 0 0', fontSize: 11 }}>JPEG thumbnail: {sci.hidden.jpeg_thumbnail.filename}</p>
            )}
          </InfoBlock>
        )}

        {data.c2pa && (
          <InfoBlock title="C2PA / Content Credentials" icon={Cpu} color="#64748b">
            {data.c2pa.status === 'not_found' ? (
              <p style={{ margin: 0, color: '#64748b' }}>C2PA manifest tapılmadı.</p>
            ) : (
              <>
                <p style={{ margin: '0 0 4px' }}>Present: {data.c2pa.c2pa_present ? 'Bəli' : 'Xeyr'}</p>
                <p style={{ margin: '0 0 4px' }}>AI generated: {data.c2pa.is_ai_generated ? 'Ehtimal var' : 'Xeyr'}</p>
                <p style={{ margin: 0 }}>Validation: {data.c2pa.validation_status}</p>
              </>
            )}
          </InfoBlock>
        )}

        {data.caption && (
          <InfoBlock title="BLIP təsviri" icon={ImageIcon} color="#94a3b8">
            <p style={{ margin: 0, fontStyle: 'italic' }}>"{data.caption}"</p>
          </InfoBlock>
        )}

        {unified.image_metadata && (
          <div style={{ marginTop: 8 }}>
            <button
              type="button"
              onClick={() => setShowJson(!showJson)}
              style={{
                padding: '6px 12px', borderRadius: 8, border: '1px solid #334155',
                background: 'transparent', color: '#94a3b8', fontSize: 11, cursor: 'pointer',
              }}
            >
              {showJson ? 'Vahid JSON gizlət' : 'Vahid forensic JSON göstər'}
            </button>
            {showJson && (
              <pre style={{
                marginTop: 10, padding: 12, background: '#0f172a', borderRadius: 8,
                border: '1px solid #334155', fontSize: 10, color: '#94a3b8',
                maxHeight: 360, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              }}>
                {JSON.stringify(unified, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
