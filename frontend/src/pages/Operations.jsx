import { useState, useEffect, useMemo } from 'react'
import CallQueue from '../components/CallQueue'
import StreamDetection from '../components/StreamDetection'
import LiveTranscript from '../components/LiveTranscript'
import AIInterpretation from '../components/AIInterpretation'
import AlertFeed from '../components/AlertFeed'
import EventLog from '../components/EventLog'
import TechStack from '../components/TechStack'
import Waveform from '../components/Waveform'
import EmotionChips from '../components/EmotionChips'
import { API_BASE } from '../config'

export default function Operations({ calls, activeCall, setActiveCall, connected, runScenario, takeover, onTakeover, onVerify }) {
  const data = activeCall || null
  const utcs = data?.utcs || { score: 0, level: 'MINIMAL' }
  const [verifState, setVerifState] = useState(null)
  const [durSec, setDurSec] = useState(0)

  // Duration counter
  useEffect(() => {
    if (!data) return
    setDurSec(0)
    const t = setInterval(() => setDurSec(s => s + 1), 1000)
    return () => clearInterval(t)
  }, [data?.call_id])

  const utcsLevel = utcs.level || 'MINIMAL'
  const score = utcs.score || 0
  const kwScore = utcs.breakdown?.keywords || 0
  const emScore = utcs.breakdown?.emotion || 0
  const noiseScore = utcs.breakdown?.noise || 0

  const getColor = (s) => s >= 600 ? 'var(--red)' : s >= 400 ? 'var(--orange)' : s >= 200 ? 'var(--yellow)' : 'var(--green)'
  const getLabel = (l) => ({ CRITICAL: '⚠ CRITICAL', HIGH: '◉ HIGH', MEDIUM: '◉ ELEVATED', LOW: '● LOW' }[l] || '● SAFE')
  const getBadgeCls = (l) => ({ CRITICAL: 'utcs-critical', HIGH: 'utcs-high', MEDIUM: 'utcs-warn', LOW: 'utcs-safe' }[l] || 'utcs-safe')

  const langDetect = data ? `LANG: ${({kn:'Kannada-KN',hi:'Hindi-HI',en:'English-EN'})[data.transcript?.language] || data.transcript?.language || '?'} · LATENCY: ${data.transcript?.asr_latency_ms || 0}ms` : 'LANG: — · LATENCY: —'

  const durStr = `${String(Math.floor(durSec / 60)).padStart(2, '0')}:${String(durSec % 60).padStart(2, '0')}`

  const handleVerify = (state) => {
    setVerifState(state)
    if (data?.call_id) onVerify(data.call_id, state === 'confirmed', state === 'partial' ? 'Partial match' : null)
  }

  // Compute signal percentages from UTCS breakdown
  const kwPct = Math.min(100, Math.round(kwScore / 7))
  const emPct = data?.emotion ? Math.round(Math.max(data.emotion.panic, data.emotion.fear, data.emotion.distress) * 100) : 0
  const noisePct = data?.noise_analysis ? Math.round((data.noise_analysis.confidence || 0) * 100) : Math.min(100, noiseScore)
  const threatPct = Math.min(100, Math.round(score / 10))

  return (
    <div className="page-ops">
      {/* LEFT PANEL: Call Queue */}
      <div className="panel">
        <div className="panel-header">
          Call Queue <span className="count-badge">{calls.filter(c => c.status === 'active').length || calls.length} ACTIVE</span>
        </div>
        <div className="panel-body">
          {/* Scenario buttons */}
          <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--muted)', letterSpacing: '1px', marginBottom: '6px' }}>DEMO SCENARIOS:</div>
            <div style={{ display: 'flex', gap: '4px' }}>
              <button className="nav-btn" onClick={() => runScenario(1)} style={{ flex: 1, fontSize: '9px', padding: '4px 6px' }}>S1·KN</button>
              <button className="nav-btn" onClick={() => runScenario(2)} style={{ flex: 1, fontSize: '9px', padding: '4px 6px' }}>S2·HI</button>
              <button className="nav-btn" onClick={() => runScenario(3)} style={{ flex: 1, fontSize: '9px', padding: '4px 6px' }}>S3·SILENT</button>
            </div>
          </div>
          <CallQueue calls={calls} activeCall={data} onSelect={setActiveCall} />
        </div>
        {/* Waveform + Lang detect */}
        <div style={{ marginTop: 'auto', borderTop: '1px solid var(--border)' }}>
          <div className="section-hdr">Audio Stream — Channel 1</div>
          <Waveform active={!!data} />
          <div style={{ padding: '0 14px 8px', fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--muted)' }}>{langDetect}</div>
        </div>
      </div>

      {/* CENTER PANEL */}
      <div className="panel" style={{ borderRight: '1px solid var(--border)' }}>
        {/* UTCS Bar */}
        <div className="utcs-bar">
          <div className="utcs-block">
            <div className="utcs-label">UTCS Score</div>
            <div className="utcs-value" style={{ color: getColor(score) }}>{score}</div>
            <div className="utcs-sub" style={{ color: getColor(score) }}>{getLabel(utcsLevel)}</div>
          </div>
          <div className="utcs-block">
            <div className="utcs-label">Keyword Match</div>
            <div className="utcs-value" style={{ color: 'var(--blue)' }}>{String(Math.min(99, Math.round(kwScore / 7))).padStart(2, '0')}</div>
            <div className="utcs-sub">Tier 1–3</div>
          </div>
          <div className="utcs-block">
            <div className="utcs-label">Emotion Score</div>
            <div className="utcs-value" style={{ color: 'var(--yellow)' }}>{String(emPct).padStart(2, '0')}</div>
            <div className="bar-track" style={{ width: '100%', marginTop: 4 }}>
              <div className="bar-fill" style={{ width: `${emPct}%`, background: emPct < 30 ? 'var(--green)' : emPct < 60 ? 'var(--yellow)' : 'var(--red)' }}></div>
            </div>
          </div>
          <div className="utcs-block">
            <div className="utcs-label">Noise Risk</div>
            <div className="utcs-value" style={{ color: 'var(--muted)' }}>{String(noisePct).padStart(2, '0')}</div>
            <div className="utcs-sub">Background Analysis</div>
          </div>
          <div className="utcs-block">
            <div className="utcs-label">Call Duration</div>
            <div className="utcs-value" style={{ color: 'var(--text)', fontSize: '22px' }}>{durStr}</div>
            <div className="utcs-sub">{data?.call_id || '—'}</div>
          </div>
        </div>

        {/* Transcript */}
        <LiveTranscript data={data} />

        {/* Verification Banner */}
        {verifState && (
          <div className={`verif-banner ${verifState === 'confirmed' ? 'verif-confirmed' : verifState === 'partial' ? 'verif-partial' : 'verif-denied'}`}>
            {verifState === 'confirmed' && '✓ CITIZEN CONFIRMED — Understanding verified. Proceeding with confidence.'}
            {verifState === 'partial' && '~ PARTIAL MATCH — Clarification loop initiated.'}
            {verifState === 'denied' && '✗ UNCONFIRMED — Escalating to human agent.'}
          </div>
        )}

        {/* AI Interpretation */}
        <div className="interp-box">
          <div className="interp-header">
            <div className="interp-title">AI Interpretation</div>
            <div className="interp-conf">{data?.nlp?.intent?.confidence ? `Confidence: ${Math.round(data.nlp.intent.confidence * 100)}%` : 'Confidence: —'}</div>
          </div>
          <div className="interp-text">
            {data?.nlp?.summary || 'Waiting for call data…'}
          </div>
          <div className="interp-actions">
            <button className="btn btn-confirm" onClick={() => handleVerify('confirmed')}>✓ Confirmed</button>
            <button className="btn btn-partial" onClick={() => handleVerify('partial')}>~ Partially Correct</button>
            <button className="btn btn-edit" onClick={() => { if (data?.nlp?.summary) { const newSummary = prompt('Edit AI Interpretation:', data.nlp.summary); if (newSummary && newSummary !== data.nlp.summary) { fetch((API_BASE || '') + '/api/interpretation/edit', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({call_id: data.call_id, field: 'summary', old_value: data.nlp.summary, new_value: newSummary}) }).catch(e => console.error('Edit failed:', e)) } } }}>✎ Edit</button>
            <button
              className={`btn btn-takeover ${takeover ? 'active-state' : ''}`}
              onClick={() => data?.call_id && onTakeover(data.call_id)}
            >🔴 TAKE OVER CALL</button>
          </div>
        </div>
      </div>

      {/* RIGHT PANEL: Signals */}
      <div className="panel">
        <div className="panel-body">
          <StreamDetection data={data} kwPct={kwPct} emPct={emPct} noisePct={noisePct} threatPct={threatPct} />
          <EmotionChips emotion={data?.emotion} />
          <AlertFeed data={data} />
          <EventLog calls={calls} />
          <TechStack />
        </div>
      </div>
    </div>
  )
}
