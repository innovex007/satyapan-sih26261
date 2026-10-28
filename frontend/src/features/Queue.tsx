import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { api } from '../lib/api'
import { Card, EmptyState, PageHeader, RiskPill } from '../components/ui'

interface Row {
  id: string
  institution: string
  permanent_id: string
  category: string
  region: string
  submitted_at: string
  documents: number
  open_flags: number
  risk_lane: 'Green' | 'Amber' | 'Red' | null
  status: string
}
interface Meta {
  categories: string[]
  regions: string[]
  risk_lanes: string[]
}

const fmtDate = (iso: string) => new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' }).replaceAll('/', '-')

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}
      className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-[14px] text-slate-700">
      <option value="">{label}: all</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  )
}

const COLS = ['w-[152px]', '', 'w-[176px]', 'w-[96px]', 'w-[92px]', 'w-[92px]', 'w-[116px]', 'w-[84px]']

export function Queue() {
  const nav = useNavigate()
  const [meta, setMeta] = useState<Meta | null>(null)
  const [rows, setRows] = useState<Row[] | null>(null)
  const [q, setQ] = useState('')
  const [lane, setLane] = useState('')
  const [category, setCategory] = useState('')
  const [region, setRegion] = useState('')

  useEffect(() => { api<Meta>('/applications/meta').then(setMeta).catch(() => setMeta(null)) }, [])
  const query = useMemo(() => {
    const p = new URLSearchParams()
    if (q) p.set('q', q)
    if (lane) p.set('risk_lane', lane)
    if (category) p.set('category', category)
    if (region) p.set('region', region)
    return p.toString()
  }, [q, lane, category, region])
  useEffect(() => {
    const t = setTimeout(() => { api<Row[]>(`/applications?${query}`).then(setRows).catch(() => setRows([])) }, 150)
    return () => clearTimeout(t)
  }, [query])

  return (
    <>
      <PageHeader title="Application queue" subtitle="2026-27 cycle · highest risk first" />
      <Card className="!p-0">
        <div className="flex items-center gap-3 p-4 border-b border-[#E5E7EB]">
          <div className="relative w-72">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by ID or institution"
              className="w-full rounded-lg border border-[#E5E7EB] bg-white pl-9 pr-3 py-2 text-[14px] outline-none focus:border-navy" />
          </div>
          <Select label="Risk lane" value={lane} onChange={setLane} options={meta?.risk_lanes ?? []} />
          <Select label="Category" value={category} onChange={setCategory} options={meta?.categories ?? []} />
          <Select label="Region" value={region} onChange={setRegion} options={meta?.regions ?? []} />
          <span className="meta ml-auto">{rows ? `${rows.length} application${rows.length === 1 ? '' : 's'}` : ''}</span>
        </div>
        {rows && rows.length === 0 ? (
          <EmptyState title="No applications match" hint="Clear a filter, or run make seed if the database is empty." />
        ) : (
          <table className="w-full table-fixed text-left">
            <colgroup>{COLS.map((c, i) => <col key={i} className={c} />)}</colgroup>
            <thead>
              <tr className="meta">
                {['Application ID', 'Institution', 'Category', 'Submitted', 'Documents', 'Open flags', 'Risk lane', 'Status'].map((h, i) => (
                  <th key={h} className={`sticky top-0 z-10 bg-slate-50 border-b border-[#E5E7EB] px-3 py-3 font-medium whitespace-nowrap ${i >= 4 && i <= 5 ? 'text-right' : ''}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(rows ?? []).map((r) => (
                <tr key={r.id} tabIndex={0} onClick={() => nav(`/workspace/${r.id}`)} onKeyDown={(e) => e.key === 'Enter' && nav(`/workspace/${r.id}`)}
                  className="cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50 focus:bg-slate-50 outline-none">
                  <td className="px-3 py-3.5 font-medium text-navy truncate">{r.id}</td>
                  <td className="px-3 py-3.5 truncate" title={`${r.institution} (#${r.permanent_id})`}>{r.institution}</td>
                  <td className="px-3 py-3.5 truncate" title={r.category}>{r.category}</td>
                  <td className="px-3 py-3.5 text-slate-600 whitespace-nowrap">{fmtDate(r.submitted_at)}</td>
                  <td className="px-3 py-3.5 text-right tabular-nums">{r.documents}</td>
                  <td className="px-3 py-3.5 text-right tabular-nums text-slate-400">{r.risk_lane ? r.open_flags : '—'}</td>
                  <td className="px-3 py-3.5"><RiskPill lane={r.risk_lane} /></td>
                  <td className="px-3 py-3.5 text-slate-600">{r.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  )
}
