import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Copy, X } from 'lucide-react'
import { api } from '../lib/api'
import { STATUSES, type Status } from '../lib/status'
import { Card, EmptyState, PageHeader, StatusChip } from '../components/ui'

interface Row {
  id: number; application_id: string; institution: string; document_id: number; filename: string; document: string
  channel: string; channel_label: string; result: Status; requested_at: string; simulated: boolean
  request: unknown; response: unknown; letter: string | null
}
const PAGE = 20
const fmt = (iso: string) => new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })

export function SourceChecks() {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [channel, setChannel] = useState('')
  const [result, setResult] = useState('')
  const [page, setPage] = useState(0)
  const [open, setOpen] = useState<Row | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => { api<Row[]>('/sources').then(setRows).catch(() => setRows([])) }, [])
  const channels = useMemo(() => [...new Map((rows ?? []).map((r) => [r.channel, r.channel_label])).entries()], [rows])
  const list = (rows ?? []).filter((r) => (!channel || r.channel === channel) && (!result || r.result === result))
  const shown = list.slice(page * PAGE, page * PAGE + PAGE)
  useEffect(() => setPage(0), [channel, result])

  const copy = async (t: string) => { try { await navigator.clipboard.writeText(t); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch { /* ignore */ } }
  const sel = 'rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-[14px] text-slate-700'
  return (
    <>
      <PageHeader tight title="Source checks" subtitle="Simulated source (prototype) · every check the pipeline ran for the 2026-27 cycle" />
      <Card className="!p-0">
        <div className="flex items-center gap-3 p-4 border-b border-[#E5E7EB]">
          <select className={sel} value={channel} onChange={(e) => setChannel(e.target.value)} aria-label="Channel">
            <option value="">Channel: all</option>{channels.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select className={sel} value={result} onChange={(e) => setResult(e.target.value)} aria-label="Result">
            <option value="">Result: all</option>{STATUSES.map((s) => <option key={s}>{s}</option>)}
          </select>
          <span className="meta ml-auto">{list.length} check{list.length === 1 ? '' : 's'}</span>
        </div>
        {rows && list.length === 0 ? <EmptyState title="No checks match" hint="Clear a filter." /> : (
          <table className="w-full table-fixed text-left">
            <colgroup><col className="w-[150px]" /><col /><col className="w-[190px]" /><col className="w-[170px]" /><col className="w-[120px]" /></colgroup>
            <thead><tr className="meta">{['Application', 'Document', 'Channel', 'Result', 'Time'].map((h) => (
              <th key={h} className="sticky top-0 bg-slate-50 border-b border-[#E5E7EB] px-3 py-3 font-medium whitespace-nowrap">{h}</th>))}</tr></thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id} onClick={() => { setOpen(r); setCopied(false) }} className="cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="px-3 py-3 font-medium text-navy truncate">{r.application_id}</td>
                  <td className="px-3 py-3 truncate" title={r.filename}>{r.document} <span className="meta">· {r.filename}</span></td>
                  <td className="px-3 py-3 truncate">{r.channel_label}</td>
                  <td className="px-3 py-3"><StatusChip status={r.result} /></td>
                  <td className="px-3 py-3 text-slate-600 whitespace-nowrap">{fmt(r.requested_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="flex items-center justify-end gap-3 p-3 border-t border-[#E5E7EB] meta">
          <button disabled={page === 0} onClick={() => setPage(page - 1)} className="rounded border border-[#E5E7EB] px-3 py-1 disabled:opacity-40">Previous</button>
          Page {page + 1} of {Math.max(1, Math.ceil(list.length / PAGE))}
          <button disabled={(page + 1) * PAGE >= list.length} onClick={() => setPage(page + 1)} className="rounded border border-[#E5E7EB] px-3 py-1 disabled:opacity-40">Next</button>
        </div>
      </Card>

      {open && (
        <div className="fixed inset-0 z-40 bg-slate-900/20" onClick={() => setOpen(null)}>
          <aside className="absolute right-0 top-0 h-full w-[460px] overflow-y-auto bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-3">
              <div><h2>{open.document}</h2><p className="meta">{open.application_id} · {open.filename}</p></div>
              <button onClick={() => setOpen(null)}><X className="h-4 w-4 text-slate-400" /></button>
            </div>
            <div className="flex items-center gap-2 mb-4"><StatusChip status={open.result} /><span className="meta">{open.channel_label}{open.simulated ? ' · Simulated source (prototype)' : ''}</span></div>
            <Link to={`/workspace/${open.application_id}`} className="text-[13px] font-medium text-navy">Open application workspace →</Link>
            <h3 className="mt-5 mb-1 text-[13px] font-semibold text-slate-700">Request</h3>
            <pre className="overflow-auto rounded-lg bg-slate-50 p-3 text-[12px] leading-5">{JSON.stringify(open.request, null, 2)}</pre>
            <h3 className="mt-4 mb-1 text-[13px] font-semibold text-slate-700">Response</h3>
            <pre className="overflow-auto rounded-lg bg-slate-50 p-3 text-[12px] leading-5">{JSON.stringify(open.response, null, 2)}</pre>
            {open.letter && (
              <>
                <div className="mt-5 mb-1 flex items-center justify-between">
                  <h3 className="text-[13px] font-semibold text-slate-700">Auto-drafted verification letter</h3>
                  <button onClick={() => copy(open.letter!)} className="inline-flex items-center gap-1 rounded-lg border border-[#E5E7EB] px-2.5 py-1 text-[12px] font-medium"><Copy className="h-3.5 w-3.5" />{copied ? 'Copied' : 'Copy'}</button>
                </div>
                <pre className="whitespace-pre-wrap rounded-lg border border-dashed border-slate-300 bg-white p-3 text-[12px] leading-5 text-slate-700">{open.letter}</pre>
              </>
            )}
          </aside>
        </div>
      )}
    </>
  )
}
