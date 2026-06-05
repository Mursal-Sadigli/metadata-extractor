import React, { useState, useRef } from 'react';
import { Search, QrCode, Users, Copy, AlertCircle, Loader2, ExternalLink } from 'lucide-react';

export default function InstagramSearchPanel({ onSearch, loading }) {
  const [username, setUsername] = useState('');
  const [maxPosts, setMaxPosts] = useState(3);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  const handleSearch = () => {
    setError('');
    if (!username.trim()) {
      setError('Lütfen Instagram kullanıcı adı girin');
      return;
    }
    onSearch(username.trim(), maxPosts);
  };

  const handleUrlInput = (e) => {
    const text = e.target.value;
    // URL'den username çıkar: instagram.com/username veya @username
    let extracted = text;
    
    if (text.includes('instagram.com/')) {
      extracted = text.split('instagram.com/')[1].split('?')[0].replace('/', '');
    }
    extracted = extracted.replace('@', '').trim();
    
    setUsername(extracted);
  };

  const handleQrScan = () => {
    // QR kod tarama - tarayıcı izni gerekli
    alert('QR Kod Tarama:\n\n1. Instagram profil sayfasından QR kodunu aç\n2. Kameran ile tara\n3. Açılan URL\'den username\'i kopyala\n4. Yukarı yapıştır');
  };

  const copyExample = () => {
    setUsername('cristiano');
  };

  return (
    <div style={{
      background: '#1e293b',
      borderRadius: '16px',
      padding: '24px',
      border: '1px solid rgba(139,92,246,0.3)',
      boxShadow: '0 0 20px rgba(139,92,246,0.1)',
      marginBottom: '24px'
    }}>
      <h2 style={{fontSize:'18px',fontWeight:'700',color:'#f1f5f9',margin:'0 0 20px',display:'flex',alignItems:'center',gap:'8px'}}>
        <Search style={{width:'20px',height:'20px',color:'#8b5cf6'}}/>
        Instagram Profili Ara (OSINT)
      </h2>

      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.1)',
          border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: '8px',
          padding: '12px',
          marginBottom: '16px',
          fontSize: '13px',
          color: '#f87171',
          display: 'flex',
          gap: '8px',
          alignItems: 'center'
        }}>
          <AlertCircle style={{width:'16px',height:'16px',flexShrink:0}}/>
          {error}
        </div>
      )}

      {/* Üç seçenek sekmeleri */}
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'12px',marginBottom:'20px'}}>
        
        {/* Seçenek 1: Username */}
        <div style={{background:'#0f172a',borderRadius:'12px',padding:'12px',border:'1px solid #334155',cursor:'pointer',transition:'all 0.2s'}}>
          <div style={{fontSize:'12px',fontWeight:'600',color:'#a78bfa',marginBottom:'8px'}}>1️⃣ Username Gir</div>
          <input
            type="text"
            placeholder="@username veya cristiano"
            value={username}
            onChange={(e) => setUsername(e.target.value.replace('@', ''))}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            style={{
              width: '100%',
              background: '#1e293b',
              border: '1px solid #475569',
              borderRadius: '6px',
              padding: '8px',
              fontSize: '12px',
              color: '#f1f5f9',
              outline: 'none',
              boxSizing: 'border-box'
            }}
          />
        </div>

        {/* Seçenek 2: URL */}
        <div style={{background:'#0f172a',borderRadius:'12px',padding:'12px',border:'1px solid #334155',cursor:'pointer',transition:'all 0.2s'}}>
          <div style={{fontSize:'12px',fontWeight:'600',color:'#a78bfa',marginBottom:'8px'}}>🔗 URL Yapıştır</div>
          <input
            type="text"
            placeholder="instagram.com/username"
            onChange={handleUrlInput}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            style={{
              width: '100%',
              background: '#1e293b',
              border: '1px solid #475569',
              borderRadius: '6px',
              padding: '8px',
              fontSize: '12px',
              color: '#f1f5f9',
              outline: 'none',
              boxSizing: 'border-box'
            }}
          />
        </div>

        {/* Seçenek 3: QR Kod */}
        <div style={{background:'#0f172a',borderRadius:'12px',padding:'12px',border:'1px solid #334155',cursor:'pointer',transition:'all 0.2s'}}>
          <div style={{fontSize:'12px',fontWeight:'600',color:'#a78bfa',marginBottom:'8px'}}>📱 QR Kod Tara</div>
          <button
            onClick={handleQrScan}
            style={{
              width: '100%',
              background: '#334155',
              border: 'none',
              borderRadius: '6px',
              padding: '8px',
              fontSize: '12px',
              color: '#cbd5e1',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '4px',
              transition: 'all 0.2s',
              fontWeight: '500'
            }}
            onMouseEnter={(e) => e.target.style.background = '#475569'}
            onMouseLeave={(e) => e.target.style.background = '#334155'}
          >
            <QrCode style={{width:'14px',height:'14px'}}/>
            Talimatlar
          </button>
        </div>
      </div>

      {/* Post Sayısı Seçici */}
      <div style={{marginBottom:'16px'}}>
        <label style={{fontSize:'12px',color:'#cbd5e1',fontWeight:'500',marginBottom:'8px',display:'block'}}>
          Analiz Edilecek Post Sayısı: <span style={{color:'#8b5cf6',fontWeight:'700'}}>{maxPosts}</span>
        </label>
        <input
          type="range"
          min="1"
          max="10"
          value={maxPosts}
          onChange={(e) => setMaxPosts(parseInt(e.target.value))}
          style={{
            width: '100%',
            height: '6px',
            background: '#0f172a',
            borderRadius: '3px',
            outline: 'none',
            accentColor: '#8b5cf6'
          }}
        />
        <div style={{fontSize:'11px',color:'#94a3b8',marginTop:'4px'}}>
          Daha fazla post = Daha detaylı analiz ama daha yavaş
        </div>
      </div>

      {/* Öneriler */}
      <div style={{
        background: 'rgba(139,92,246,0.05)',
        borderRadius: '8px',
        padding: '12px',
        marginBottom: '16px',
        fontSize: '12px',
        color: '#cbd5e1',
        border: '1px solid rgba(139,92,246,0.1)'
      }}>
        <div style={{fontWeight:'600',color:'#a78bfa',marginBottom:'8px'}}>💡 İpuçları:</div>
        <ul style={{margin:'0',paddingLeft:'16px',lineHeight:'1.6'}}>
          <li>Genel profiller en hızlı sonuç verir (örn: cristiano, instagram)</li>
          <li>Özel hesaplar erişilemez</li>
          <li>Silinen hesapları bulunabilir ama post yüklü seçilemez</li>
          <li>Instagram anti-bot koruması varsa 2FA giriş gerekebilir</li>
        </ul>
      </div>

      {/* Arama Butonu */}
      <button
        onClick={handleSearch}
        disabled={loading}
        style={{
          width: '100%',
          background: loading ? '#475569' : 'linear-gradient(135deg, #8b5cf6, #a78bfa)',
          border: 'none',
          borderRadius: '8px',
          padding: '12px',
          fontSize: '14px',
          fontWeight: '700',
          color: '#f1f5f9',
          cursor: loading ? 'default' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          transition: 'all 0.3s',
          opacity: loading ? 0.7 : 1
        }}
        onMouseEnter={(e) => !loading && (e.target.style.transform = 'translateY(-2px)', e.target.style.boxShadow = '0 8px 20px rgba(139,92,246,0.4)')}
        onMouseLeave={(e) => !loading && (e.target.style.transform = 'translateY(0)', e.target.style.boxShadow = 'none')}
      >
        {loading ? (
          <>
            <Loader2 style={{width:'16px',height:'16px',animation:'spin 1s linear infinite'}}/>
            Profil Yükleniyor...
          </>
        ) : (
          <>
            <Search style={{width:'16px',height:'16px'}}/>
            Aramayı Başlat
          </>
        )}
      </button>

      {/* Test Butonu */}
      <button
        onClick={copyExample}
        style={{
          marginTop: '12px',
          width: '100%',
          background: '#334155',
          border: '1px solid #475569',
          borderRadius: '8px',
          padding: '10px',
          fontSize: '12px',
          color: '#cbd5e1',
          cursor: 'pointer',
          fontWeight: '500',
          transition: 'all 0.2s'
        }}
        onMouseEnter={(e) => (e.target.style.background = '#475569', e.target.style.color = '#f1f5f9')}
        onMouseLeave={(e) => (e.target.style.background = '#334155', e.target.style.color = '#cbd5e1')}
      >
        Test Et (Cristiano Ronaldo)
      </button>
    </div>
  );
}
