import React, { useEffect, useMemo, useState } from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
  useMap,
} from 'react-leaflet';
import {
  Route,
  Upload,
  Loader2,
  MapPin,
  Clock,
  Navigation,
  ChevronDown,
  ChevronUp,
  ExternalLink,
} from 'lucide-react';
import { api } from '../apiClient';
import L from 'leaflet';
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({ iconUrl: icon, shadowUrl: iconShadow, iconAnchor: [12, 41] });
L.Marker.prototype.options.icon = DefaultIcon;

const TILES = {
  osm: {
    label: 'OpenStreetMap',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap',
  },
  satellite: {
    label: 'Peyk (ArcGIS)',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri',
  },
};

function numberedIcon(n) {
  return L.divIcon({
    className: '',
    html: `<div style="
      background:#dc2626;color:#fff;font-weight:700;font-size:11px;
      width:26px;height:26px;border-radius:50%;display:flex;align-items:center;
      justify-content:center;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.45);
    ">${n}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}

function FitBounds({ positions }) {
  const map = useMap();
  useEffect(() => {
    if (!positions?.length) return;
    if (positions.length === 1) {
      map.setView(positions[0], 14);
      return;
    }
    const bounds = L.latLngBounds(positions);
    map.fitBounds(bounds, { padding: [48, 48], maxZoom: 15 });
  }, [map, positions]);
  return null;
}

export default function TimelineMappingPanel({ currentFilename, currentOriginalName }) {
  const [expanded, setExpanded] = useState(false);
  const [mapStyle, setMapStyle] = useState('osm');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [timeline, setTimeline] = useState(null);
  const [error, setError] = useState(null);
  const [batchFiles, setBatchFiles] = useState([]);

  const addCurrentToBatch = () => {
    if (!currentFilename) return;
    setBatchFiles((prev) => {
      if (prev.some((f) => f.filename === currentFilename)) return prev;
      return [
        ...prev,
        {
          filename: currentFilename,
          originalName: currentOriginalName || currentFilename,
        },
      ];
    });
  };

  const onPickFiles = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    setError(null);
    try {
      const uploaded = [];
      for (const file of files) {
        const form = new FormData();
        form.append('file', file);
        const res = await api.post('/api/upload', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        uploaded.push({
          filename: res.data.filename,
          originalName: res.data.originalName,
        });
      }
      setBatchFiles((prev) => {
        const seen = new Set(prev.map((p) => p.filename));
        return [...prev, ...uploaded.filter((u) => !seen.has(u.filename))];
      });
    } catch (err) {
      setError('Fayllar yüklənərkən xəta baş verdi.');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const runTimeline = async () => {
    if (batchFiles.length < 2) {
      setError('Marşrut üçün ən azı 2 şəkil seçin.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await api.post('/api/timeline-mapping', {
        filenames: batchFiles.map((f) => f.filename),
      });
      setTimeline(res.data);
      setExpanded(true);
    } catch (err) {
      setError(err.response?.data?.error || 'Marşrut analizi uğursuz oldu.');
      setTimeline(null);
    } finally {
      setLoading(false);
    }
  };

  const waypoints = timeline?.waypoints || [];
  const positions = useMemo(
    () => waypoints.map((w) => [w.latitude, w.longitude]),
    [waypoints],
  );
  const center = timeline?.bounds?.center
    ? [timeline.bounds.center.latitude, timeline.bounds.center.longitude]
    : positions[0] || [40.4093, 49.8671];

  const removeFromBatch = (filename) => {
    setBatchFiles((prev) => prev.filter((f) => f.filename !== filename));
  };

  return (
    <div style={{
      background: 'rgba(59,130,246,0.08)',
      border: '1px solid rgba(96,165,250,0.35)',
      borderRadius: 12,
      padding: 14,
      marginBottom: 14,
    }}>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: 'transparent',
          border: 'none',
          color: '#93c5fd',
          cursor: 'pointer',
          padding: 0,
          fontSize: 14,
          fontWeight: 700,
        }}
      >
        <Route style={{ width: 18, height: 18 }} />
        Timeline Mapping — Marşrut Analizi
        {expanded ? <ChevronUp style={{ marginLeft: 'auto', width: 16 }} /> : <ChevronDown style={{ marginLeft: 'auto', width: 16 }} />}
      </button>

      {expanded && (
        <div style={{ marginTop: 12 }}>
          <p style={{ margin: '0 0 10px', fontSize: 12, color: '#94a3b8', lineHeight: 1.55 }}>
            Çoxlu foto yükləyin; EXIF GPS və tarix əsasında şəxsin hərəkət marşrutu xronoloji ardıcıllıqla xəritədə göstərilir.
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
            <label style={btnStyle}>
              <Upload style={{ width: 14, height: 14 }} />
              Şəkillər əlavə et
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={onPickFiles}
                style={{ display: 'none' }}
                disabled={uploading}
              />
            </label>
            {currentFilename && (
              <button type="button" onClick={addCurrentToBatch} style={btnStyle}>
                <MapPin style={{ width: 14, height: 14 }} />
                Cari faylı əlavə et
              </button>
            )}
            <button
              type="button"
              onClick={runTimeline}
              disabled={loading || uploading || batchFiles.length < 2}
              style={{ ...btnStyle, background: '#2563eb', borderColor: '#3b82f6', color: '#fff' }}
            >
              {loading ? <Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} /> : <Navigation style={{ width: 14, height: 14 }} />}
              Marşrutu qur ({batchFiles.length})
            </button>
          </div>

          {uploading && (
            <p style={{ fontSize: 11, color: '#64748b', margin: '0 0 8px' }}>Yüklənir...</p>
          )}

          {batchFiles.length > 0 && (
            <div style={{ maxHeight: 100, overflowY: 'auto', marginBottom: 10 }}>
              {batchFiles.map((f) => (
                <div key={f.filename} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: 11,
                  color: '#cbd5e1',
                  padding: '4px 0',
                  borderBottom: '1px solid #334155',
                }}>
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {f.originalName}
                  </span>
                  <button type="button" onClick={() => removeFromBatch(f.filename)} style={miniBtn}>
                    Sil
                  </button>
                </div>
              ))}
            </div>
          )}

          {error && <p style={{ color: '#f87171', fontSize: 12, margin: '0 0 8px' }}>{error}</p>}

          {timeline && (
            <>
              <div style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 12,
                fontSize: 12,
                color: '#cbd5e1',
                marginBottom: 10,
              }}>
                <span><strong style={{ color: '#60a5fa' }}>{waypoints.length}</strong> GPS nöqtəsi</span>
                {timeline.route?.total_distance_km != null && (
                  <span><Navigation style={{ width: 12, display: 'inline', verticalAlign: 'middle' }} /> {timeline.route.total_distance_km} km</span>
                )}
                {timeline.route?.duration_sec != null && (
                  <span><Clock style={{ width: 12, display: 'inline', verticalAlign: 'middle' }} /> {(timeline.route.duration_sec / 3600).toFixed(1)} saat</span>
                )}
                {timeline.skipped?.length > 0 && (
                  <span style={{ color: '#fbbf24' }}>{timeline.skipped.length} atlandı</span>
                )}
              </div>

              {timeline.summary && (
                <p style={{ fontSize: 12, color: '#94a3b8', margin: '0 0 10px', lineHeight: 1.5 }}>{timeline.summary}</p>
              )}

              {timeline.warnings?.map((w, i) => (
                <p key={i} style={{ fontSize: 11, color: '#fbbf24', margin: '0 0 6px' }}>{w}</p>
              ))}

              {waypoints.length >= 2 && (
                <>
                  <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
                    {Object.entries(TILES).map(([key, t]) => (
                      <button
                        key={key}
                        type="button"
                        onClick={() => setMapStyle(key)}
                        style={{
                          ...miniBtn,
                          background: mapStyle === key ? 'rgba(37,99,235,0.35)' : '#1e293b',
                          color: mapStyle === key ? '#93c5fd' : '#94a3b8',
                        }}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>

                  <div style={{
                    height: 380,
                    borderRadius: 12,
                    overflow: 'hidden',
                    border: '2px solid #334155',
                    marginBottom: 12,
                  }}>
                    <MapContainer center={center} zoom={12} style={{ height: '100%', width: '100%' }}>
                      <TileLayer url={TILES[mapStyle].url} attribution={TILES[mapStyle].attribution} />
                      <FitBounds positions={positions} />
                      <Polyline
                        positions={positions}
                        pathOptions={{ color: '#3b82f6', weight: 4, opacity: 0.85, dashArray: '8 6' }}
                      />
                      {waypoints.map((w) => (
                        <Marker
                          key={`${w.filename}-${w.sequence}`}
                          position={[w.latitude, w.longitude]}
                          icon={numberedIcon(w.sequence)}
                        >
                          <Popup>
                            <strong>#{w.sequence}</strong> {w.filename}<br />
                            {w.timestamp_iso ? (
                              <span>{new Date(w.timestamp_iso).toLocaleString('az-AZ')}</span>
                            ) : (
                              <span style={{ color: '#888' }}>Tarix yoxdur</span>
                            )}
                            <br />
                            {w.latitude?.toFixed(5)}, {w.longitude?.toFixed(5)}
                            {w.map_urls?.google && (
                              <>
                                <br />
                                <a href={w.map_urls.google} target="_blank" rel="noreferrer">Google Maps</a>
                                {' · '}
                                <a href={w.map_urls.osm} target="_blank" rel="noreferrer">OSM</a>
                              </>
                            )}
                          </Popup>
                        </Marker>
                      ))}
                    </MapContainer>
                  </div>

                  <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                    <h4 style={{ fontSize: 12, color: '#94a3b8', margin: '0 0 8px' }}>Xronoloji cədvəl</h4>
                    {waypoints.map((w) => (
                      <div key={w.sequence} style={{
                        display: 'flex',
                        gap: 10,
                        alignItems: 'flex-start',
                        padding: '8px 10px',
                        marginBottom: 6,
                        background: '#0f172a',
                        borderRadius: 8,
                        border: '1px solid #334155',
                        fontSize: 11,
                      }}>
                        <span style={{
                          background: '#dc2626',
                          color: '#fff',
                          fontWeight: 700,
                          borderRadius: '50%',
                          width: 22,
                          height: 22,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}>
                          {w.sequence}
                        </span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ color: '#e2e8f0', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {w.filename}
                          </div>
                          <div style={{ color: '#64748b', marginTop: 2 }}>
                            {w.timestamp_iso
                              ? new Date(w.timestamp_iso).toLocaleString('az-AZ')
                              : 'EXIF tarix yoxdur'}
                            {' · '}
                            {w.latitude?.toFixed(5)}, {w.longitude?.toFixed(5)}
                          </div>
                          {timeline.route?.segments?.[w.sequence - 2] && (
                            <div style={{ color: '#60a5fa', marginTop: 4 }}>
                              → {timeline.route.segments[w.sequence - 2].distance_km} km
                              {timeline.route.segments[w.sequence - 2].duration_sec != null && (
                                <span style={{ color: '#64748b' }}>
                                  {' '}({Math.round(timeline.route.segments[w.sequence - 2].duration_sec / 60)} dəq)
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                        {w.map_urls?.google && (
                          <a href={w.map_urls.google} target="_blank" rel="noreferrer" style={{ color: '#60a5fa', flexShrink: 0 }}>
                            <ExternalLink style={{ width: 14, height: 14 }} />
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}

              {timeline.status !== 'ok' && waypoints.length < 2 && (
                <p style={{ fontSize: 12, color: '#fbbf24' }}>{timeline.summary}</p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

const btnStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  padding: '8px 12px',
  borderRadius: 8,
  border: '1px solid #475569',
  background: '#1e293b',
  color: '#e2e8f0',
  fontSize: 12,
  fontWeight: 600,
  cursor: 'pointer',
};

const miniBtn = {
  padding: '4px 8px',
  borderRadius: 6,
  border: '1px solid #475569',
  background: '#1e293b',
  color: '#94a3b8',
  fontSize: 10,
  cursor: 'pointer',
};
