import React from 'react';
import { Globe, CloudRain, Search, Lock } from 'lucide-react';
import WeatherConsistencyPanel from './WeatherConsistencyPanel';
import ReverseImageSearchPanel from './ReverseImageSearchPanel';
import { UPLOADS_BASE } from '../apiClient';

export default function OsintPanel({ data, imageUrl, filename, uploadMeta }) {
  if (!data) return null;

  return (
    <div style={{
      background: '#1e293b', borderRadius: '16px', padding: '20px',
      border: '1px solid rgba(16,185,129,0.3)',
      boxShadow: '0 0 15px rgba(16,185,129,0.08)'
    }} className="cyber-panel">
      <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'16px',paddingBottom:'12px',borderBottom:'1px solid #334155'}}>
        <div style={{background:'rgba(16,185,129,0.2)',padding:'6px',borderRadius:'8px'}}>
          <Globe style={{width:'16px',height:'16px',color:'#10b981'}} />
        </div>
        <h2 style={{fontSize:'15px',fontWeight:'700',color:'#f1f5f9',margin:0}}>Kəşfiyyat (OSINT)</h2>
      </div>

      <div style={{display: 'flex', flexDirection: 'column', gap: '20px'}}>
        
        {/* Reverse Weather Forecast */}
        {data.reverse_weather ? (
          <WeatherConsistencyPanel data={data.reverse_weather} />
        ) : data.weather ? (
          data.weather.error ? (
            <p style={{fontSize:'12px',color:'#ef4444'}}>Hava: {data.weather.error}</p>
          ) : (
            <div>
              <h3 style={{fontSize:'13px',color:'#94a3b8',marginBottom:'8px',display:'flex',alignItems:'center',gap:'6px'}}>
                <CloudRain style={{width:'14px',height:'14px'}}/> Hava Durumu Arxivi
              </h3>
              <div style={{background:'#0f172a',padding:'12px',borderRadius:'10px',border:'1px solid #334155'}}>
                <p style={{margin:'0 0 6px',fontSize:'13px',fontWeight:'600',color:'#e2e8f0'}}>Tarix: {data.weather.date}</p>
                <div style={{display:'flex',gap:'15px',fontSize:'12px',color:'#cbd5e1'}}>
                  <div><span style={{color:'#94a3b8'}}>Max Temp:</span> {data.weather.max_temp_c}°C</div>
                  <div><span style={{color:'#94a3b8'}}>Min Temp:</span> {data.weather.min_temp_c}°C</div>
                  <div><span style={{color:'#94a3b8'}}>Yağıntı:</span> {data.weather.precipitation_mm}mm</div>
                </div>
                <div style={{marginTop:'8px',paddingTop:'8px',borderTop:'1px solid #1e293b',fontSize:'13px'}}>
                  <span style={{color:'#94a3b8'}}>Təsvir:</span> <strong style={{color:'#10b981'}}>{data.weather.description}</strong>
                </div>
              </div>
            </div>
          )
        ) : (
           <p style={{fontSize:'12px',color:'#64748b',fontStyle:'italic'}}>Hava durumu üçün GPS və Tarix məlumatı tapılmadı.</p>
        )}

        {/* Tərs Şəkil Axtarışı */}
        <div style={{ paddingBottom: 4, borderBottom: data.reverse_weather ? '1px solid #334155' : undefined, marginBottom: data.reverse_weather ? 16 : 0 }}>
          <ReverseImageSearchPanel
            data={data.reverse_image_search}
            filename={filename}
            imageUrl={imageUrl}
            uploadMeta={uploadMeta}
          />
        </div>

        {/* Steganografiya (yalnız şəkil) */}
        {data.steganography && data.steganography.status !== 'error' && (
          <div style={{ paddingTop: '4px', borderTop: '1px solid #334155' }}>
            <h3 style={{ fontSize: '13px', color: '#94a3b8', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Lock style={{ width: '14px', height: '14px' }} /> Steganografiya (LSB / DCT)
            </h3>
            <div
              style={{
                background: '#0f172a',
                padding: '12px',
                borderRadius: '10px',
                border: `1px solid ${data.steganography.suspicious ? 'rgba(251,191,36,0.4)' : '#334155'}`,
                fontSize: '12px',
                color: '#cbd5e1',
              }}
            >
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '8px', alignItems: 'center' }}>
                <span style={{ fontWeight: 700, color: data.steganography.suspicious ? '#fbbf24' : '#10b981' }}>
                  Skor: {data.steganography.stego_score}/100
                </span>
                <span style={{ color: '#94a3b8' }}>
                  Risk: {data.steganography.risk_level_az || data.steganography.lsb_suspicion}
                </span>
                {data.steganography.suspicious && (
                  <span style={{ fontSize: 11, color: '#fbbf24', fontWeight: 700 }}>Şübhəli</span>
                )}
              </div>
              {data.steganography.methods?.length > 0 && (
                <p style={{ margin: '0 0 8px', color: '#64748b', fontSize: 11 }}>
                  Metodlar: {data.steganography.methods.join(' · ')}
                </p>
              )}
              {(data.steganography.findings || []).map((f, i) => (
                <p key={i} style={{ margin: '4px 0 0', color: '#94a3b8', lineHeight: 1.45 }}>{f}</p>
              ))}
              {data.steganography.hidden_message_preview && (
                <p style={{ margin: '10px 0 0', padding: '8px', background: '#1e293b', borderRadius: 6, color: '#fbbf24', wordBreak: 'break-word' }}>
                  Gizli mətn (önizləmə): {data.steganography.hidden_message_preview}
                </p>
              )}
              {(data.steganography.embedded_findings || []).length > 0 && (
                <div style={{ marginTop: 10 }}>
                  <p style={{ margin: '0 0 6px', fontSize: 11, color: '#94a3b8', fontWeight: 600 }}>Gömülü fayl imzaları:</p>
                  {(data.steganography.embedded_findings || []).slice(0, 6).map((e, i) => (
                    <p key={i} style={{ margin: '3px 0', fontSize: 11, color: '#cbd5e1' }}>{e.description_az}</p>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {data.internal_structure?.embedded_findings?.length > 0 && !(data.steganography?.embedded_findings?.length > 0) && (
          <div style={{ paddingTop: '4px', borderTop: '1px solid #334155' }}>
            <h3 style={{ fontSize: '13px', color: '#94a3b8', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Lock style={{ width: '14px', height: '14px' }} /> Gömülü fayl (struktur skanı)
            </h3>
            {(data.internal_structure.embedded_findings || []).slice(0, 6).map((e, i) => (
              <p key={i} style={{ margin: '4px 0', fontSize: 11, color: '#cbd5e1' }}>{e.description_az}</p>
            ))}
          </div>
        )}

        {/* Landşaft və Peyk Uyğunlaşdırması */}
        {data.terrain && !data.terrain.error && (
          <div style={{marginTop: '20px', paddingTop: '20px', borderTop: '1px solid #334155'}}>
            <h3 style={{fontSize:'13px',color:'#94a3b8',marginBottom:'8px',display:'flex',alignItems:'center',gap:'6px'}}>
              <Globe style={{width:'14px',height:'14px'}}/> Peyk və Landşaft Profil Analizi
            </h3>
            <div style={{display:'flex',gap:'12px',alignItems:'flex-start', flexWrap:'wrap'}}>
              <div style={{background:'#0f172a',padding:'10px',borderRadius:'10px',border:'1px solid #334155'}}>
                <img src={`${UPLOADS_BASE}/${data.terrain.terrain_image_path.split('\\\\').pop().split('/').pop()}`} 
                     alt="Terrain" 
                     style={{width:'120px',height:'120px',objectFit:'contain',borderRadius:'4px'}} />
              </div>
              <div style={{fontSize:'12px',color:'#cbd5e1',background:'#0f172a',padding:'10px',borderRadius:'10px',flex:1,border:'1px solid #334155'}}>
                <p style={{margin:'0 0 4px', fontSize:'13px'}}><strong>Aşkarlanan Konturlar (SIFT):</strong> <span style={{color:'#10b981'}}>{data.terrain.sift_keypoints_found}</span> nöqtə</p>
                <p style={{margin:0,color:'#94a3b8', lineHeight:'1.5'}}>{data.terrain.message}</p>
              </div>
            </div>
          </div>
        )}

        {/* AI Obyekt və Brend Tanıma */}
        {data.ai && data.ai.detected_objects && data.ai.detected_objects.length > 0 && (
          <div style={{marginTop: '20px', paddingTop: '20px', borderTop: '1px solid #334155'}}>
            <h3 style={{fontSize:'13px',color:'#94a3b8',marginBottom:'8px',display:'flex',alignItems:'center',gap:'6px'}}>
              <Search style={{width:'14px',height:'14px'}}/> Obyekt, Brend və Landmark Tanıma
            </h3>
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill, minmax(130px, 1fr))',gap:'8px'}}>
              {data.ai.detected_objects.map((obj, i) => (
                <div key={i} style={{background:'#0f172a',padding:'8px 12px',borderRadius:'8px',border:'1px solid #334155',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <span style={{fontSize:'13px',fontWeight:'600',color:'#e2e8f0',textTransform:'capitalize'}}>{obj.object}</span>
                  <span style={{fontSize:'11px',color:'#10b981',fontWeight:'700'}}>{(obj.confidence * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
