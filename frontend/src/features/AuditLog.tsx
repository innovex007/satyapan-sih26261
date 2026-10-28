import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'
import { api } from '../lib/api'
import { Card, EmptyState, PageHeader } from '../components/ui'

interface Ev { id: number; ts: string; actor: string; role: string; action: string; entity: string; hash: string; prev_hash: string }
interface Page { total: number; events: Ev[] }
interface Verify { ok: boolean; events: number; broken_at: number | null }
const SIZE = 20

export function AuditLog() {
  const [page, setPage] = useState(0)
  const [data, setData] = useState<Page | null>(null)
  const [v, setV] = useState<Verify | null>(null)
  const load = useCallback(() => { api<Page>(`/audit/page?limit=${SIZE}&offset=${page * SIZE}`).then(setData).catch(() => setData({ total: 0, events: [] })) }, [page])
  useEffect(load, [load])
  const verify = async () => setV(await api<Verify>('/audit/verify', { method: 'POST' }))
  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / SIZE))
  return (
    <>
      <PageHeader tight title="Audit log" subtitle="Hash-chained record of every pipeline run and officer action" actions={
        <div className="flex items-center gap-3">
          {v && (v.ok
            ? <span className="inline-flex items-center gap-1.5 rounded-full bg-[#E3F5E8] px-3 py-1.5 text-[13px] font-medium text-[#1E7B3A]"><CheckCircle2 className="h-4 w-4" />Chain intact – {v.events} events</span>
            : <span className="inline-flex items-center gap-1.5 rounded-full bg-[#FDE3E3] px-3 py-1.5 text-[13px] font-medium text-[#C62828]"><XCircle className="h-4 w-4" />Chain broken at event #{v.broken_at}</span>)}
          <button onClick={verify} className="rounded-lg bg-navy px-4 py-2 text-[14px] font-medium text-white">Verify integrity</button>
        </div>} />
      <Card className="!p-0">
        {data && data.events.length === 0 ? <EmptyState title="No events yet" hint="Run the pipeline to create events." /> : (
          <table className="w-full table-fixed text-left text-[13px]">
            <colgroup><col className="w-[150px]" /><col className="w-[110px]" /><col className="w-[150px]" /><col className="w-[230px]" /><col /><col className="w-[110px]" /></colgroup>
            <thead><tr className="meta">{['Time', 'Actor', 'Role', 'Action', 'Entity', 'Hash'].map((h) => <th key={h} className="sticky top-0 bg-slate-50 border-b border-[#E5E7EB] px-3 py-3 font-medium">{h}</th>)}</tr></thead>
            <tbody>
              {(data?.events ?? []).map((e) => (
                <tr key={e.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-3 py-2.5 whitespace-nowrap text-slate-600">{new Date(e.ts).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
                  <td className="px-3 py-2.5 truncate">{e.actor}</td><td className="px-3 py-2.5 truncate">{e.role}</td>
                  <td className="px-3 py-2.5 truncate font-medium text-slate-800">{e.action}</td><td className="px-3 py-2.5 truncate" title={e.entity}>{e.entity}</td>
                  <td className="px-3 py-2.5 font-mono text-[12px] text-slate-500" title={`prev ${e.prev_hash}`}>{e.hash}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="flex items-center justify-between gap-3 p-3 border-t border-[#E5E7EB] meta">
          <span>{data?.total ?? 0} events, newest first</span>
          <span className="flex items-center gap-3">
            <button disabled={page === 0} onClick={() => setPage(page - 1)} className="rounded border border-[#E5E7EB] px-3 py-1 disabled:opacity-40">Previous</button>
            Page {page + 1} of {pages}
            <button disabled={page + 1 >= pages} onClick={() => setPage(page + 1)} className="rounded border border-[#E5E7EB] px-3 py-1 disabled:opacity-40">Next</button>
          </span>
        </div>
      </Card>
    </>
  )
}
