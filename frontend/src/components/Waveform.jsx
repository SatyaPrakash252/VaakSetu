import { useEffect, useRef } from 'react'

/**
 * Waveform — Compact audio waveform for the Operations dashboard sidebar
 * Shows a gentle animated sine wave (no random bars)
 */
export default function Waveform({ bars = 32 }) {
  const containerRef = useRef(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    // Create bar elements once
    container.innerHTML = ''
    for (let i = 0; i < bars; i++) {
      const bar = document.createElement('div')
      bar.className = 'wave-bar'
      bar.style.animationDelay = `${(i / bars) * 0.8}s`
      bar.style.height = '100%'
      container.appendChild(bar)
    }
  }, [bars])

  return <div ref={containerRef} className="waveform" />
}
