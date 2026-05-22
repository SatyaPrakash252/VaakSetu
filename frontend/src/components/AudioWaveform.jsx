import { useRef, useEffect, useCallback } from 'react'

/**
 * AudioWaveform — Real-time audio visualizer using Web Audio API + Canvas
 * Props:
 *   stream      — MediaStream from getUserMedia (null when idle)
 *   isRecording — boolean
 *   isProcessing — boolean
 *   height      — canvas height (default 120)
 */
export default function AudioWaveform({ stream, isRecording, isProcessing, height = 120 }) {
  const canvasRef = useRef(null)
  const animFrameRef = useRef(null)
  const analyserRef = useRef(null)
  const audioCtxRef = useRef(null)
  const sourceRef = useRef(null)
  const idlePhaseRef = useRef(0)

  // Setup audio context and analyser when stream changes
  useEffect(() => {
    if (!stream) {
      // Cleanup previous
      if (sourceRef.current) { try { sourceRef.current.disconnect() } catch(e){} }
      if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
        try { audioCtxRef.current.close() } catch(e){}
      }
      analyserRef.current = null
      audioCtxRef.current = null
      sourceRef.current = null
      return
    }

    const audioCtx = new (window.AudioContext || window.webkitAudioContext)()
    const analyser = audioCtx.createAnalyser()
    analyser.fftSize = 256
    analyser.smoothingTimeConstant = 0.8
    const source = audioCtx.createMediaStreamSource(stream)
    source.connect(analyser)

    audioCtxRef.current = audioCtx
    analyserRef.current = analyser
    sourceRef.current = source

    return () => {
      try { source.disconnect() } catch(e){}
      if (audioCtx.state !== 'closed') {
        try { audioCtx.close() } catch(e){}
      }
    }
  }, [stream])

  // Draw function
  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const W = canvas.width
    const H = canvas.height

    ctx.clearRect(0, 0, W, H)

    if (analyserRef.current && isRecording) {
      // === LIVE RECORDING MODE — Frequency Bars ===
      const analyser = analyserRef.current
      const bufferLength = analyser.frequencyBinCount
      const dataArray = new Uint8Array(bufferLength)
      analyser.getByteFrequencyData(dataArray)

      const barCount = 64
      const gap = 2
      const barWidth = (W - gap * (barCount - 1)) / barCount

      for (let i = 0; i < barCount; i++) {
        const dataIdx = Math.floor(i * bufferLength / barCount)
        const value = dataArray[dataIdx] / 255
        const barH = Math.max(2, value * H * 0.85)
        const x = i * (barWidth + gap)
        const y = H - barH

        // Green gradient
        const grad = ctx.createLinearGradient(x, y, x, H)
        grad.addColorStop(0, `rgba(0, 230, 118, ${0.9 + value * 0.1})`)
        grad.addColorStop(0.5, `rgba(0, 200, 83, ${0.7 + value * 0.3})`)
        grad.addColorStop(1, `rgba(0, 230, 118, 0.3)`)
        ctx.fillStyle = grad
        ctx.beginPath()
        ctx.roundRect(x, y, barWidth, barH, 2)
        ctx.fill()

        // Glow effect for active bars
        if (value > 0.3) {
          ctx.shadowColor = '#00e676'
          ctx.shadowBlur = value * 12
          ctx.fillStyle = `rgba(0, 230, 118, ${value * 0.3})`
          ctx.beginPath()
          ctx.roundRect(x, y, barWidth, barH, 2)
          ctx.fill()
          ctx.shadowBlur = 0
        }

        // Reflection
        const reflH = barH * 0.2
        const reflGrad = ctx.createLinearGradient(x, H, x, H + reflH)
        reflGrad.addColorStop(0, `rgba(0, 230, 118, 0.1)`)
        reflGrad.addColorStop(1, `rgba(0, 230, 118, 0)`)
        ctx.fillStyle = reflGrad
        ctx.fillRect(x, H, barWidth, reflH)
      }

    } else if (isProcessing) {
      // === PROCESSING MODE — Amber Pulsing Bars ===
      const t = Date.now() / 1000
      const barCount = 64
      const gap = 2
      const barWidth = (W - gap * (barCount - 1)) / barCount

      for (let i = 0; i < barCount; i++) {
        const phase = (i / barCount) * Math.PI * 4 + t * 3
        const value = (Math.sin(phase) + 1) / 2 * 0.6 + 0.1
        const pulse = (Math.sin(t * 2) + 1) / 2 * 0.3
        const barH = Math.max(2, (value + pulse) * H * 0.5)
        const x = i * (barWidth + gap)
        const y = H - barH

        const grad = ctx.createLinearGradient(x, y, x, H)
        grad.addColorStop(0, `rgba(255, 214, 0, 0.8)`)
        grad.addColorStop(1, `rgba(255, 214, 0, 0.2)`)
        ctx.fillStyle = grad
        ctx.beginPath()
        ctx.roundRect(x, y, barWidth, barH, 2)
        ctx.fill()
      }

    } else {
      // === IDLE MODE — Gentle Sine Wave ===
      idlePhaseRef.current += 0.02
      const phase = idlePhaseRef.current
      const barCount = 64
      const gap = 2
      const barWidth = (W - gap * (barCount - 1)) / barCount

      for (let i = 0; i < barCount; i++) {
        const wave1 = Math.sin((i / barCount) * Math.PI * 2 + phase) * 0.15 + 0.15
        const wave2 = Math.sin((i / barCount) * Math.PI * 3 + phase * 0.7) * 0.08
        const value = Math.max(0.04, wave1 + wave2)
        const barH = Math.max(2, value * H * 0.5)
        const x = i * (barWidth + gap)
        const y = H - barH

        ctx.fillStyle = `rgba(74, 98, 120, ${0.3 + value * 0.4})`
        ctx.beginPath()
        ctx.roundRect(x, y, barWidth, barH, 2)
        ctx.fill()
      }
    }

    animFrameRef.current = requestAnimationFrame(draw)
  }, [isRecording, isProcessing])

  // Animation loop
  useEffect(() => {
    animFrameRef.current = requestAnimationFrame(draw)
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    }
  }, [draw])

  // Handle resize
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const observer = new ResizeObserver(() => {
      const rect = canvas.parentElement.getBoundingClientRect()
      canvas.width = rect.width
      canvas.height = height
    })
    observer.observe(canvas.parentElement)
    // Initial size
    const rect = canvas.parentElement.getBoundingClientRect()
    canvas.width = rect.width
    canvas.height = height
    return () => observer.disconnect()
  }, [height])

  return (
    <div style={{ width: '100%', position: 'relative', height: `${height}px`, borderRadius: '6px', overflow: 'hidden' }}>
      <canvas
        ref={canvasRef}
        style={{ display: 'block', width: '100%', height: '100%' }}
      />
      {isRecording && (
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0, height: '2px',
          background: 'linear-gradient(90deg, transparent, #00e676, transparent)',
          animation: 'pulse-green 1.5s infinite'
        }} />
      )}
    </div>
  )
}
