import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '../config'

export default function DatabaseViewer() {
  const [tables, setTables] = useState([])
  const [dbInfo, setDbInfo] = useState({})
  const [activeTable, setActiveTable] = useState(null)
  const [rows, setRows] = useState([])
  const [totalRows, setTotalRows] = useState(0)
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)

  const fetchTables = useCallback(async () => {
    try {
      const res = await fetch(API_BASE + '/api/db/tables')
      const data = await res.json()
      setTables(data.tables || [])
      setDbInfo({ path: data.db_path, size: data.db_size_kb })
    } catch (e) {
      console.error('Failed to fetch tables:', e)
    }
  }, [])

  const fetchRows = useCallback(async (tableName) => {
    setLoading(true)
    try {
      const res = await fetch(API_BASE + `/api/db/table/${tableName}?limit=100`)
      const data = await res.json()
      setRows(data.rows || [])
      setTotalRows(data.total || 0)
      setActiveTable(tableName)
    } catch (e) {
      console.error('Failed to fetch rows:', e)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    fetchTables()
  }, [fetchTables])

  useEffect(() => {
    if (!autoRefresh || !activeTable) return
    const interval = setInterval(() => {
      fetchRows(activeTable)
      fetchTables()
    }, 3000)
    return () => clearInterval(interval)
  }, [autoRefresh, activeTable, fetchRows, fetchTables])

  const formatValue = (val) => {
    if (val === null || val === undefined) return '—'
    if (typeof val === 'string' && val.startsWith('{')) {
      try {
        const obj = JSON.parse(val)
        return JSON.stringify(obj, null, 1).slice(0, 200)
      } catch { return val.slice(0, 200) }
    }
    if (typeof val === 'string' && val.length > 100) return val.slice(0, 100) + '…'
    return String(val)
  }

  const getRowClass = (row) => {
    if (row.utcs_level === 'CRITICAL' || row.severity === 'critical') return 'row-critical'
    if (row.utcs_level === 'HIGH' || row.severity === 'high') return 'row-high'
    if (row.status === 'active') return 'row-active'
    return ''
  }

  return (
    <div className="db-viewer">
      <div className="db-header">
        <div>
          <h1>🗄️ DATABASE VIEWER</h1>
          <div className="subtitle">Live SQLite database — {dbInfo.path || 'Loading...'} ({dbInfo.size || 0} KB)</div>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--muted)' }}>
            <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
            AUTO-REFRESH (3s)
          </label>
          <button className="btn btn-confirm" onClick={() => { fetchTables(); if (activeTable) fetchRows(activeTable) }}
            style={{ padding: '6px 14px', fontSize: '10px' }}>
            🔄 REFRESH
          </button>
        </div>
      </div>

      {/* Table selector */}
      <div className="db-tables-grid">
        {tables.map(t => (
          <div key={t.name}
            className={`db-table-card ${activeTable === t.name ? 'active' : ''}`}
            onClick={() => fetchRows(t.name)}>
            <div className="db-table-name">{t.name}</div>
            <div className="db-table-count">{t.row_count} rows</div>
            <div className="db-table-cols">{t.columns.length} columns</div>
          </div>
        ))}
      </div>

      {/* Table data */}
      {activeTable && (
        <div className="db-data-panel">
          <div className="db-data-header">
            <h3>{activeTable.toUpperCase()} — {totalRows} total rows</h3>
            {loading && <span className="db-loading">Loading...</span>}
          </div>

          {rows.length > 0 ? (
            <div className="db-table-wrapper">
              <table className="db-table">
                <thead>
                  <tr>
                    {Object.keys(rows[0]).map(col => (
                      <th key={col}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={i} className={getRowClass(row)}>
                      {Object.values(row).map((val, j) => (
                        <td key={j} title={typeof val === 'string' ? val : ''}>
                          {formatValue(val)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="db-empty">No data in this table yet. Process some audio/text to populate it.</div>
          )}
        </div>
      )}

      {/* Schema info */}
      {activeTable && tables.length > 0 && (
        <div className="db-schema">
          <h4>Schema: {activeTable}</h4>
          <div className="db-schema-cols">
            {tables.find(t => t.name === activeTable)?.columns.map((col, i) => (
              <div key={i} className="db-schema-col">
                <span className="col-name">{col.name}</span>
                <span className="col-type">{col.type}</span>
                {col.nullable && <span className="col-null">nullable</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
