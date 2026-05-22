import { useMemo, useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area } from 'recharts'
import { API_BASE } from '../config'

const COLORS = ['#00e676', '#40c4ff', '#ffd600', '#ff6d00', '#ff1744', '#8b5cf6']

export default function Analytics({ calls }) {
  const [apiStats, setApiStats] = useState(null)
  const [loading, setLoading] = useState(true)

  // Fetch real analytics data from backend
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch(API_BASE + '/api/analytics/summary')
        if (res.ok) {
          const data = await res.json()
          setApiStats(data)
        }
      } catch (e) {
        console.warn('[Analytics] API unavailable, using local calls data:', e.message)
      } finally {
        setLoading(false)
      }
    }
    fetchStats()
  }, [])

  const stats = useMemo(() => {
    if (apiStats) {
      return {
        total: apiStats.total_calls || calls.length,
        active: calls.filter(c => c.status === 'active').length,
        critical: apiStats.utcs_distribution?.CRITICAL || calls.filter(c => c.utcs?.level === 'CRITICAL').length,
        avgUtcs: apiStats.avg_utcs || 0,
        threats: apiStats.total_threats || 0,
      }
    }
    const total = calls.length
    const active = calls.filter(c => c.status === 'active').length
    const critical = calls.filter(c => c.utcs?.level === 'CRITICAL').length
    return { total, active, critical, avgUtcs: 0, threats: 0 }
  }, [calls, apiStats])

  const langData = useMemo(() => {
    if (apiStats?.language_distribution) {
      return Object.entries(apiStats.language_distribution).map(([lang, count]) => ({
        name: ({ kn: 'Kannada', hi: 'Hindi', en: 'English' })[lang] || lang,
        value: count,
      }))
    }
    const map = {}
    calls.forEach(c => {
      const l = ({ kn: 'Kannada', hi: 'Hindi', en: 'English' })[c.language] || c.language || 'Unknown'
      map[l] = (map[l] || 0) + 1
    })
    return Object.entries(map).map(([name, value]) => ({ name, value }))
  }, [calls, apiStats])

  const utcsData = useMemo(() => {
    return calls.map((c, i) => ({
      name: c.call_id?.slice(-4) || `#${i}`,
      score: c.utcs?.score || 0,
    })).slice(0, 10)
  }, [calls])

  const levelData = useMemo(() => {
    if (apiStats?.utcs_distribution) {
      return Object.entries(apiStats.utcs_distribution)
        .filter(([, v]) => v > 0)
        .map(([name, value]) => ({ name, value }))
    }
    const map = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, MINIMAL: 0 }
    calls.forEach(c => { map[c.utcs?.level || 'MINIMAL']++ })
    return Object.entries(map).filter(([, v]) => v > 0).map(([name, value]) => ({ name, value }))
  }, [calls, apiStats])

  const timelineData = useMemo(() => {
    if (apiStats?.volume_by_hour && Object.keys(apiStats.volume_by_hour).length > 0) {
      return Object.entries(apiStats.volume_by_hour).slice(-24).map(([hour, count]) => ({
        hour: hour.slice(-5) || hour, // "2026-05-22T11" → "T11" or just show as is
        calls: count,
      }))
    }
    // Fallback: use local calls timestamps
    const hourMap = {}
    calls.forEach(c => {
      const ts = c.started_at || c.timestamp || ''
      if (ts) {
        const h = ts.slice(11, 13) || '00'
        hourMap[h] = (hourMap[h] || 0) + 1
      }
    })
    return Array.from({ length: 24 }, (_, h) => ({
      hour: `${String(h).padStart(2, '0')}:00`,
      calls: hourMap[String(h).padStart(2, '0')] || 0,
    }))
  }, [calls, apiStats])

  const tooltipStyle = { contentStyle: { background: '#0d1117', border: '1px solid #1e2d3d', borderRadius: '4px', fontFamily: "'IBM Plex Mono', monospace", fontSize: '10px' } }

  return (
    <div className="analytics-page">
      <h1>ANALYTICS</h1>
      <div className="subtitle" style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--muted)', letterSpacing: '2px', textTransform: 'uppercase', marginBottom: '30px' }}>
        {loading ? 'Loading analytics data...' : 'System Performance & Call Distribution'}
      </div>

      <div className="analytics-grid">
        <div className="stat-card">
          <div className="stat-num" style={{ color: 'var(--blue)' }}>{stats.total}</div>
          <div className="stat-lbl">Total Calls</div>
        </div>
        <div className="stat-card">
          <div className="stat-num" style={{ color: 'var(--green)' }}>{stats.active}</div>
          <div className="stat-lbl">Active Now</div>
        </div>
        <div className="stat-card">
          <div className="stat-num" style={{ color: 'var(--red)' }}>{stats.critical}</div>
          <div className="stat-lbl">Critical</div>
        </div>
        <div className="stat-card">
          <div className="stat-num" style={{ color: 'var(--yellow)' }}>{stats.avgUtcs || '—'}</div>
          <div className="stat-lbl">Avg UTCS</div>
        </div>
      </div>

      <div className="chart-grid">
        <div className="chart-card">
          <h3>UTCS Score Distribution</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={utcsData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2d3d" />
              <XAxis dataKey="name" tick={{ fill: '#4a6278', fontSize: 9, fontFamily: "'IBM Plex Mono'" }} />
              <YAxis tick={{ fill: '#4a6278', fontSize: 9, fontFamily: "'IBM Plex Mono'" }} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="score" fill="#00e676" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>Language Distribution</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={langData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3} dataKey="value">
                {langData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip {...tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '12px', marginTop: '8px' }}>
            {langData.map((d, i) => (
              <span key={d.name} style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: COLORS[i % COLORS.length] }}>● {d.name}: {d.value}</span>
            ))}
          </div>
        </div>

        <div className="chart-card">
          <h3>Call Volume Timeline</h3>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={timelineData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2d3d" />
              <XAxis dataKey="hour" tick={{ fill: '#4a6278', fontSize: 8, fontFamily: "'IBM Plex Mono'" }} interval={3} />
              <YAxis tick={{ fill: '#4a6278', fontSize: 9, fontFamily: "'IBM Plex Mono'" }} />
              <Tooltip {...tooltipStyle} />
              <Area type="monotone" dataKey="calls" stroke="#00e676" fill="rgba(0,230,118,0.1)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <h3>Threat Level Breakdown</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={levelData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2d3d" />
              <XAxis type="number" tick={{ fill: '#4a6278', fontSize: 9, fontFamily: "'IBM Plex Mono'" }} />
              <YAxis type="category" dataKey="name" tick={{ fill: '#4a6278', fontSize: 9, fontFamily: "'IBM Plex Mono'" }} width={70} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="value" radius={[0, 2, 2, 0]}>
                {levelData.map((entry, i) => (
                  <Cell key={i} fill={
                    entry.name === 'CRITICAL' ? '#ff1744' :
                    entry.name === 'HIGH' ? '#ff6d00' :
                    entry.name === 'MEDIUM' ? '#ffd600' :
                    entry.name === 'LOW' ? '#00e676' : '#40c4ff'
                  } />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
