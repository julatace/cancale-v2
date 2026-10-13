import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';

// Évite l'écran noir en cas d'erreur de rendu : les données locales restent intactes
class ErrorBoundary extends React.Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error('Render error:', error, info); }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div style={{ minHeight: '100vh', background: '#09090b', color: '#fafafa', fontFamily: 'monospace', padding: 24 }}>
        <h2 style={{ color: '#ff4d6d' }}>Une erreur est survenue</h2>
        <p style={{ color: '#71717a' }}>Tes données sont conservées. Recharge l'application.</p>
        <button onClick={() => window.location.reload()} style={{ background: '#00e5a0', border: 'none', borderRadius: 8, padding: '8px 16px', fontWeight: 700 }}>
          Recharger
        </button>
      </div>
    );
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
