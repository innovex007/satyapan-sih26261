import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { Card, EmptyState, PageHeader, StatusChip } from '../components/ui'

type Kind = 'copy' | 'reshot' | null
interface Src { document_id: number; application_id: string; filename: string; label: string; flagged: boolean; twin_kind: Kind }
interface Match {
  document_id: number; application_id: string; filename: string; institution: string; permanent_id: string; cycle_label: string
  phash_distance: number; inliers: number | null; similarity_pct: number; kind: Kind; twin: boolean
}
interface Result {
  query: { document_id: number; application_id: string; institution: string; permanent_id: string; filename: string }
  thresholds: { phash_copy: number; phash_candidate: number; orb_min_inliers: number }
  matches: Match[]
}

const lines = (a: number, b: number) => `/api/twins/match.png?a=${a}&b=${b}`
const FILTERS: { key: 'all' | 'copy' | 'reshot'; label: string }[] = [{ key: 'all', label: 'All' }, { key: 'copy', label: 'Copied' }, { key: 'reshot', label: 'Re-shot' }]

// The type badge sits above the photos: amber = copied photo (hash catches it), purple = same room re-photographed (only keypoints catch it)
function TypeBadge({ m, t }: { m: Match; t: Result['thresholds'] }) {
  if (m.kind === 'copy')
    return (
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="rounded-full bg-[#FFF3D6] px-3 py-1 text-[13px] font-semibold text-[#9A6200]">Copied photo (edited copy)</span>
        <span className="text-[13px] text-slate-700">pHash distance {m.phash_distance}</span>
        <span className="meta">(copy threshold ≤ {t.phash_copy})</span>
      </div>
    )
  if (m.kind === 'reshot')
    return (
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="rounded-full bg-[#EFE6FB] px-3 py-1 text-[13px] font-semibold text-[#6A3FB5]">Same room, re-photographed</span>
        <span className="text-[13px] text-slate-700">{m.inliers} keypoint matches (threshold {t.orb_min_inliers})</span>
        <span className="meta">pHash distance {m.phash_distance} (hash alone would miss this)</span>
      </div>
    )
  return (
    <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className="rounded-full bg-slate-100 px-3 py-1 text-[13px] font-semibold text-slate-600">Not a match</span>
      <span className="text-[13px] text-slate-600">pHash distance {m.phash_distance}{m.inliers != null ? ` · ${m.inliers} keypoint matches (threshold ${t.orb_min_inliers})` : ''}</span>
    </div>
  )
}

function Pair({ q, m, t, big }: { q: Result['query']; m: Match; t: Result['thresholds']; big?: boolean }) {
  return (
    <Card dense className={big ? 'col-span-3' : ''}>
      <div className="flex items-start justify-between gap-3">
        <TypeBadge m={m} t={t} />
        {m.twin ? <StatusChip status="Manual review required" /> : <span className="meta shrink-0 pt-1">no flag</span>}
      </div>
      <img src={lines(q.document_id, m.document_id)} alt="matched keypoints" className="w-full rounded-lg border border-[#E5E7EB]" />
      <p className="meta mt-1.5">Sample photo · {q.application_id} (left) · {m.institution} #{m.permanent_id} (right)</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-purple-50 px-2.5 py-0.5 text-[12px] font-medium text-purple-800">Different institution</span>
        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[12px] text-slate-600">{m.cycle_label}</span>
      </div>
    </Card>
  )
}

export function TwinSearch() {
  const [params, setParams] = useSearchParams()
  const [sources, setSources] = useState<Src[]>([])
  const [filter, setFilter] = useState<'all' | 'copy' | 'reshot'>('all')
  const [res, setRes] = useState<Result | null>(null)
  const doc = params.get('doc')

  useEffect(() => { api<Src[]>('/twins/sources').then(setSources).catch(() => setSources([])) }, [])
  const options = useMemo(() => sources.filter((s) => filter === 'all' || s.twin_kind === filter), [sources, filter])
  useEffect(() => {  // default: the first image of the list (the hero re-shot on EoA-DEMO-0417), or the first one the filter allows
    if (options.length && !options.some((o) => String(o.document_id) === doc)) setParams({ doc: String(options[0].document_id) }, { replace: true })
  }, [options, doc, setParams])
  useEffect(() => { setRes(null); if (doc) api<Result>(`/twins?document_id=${doc}&limit=4`).then(setRes).catch(() => setRes(null)) }, [doc])

  const count = (k: 'all' | 'copy' | 'reshot') => sources.filter((s) => k === 'all' || s.twin_kind === k).length
  return (
    <>
      <PageHeader tight title="Twin search" subtitle="Nearest images from other institutions, including the archive · pHash first, then keypoint verification" actions={
        <div className="flex items-center gap-3">
          <div className="inline-flex rounded-lg border border-[#E5E7EB] bg-white p-0.5" role="group" aria-label="Match type">
            {FILTERS.map((f) => (
              <button key={f.key} onClick={() => setFilter(f.key)}
                className={`whitespace-nowrap rounded-md px-3 py-1.5 text-[13px] font-medium ${filter === f.key ? 'bg-navy text-white' : 'text-slate-600 hover:bg-slate-50'}`}>
                {f.label} <span className={filter === f.key ? 'text-white/70' : 'text-slate-400'}>{count(f.key)}</span>
              </button>
            ))}
          </div>
          <select value={doc ?? ''} onChange={(e) => setParams({ doc: e.target.value })} className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-[14px] max-w-[300px]">
            {options.map((s) => <option key={s.document_id} value={s.document_id}>{s.flagged ? '⚑ ' : ''}{s.label}</option>)}
          </select>
        </div>} />
      {!res ? <Card><EmptyState title="Searching…" hint="Comparing this image with every other institution's photos." /></Card> : (
        <div className="grid grid-cols-3 gap-6">
          {res.matches.map((m, i) => <Pair key={m.document_id} q={res.query} m={m} t={res.thresholds} big={i === 0} />)}
        </div>
      )}
    </>
  )
}
