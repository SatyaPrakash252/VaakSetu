import { useState, useRef, useCallback } from 'react'
import { API_BASE } from '../config'

export default function AudioTest({ processResult }) {
  const [mode, setMode] = useState(null) // 'upload' | 'record' | null
  const [recording, setRecording] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [textInput, setTextInput] = useState('')
  const [textLang, setTextLang] = useState('auto')
  const [dragOver, setDragOver] = useState(false)
  const [fileName, setFileName] = useState(null)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const fileInputRef = useRef(null)

  const processAudio = useCallback(async (audioBase64, callerId = '+910000000000') => {
    setProcessing(true)
    setError(null)
    setResult(null)
    try {
      // Start a call first
      const callRes = await fetch(API_BASE + '/api/calls/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ caller_number: callerId, agent_id: 'TEST-AGENT', language_hint: textLang === 'auto' ? null : textLang })
      })
      const call = await callRes.json()

      // Process audio through full pipeline
      const procRes = await fetch(API_BASE + '/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          call_id: call.call_id,
          audio_base64: audioBase64,
          language: textLang
        })
      })
      const data = await procRes.json()
      setResult(data)
      processResult(data)
    } catch (e) {
      setError(`Pipeline error: ${e.message}. Is the backend running on port 8000?`)
    } finally {
      setProcessing(false)
    }
  }, [processResult, textLang])

  const processText = useCallback(async () => {
    if (!textInput.trim()) return
    setProcessing(true)
    setError(null)
    setResult(null)
    try {
      const callRes = await fetch(API_BASE + '/api/calls/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ caller_number: '+910000000000', agent_id: 'TEST-AGENT', language_hint: textLang === 'auto' ? null : textLang })
      })
      const call = await callRes.json()
      const procRes = await fetch(API_BASE + '/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ call_id: call.call_id, text: textInput, language: textLang })
      })
      const data = await procRes.json()
      setResult(data)
      processResult(data)
    } catch (e) {
      setError(`Pipeline error: ${e.message}`)
    } finally {
      setProcessing(false)
    }
  }, [textInput, textLang, processResult])

  const handleFileUpload = useCallback(async (file) => {
    if (!file) return
    setFileName(file.name)
    const reader = new FileReader()
    reader.onload = () => {
      const base64 = reader.result.split(',')[1]
      processAudio(base64)
    }
    reader.readAsDataURL(file)
  }, [processAudio])

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder
      chunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const reader = new FileReader()
        reader.onload = () => {
          const base64 = reader.result.split(',')[1]
          processAudio(base64)
        }
        reader.readAsDataURL(blob)
        stream.getTracks().forEach(t => t.stop())
      }
      mediaRecorder.start()
      setRecording(true)
    } catch (e) {
      setError('Microphone access denied. Please allow microphone access.')
    }
  }, [processAudio])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop()
      setRecording(false)
    }
  }, [])

  const getColor = (level) => ({ CRITICAL: 'var(--red)', HIGH: 'var(--orange)', MEDIUM: 'var(--yellow)', LOW: 'var(--green)' }[level] || 'var(--blue)')
  
  const getSeverityColor = (sev) => ({ CRITICAL: '#ff0040', HIGH: '#ff6600', MEDIUM: '#ffd700', LOW: '#00cc66', NONE: '#666' }[sev] || '#666')

  return (
    <div className="test-page">
      <h1>AUDIO TEST LAB</h1>
      <div className="subtitle">Upload audio, record from mic, or type text — runs through the full backend pipeline</div>

      <div className="test-grid">
        {/* Upload */}
        <div className="test-card">
          <h3>📂 Upload Audio File</h3>
          <div className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFileUpload(e.dataTransfer.files[0]) }}>
            <div className="upload-icon">🎵</div>
            <div className="upload-text">{fileName || 'Drop WAV/MP3/WEBM here or click to browse'}</div>
            <input ref={fileInputRef} type="file" accept="audio/*" hidden onChange={(e) => handleFileUpload(e.target.files[0])} />
          </div>
        </div>

        {/* Record */}
        <div className="test-card">
          <h3>🎙️ Record from Microphone</h3>
          <div style={{ textAlign: 'center', padding: '10px 0' }}>
            <button className={`record-btn ${recording ? 'recording' : ''}`}
              onClick={recording ? stopRecording : startRecording}>
              <div className="rec-inner"></div>
            </button>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: recording ? 'var(--red)' : 'var(--muted)', letterSpacing: '1px' }}>
              {recording ? '● RECORDING — CLICK TO STOP' : 'CLICK TO RECORD'}
            </div>
          </div>
        </div>

        {/* Text Input */}
        <div className="test-card" style={{ gridColumn: 'span 2' }}>
          <h3>⌨️ Direct Text Input (bypass ASR)</h3>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end' }}>
            <div style={{ flex: 1 }}>
              <textarea value={textInput} onChange={(e) => setTextInput(e.target.value)}
                placeholder="Type in any language: Kannada, Hindi, English... e.g. bachao bachao, maar raha hai, help me"
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); processText() } }}
                style={{
                  width: '100%', height: '60px', background: 'var(--surface2)', border: '1px solid var(--border2)',
                  borderRadius: '4px', padding: '10px', color: 'var(--text)', fontFamily: 'var(--font-sans)',
                  fontSize: '12px', resize: 'none', outline: 'none'
                }} />
            </div>
            <select value={textLang} onChange={(e) => setTextLang(e.target.value)}
              style={{
                background: 'var(--surface2)', border: '1px solid var(--border2)', color: 'var(--text)',
                padding: '8px', borderRadius: '4px', fontFamily: 'var(--font-mono)', fontSize: '10px'
              }}>
              <option value="auto">Auto</option>
              <option value="kn">Kannada</option>
              <option value="hi">Hindi</option>
              <option value="en">English</option>
            </select>
            <button className="btn btn-confirm" onClick={processText} disabled={processing || !textInput.trim()}
              style={{ padding: '8px 20px', opacity: processing || !textInput.trim() ? 0.5 : 1 }}>
              {processing ? '⏳ PROCESSING...' : '▶ PROCESS'}
            </button>
          </div>
          <div style={{ marginTop: '6px', fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--muted)', letterSpacing: '0.5px' }}>
            TRY: "bachao bachao maar raha hai" • "kill me help" • "maar daalega chaku" • Press Enter to submit
          </div>
        </div>
      </div>

      {/* Processing */}
      {processing && (
        <div className="processing-indicator">
          <div className="spinner"></div>
          PROCESSING THROUGH PIPELINE: ASR → Keywords → NLP → Emotion → UTCS
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{ padding: '12px 16px', background: 'var(--red-dim)', border: '1px solid var(--red)', borderRadius: '4px', marginBottom: '20px', fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--red)' }}>
          ✗ {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="result-panel">
          <h3>Pipeline Results — {result.call_id}</h3>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '16px' }}>
            <div className="stat-card">
              <div className="stat-num" style={{ color: getColor(result.utcs?.level) }}>{result.utcs?.score || 0}</div>
              <div className="stat-lbl">UTCS Score</div>
            </div>
            <div className="stat-card">
              <div className="stat-num" style={{ color: result.keywords?.total_hits > 0 ? '#ff0040' : 'var(--blue)' }}>
                {result.keywords?.total_hits || 0}
              </div>
              <div className="stat-lbl">Keyword Hits</div>
            </div>
            <div className="stat-card">
              <div className="stat-num" style={{ color: 'var(--yellow)' }}>{Math.round((result.emotion?.panic || 0) * 100)}%</div>
              <div className="stat-lbl">Panic Level</div>
            </div>
            <div className="stat-card">
              <div className="stat-num" style={{ color: 'var(--accent)' }}>{result.transcript?.asr_latency_ms || 0}ms</div>
              <div className="stat-lbl">ASR Latency</div>
            </div>
          </div>

          {/* Keyword Severity Banner */}
          {result.keywords?.severity && result.keywords.severity !== 'NONE' && (
            <div style={{
              padding: '10px 16px', marginBottom: '12px', borderRadius: '4px',
              background: `${getSeverityColor(result.keywords.severity)}15`,
              border: `1px solid ${getSeverityColor(result.keywords.severity)}`,
              display: 'flex', alignItems: 'center', gap: '10px',
            }}>
              <span style={{ fontSize: '18px' }}>
                {result.keywords.severity === 'CRITICAL' ? '🚨' : result.keywords.severity === 'HIGH' ? '⚠️' : '🔔'}
              </span>
              <div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 700,
                  color: getSeverityColor(result.keywords.severity), letterSpacing: '1px' }}>
                  KEYWORD SEVERITY: {result.keywords.severity}
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--muted)', marginTop: '2px' }}>
                  Tier 1: {result.keywords.tier_counts?.[1] || 0} hits • 
                  Tier 2: {result.keywords.tier_counts?.[2] || 0} hits • 
                  Tier 3: {result.keywords.tier_counts?.[3] || 0} hits
                </div>
              </div>
            </div>
          )}

          {/* ASR Error Banner */}
          {(result.asr_error || result.transcript?.error) && (
            <div style={{
              padding: '10px 16px', marginBottom: '12px', borderRadius: '4px',
              background: 'rgba(255,100,0,0.1)', border: '1px solid #ff6600',
              display: 'flex', alignItems: 'center', gap: '10px',
            }}>
              <span style={{ fontSize: '18px' }}>⚠️</span>
              <div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 700, color: '#ff6600', letterSpacing: '1px' }}>
                  ASR ERROR
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--muted)', marginTop: '2px' }}>
                  {result.asr_error || result.transcript?.error} — Use text input instead for reliable results
                </div>
              </div>
            </div>
          )}

          <div className="result-row">
            <span className="result-label">Transcript</span>
            <span className="result-value" style={{ color: result.transcript?.text ? 'var(--text)' : 'var(--muted)', fontStyle: result.transcript?.text ? 'normal' : 'italic' }}>
              {result.transcript?.text || '(empty — no speech detected)'}
            </span>
          </div>
          <div className="result-row">
            <span className="result-label">Language</span>
            <span className="result-value">{result.transcript?.language || '—'}</span>
          </div>
          <div className="result-row">
            <span className="result-label">Input Mode</span>
            <span className="result-value" style={{ color: result.transcript?.input_mode === 'text' ? 'var(--green)' : 'var(--blue)' }}>
              {result.transcript?.input_mode === 'text' ? '⌨️ Direct Text' : '🎙️ Audio/ASR'}
              {result.transcript?.backend && result.transcript.backend !== 'text_input' && (
                <span style={{ opacity: 0.6, marginLeft: '6px', fontSize: '9px' }}>via {result.transcript.backend}</span>
              )}
            </span>
          </div>
          <div className="result-row">
            <span className="result-label">Intent</span>
            <span className="result-value">{result.nlp?.intent ? `${result.nlp.intent.category} → ${result.nlp.intent.subcategory}` : '—'}</span>
          </div>
          <div className="result-row">
            <span className="result-label">Summary</span>
            <span className="result-value">{result.nlp?.summary || '—'}</span>
          </div>
          <div className="result-row">
            <span className="result-label">Urgency</span>
            <span className="result-value" style={{ 
              color: result.nlp?.urgency === 'critical' ? '#ff0040' : result.nlp?.urgency === 'high' ? '#ff6600' : 'var(--green)',
              fontWeight: result.nlp?.urgency === 'critical' ? 700 : 400,
            }}>
              {result.nlp?.urgency?.toUpperCase() || '—'}
            </span>
          </div>
          <div className="result-row">
            <span className="result-label">Location</span>
            <span className="result-value">{result.nlp?.entities?.location || '—'}</span>
          </div>
          <div className="result-row">
            <span className="result-label">UTCS Level</span>
            <span className="result-value" style={{ color: getColor(result.utcs?.level), fontWeight: 700 }}>
              {result.utcs?.level || '—'} — {result.utcs?.action?.replace(/_/g, ' ') || ''}
            </span>
          </div>

          {/* UTCS Breakdown */}
          {result.utcs?.breakdown && (
            <div style={{ marginTop: '8px', padding: '8px 12px', background: 'var(--surface2)', borderRadius: '4px' }}>
              <span className="result-label" style={{ display: 'block', marginBottom: '6px' }}>UTCS Score Breakdown</span>
              <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                {Object.entries(result.utcs.breakdown).map(([k, v]) => (
                  <div key={k} style={{ fontFamily: 'var(--font-mono)', fontSize: '10px' }}>
                    <span style={{ color: 'var(--muted)', textTransform: 'uppercase' }}>{k}: </span>
                    <span style={{ color: v > 0 ? '#ff0040' : 'var(--text)', fontWeight: v > 0 ? 700 : 400 }}>
                      {typeof v === 'number' ? v.toFixed(1) : v}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Keywords detail */}
          {result.keywords?.hits?.length > 0 && (
            <div style={{ padding: '10px 0' }}>
              <span className="result-label" style={{ display: 'block', marginBottom: '6px' }}>🔑 Matched Keywords</span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {result.keywords.hits.map((h, i) => (
                  <span key={i} style={{
                    fontFamily: 'var(--font-mono)', fontSize: '10px', padding: '3px 10px', borderRadius: '3px',
                    background: h.tier === 1 ? 'rgba(255,0,64,0.15)' : h.tier === 2 ? 'rgba(255,102,0,0.15)' : 'rgba(255,215,0,0.1)',
                    color: h.tier === 1 ? '#ff0040' : h.tier === 2 ? '#ff6600' : '#ffd700',
                    border: `1px solid ${h.tier === 1 ? '#ff004050' : h.tier === 2 ? '#ff660050' : '#ffd70050'}`,
                  }}>
                    {h.keyword} 
                    <span style={{ opacity: 0.6, marginLeft: '4px' }}>T{h.tier}</span>
                    {h.match_type && h.match_type !== 'exact' && (
                      <span style={{ opacity: 0.4, marginLeft: '3px', fontSize: '8px' }}>({h.match_type})</span>
                    )}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Emotion bars */}
          <div style={{ marginTop: '12px' }}>
            <span className="result-label">Emotion Analysis {result.emotion?.source === 'text_estimation' ? '(estimated from text)' : '(from audio)'}</span>
            {Object.entries(result.emotion || {}).filter(([k]) => k !== 'features' && k !== 'source').map(([k, v]) => (
              typeof v === 'number' && (
                <div key={k} style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: '4px 0' }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--muted)', width: '50px', textTransform: 'capitalize' }}>{k}</span>
                  <div className="bar-track" style={{ flex: 1 }}>
                    <div className="bar-fill" style={{ width: `${v * 100}%`, background: k === 'calm' ? 'var(--green)' : k === 'panic' ? 'var(--red)' : 'var(--yellow)' }}></div>
                  </div>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text)', width: '30px', textAlign: 'right' }}>{Math.round(v * 100)}%</span>
                </div>
              )
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
