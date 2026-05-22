import { useState, useCallback, useEffect, useRef } from 'react'
import { API_BASE } from '../config'

export function useCallState() {
  const [calls, setCalls] = useState([])
  const [activeCall, setActiveCall] = useState(null)
  const [loading, setLoading] = useState(true)
  const fetchedRef = useRef(false)

  // Fetch initial calls from API on mount
  useEffect(() => {
    if (fetchedRef.current) return
    fetchedRef.current = true
    const fetchCalls = async () => {
      try {
        const res = await fetch(API_BASE + '/api/calls?limit=20')
        if (res.ok) {
          const data = await res.json()
          if (data.calls?.length) {
            setCalls(data.calls)
          }
        }
      } catch (e) {
        console.warn('[CallState] Failed to fetch initial calls:', e.message)
      } finally {
        setLoading(false)
      }
    }
    fetchCalls()
  }, [])

  const processResult = useCallback((result) => {
    if (!result) return
    const callEntry = {
      call_id: result.call_id,
      caller_number: 'Demo Call',
      agent_id: 'DEMO-AGENT',
      language: result.transcript?.language || 'en',
      status: 'active',
      started_at: result.timestamp || new Date().toISOString(),
      utcs: result.utcs || { score: 0, level: 'MINIMAL' },
      summary: result.nlp?.summary || '',
      keyword_severity: result.keywords?.severity || 'NONE',
    }
    // Deduplication — replace existing call_id or prepend
    setCalls(prev => {
      const exists = prev.findIndex(c => c.call_id === result.call_id)
      if (exists >= 0) {
        const updated = [...prev]
        updated[exists] = callEntry
        return updated
      }
      return [callEntry, ...prev]
    })
    setActiveCall(result)
  }, [])

  const updateFromWS = useCallback((msg) => {
    if (!msg) return
    if (msg.type === 'processing_result' && msg.data) {
      processResult(msg.data)
    }
    if (msg.type === 'new_call' && msg.call) {
      setCalls(prev => {
        // Dedup
        if (prev.some(c => c.call_id === msg.call.call_id)) return prev
        return [msg.call, ...prev]
      })
    }
    if (msg.type === 'call_ended' && msg.call_id) {
      setCalls(prev => prev.map(c =>
        c.call_id === msg.call_id ? { ...c, status: 'completed' } : c
      ))
    }
  }, [processResult])

  return { calls, activeCall, setActiveCall, loading, processResult, updateFromWS }
}
