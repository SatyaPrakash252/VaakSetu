import { useState, useRef, useCallback, useEffect } from 'react'
import { API_BASE } from '../config'
import AudioWaveform from '../components/AudioWaveform'

const RECORD_STATES = { IDLE: 'idle', RECORDING: 'recording', REVIEW: 'review', PROCESSING: 'processing' }
const MAX_RECORD_SECS = 60
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB
const ALLOWED_FORMATS = ['audio/wav', 'audio/mpeg', 'audio/mp3', 'audio/webm', 'audio/ogg', 'audio/flac', 'audio/x-m4a', 'audio/mp4']
const PIPELINE_STEPS = ['ASR', 'KEYWORDS', 'NLP', 'EMOTION', 'UTCS']

export default function AudioTest({ processResult }) {
  // Recording state
  const [recState, setRecState] = useState(RECORD_STATES.IDLE)
  const [elapsed, setElapsed] = useState(0)
  const [audioBlob, setAudioBlob] = useState(null)
  const [audioBlobUrl, setAudioBlobUrl] = useState(null)
  const [mediaStream, setMediaStream] = useState(null)

  // File upload state
  const [fileName, setFileName] = useState(null)
  const [fileInfo, setFileInfo] = useState(null)
  const [fileAudioUrl, setFileAudioUrl] = useState(null)
  const [fileBase64, setFileBase64] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  // Processing state
  const [processing, setProcessing] = useState(false)
  const [pipelineStep, setPipelineStep] = useState(-1)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  // Text input
  const [textInput, setTextInput] = useState('')
  const [textLang, setTextLang] = useState('auto')

  // Refs
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const fileInputRef = useRef(null)
  const timerRef = useRef(null)
  const streamRef = useRef(null)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop())
      if (audioBlobUrl) URL.revokeObjectURL(audioBlobUrl)
      if (fileAudioUrl) URL.revokeObjectURL(fileAudioUrl)
    }
  }, [])

  // ── Process audio through backend pipeline ──
  const processAudio = useCallback(async (audioBase64) => {
    setProcessing(true)
    setError(null)
    setResult(null)
    setPipelineStep(0)

    // Simulate pipeline step progression
    const stepTimer = setInterval(() => {
      setPipelineStep(prev => {
        if (prev >= PIPELINE_STEPS.length - 1) { clearInterval(stepTimer); return prev }
        return prev + 1
      })
    }, 800)

    try {
      const callRes = await fetch(API_BASE + '/api/calls/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ caller_number: '+910000000000', agent_id: 'TEST-AGENT', language_hint: textLang === 'auto' ? null : textLang })
      })
      if (!callRes.ok) throw new Error(`Failed to start call: ${callRes.status}`)
      const call = await callRes.json()

      const procRes = await fetch(API_BASE + '/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          call_id: call.call_id,
          audio_base64: audioBase64,
          language: textLang
        })
      })
      if (!procRes.ok) throw new Error(`Pipeline error: ${procRes.status}`)
      const data = await procRes.json()
      clearInterval(stepTimer)
      setPipelineStep(PIPELINE_STEPS.length)
      setResult(data)
      processResult(data)
    } catch (e) {
      clearInterval(stepTimer)
      setError(`Pipeline error: ${e.message}. Is the backend running?`)
    } finally {
      setProcessing(false)
    }
  }, [processResult, textLang])

  // ── Process text ──
  const processText = useCallback(async () => {
    if (!textInput.trim()) return
    setProcessing(true)
    setError(null)
    setResult(null)
    setPipelineStep(0)

    const stepTimer = setInterval(() => {
      setPipelineStep(prev => {
        if (prev >= PIPELINE_STEPS.length - 1) { clearInterval(stepTimer); return prev }
        return prev + 1
      })
    }, 600)

    try {
      const callRes = await fetch(API_BASE + '/api/calls/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ caller_number: '+910000000000', agent_id: 'TEST-AGENT', language_hint: textLang === 'auto' ? null : textLang })
      })
      if (!callRes.ok) throw new Error(`Failed to start call: ${callRes.status}`)
      const call = await callRes.json()

      const procRes = await fetch(API_BASE + '/api/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ call_id: call.call_id, text: textInput, language: textLang })
      })
      if (!procRes.ok) throw new Error(`Pipeline error: ${procRes.status}`)
      const data = await procRes.json()
      clearInterval(stepTimer)
      setPipelineStep(PIPELINE_STEPS.length)
      setResult(data)
      processResult(data)
    } catch (e) {
      clearInterval(stepTimer)
      setError(`Pipeline error: ${e.message}`)
    } finally {
      setProcessing(false)
    }
  }, [textInput, textLang, processResult])

  // ── File Upload ──
  const handleFileUpload = useCallback((file) => {
    if (!file) return
    // Validate format
    if (!ALLOWED_FORMATS.includes(file.type) && !file.name.match(/\.(wav|mp3|webm|ogg|flac|m4a|mp4)$/i)) {
      setError(`Unsupported format: ${file.type || file.name.split('.').pop()}. Use WAV, MP3, WEBM, OGG, FLAC, or M4A.`)
      return
    }
    // Validate size
    if (file.size > MAX_FILE_SIZE) {
      setError(`File too large: ${(file.size / 1024 / 1024).toFixed(1)}MB. Maximum is 10MB.`)
      return
    }
    setError(null)
    setResult(null)
    setFileName(file.name)
    setFileInfo({ name: file.name, size: (file.size / 1024).toFixed(1) + ' KB', type: file.type || file.name.split('.').pop() })

    // Create playback URL
    if (fileAudioUrl) URL.revokeObjectURL(fileAudioUrl)
    setFileAudioUrl(URL.createObjectURL(file))

    // Read as base64
    const reader = new FileReader()
    reader.onload = () => {
      setFileBase64(reader.result.split(',')[1])
    }
    reader.readAsDataURL(file)
  }, [fileAudioUrl])

  const submitFile = useCallback(() => {
    if (fileBase64) processAudio(fileBase64)
  }, [fileBase64, processAudio])

  const clearFile = useCallback(() => {
    setFileName(null)
    setFileInfo(null)
    if (fileAudioUrl) URL.revokeObjectURL(fileAudioUrl)
    setFileAudioUrl(null)
    setFileBase64(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [fileAudioUrl])

  // ── Recording ──
  const startRecording = useCallback(async () => {
    try {
      setError(null)
      setResult(null)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } })
      streamRef.current = stream
      setMediaStream(stream)

      const mediaRecorder = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm' })
      mediaRecorderRef.current = mediaRecorder
      chunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setAudioBlob(blob)
        if (audioBlobUrl) URL.revokeObjectURL(audioBlobUrl)
        setAudioBlobUrl(URL.createObjectURL(blob))
        setRecState(RECORD_STATES.REVIEW)
        // Don't stop the stream yet — we keep it for the waveform fadeout
        setTimeout(() => {
          if (streamRef.current) {
            streamRef.current.getTracks().forEach(t => t.stop())
            streamRef.current = null
          }
          setMediaStream(null)
        }, 300)
      }

      mediaRecorder.start(100) // collect data every 100ms
      setRecState(RECORD_STATES.RECORDING)
      setElapsed(0)

      // Timer
      let secs = 0
      timerRef.current = setInterval(() => {
        secs++
        setElapsed(secs)
        if (secs >= MAX_RECORD_SECS) {
          if (mediaRecorderRef.current?.state === 'recording') {
            mediaRecorderRef.current.stop()
          }
          clearInterval(timerRef.current)
        }
      }, 1000)
    } catch (e) {
      setError('🎙️ Microphone access denied. Please allow microphone access in your browser settings and try again.')
    }
  }, [audioBlobUrl])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop()
    }
    if (timerRef.current) clearInterval(timerRef.current)
  }, [])

  const submitRecording = useCallback(() => {
    if (!audioBlob) return
    setRecState(RECORD_STATES.PROCESSING)
    const reader = new FileReader()
    reader.onload = () => {
      const base64 = reader.result.split(',')[1]
      processAudio(base64)
    }
    reader.readAsDataURL(audioBlob)
  }, [audioBlob, processAudio])

  const reRecord = useCallback(() => {
    if (audioBlobUrl) URL.revokeObjectURL(audioBlobUrl)
    setAudioBlob(null)
    setAudioBlobUrl(null)
    setRecState(RECORD_STATES.IDLE)
    setElapsed(0)
  }, [audioBlobUrl])

  const formatTime = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

  const getColor = (level) => ({ CRITICAL: 'var(--red)', HIGH: 'var(--orange)', MEDIUM: 'var(--yellow)', LOW: 'var(--green)' }[level] || 'var(--blue)')
  const getSeverityColor = (sev) => ({ CRITICAL: '#ff0040', HIGH: '#ff6600', MEDIUM: '#ffd700', LOW: '#00cc66', NONE: '#666' }[sev] || '#666')

  return (
    <div className="test-page">
      <h1>AUDIO TEST LAB</h1>
      <div className="subtitle">Upload audio, record from mic, or type text — runs through the full backend pipeline</div>

      <div className="test-grid">
        {/* ── Upload Card ── */}
        <div className="test-card">
          <h3>📂 Upload Audio File</h3>
          {!fileInfo ? (
            <div className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFileUpload(e.dataTransfer.files[0]) }}>
              <div className="upload-icon">🎵</div>
              <div className="upload-text">Drop WAV/MP3/WEBM here or click to browse</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--muted)', marginTop: '8px' }}>
                Max 10MB • WAV, MP3, WEBM, OGG, FLAC, M4A
              </div>
              <input ref={fileInputRef} type="file" accept="audio/*" hidden onChange={(e) => handleFileUpload(e.target.files[0])} />
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ padding: '12px', background: 'var(--surface2)', borderRadius: '6px', border: '1px solid var(--border2)' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--accent)', marginBottom: '6px' }}>
                  ✓ {fileInfo.name}
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--muted)' }}>
                  {fileInfo.size} • {fileInfo.type}
                </div>
              </div>
              <audio src={fileAudioUrl} controls style={{ width: '100%', height: '36px', borderRadius: '4px' }} />
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="btn btn-confirm" onClick={submitFile} disabled={processing}
                  style={{ flex: 1, opacity: processing ? 0.5 : 1 }}>
                  {processing ? '⏳ PROCESSING...' : '▶ SUBMIT'}
                </button>
                <button className="btn btn-edit" onClick={clearFile}>✕ CLEAR</button>
              </div>
            </div>
          )}
        </div>

        {/* ── Record Card ── */}
        <div className="test-card">
          <h3>🎙️ Record from Microphone</h3>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>

            {/* Waveform Visualizer */}
            <AudioWaveform
              stream={mediaStream}
              isRecording={recState === RECORD_STATES.RECORDING}
              isProcessing={processing}
              height={100}
            />

            {/* Record Button + Timer */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              {recState === RECORD_STATES.IDLE && (
                <button className="record-btn" onClick={startRecording} title="Click to start recording">
                  <div className="rec-inner"></div>
                </button>
              )}
              {recState === RECORD_STATES.RECORDING && (
                <>
                  <button className="record-btn recording" onClick={stopRecording} title="Click to stop recording">
                    <div className="rec-inner"></div>
                  </button>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontFamily: 'var(--font-display)', fontSize: '28px', color: 'var(--red)', letterSpacing: '2px' }}>
                      {formatTime(elapsed)}
                    </div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--muted)' }}>
                      {MAX_RECORD_SECS - elapsed}s remaining
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Status Text */}
            {recState === RECORD_STATES.IDLE && (
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--muted)', letterSpacing: '1px', textAlign: 'center' }}>
                CLICK TO RECORD
              </div>
            )}
            {recState === RECORD_STATES.RECORDING && (
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--red)', letterSpacing: '1px', animation: 'blink 1s step-end infinite' }}>
                ● RECORDING — CLICK TO STOP
              </div>
            )}

            {/* Review Mode: Playback + Submit */}
            {recState === RECORD_STATES.REVIEW && audioBlobUrl && (
              <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ padding: '8px 12px', background: 'var(--green-dim)', border: '1px solid var(--accent)', borderRadius: '4px', textAlign: 'center' }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--accent)', letterSpacing: '1px' }}>
                    ✓ RECORDED {formatTime(elapsed)}
                  </span>
                </div>
                <audio src={audioBlobUrl} controls style={{ width: '100%', height: '36px', borderRadius: '4px' }} />
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="btn btn-confirm" onClick={submitRecording} style={{ flex: 1 }}>
                    ▶ SUBMIT RECORDING
                  </button>
                  <button className="btn btn-edit" onClick={reRecord}>
                    ↺ RE-RECORD
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Text Input Card ── */}
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

      {/* ── Pipeline Processing Indicator ── */}
      {processing && (
        <div style={{
          background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '6px',
          padding: '20px', marginBottom: '24px', textAlign: 'center'
        }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--accent)', letterSpacing: '2px', marginBottom: '16px' }}>
            PROCESSING THROUGH PIPELINE
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '4px', alignItems: 'center' }}>
            {PIPELINE_STEPS.map((step, i) => (
              <div key={step} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: '10px', letterSpacing: '1px',
                  padding: '6px 14px', borderRadius: '4px', transition: 'all 0.4s ease',
                  background: pipelineStep > i ? 'var(--green-dim)' : pipelineStep === i ? 'var(--surface3)' : 'var(--surface2)',
                  border: `1px solid ${pipelineStep > i ? 'var(--accent)' : pipelineStep === i ? 'var(--border2)' : 'var(--border)'}`,
                  color: pipelineStep > i ? 'var(--accent)' : pipelineStep === i ? 'var(--text)' : 'var(--muted)',
                }}>
                  {pipelineStep > i ? '✓ ' : pipelineStep === i ? '◉ ' : '○ '}{step}
                </div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <span style={{ color: pipelineStep > i ? 'var(--accent)' : 'var(--muted)', fontSize: '12px' }}>→</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Error ── */}
      {error && (
        <div style={{ padding: '12px 16px', background: 'var(--red-dim)', border: '1px solid var(--red)', borderRadius: '4px', marginBottom: '20px', fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--red)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>✗ {error}</span>
          <button onClick={() => setError(null)} style={{ background: 'none', border: 'none', color: 'var(--red)', cursor: 'pointer', fontSize: '14px' }}>×</button>
        </div>
      )}

      {/* ── Results ── */}
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
