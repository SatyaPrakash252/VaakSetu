import { NavLink } from 'react-router-dom'
import { useState, useEffect } from 'react'

export default function Header({ connected, reconnecting }) {
  const [time, setTime] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const statusText = connected ? 'LIVE' : reconnecting ? 'RECONNECTING' : 'OFFLINE'
  const wsText = connected ? 'WS:CONNECTED' : reconnecting ? 'WS:RECONNECTING...' : 'WS:DISCONNECTED'

  return (
    <header className="header">
      <div className="logo">
        <div>
          <div className="logo-text">VAAKSETU</div>
          <div className="logo-sub">1092 Helpline · AI Assist Layer</div>
        </div>
        <span className="version-badge">v2.0</span>
      </div>
      <div className="header-nav">
        <NavLink to="/" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`} end>◉ OPERATIONS</NavLink>
        <NavLink to="/map" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>🗺 MAP</NavLink>
        <NavLink to="/test" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>🎤 AUDIO TEST</NavLink>
        <NavLink to="/analytics" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>📊 ANALYTICS</NavLink>
        <NavLink to="/demo" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>▶ DEMO</NavLink>
        <NavLink to="/db" className={({ isActive }) => `nav-btn ${isActive ? 'active' : ''}`}>🗄️ DATABASE</NavLink>
      </div>
      <div className="header-right">
        <div className="live-badge">
          <div className={`live-dot ${connected ? '' : 'off'}`}></div>
          {statusText}
        </div>
        <div className="clock">{time.toLocaleTimeString('en-IN')}</div>
        <div className="ws-status">{wsText}</div>
      </div>
    </header>
  )
}
