import { useState, useEffect, useCallback } from 'react'
import { Routes, Route, useNavigate } from 'react-router-dom'
import Header from './components/Header'
import Operations from './pages/Operations'
import MapPage from './pages/MapPage'
import AudioTest from './pages/AudioTest'
import Analytics from './pages/Analytics'
import Demo from './pages/Demo'
import DatabaseViewer from './pages/DatabaseViewer'
import { useWebSocket } from './hooks/useWebSocket'
import { useCallState } from './hooks/useCallState'
import { API_BASE } from './config'

export default function App() {
  const navigate = useNavigate()
  const { messages, connected, sendMessage } = useWebSocket()
  const { calls, activeCall, setActiveCall, processResult, updateFromWS } = useCallState()
  const [takeover, setTakeover] = useState(false)

  useEffect(() => {
    if (messages.length === 0) return
    const latest = messages[messages.length - 1]
    updateFromWS(latest)
  }, [messages])

  const runScenario = useCallback(async (id) => {
    try {
      const res = await fetch(API_BASE + `/api/demo/scenario/${id}`, { method: 'POST' })
      const data = await res.json()
      processResult(data.result)
      navigate('/')
    } catch {
      processResult(MOCK[id]())
      navigate('/')
    }
  }, [processResult, navigate])

  const handleTakeover = useCallback(async (callId) => {
    setTakeover(prev => !prev)
    try {
      await fetch(API_BASE + `/api/calls/${callId}/takeover`, { method: 'POST' })
    } catch {}
  }, [])

  const handleVerify = useCallback(async (callId, confirmed, corrections) => {
    try {
      await fetch(API_BASE + '/api/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ call_id: callId, confirmed, partial_corrections: corrections })
      })
    } catch {}
  }, [])

  return (
    <>
      <div className={`critical-overlay ${takeover ? 'show' : ''}`}></div>
      <div className={`takeover-banner ${takeover ? 'show' : ''}`}>⚠ HUMAN TAKEOVER ACTIVE — AGENT IN CONTROL ⚠</div>
      <Header connected={connected} />
      <Routes>
        <Route path="/" element={
          <Operations
            calls={calls}
            activeCall={activeCall}
            setActiveCall={setActiveCall}
            connected={connected}
            runScenario={runScenario}
            takeover={takeover}
            onTakeover={handleTakeover}
            onVerify={handleVerify}
          />
        } />
        <Route path="/map" element={<MapPage calls={calls} />} />
        <Route path="/test" element={<AudioTest processResult={processResult} />} />
        <Route path="/analytics" element={<Analytics calls={calls} />} />
        <Route path="/demo" element={<Demo runScenario={runScenario} />} />
        <Route path="/db" element={<DatabaseViewer />} />
      </Routes>
    </>
  )
}

/* ── Mock Data for offline ── */
const MOCK = {
  1: () => ({
    call_id:'CALL-DEMO01',timestamp:new Date().toISOString(),
    transcript:{text:'ನಮಸ್ಕಾರ ಸಾರ್, ನಾನು ರಾಜಾಜಿನಗರದಲ್ಲಿ ಇದ್ದೀನಿ. ನಮ್ಮ ಏರಿಯಾದಲ್ಲಿ ರಸ್ತೆಯಲ್ಲಿ ದೊಡ್ಡ ಗುಂಡಿ ಬಿದ್ದಿದೆ.',language:'kn',asr_latency_ms:340},
    keywords:{total_hits:2,tier_counts:{1:0,2:0,3:2},hits:[{keyword:'ರಸ್ತೆ',tier:3,language:'kn'},{keyword:'ಗುಂಡಿ',tier:3,language:'kn'}],severity:'LOW'},
    nlp:{intent:{category:'infrastructure',subcategory:'road_issue',confidence:.92},entities:{location:'Rajajinagar, Bengaluru',lat:12.9906,lng:77.5527},summary:'Citizen reporting large pothole on road in Rajajinagar area, unattended for 3 days.',sentiment:{overall:'concerned',negative:.25},urgency:'medium',suggested_action:'Route to BBMP road maintenance department'},
    emotion:{panic:.05,fear:.08,distress:.15,calm:.72},
    utcs:{score:145,level:'LOW',color:'#22c55e',action:'NORMAL_PROCESSING',breakdown:{keywords:30,nlp:25,emotion:15,noise:0}},
  }),
  2: () => ({
    call_id:'CALL-DEMO02',timestamp:new Date().toISOString(),
    transcript:{text:'bachao bachao, wo mujhe maar raha hai! Please help karo, bahut darr lag raha hai.',language:'hi',asr_latency_ms:210},
    keywords:{total_hits:5,tier_counts:{1:3,2:2,3:0},hits:[{keyword:'bachao',tier:1},{keyword:'maar raha hai',tier:1},{keyword:'help karo',tier:1},{keyword:'darr',tier:2},{keyword:'police',tier:2}],severity:'CRITICAL'},
    nlp:{intent:{category:'emergency',subcategory:'immediate_danger',confidence:.97},entities:{location:'Koramangala, Bengaluru',lat:12.9352,lng:77.6245},summary:'Citizen in immediate physical danger — being beaten, requesting urgent police help.',sentiment:{overall:'panicked',negative:.95},urgency:'critical',suggested_action:'IMMEDIATE DISPATCH — Police + Ambulance'},
    emotion:{panic:.92,fear:.85,distress:.88,calm:.05},
    utcs:{score:750,level:'CRITICAL',color:'#ef4444',action:'IMMEDIATE_TAKEOVER',breakdown:{keywords:675,nlp:250,emotion:220,noise:0}},
  }),
  3: () => ({
    call_id:'CALL-DEMO03',timestamp:new Date().toISOString(),
    transcript:{text:'...help...',language:'en',asr_latency_ms:150},
    keywords:{total_hits:1,tier_counts:{1:1,2:0,3:0},hits:[{keyword:'help',tier:1}],severity:'CRITICAL'},
    nlp:{intent:{category:'emergency',subcategory:'silent_emergency',confidence:.65},entities:{location:'Jayanagar, Bengaluru',lat:12.9250,lng:77.5938},summary:'Silent emergency — citizen barely able to speak. Background audio analysis required.',sentiment:{overall:'distressed',negative:.8},urgency:'critical',suggested_action:'IMMEDIATE ATTENTION — Silent emergency protocol'},
    emotion:{panic:.4,fear:.6,distress:.7,calm:.1},
    utcs:{score:620,level:'CRITICAL',color:'#ef4444',action:'IMMEDIATE_TAKEOVER',breakdown:{keywords:200,nlp:150,emotion:100,noise:280}},
    noise_analysis:{screaming:.85,struggle:.72,crying:.45,dominant_type:'screaming',is_threat:true,confidence:.85},
  }),
}
