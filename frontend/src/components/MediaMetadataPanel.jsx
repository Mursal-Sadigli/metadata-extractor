import React from 'react';
import { Film, Music, Waves, Fingerprint, Clock, Cpu } from 'lucide-react';

function Row({ label, value }) {
  if (value == null || value === '') return null;
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, fontSize: 12, marginBottom: 4 }}>
      <span style={{ color: '#94a3b8' }}>{label}</span>
      <span style={{ color: '#e2e8f0', fontWeight: 500, textAlign: 'right', wordBreak: 'break-word' }}>{String(value)}</span>
    </div>
  );
}

export default function MediaMetadataPanel({ data }) {
  if (!data) return null;

  const isVideo = data.type === 'video';
  const container = data.video?.container || {};
  const audioTags = data.audio?.tags || data.embedded_audio_tags || {};
  const ac = data.audio_analysis || {};
  const freq = ac.frequency_profile || {};
  const fp = ac.acoustic_fingerprint || {};
  const chroma = ac.chromaprint;

  return (
    <div style={{
      background: '#1e293b',
      borderRadius: 16,
      padding: 20,
      border: '1px solid rgba(168,85,247,0.35)',
      boxShadow: '0 0 15px rgba(168,85,247,0.08)',
    }} className="cyber-panel">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, paddingBottom: 12, borderBottom: '1px solid #334155' }}>
        <div style={{ background: 'rgba(168,85,247,0.2)', padding: 6, borderRadius: 8 }}>
          {isVideo ? <Film style={{ width: 16, height: 16, color: '#c084fc' }} /> : <Music style={{ width: 16, height: 16, color: '#c084fc' }} />}
        </div>
        <h2 style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>
          Səs & Video Metadata
        </h2>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: '#a78bfa', fontWeight: 600 }}>
          {data.media_type_az || data.type}
        </span>
      </div>

      {data.summary_az && (
        <p style={{ fontSize: 12, color: '#cbd5e1', margin: '0 0 12px', lineHeight: 1.5 }}>{data.summary_az}</p>
      )}

      {data.warnings?.map((w, i) => (
        <p key={i} style={{ fontSize: 11, color: '#fbbf24', margin: '0 0 6px' }}>{w}</p>
      ))}

      {isVideo && container && !container.error && (
        <div style={card}>
          <h3 style={title}><Film style={{ width: 14, height: 14 }} /> Video konteyner</h3>
          <Row label="Müddət" value={container.duration_sec != null ? `${container.duration_sec}s` : null} />
          <Row label="Format" value={container.format_name} />
          <Row label="Video codec" value={container.video_codec} />
          <Row label="Ölçü" value={container.width && container.height ? `${container.width}×${container.height}` : null} />
          <Row label="Audio codec" value={container.audio_codec} />
          <Row label="Encoder" value={container.encoder} />
          <Row label="Cihaz" value={container.device} />
          <Row label="Yaradılma" value={container.creation_time} />
          <Row label="GPS (tags)" value={container.gps} />
        </div>
      )}

      {data.frame_preview && (
        <div style={card}>
          <h3 style={title}><Clock style={{ width: 14, height: 14 }} /> Aktiv frame</h3>
          <Row label="Frame" value={`#${data.frame_preview.index} @ ${data.frame_preview.timestamp_sec}s`} />
          <Row label="Fayl" value={data.frame_preview.filename} />
        </div>
      )}

      {Object.keys(audioTags).length > 0 && (
        <div style={card}>
          <h3 style={title}><Music style={{ width: 14, height: 14 }} /> ID3 / Audio teqlər</h3>
          {Object.entries(audioTags).map(([k, v]) => (
            <Row key={k} label={k} value={v} />
          ))}
        </div>
      )}

      {ac.status === 'ok' && (
        <>
          <div style={card}>
            <h3 style={title}><Waves style={{ width: 14, height: 14 }} /> Tezlik profili</h3>
            <Row label="Sample rate" value={ac.sample_rate_hz ? `${ac.sample_rate_hz} Hz` : null} />
            <Row label="Analiz müddəti" value={ac.duration_analyzed_sec != null ? `${ac.duration_analyzed_sec}s` : null} />
            <Row label="Dominant tezlik" value={freq.dominant_frequency_hz != null ? `${freq.dominant_frequency_hz} Hz` : null} />
            <Row label="Spektral mərkəz" value={freq.spectral_centroid_hz != null ? `${freq.spectral_centroid_hz} Hz` : null} />
            <Row label="Rolloff" value={freq.spectral_rolloff_hz != null ? `${freq.spectral_rolloff_hz} Hz` : null} />
            <Row label="Pitch class" value={freq.estimated_pitch_class} />
            {freq.band_energy_percent && (
              <div style={{ marginTop: 8 }}>
                <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 6 }}>Tezlik zolaqları (%)</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {Object.entries(freq.band_energy_percent).map(([band, pct]) => (
                    <span key={band} style={{
                      fontSize: 10, padding: '4px 8px', borderRadius: 6,
                      background: '#0f172a', border: '1px solid #334155', color: '#cbd5e1',
                    }}>
                      {band}: {pct}%
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div style={card}>
            <h3 style={title}><Fingerprint style={{ width: 14, height: 14 }} /> Akustik barmaq izi</h3>
            {fp.hash_preview && (
              <div style={{
                fontFamily: 'monospace', fontSize: 13, color: '#a78bfa', fontWeight: 700,
                padding: 10, background: '#0f172a', borderRadius: 8, border: '1px solid #334155',
                marginBottom: 8, wordBreak: 'break-all',
              }}>
                {fp.hash_preview}
              </div>
            )}
            <Row label="Alqoritm" value={fp.algorithm} />
            <Row label="Seqment" value={fp.segment_count} />
            {fp.note_az && <p style={{ fontSize: 11, color: '#64748b', margin: '8px 0 0' }}>{fp.note_az}</p>}
            {chroma && (
              <>
                <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid #334155' }}>
                  <Row label="Chromaprint" value={chroma.engine} />
                  <Row label="Müddət" value={chroma.duration_sec != null ? `${chroma.duration_sec}s` : null} />
                  <p style={{ fontSize: 10, color: '#64748b', marginTop: 6 }}>
                    <Cpu style={{ width: 11, display: 'inline', verticalAlign: 'middle' }} /> {chroma.note_az}
                  </p>
                  {chroma.fingerprint && (
                    <p style={{ fontSize: 10, color: '#475569', wordBreak: 'break-all', marginTop: 4 }}>
                      {String(chroma.fingerprint).slice(0, 120)}…
                    </p>
                  )}
                </div>
              </>
            )}
          </div>
        </>
      )}

      {ac.status === 'skipped' && (
        <p style={{ fontSize: 12, color: '#64748b', fontStyle: 'italic' }}>{ac.summary_az}</p>
      )}
    </div>
  );
}

const card = {
  background: '#0f172a',
  padding: 12,
  borderRadius: 10,
  border: '1px solid #334155',
  marginBottom: 12,
};

const title = {
  fontSize: 13,
  color: '#c084fc',
  margin: '0 0 10px',
  display: 'flex',
  alignItems: 'center',
  gap: 6,
};
