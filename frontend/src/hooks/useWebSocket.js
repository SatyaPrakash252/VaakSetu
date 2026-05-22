import { useState, useEffect, useRef, useCallback } from 'react'
import { WS_URL, API_BASE } from '../config'

const MAX_MESSAGES = 100
const MAX_RECONNECT_ATTEMPTS = 50
const HEARTBEAT_INTERVAL = 30000

export function useWebSocket() {
  const [messages, setMessages] = useState([])
  const [connected, setConnected] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const heartbeatTimer = useRef(null)
  const attemptsRef = useRef(0)
  const backoffRef = useRef(1000)
  const mountedRef = useRef(true)

  const startHeartbeat = useCallback(() => {
    if (heartbeatTimer.current) clearInterval(heartbeatTimer.current)
    heartbeatTimer.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }))
      }
    }, HEARTBEAT_INTERVAL)
  }, [])

  const connect = useCallback(() => {
    if (!mountedRef.current) return
    if (attemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
      setConnected(false)
      setReconnecting(false)
      return
    }

    // Wake up the Render backend first (free tier sleeps after inactivity)
    const wakeUp = API_BASE
      ? fetch(API_BASE + '/health').catch(() => {})
      : Promise.resolve()

    wakeUp.then(() => {
      if (!mountedRef.current) return
      try {
        const ws = new WebSocket(WS_URL)
        wsRef.current = ws

        ws.onopen = () => {
          if (!mountedRef.current) return
          setConnected(true)
          setReconnecting(false)
          attemptsRef.current = 0
          backoffRef.current = 1000 // Reset backoff on success
          startHeartbeat()
          console.log('[WS] Connected')
        }

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (data.type === 'pong') return // Heartbeat response, skip
            setMessages(prev => {
              const next = [...prev, data]
              return next.length > MAX_MESSAGES ? next.slice(-MAX_MESSAGES) : next
            })
          } catch (e) {
            console.warn('[WS] Parse error:', e)
          }
        }

        ws.onclose = () => {
          if (!mountedRef.current) return
          setConnected(false)
          if (heartbeatTimer.current) clearInterval(heartbeatTimer.current)
          // Exponential backoff: 1s → 2s → 4s → 8s → 16s → 30s max
          attemptsRef.current++
          const delay = Math.min(backoffRef.current, 30000)
          backoffRef.current = Math.min(delay * 2, 30000)
          setReconnecting(true)
          console.log(`[WS] Disconnected. Reconnecting in ${delay / 1000}s (attempt ${attemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`)
          reconnectTimer.current = setTimeout(connect, delay)
        }

        ws.onerror = () => {
          setConnected(false)
        }
      } catch (e) {
        setConnected(false)
        attemptsRef.current++
        const delay = Math.min(backoffRef.current, 30000)
        backoffRef.current = Math.min(delay * 2, 30000)
        reconnectTimer.current = setTimeout(connect, delay)
      }
    })
  }, [startHeartbeat])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      if (wsRef.current) {
        wsRef.current.onclose = null // Prevent reconnect on intentional close
        wsRef.current.close()
      }
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (heartbeatTimer.current) clearInterval(heartbeatTimer.current)
    }
  }, [connect])

  const sendMessage = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  return { messages, connected, reconnecting, sendMessage }
}
