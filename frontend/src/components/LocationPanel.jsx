import React, { useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, CircleMarker } from 'react-leaflet';
import { MapPin, Copy, ExternalLink, Search, Loader2, HardDrive } from 'lucide-react';
import { api } from '../apiClient';
import L from 'leaflet';
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
import TimelineMappingPanel from './TimelineMappingPanel';
import WeatherConsistencyPanel from './WeatherConsistencyPanel';

const DefaultIcon = L.icon({ iconUrl: icon, shadowUrl: iconShadow, iconAnchor: [12, 41] });
L.Marker.prototype.options.icon = DefaultIcon;

const SOURCE_LABELS = {
  thumbnail_exif: 'Thumbnail EXIF',
  xmp_metadata: 'XMP',
  binary_scan: 'Binary skan',
  ocr_coordinates: 'OCR koordinat',
  nominatim_geocode: 'Nominatim',
  nominatim_structured: 'Struktur ünvan',
  carved_metadata: 'Carved GPS',
  file_carving_ml: 'File Carving 4.0',
  known_place: 'Gazetteer',
  gazetteer_entity: 'Entity',
  text_decimal: 'Decimal',
  text_dms_pair: 'DMS',
  text_nmea: 'NMEA GPS',
  text_ddm: 'DDM',
  text_map_url: 'Xəritə URL',
  text_suffix_ne: 'N/E koordinat',
  web_meta_geo: 'Veb səhifə geo',
  web_json_ld: 'JSON-LD',
  web_url_map: 'URL xəritə',
  web_url_query: 'URL koordinat',
  web_gazetteer: 'Veb yer adı',
  web_nominatim_page: 'Məqalə geocode',
  web_page_html: 'Səhifə HTML',
};

const ENTITY_COLORS = {
  place: '#34d399',
  country: '#60a5fa',
  address: '#f472b6',
  landmark: '#fbbf24',
};

function copyText(str) {
  if (!str) return;
  navigator.clipboard?.writeText(str);
}

function coordKey(c) {
  return `${c?.latitude}-${c?.longitude}-${c?.source}`;
}

