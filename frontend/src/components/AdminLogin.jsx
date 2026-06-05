import React, { useState } from 'react';
import axios from 'axios';
import { Lock, Loader2, ShieldAlert } from 'lucide-react';
import { API_BASE, setAuthToken } from '../apiClient';

export default function AdminLogin({ onSuccess }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!password.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_BASE}/api/auth/login`, { password });
      if (res.data?.token) {
        setAuthToken(res.data.token);
        onSuccess(res.data.token);
      } else {
        setError('Giriş cavabı alınmadı.');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Parol səhvdir və ya server cavab vermir.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(160deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)',
        padding: 24,
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          width: '100%',
          maxWidth: 380,
          background: 'rgba(30,41,59,0.95)',
          border: '1px solid #334155',
          borderRadius: 16,
          padding: '32px 28px',
          boxShadow: '0 24px 48px rgba(0,0,0,0.35)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <div
            style={{
              background: 'rgba(96,165,250,0.15)',
              padding: 10,
              borderRadius: 12,
            }}
          >
            <Lock style={{ width: 22, height: 22, color: '#60a5fa' }} />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#f1f5f9' }}>
              Admin girişi
            </h1>
            <p style={{ margin: '4px 0 0', fontSize: 12, color: '#64748b' }}>
              Metadata Extractor — məhdud giriş
            </p>
          </div>
        </div>

        <label style={{ display: 'block', fontSize: 12, color: '#94a3b8', margin: '20px 0 8px' }}>
          Parol
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Admin parolu"
          autoComplete="current-password"
          autoFocus
          style={{
            width: '100%',
            boxSizing: 'border-box',
            padding: '12px 14px',
            borderRadius: 10,
            border: '1px solid #475569',
            background: '#0f172a',
            color: '#e2e8f0',
            fontSize: 15,
            outline: 'none',
          }}
        />

        {error && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginTop: 12,
              fontSize: 12,
              color: '#f87171',
            }}
          >
            <ShieldAlert style={{ width: 14, height: 14, flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !password.trim()}
          style={{
            width: '100%',
            marginTop: 20,
            padding: '12px 16px',
            borderRadius: 10,
            border: 'none',
            background: loading ? '#334155' : 'linear-gradient(135deg, #3b82f6, #6366f1)',
            color: '#fff',
            fontSize: 14,
            fontWeight: 600,
            cursor: loading ? 'wait' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
          }}
        >
          {loading ? (
            <Loader2 style={{ width: 16, height: 16, animation: 'spin 1s linear infinite' }} />
          ) : (
            <Lock style={{ width: 16, height: 16 }} />
          )}
          Daxil ol
        </button>
      </form>
    </div>
  );
}
