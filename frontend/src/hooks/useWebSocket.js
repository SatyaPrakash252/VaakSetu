import { useState, useEffect, useRef, useCallback } from 'react'
import { WS_URL } from '../config'

export function useWebSocket() {
  const [messages, setMessages] = useState([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        console.log('WebSocket connected')
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          setMessages(prev => [...prev, data])
        } catch (e) {
          console.warn('WS parse error:', e)
        }
      }

      ws.onclose = () => {
        setConnected(false)
        // Auto-reconnect after 3s
        reconnectTimer.current = setTimeout(connect, 3000)
      }

      ws.onerror = () => {
        setConnected(false)
      }
    } catch (e) {
      setConnected(false)
      reconnectTimer.current = setTimeout(connect, 3000)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (wsRef.current) wsRef.current.close()
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }
  }, [connect])

  const sendMessage = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg))
    }
  }, [])

  return { messages, connected, sendMessage }
}
