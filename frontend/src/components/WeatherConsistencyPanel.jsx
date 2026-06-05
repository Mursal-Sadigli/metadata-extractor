import React from 'react';
import { CloudRain, Sun, Wind, Droplets, CheckCircle2, AlertTriangle, XCircle, Eye } from 'lucide-react';

const VERDICT_STYLE = {
  consistent: { color: '#10b981', icon: CheckCircle2, label: 'Uyğun' },
  partial: { color: '#fbbf24', icon: AlertTriangle, label: 'Qismən uyğun' },
  inconsistent: { color: '#f87171', icon: XCircle, label: 'Uyğunsuz' },
  insufficient_data: { color: '#64748b', icon: AlertTriangle, label: 'Natamam məlumat' },
};

export default function WeatherConsistencyPanel({ data }) {
  const rw = data?.reverse_weather || data;
  if (!rw || rw.status === 'no_coordinates') return null;

  if (rw.error && rw.status === 'error') {
    return (
      <div style={{ marginTop: 15, paddingTop: 15, borderTop: '1px solid #334155' }}>
        <h3 style={{ fontSize: 13, color: '#f87171', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
          <CloudRain style={{ width: 14, height: 14 }} />
          Reverse Weather Forecast
        </h3>
        <p style={{ fontSize: 12, color: '#ef4444' }}>{rw.error}</p>
      </div>
    );
  }

  const hist = rw.historical || {};
  const at = hist.at_capture || {};
  const daily = hist.daily_summary || {};
  const vis = rw.visual_analysis || {};
  const con = rw.consistency || {};
  const verdict = VERDICT_STYLE[con.verdict] || VERDICT_STYLE.insufficient_data;
  const VerdictIcon = verdict.icon;

  return (
    <div style={{ marginTop: 15, paddingTop: 15, borderTop: '1px solid #334155' }}>
      <h3 style={{ fontSize: 13, color: '#60a5fa', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
        <CloudRain style={{ width: 14, height: 14 }} />
        Reverse Weather Forecast — Hava & Vizual Uyğunlaşdırma
      </h3>

      {con.score != null && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginBottom: 12,
          padding: '10px 12px',
          background: 'rgba(96,165,250,0.08)',
          borderRadius: 10,
          border: `1px solid ${verdict.color}44`,
        }}>
          <VerdictIcon style={{ width: 20, height: 20, color: verdict.color, flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: verdict.color }}>
              {con.score}/100 — {con.verdict_az || verdict.label}
            </div>
            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{con.summary_az}</div>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10, marginBottom: 12 }}>
        <div style={cardStyle}>
          <div style={cardTitle}><CloudRain style={{ width: 12, height: 12 }} /> Tarixi hava (Open-Meteo)</div>
          {hist.date && <Row label="Tarix" value={hist.date} />}
          {hist.capture_hour && <Row label="Çəkiliş saatı" value={hist.capture_hour} />}
          {rw.capture_datetime && <Row label="EXIF vaxt" value={String(rw.capture_datetime).slice(0, 19)} />}
          {at.description_az && <Row label="Həmin saat" value={at.description_az} strong />}
          {at.temperature_c != null && <Row label="Temperatur" value={`${at.temperature_c}°C`} />}
          {at.precipitation_mm != null && <Row label="Yağıntı (saat)" value={`${at.precipitation_mm} mm`} />}
          {at.wind_speed_kmh != null && (
            <Row label="Külək" value={`${at.wind_speed_kmh} km/saat`} icon={Wind} highlight={at.is_windy} />
          )}
          {at.cloud_cover_pct != null && <Row label="Bulud" value={`${at.cloud_cover_pct}%`} />}
          {daily.max_temp_c != null && (
            <Row label="Gün (min/max)" value={`${daily.min_temp_c}° / ${daily.max_temp_c}°C`} />
          )}
          {daily.precipitation_mm != null && <Row label="Gün yağıntısı" value={`${daily.precipitation_mm} mm`} />}
          <p style={{ margin: '8px 0 0', fontSize: 10, color: '#64748b' }}>{hist.source}</p>
        </div>

        <div style={cardStyle}>
          <div style={cardTitle}><Eye style={{ width: 12, height: 12 }} /> Şəkil vizual analizi</div>
          {vis.status === 'skipped' ? (
            <p style={{ fontSize: 11, color: '#64748b', margin: 0 }}>{vis.error || 'Vizual analiz edilmədi'}</p>
          ) : (
            <>
              {vis.inferred_weather_az && <Row label="Təxmini hava" value={vis.inferred_weather_az} strong />}
              {vis.sky_summary_az && <Row label="Səma" value={vis.sky_summary_az} icon={Sun} />}
              {vis.ground_summary_az && <Row label="Zəmin" value={vis.ground_summary_az} icon={Droplets} />}
              {vis.ground_wetness_score != null && (
                <Row label="İslaklıq skoru" value={`${vis.ground_wetness_score}/100`} highlight={vis.ground_wetness_score >= 55} />
              )}
              {vis.snow_likelihood != null && vis.snow_likelihood >= 40 && (
                <Row label="Qar ehtimalı" value={`${vis.snow_likelihood}%`} />
              )}
              {vis.motion_blur_hint && (
                <Row label="Hərəkət bulanıqlığı" value="Mümkün (külək/foto)" icon={Wind} />
              )}
            </>
          )}
        </div>
      </div>

      {con.findings?.length > 0 && (
        <div style={{ ...cardStyle, marginBottom: 0 }}>
          <div style={cardTitle}>Uyğunlaşma tapıntıları</div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: '#cbd5e1', lineHeight: 1.55 }}>
            {con.findings.map((f, i) => (
              <li key={i} style={{ marginBottom: 4 }}>{f}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Row({ label, value, strong, highlight, icon: Icon }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, marginBottom: 4 }}>
      <span style={{ color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 4 }}>
        {Icon && <Icon style={{ width: 11, height: 11 }} />}
        {label}
      </span>
      <span style={{
        color: highlight ? '#fbbf24' : strong ? '#e2e8f0' : '#cbd5e1',
        fontWeight: strong ? 600 : 400,
        textAlign: 'right',
      }}>
        {value}
      </span>
    </div>
  );
}

const cardStyle = {
  background: '#0f172a',
  padding: 12,
  borderRadius: 10,
  border: '1px solid #334155',
};

const cardTitle = {
  fontSize: 11,
  color: '#94a3b8',
  fontWeight: 700,
  marginBottom: 8,
  display: 'flex',
  alignItems: 'center',
  gap: 6,
};
