import React from 'react';
import { Camera, MapPin, Hash, Image as ImageIcon, Map, Search, EyeOff, CheckCircle } from 'lucide-react';

export default function InstagramPanel({ data }) {
  if (!data) return null;

  if (data.error) {
    return (
      <div style={{
        background: '#1e293b', borderRadius: '16px', padding: '20px',
        border: '1px solid rgba(239,68,68,0.3)',
        boxShadow: '0 0 15px rgba(239,68,68,0.08)'
      }}>
        <h2 style={{fontSize:'15px',fontWeight:'700',color:'#f87171',margin:'0 0 8px'}}>İnstagram Kəşfiyyat Xətası</h2>
        <p style={{fontSize:'13px',color:'#cbd5e1',margin:0}}>{data.error}</p>
      </div>
    );
  }

  const { profile, posts } = data;

  return (
    <div style={{
      background: '#1e293b', borderRadius: '16px', padding: '24px',
      border: '1px solid rgba(139,92,246,0.3)',
      boxShadow: '0 0 20px rgba(139,92,246,0.1)'
    }}>
      
      {/* Profil Başlığı */}
      <div style={{display:'flex',gap:'20px',alignItems:'center',marginBottom:'24px',paddingBottom:'20px',borderBottom:'1px solid #334155'}}>
        {profile.profile_pic_url ? (
          <img src={profile.profile_pic_url} alt="Profile" style={{width:'80px',height:'80px',borderRadius:'50%',border:'2px solid #8b5cf6',objectFit:'cover'}} />
        ) : (
          <div style={{width:'80px',height:'80px',borderRadius:'50%',background:'#0f172a',display:'flex',alignItems:'center',justifyContent:'center',border:'2px solid #8b5cf6'}}>
            <Camera style={{width:'32px',height:'32px',color:'#8b5cf6'}} />
          </div>
        )}
        <div style={{flex:1}}>
          <h2 style={{fontSize:'20px',fontWeight:'800',color:'#f1f5f9',margin:'0 0 4px',display:'flex',alignItems:'center',gap:'8px'}}>
            @{data.target}
            {profile.is_verified && <CheckCircle style={{width:'16px',height:'16px',color:'#3b82f6'}} />}
            {profile.is_private && <EyeOff style={{width:'16px',height:'16px',color:'#ef4444'}} />}
          </h2>
          <p style={{fontSize:'14px',color:'#e2e8f0',fontWeight:'600',margin:'0 0 4px'}}>{profile.full_name}</p>
          <div style={{display:'flex',gap:'15px',fontSize:'12px',color:'#94a3b8',marginBottom:'4px'}}>
            <span>İzləyici: <strong style={{color:'#cbd5e1'}}>{profile.followers}</strong></span>
            <span>İzləyir: <strong style={{color:'#cbd5e1'}}>{profile.followees}</strong></span>
          </div>
          <div style={{display:'flex',gap:'15px',fontSize:'11px',color:'#94a3b8',marginBottom:'8px',flexWrap:'wrap'}}>
            {profile.estimated_creation && (
              <span style={{background:'rgba(139,92,246,0.1)',padding:'2px 6px',borderRadius:'4px',border:'1px solid rgba(139,92,246,0.2)',color:'#a78bfa'}}>
                Yaradılma: {profile.estimated_creation}
              </span>
            )}
            {profile.risk_ratio !== undefined && (
              <span style={{background: profile.risk_ratio > 10 ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)',padding:'2px 6px',borderRadius:'4px',border:`1px solid ${profile.risk_ratio > 10 ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)'}`,color: profile.risk_ratio > 10 ? '#f87171' : '#10b981'}}>
                İzləmə Nisbəti Risk: {profile.risk_ratio > 10 ? 'YÜKSƏK (Spam/Bot Ola bilər)' : 'Normal'} ({profile.risk_ratio})
              </span>
            )}
          </div>
          {profile.biography && <p style={{fontSize:'12px',color:'#cbd5e1',margin:0,whiteSpace:'pre-wrap'}}>{profile.biography}</p>}
        </div>
      </div>

      {data.behavior_analysis && (
        <div style={{background:'#0f172a', borderRadius:'12px', padding:'16px', border:'1px solid #334155', marginBottom:'24px'}}>
          <h3 style={{fontSize:'14px',color:'#f1f5f9',marginBottom:'10px',display:'flex',alignItems:'center',gap:'6px'}}>
             Profil Davranış Analizi
          </h3>
          <div style={{display:'flex', gap:'20px', fontSize:'12px', color:'#cbd5e1'}}>
            <div><span style={{color:'#94a3b8'}}>Ən Aktiv Vaxt:</span> <strong style={{color:'#8b5cf6'}}>{data.behavior_analysis.most_active_time_of_day}</strong></div>
            <div><span style={{color:'#94a3b8'}}>Orta Saat:</span> <strong style={{color:'#8b5cf6'}}>{data.behavior_analysis.average_post_hour}:00</strong></div>
            <div style={{flex:1, fontStyle:'italic', color:'#94a3b8'}}>{data.behavior_analysis.notes}</div>
          </div>
        </div>
      )}

      <h3 style={{fontSize:'16px',color:'#a78bfa',marginBottom:'16px',fontWeight:'700'}}>OSINT Post Analizi (Son {posts.length} post)</h3>
      
      {/* Postlar Grid-i */}
      <div style={{display:'flex',flexDirection:'column',gap:'20px'}}>
        {posts.map((post, idx) => (
          <div key={idx} style={{background:'#0f172a',borderRadius:'12px',border:'1px solid #334155',padding:'16px'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'12px'}}>
              <div style={{fontSize:'12px',color:'#94a3b8'}}>{new Date(post.date).toLocaleString('az-AZ')}</div>
              <a href={`https://instagram.com/p/${post.url}`} target="_blank" rel="noreferrer" style={{fontSize:'12px',color:'#8b5cf6',textDecoration:'none',fontWeight:'600'}}>
                Posta Bax →
              </a>
            </div>

            <p style={{fontSize:'13px',color:'#cbd5e1',margin:'0 0 16px',lineHeight:'1.5'}}>{post.caption}</p>

            {/* Məkan və OSINT Etiketləri */}
            <div style={{display:'flex',flexWrap:'wrap',gap:'10px',marginBottom:'16px'}}>
              {post.location && (
                <div style={{display:'flex',alignItems:'center',gap:'4px',padding:'6px 10px',background:'rgba(239,68,68,0.1)',color:'#f87171',borderRadius:'6px',fontSize:'11px',fontWeight:'600',border:'1px solid rgba(239,68,68,0.2)'}}>
                  <MapPin style={{width:'12px',height:'12px'}}/> {post.location}
                </div>
              )}
              {post.estimated_device && (
                <div style={{display:'flex',alignItems:'center',gap:'4px',padding:'6px 10px',background:'rgba(234,179,8,0.1)',color:'#eab308',borderRadius:'6px',fontSize:'11px',fontWeight:'600',border:'1px solid rgba(234,179,8,0.2)'}}>
                   Cihaz: {post.estimated_device}
                </div>
              )}
              {post.hashtags && post.hashtags.map((tag, i) => (
                <div key={i} style={{display:'flex',alignItems:'center',gap:'4px',padding:'6px 10px',background:'rgba(59,130,246,0.1)',color:'#60a5fa',borderRadius:'6px',fontSize:'11px',fontWeight:'600',border:'1px solid rgba(59,130,246,0.2)'}}>
                  <Hash style={{width:'12px',height:'12px'}}/> {tag}
                </div>
              ))}
            </div>

            {/* AI Nəticələri */}
            {post.ai_analysis && Object.keys(post.ai_analysis).length > 0 && (
              <div style={{borderTop:'1px dashed #334155',paddingTop:'16px'}}>
                <h4 style={{fontSize:'12px',color:'#94a3b8',margin:'0 0 10px',textTransform:'uppercase',letterSpacing:'0.5px'}}>AI Vizual Təxminlər</h4>
                
                <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit, minmax(200px, 1fr))',gap:'12px'}}>
                  {/* Obyektlər */}
                  {post.ai_analysis.objects_and_text?.detected_objects && (
                    <div style={{background:'#1e293b',padding:'10px',borderRadius:'8px',border:'1px solid #334155'}}>
                      <div style={{fontSize:'11px',color:'#94a3b8',marginBottom:'6px',display:'flex',alignItems:'center',gap:'4px'}}><Search style={{width:'12px',height:'12px'}}/> Obyektlər</div>
                      <div style={{display:'flex',flexWrap:'wrap',gap:'6px'}}>
                        {post.ai_analysis.objects_and_text.detected_objects.map((o, i) => (
                          <span key={i} style={{fontSize:'11px',color:'#10b981',background:'rgba(16,185,129,0.1)',padding:'2px 6px',borderRadius:'4px',textTransform:'capitalize'}}>{o.object}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* OCR Mətn */}
                  {post.ai_analysis.objects_and_text?.extracted_text && (
                    <div style={{background:'#1e293b',padding:'10px',borderRadius:'8px',border:'1px solid #334155'}}>
                      <div style={{fontSize:'11px',color:'#94a3b8',marginBottom:'6px',display:'flex',alignItems:'center',gap:'4px'}}><ImageIcon style={{width:'12px',height:'12px'}}/> Fotodakı Yazılar</div>
                      <div style={{fontSize:'11px',color:'#e2e8f0',lineHeight:'1.4'}}>
                        {post.ai_analysis.objects_and_text.extracted_text.join(', ')}
                      </div>
                    </div>
                  )}

                  {/* Landşaft */}
                  {post.ai_analysis.terrain_keypoints > 0 && (
                    <div style={{background:'#1e293b',padding:'10px',borderRadius:'8px',border:'1px solid #334155'}}>
                      <div style={{fontSize:'11px',color:'#94a3b8',marginBottom:'6px',display:'flex',alignItems:'center',gap:'4px'}}><Map style={{width:'12px',height:'12px'}}/> Relyef/Peyk Xüsusiyyəti</div>
                      <div style={{fontSize:'11px',color:'#e2e8f0'}}>
                        {post.ai_analysis.terrain_keypoints} geoloji/memarlıq SIFT nöqtəsi tapıldı.
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
            
          </div>
        ))}
        {posts.length === 0 && <p style={{color:'#64748b',fontSize:'13px',textAlign:'center',padding:'20px 0'}}>Heç bir post tapılmadı və ya profil gizlidir.</p>}
      </div>
    </div>
  );
}