export default function LocationPanel({ data, currentFilename, currentOriginalName }) {
  const [geoText, setGeoText] = useState('');
  const [geoLoading, setGeoLoading] = useState(false);
  const [textGeoResult, setTextGeoResult] = useState(null);

  const inf = data?.location_inference;
  const loc = data?.location;
  const carving = data?.file_carving_ml;
  const carvedLegacy = data?.carved_metadata;

  const mapCenter = loc?.latitude != null
    ? [loc.latitude, loc.longitude]
    : inf?.candidates?.[0]?.latitude != null
      ? [inf.candidates[0].latitude, inf.candidates[0].longitude]
      : null;

  const runTextGeocode = async () => {
    if (!geoText.trim()) return;
    setGeoLoading(true);
    try {
      const res = await api.post('/api/geocode-text', { text: geoText });
      setTextGeoResult(res.data);
    } catch (e) {
      setTextGeoResult({ error: e.response?.data?.error || e.message });
    } finally {
      setGeoLoading(false);
    }
  };

  const displayInf = textGeoResult?.candidates ? textGeoResult : inf;
  const displayLoc = textGeoResult?.best_guess && !loc?.latitude
    ? { ...textGeoResult.best_guess, inferred: true }
    : loc;

  const mapZoom = displayLoc?.inferred
    ? (displayLoc?.location_quality >= 0.55 ? 14 : 11)
    : 16;

  const candidates = displayInf?.candidates || [];
  const extracted = displayInf?.extracted_coordinates || [];
  const queries = displayInf?.place_queries || [];
  const mapLinks = displayInf?.map_links || [];
  const methods = displayInf?.methods_used || [];
  const geoParse = displayInf?.geoparsing || {};
  const entities = displayInf?.geographic_entities || [];
  return (
    <div style={{ marginTop: 0 }}>
      <TimelineMappingPanel
        currentFilename={currentFilename}
        currentOriginalName={currentOriginalName}
      />
      {data?.warnings?.map((msg, i) => (
        <p key={i} style={{ color: '#fbbf24', fontSize: '12px', margin: '0 0 12px', lineHeight: 1.5 }}>{msg}</p>
      ))}
      {displayInf?.limitations && (
        <p style={{ color: '#94a3b8', fontSize: '12px', margin: '0 0 12px', lineHeight: 1.6 }}>
          {displayInf.limitations}
        </p>
      )}

      {carving && carving.status !== 'error' && (
        <div style={{
          background: 'rgba(139,92,246,0.1)',
          padding: 14,
          borderRadius: 12,
          border: '1px solid rgba(167,139,250,0.35)',
          marginBottom: 14,
        }}>
          <h3 style={{ fontSize: 14, color: '#c4b5fd', margin: '0 0 10px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <HardDrive style={{ width: 16, height: 16 }} />
            File Carving 4.0 (CNN + LSTM)
          </h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, fontSize: 12, color: '#cbd5e1', marginBottom: 8 }}>
            <span>Bərpa skoru: <strong style={{ color: '#a78bfa' }}>{carving.recovery_score ?? 0}/100</strong></span>
            <span>Seqment: <strong>{carving.segments?.length ?? 0}</strong></span>
            <span>Silinmiş iz: <strong style={{ color: carving.deleted_segments_found > 0 ? '#fbbf24' : '#64748b' }}>
              {carving.deleted_segments_found ?? 0}
            </strong></span>
            <span>Pəncərə: <strong>{carving.windows_analyzed ?? 0}</strong></span>
          </div>
          <p style={{ margin: '0 0 8px', color: '#94a3b8', fontSize: 12, lineHeight: 1.5 }}>{carving.summary}</p>
          {carving.model && (
            <p style={{ margin: '0 0 10px', fontSize: 11, color: '#64748b' }}>
              {carving.model.architecture} · window {carving.model.window_size}/{carving.model.window_stride}
            </p>
          )}
          {carving.recovered_gps?.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>Bərpa olunmuş GPS</div>
              {carving.recovered_gps.map((g, i) => (
                <div key={i} style={{ fontSize: 12, color: '#10b981', marginBottom: 2 }}>
                  {g.latitude?.toFixed?.(5) ?? g.latitude}, {g.longitude?.toFixed?.(5) ?? g.longitude}
                  {g.source && <span style={{ color: '#64748b', marginLeft: 6 }}>({g.source})</span>}
                </div>
              ))}
            </div>
          )}
          {carving.segments?.length > 0 && (
            <div style={{ maxHeight: 160, overflowY: 'auto', fontSize: 11 }}>
              {carving.segments.slice(0, 8).map((s) => (
                <div key={s.segment_id} style={{
                  padding: '6px 8px', marginBottom: 4, background: '#0f172a',
                  borderRadius: 6, border: '1px solid #334155', color: '#94a3b8',
                }}>
                  <span style={{ color: '#e2e8f0', fontWeight: 600 }}>#{s.segment_id}</span>
                  {' '}{s.start_hex}–{s.end_hex} · {s.predicted_type}
                  {' '}({Math.round((s.boundary_confidence || 0) * 100)}%)
                  {s.metadata_recovery?.gps_count > 0 && (
                    <span style={{ color: '#10b981', marginLeft: 6 }}>GPS+{s.metadata_recovery.gps_count}</span>
                  )}
                </div>
              ))}
            </div>
          )}
          {carving.note && (
            <p style={{ margin: '10px 0 0', fontSize: 11, color: '#64748b' }}>{carving.note}</p>
          )}
        </div>
      )}

      {carvedLegacy && carvedLegacy.status !== 'error' && !carving && (
        <div style={{ background: '#0f172a', padding: 12, borderRadius: 10, border: '1px solid #334155', marginBottom: 12, fontSize: 12 }}>
          <strong style={{ color: '#a78bfa' }}>Klassik carved metadata</strong>
          <p style={{ margin: '6px 0 0', color: '#94a3b8' }}>{carvedLegacy.summary}</p>
        </div>
      )}

      <div style={{ background: '#0f172a', padding: '12px', borderRadius: '10px', border: '1px solid #334155', marginBottom: '12px' }}>
        <h3 style={{ fontSize: '13px', color: '#f87171', margin: '0 0 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Search style={{ width: 14, height: 14 }} /> Mətn / ünvan / koordinat analizi
        </h3>
        <textarea
          value={geoText}
          onChange={(e) => setGeoText(e.target.value)}
          placeholder="Ünvan, NMEA, DMS, Plus Code, Google Maps linki, şəhər adı..."
          rows={3}
          style={{
            width: '100%', boxSizing: 'border-box', background: '#020617', color: '#e2e8f0',
            border: '1px solid #475569', borderRadius: 8, padding: 10, fontSize: 12, resize: 'vertical',
          }}
        />
        <button
          type="button"
          onClick={runTextGeocode}
          disabled={geoLoading || !geoText.trim()}
          style={{
            marginTop: 8, padding: '8px 14px', borderRadius: 8, border: 'none',
            background: '#dc2626', color: '#fff', fontSize: 12, fontWeight: 600,
            cursor: geoLoading ? 'wait' : 'pointer', display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          {geoLoading ? <Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} /> : <MapPin style={{ width: 14, height: 14 }} />}
          Koordinat çıxar
        </button>
        {textGeoResult?.error && (
          <p style={{ color: '#f87171', fontSize: 12, marginTop: 8 }}>{textGeoResult.error}</p>
        )}
      </div>

      {(geoParse.entity_count > 0 || geoParse.country_bias) && (
        <div style={{ background: 'rgba(239,68,68,0.08)', padding: 10, borderRadius: 8, border: '1px solid #7f1d1d', marginBottom: 12, fontSize: 11 }}>
          <strong style={{ color: '#fca5a5' }}>Super geoparsing</strong>
          <span style={{ color: '#94a3b8', marginLeft: 8 }}>
            {geoParse.entity_count || 0} entity · {geoParse.strategy_count || 0} strategiya
            {geoParse.country_bias ? ` · bias: ${geoParse.country_bias.toUpperCase()}` : ''}
          </span>
          {displayLoc?.geoparse_summary && (
            <div style={{ color: '#64748b', marginTop: 4 }}>{displayLoc.geoparse_summary}</div>
          )}
        </div>
      )}

      {entities.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <h3 style={{ fontSize: 13, color: '#f87171', marginBottom: 8 }}>Geoparsed entity-lər ({entities.length})</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {entities.slice(0, 12).map((e, i) => (
              <span
                key={i}
                style={{
                  fontSize: 10, padding: '5px 10px', borderRadius: 6,
                  background: '#0f172a', border: `1px solid ${ENTITY_COLORS[e.entity_type] || '#475569'}`,
                  color: ENTITY_COLORS[e.entity_type] || '#cbd5e1',
                }}
              >
                {e.entity_type}: {e.value?.slice(0, 40)}
              </span>
            ))}
          </div>
        </div>
      )}

      {methods.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
          {methods.map((m) => (
            <span key={m} style={{ fontSize: 10, padding: '4px 8px', borderRadius: 6, background: 'rgba(239,68,68,0.15)', color: '#fca5a5', border: '1px solid #7f1d1d' }}>
              {SOURCE_LABELS[m] || m}
            </span>
          ))}
        </div>
      )}

      {!displayLoc?.latitude && !candidates.length && (
        <p style={{ color: '#64748b', fontSize: '13px', margin: '0 0 12px', lineHeight: 1.6 }}>
          Birbaşa GPS tapılmadı. Şəkildə ünvan/cədvəl, thumbnail EXIF, binary skan və ya yuxarıdakı mətn analizi istifadə edin.
        </p>
      )}

      {mapCenter && (
        <div style={{ height: '320px', borderRadius: '12px', overflow: 'hidden', border: '2px solid #334155', marginBottom: 12 }}>
          <MapContainer
            center={mapCenter}
            zoom={mapZoom}
            style={{ height: '100%', width: '100%' }}
          >
            <TileLayer
              attribution="&copy; OpenStreetMap"
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              opacity={0.45}
            />
            {displayLoc?.latitude != null && (
              <Marker position={[displayLoc.latitude, displayLoc.longitude]}>
                <Popup>{displayLoc.inferred ? 'Təxmini yer' : 'Əsas GPS'} 📍</Popup>
              </Marker>
            )}
            {candidates
              .filter((c) => c.latitude != null && c.longitude != null)
              .slice(0, 8)
              .map((c, i) => (
                <CircleMarker
                  key={coordKey(c) + i}
                  center={[c.latitude, c.longitude]}
                  radius={i === 0 && !displayLoc?.latitude ? 10 : 7}
                  pathOptions={{
                    color: i === 0 ? '#f87171' : '#60a5fa',
                    fillColor: i === 0 ? '#ef4444' : '#3b82f6',
                    fillOpacity: 0.45,
                  }}
                >
                  <Popup>
                    {c.label}<br />
                    {c.latitude?.toFixed(5)}, {c.longitude?.toFixed(5)}
                  </Popup>
                </CircleMarker>
              ))}
          </MapContainer>
        </div>
      )}

      {displayLoc?.latitude != null && (
        <div style={{ background: '#0f172a', padding: 12, borderRadius: 10, border: '1px solid #334155', marginBottom: 12, fontSize: 12 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
            <strong style={{ color: '#e2e8f0' }}>{displayLoc.display || `${displayLoc.latitude}, ${displayLoc.longitude}`}</strong>
            {displayLoc.inferred && (
              <span style={{ fontSize: 10, color: '#fbbf24', fontWeight: 700 }}>
                TƏXMİNİ ({displayLoc.source || 'inference'}{' '}
                {Math.round((displayLoc.location_quality || displayLoc.fusion_score || displayLoc.confidence || 0) * 100)}%)
              </span>
            )}
            {displayLoc.lat_lon_swapped && (
              <span style={{ fontSize: 10, color: '#60a5fa', fontWeight: 600 }}>GPS düzəldildi</span>
            )}
            {displayLoc.source === 'exif' && !displayLoc.inferred && (
              <span style={{ fontSize: 10, color: '#34d399', fontWeight: 600 }}>EXIF GPS</span>
            )}
            <button type="button" onClick={() => copyText(`${displayLoc.latitude}, ${displayLoc.longitude}`)} style={iconBtnStyle} title="Kopyala">
              <Copy style={{ width: 12, height: 12 }} />
            </button>
            {displayLoc.map_url && (
              <a href={displayLoc.map_url} target="_blank" rel="noreferrer" style={linkStyle}>Google Maps</a>
            )}
            {displayLoc.osm_url && (
              <a href={displayLoc.osm_url} target="_blank" rel="noreferrer" style={linkStyle}>OpenStreetMap</a>
            )}
          </div>
          {displayLoc.dms && (
            <div style={{ color: '#94a3b8', marginTop: 6 }}>
              DMS: {displayLoc.dms.latitude_dms}, {displayLoc.dms.longitude_dms}
            </div>
          )}
          {displayLoc.display_name && (
            <div style={{ color: '#cbd5e1', marginTop: 6 }}>{displayLoc.display_name}</div>
          )}
          {displayLoc.address && (
            <div style={{ color: '#94a3b8', marginTop: 4 }}>
              {displayLoc.address.city} • {displayLoc.address.country_code}
            </div>
          )}
        </div>
      )}

      {extracted.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <h3 style={{ fontSize: '13px', color: '#f87171', marginBottom: 8 }}>Çıxarılmış koordinatlar ({extracted.length})</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {extracted.slice(0, 12).map((ec, i) => (
              <div key={i} style={rowStyle}>
                <span style={{ color: '#94a3b8' }}>{ec.format}</span>
                {ec.latitude != null ? (
                  <span style={{ color: '#e2e8f0' }}>
                    {ec.latitude?.toFixed(5)}, {ec.longitude?.toFixed(5)}
                  </span>
                ) : (
                  <span style={{ color: '#64748b' }}>{ec.raw || ec.note}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {queries.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <h3 style={{ fontSize: '13px', color: '#94a3b8', marginBottom: 8 }}>Ünvan / yer sorğuları</h3>
          {queries.slice(0, 10).map((q, i) => (
            <div key={i} style={{ ...rowStyle, marginBottom: 4 }}>
              <span style={{ color: '#64748b', fontSize: 10 }}>{q.type}</span>
              <span style={{ color: '#cbd5e1', wordBreak: 'break-word' }}>{q.query}</span>
            </div>
          ))}
        </div>
      )}

      {mapLinks.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <h3 style={{ fontSize: '13px', color: '#94a3b8', marginBottom: 8 }}>Xəritə linkləri</h3>
          {mapLinks.map((url, i) => (
            <a key={i} href={url} target="_blank" rel="noreferrer" style={{ ...linkStyle, display: 'block', marginBottom: 4, wordBreak: 'break-all' }}>
              <ExternalLink style={{ width: 12, height: 12, display: 'inline', verticalAlign: 'middle' }} /> {url.slice(0, 80)}…
            </a>
          ))}
        </div>
      )}

      {candidates.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <h3 style={{ fontSize: '13px', color: '#f87171', marginBottom: 8 }}>Lokasiya variantları ({candidates.length})</h3>
          {candidates.slice(0, 10).map((c, i) => (
            <div key={coordKey(c) + i} style={{ ...rowStyle, flexDirection: 'column', alignItems: 'flex-start', padding: 10, marginBottom: 6 }}>
              <div style={{ fontWeight: 600, color: '#e2e8f0' }}>{c.label}</div>
              <div style={{ color: '#94a3b8', marginTop: 4 }}>
                {c.latitude?.toFixed(5)}, {c.longitude?.toFixed(5)} — {SOURCE_LABELS[c.source] || c.source}
                {' '}(fusion {Math.round((c.fusion_score || c.confidence || 0) * 100)}%
                {c.cluster_size > 1 ? `, ${c.cluster_size} mənbə` : ''})
              </div>
              {c.dms && (
                <div style={{ color: '#64748b', marginTop: 4, fontSize: 11 }}>
                  {c.dms.latitude_dms}, {c.dms.longitude_dms}
                </div>
              )}
              {c.display_name && <div style={{ color: '#64748b', marginTop: 4, fontSize: 11 }}>{c.display_name}</div>}
              <div style={{ marginTop: 6, display: 'flex', gap: 8 }}>
                <button type="button" onClick={() => copyText(`${c.latitude}, ${c.longitude}`)} style={iconBtnStyle}>Kopyala</button>
                {c.map_url && <a href={c.map_url} target="_blank" rel="noreferrer" style={linkStyle}>Xəritə</a>}
              </div>
            </div>
          ))}
        </div>
      )}

      {displayInf?.regional_hints?.length > 0 && (
        <div style={{ background: '#0f172a', padding: 12, borderRadius: 10, border: '1px solid #334155' }}>
          <h3 style={{ fontSize: '13px', color: '#94a3b8', margin: '0 0 8px' }}>Regional ipucları (koordinatsız)</h3>
          {displayInf.regional_hints.map((h, i) => (
            <div key={i} style={{ fontSize: 12, color: '#cbd5e1', marginBottom: 4 }}>
              {h.type}: <strong>{h.value}</strong>
            </div>
          ))}
        </div>
      )}

      <WeatherConsistencyPanel data={data?.location?.reverse_weather || data?.reverse_weather} />

      {data?.location?.astronomy && !data.location.astronomy.error && (
        <div style={{ marginTop: 15, paddingTop: 15, borderTop: '1px solid #334155' }}>
          <h3 style={{ fontSize: '13px', color: '#f87171', marginBottom: 8 }}>Kölgə və işıq (Astronomy)</h3>
          <div style={{ background: '#0f172a', padding: 12, borderRadius: 10, border: '1px solid #334155', fontSize: 13, color: '#cbd5e1', display: 'flex', gap: 15, flexWrap: 'wrap' }}>
            <div><span style={{ color: '#94a3b8' }}>Altitude:</span> <strong>{data.location.astronomy.sun_altitude_degrees}°</strong></div>
            <div><span style={{ color: '#94a3b8' }}>Azimut:</span> <strong>{data.location.astronomy.sun_azimuth_degrees}°</strong></div>
            <div><span style={{ color: '#94a3b8' }}>Kölgə:</span> <strong style={{ color: '#eab308' }}>{data.location.astronomy.shadow_direction}</strong></div>
          </div>
        </div>
      )}
    </div>
  );
}

const rowStyle = {
  background: '#0f172a',
  padding: '8px 10px',
  borderRadius: 8,
  border: '1px solid #334155',
  fontSize: 12,
  display: 'flex',
  justifyContent: 'space-between',
  gap: 8,
  flexWrap: 'wrap',
};

const iconBtnStyle = {
  background: '#1e293b',
  border: '1px solid #475569',
  borderRadius: 6,
  padding: '4px 8px',
  color: '#e2e8f0',
  cursor: 'pointer',
  fontSize: 11,
};

const linkStyle = { color: '#60a5fa', fontSize: 11, textDecoration: 'none' };
