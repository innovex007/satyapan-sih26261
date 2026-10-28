import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ChevronDown, ChevronRight, FileText, GitCompare, Image as ImageIcon, X } from 'lucide-react'
import { api } from '../lib/api'
import { STATUS_STYLE, type Status } from '../lib/status'
import type { DocItem, Evidence, Finding, Workspace as WS } from '../lib/types'
import { Card, EmptyState, PageHeader, RiskPill, StatusChip } from '../components/ui'
import { DocViewer, type Box } from '../components/DocViewer'

const TABS: { key: string; label: string; types: string[] | null }[] = [
  { key: 'all', label: 'All', types: null },
  { key: 'cross', label: 'Cross-checks', types: ['completeness', 'expiry', 'contradiction', 'faculty'] },
  { key: 'twin', label: 'Twins', types: ['twin'] },
  { key: 'forensic', label: 'Forensics', types: ['forensic'] },
  { key: 'source', label: 'Source checks', types: ['source'] },
]

function useSize(ref: React.RefObject<HTMLElement | null>) {
  const [s, setS] = useState({ w: 0, h: 0 })
  useLayoutEffect(() => {
    if (!ref.current) return
    const el = ref.current
    const ro = new ResizeObserver(() => setS({ w: el.clientWidth, h: el.clientHeight }))
    ro.observe(el)
    setS({ w: el.clientWidth, h: el.clientHeight })
    return () => ro.disconnect()
  }, [ref])
  return s
}

const colorOf = (status: Status) => STATUS_STYLE[status].fg

// normalised, human-readable value for the main chip; the raw OCR/text-layer string is shown small beneath it
function shown(e: Evidence): string {
  if (!e.normalised) return e.value
  if (e.key === 'land_area_acres') return `${e.normalised} acres`
  if (/^\d{4}-\d{2}-\d{2}$/.test(e.normalised)) return e.normalised.split('-').reverse().join('-')
  return e.value
}

function docIcon(d: DocItem) {
  return d.kind === 'image' ? <ImageIcon className="h-4 w-4 text-slate-400 shrink-0" /> : <FileText className="h-4 w-4 text-slate-400 shrink-0" />
}

// ---------------------------------------------------------------------------------------------
function DocList({ ws, selected, onSelect }: { ws: WS; selected: number | null; onSelect: (d: DocItem) => void }) {
  const [closed, setClosed] = useState<Record<string, boolean>>({})
  return (
    <div className="space-y-4">
      {ws.groups.map((g) => (
        <div key={g.group}>
          <button className="flex w-full items-center gap-1 text-left meta font-medium uppercase tracking-wide mb-1" onClick={() => setClosed({ ...closed, [g.group]: !closed[g.group] })}>
            {closed[g.group] ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {g.group} <span className="ml-auto font-normal normal-case">{g.documents.length}</span>
          </button>
          {!closed[g.group] && g.documents.map((d) => (
            <button key={d.id} onClick={() => onSelect(d)} title={d.filename}
              className={`w-full text-left rounded-lg px-2.5 py-2 mb-1 border ${selected === d.id ? 'border-navy bg-slate-50' : 'border-transparent hover:bg-slate-50'}`}>
              <div className="flex items-center gap-2">
                {docIcon(d)}
                <span className="truncate text-[13px] font-medium text-slate-800">{d.label}</span>
              </div>
              <div className="flex items-center gap-2 mt-1 pl-6">
                <StatusChip status={d.status} />
              </div>
            </button>
          ))}
        </div>
      ))}
      {ws.missing.length > 0 && (
        <div>
          <p className="meta font-medium uppercase tracking-wide mb-1">Missing · {ws.missing.length}</p>
          {ws.missing.map((m) => (
            <div key={m.doc_type} className="rounded-lg border border-dashed border-slate-300 px-2.5 py-2 mb-1 text-[13px] text-slate-500">
              {m.label}
              <p className="meta">Required, not uploaded</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------------------------
function FindingCard({ f, active, onSelect, onCompare, onAction }: {
  f: Finding; active: boolean; onSelect: () => void; onCompare?: () => void; onAction: (a: 'accept' | 'dismiss' | 'clarify') => void
}) {
  const done = f.officer_action !== 'none'
  const sources = f.evidence.filter((e) => e.filename).map((e) => e.filename).slice(0, 2).join(' · ')
  const simulated = f.check_type === 'source' || f.rule_id.includes('SRC')
  return (
    <div onClick={onSelect} className={`rounded-xl border p-4 mb-3 cursor-pointer ${active ? 'border-navy shadow-card' : 'border-[#E5E7EB] hover:border-slate-300'} ${done ? 'opacity-70' : ''}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2">
          <StatusChip status={f.status} />
          {/SHAREDLAND|TIMELINE/.test(f.rule_id) && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-amber-800">NEW</span>}
        </span>
        <span className="meta">{f.severity} severity</span>
      </div>
      <p className="mt-2 text-[13px] leading-5 text-slate-800">{f.reason}</p>
      <div className="mt-2 flex items-center gap-2">
        <div className="h-1.5 flex-1 rounded-full bg-slate-100"><div className="h-1.5 rounded-full bg-navy" style={{ width: `${f.confidence * 100}%` }} /></div>
        <span className="meta tabular-nums">{Math.round(f.confidence * 100)}% confidence</span>
      </div>
      <p className="meta mt-2">Rule {f.rule_id.split('/')[1]} · Source: {sources || 'application checklist'}{simulated ? ' · Simulated source (prototype)' : ''}</p>
      <p className="mt-2 text-[12px] leading-[18px] text-slate-600"><span className="font-medium text-slate-700">How to clear: </span>{f.how_to_clear}</p>
      {onCompare && (
        <button onClick={(e) => { e.stopPropagation(); onCompare() }} className="mt-2 inline-flex items-center gap-1 text-[12px] font-medium text-navy">
          <GitCompare className="h-3.5 w-3.5" /> Compare side by side
        </button>
      )}
      <div className="mt-3 flex flex-wrap gap-2" onClick={(e) => e.stopPropagation()}>
        {done ? (
          <span className="meta">Officer: {f.officer_action.replace('_', ' ')}{f.officer_note ? ` — ${f.officer_note}` : ''}</span>
        ) : (
          <>
            <button onClick={() => onAction('accept')} className="rounded-lg bg-navy px-3 py-1.5 text-[12px] font-medium text-white">Accept flag</button>
            <button onClick={() => onAction('dismiss')} className="rounded-lg border border-[#E5E7EB] px-3 py-1.5 text-[12px] font-medium text-slate-700">Dismiss with reason</button>
            <button onClick={() => onAction('clarify')} className="rounded-lg border border-[#E5E7EB] px-3 py-1.5 text-[12px] font-medium text-slate-700">Request clarification</button>
          </>
        )}
      </div>
    </div>
  )
}

function ActionDialog({ kind, onCancel, onSubmit }: { kind: 'dismiss' | 'clarify'; onCancel: () => void; onSubmit: (note: string) => void }) {
  const [note, setNote] = useState('')
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/30" onClick={onCancel}>
      <div className="w-[440px] rounded-xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-2">
          <h2>{kind === 'dismiss' ? 'Dismiss with reason' : 'Request clarification'}</h2>
          <button onClick={onCancel}><X className="h-4 w-4 text-slate-400" /></button>
        </div>
        <p className="meta mb-3">{kind === 'dismiss' ? 'A reason is required and is written to the audit log.' : 'The note is recorded and sent with the clarification request.'}</p>
        <textarea autoFocus value={note} onChange={(e) => setNote(e.target.value)} rows={4}
          className="w-full rounded-lg border border-[#E5E7EB] p-3 text-[14px] outline-none focus:border-navy" placeholder="Reason" />
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onCancel} className="rounded-lg border border-[#E5E7EB] px-4 py-2 text-[13px]">Cancel</button>
          <button disabled={!note.trim()} onClick={() => onSubmit(note)} className="rounded-lg bg-navy px-4 py-2 text-[13px] font-medium text-white disabled:opacity-40">Submit</button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------------------------
function Compare({ ws, finding, left, right, onClose }: { ws: WS; finding: Finding; left: Evidence; right: Evidence; onClose: () => void }) {
  const wrap = useRef<HTMLDivElement>(null)
  const body = useRef<HTMLDivElement>(null)
  const { w, h } = useSize(body)
  const [line, setLine] = useState<{ x1: number; y1: number; x2: number; y2: number } | null>(null)
  const [ready, setReady] = useState(0)
  const all = [...ws.groups.flatMap((g) => g.documents), ...(ws.external ?? [])]
  const dl = all.find((d) => d.id === left.document_id)!
  const dr = all.find((d) => d.id === right.document_id)!
  const color = colorOf(finding.status)
  const paneW = Math.max(200, Math.min((w - 64) / 2, (h - 96) / 1.414))

  const measure = useCallback(() => {
    const c = wrap.current
    if (!c) return
    const a = c.querySelector('[data-hl="L"]') as HTMLElement | null
    const b = c.querySelector('[data-hl="R"]') as HTMLElement | null
    if (!a || !b) return setLine(null)
    const cr = c.getBoundingClientRect(), ar = a.getBoundingClientRect(), br = b.getBoundingClientRect()
    setLine({ x1: ar.right - cr.left, y1: ar.top + ar.height / 2 - cr.top, x2: br.left - cr.left, y2: br.top + br.height / 2 - cr.top })
  }, [])
  useEffect(() => { const t = setTimeout(measure, 120); return () => clearTimeout(t) }, [ready, paneW, measure])

  const pane = (d: DocItem, ev: Evidence, tag: 'L' | 'R') => (
    <div className="flex flex-col items-center min-w-0">
      <p className="text-[13px] font-medium text-slate-800">{d.label}</p>
      <p className="meta max-w-full truncate">{d.filename} · page {ev.page}</p>
      <span className="mt-1.5 rounded-full px-3 py-0.5 text-[13px] font-semibold" style={{ color, background: `${color}1A` }}>{shown(ev)}</span>
      <span className="mb-1.5 text-[11px] leading-4 text-slate-400">OCR text: “{ev.value}”</span>
      <DocViewer docId={d.id} kind={d.kind} pages={d.pages} page={ev.page} width={paneW} onReady={() => setReady((r) => r + 1)}
        boxes={[{ bbox: ev.bbox, color, tag, label: ev.value }]} />
    </div>
  )
  return (
    <Card className="h-full flex flex-col !p-5">
      <div className="flex items-center justify-between mb-3 shrink-0">
        <div>
          <h2>Side-by-side compare</h2>
          <p className="meta">The highlighted values are the evidence for this flag; the line joins the two regions.</p>
        </div>
        <button onClick={onClose} className="rounded-lg border border-[#E5E7EB] px-3 py-1.5 text-[12px] font-medium">Close compare</button>
      </div>
      <div ref={body} className="flex-1 min-h-0 overflow-hidden">
        <div ref={wrap} className="relative grid grid-cols-2 gap-12 justify-items-center">
          {pane(dl, left, 'L')}
          {pane(dr, right, 'R')}
          {line && (
            <svg className="absolute inset-0 pointer-events-none" width="100%" height="100%" style={{ overflow: 'visible' }}>
              <path d={`M ${line.x1} ${line.y1} C ${line.x1 + 40} ${line.y1}, ${line.x2 - 40} ${line.y2}, ${line.x2} ${line.y2}`} stroke={color} strokeWidth={2} fill="none" strokeDasharray="5 4" />
              <circle cx={line.x1} cy={line.y1} r={4} fill={color} />
              <circle cx={line.x2} cy={line.y2} r={4} fill={color} />
            </svg>
          )}
        </div>
      </div>
    </Card>
  )
}

// ---------------------------------------------------------------------------------------------
export function Workspace() {
  const { id } = useParams()
  const nav = useNavigate()
  const [params, setParams] = useSearchParams()
  const [ws, setWs] = useState<WS | null>(null)
  const [selDoc, setSelDoc] = useState<number | null>(null)
  const [selFinding, setSelFinding] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const [tab, setTab] = useState('all')
  const [dialog, setDialog] = useState<{ f: Finding; kind: 'dismiss' | 'clarify' } | null>(null)
  const viewer = useRef<HTMLDivElement>(null)
  const vsize = useSize(viewer)

  const load = useCallback(() => {
    if (!id) return
    api<WS>(`/applications/${id}/workspace`).then((d) => {
      setWs(d)
      setSelDoc((cur) => cur ?? d.groups[0]?.documents[0]?.id ?? null)
    }).catch(() => setWs(null))
  }, [id])
  useEffect(() => { setWs(null); setSelDoc(null); setSelFinding(null); load() }, [load])

  const finding = ws?.findings.find((f) => f.id === selFinding) ?? null
  const compareEv = useMemo(() => finding?.evidence.filter((e) => e.document_id && (ws?.groups.some((g) => g.documents.some((d) => d.id === e.document_id)) || ws?.external?.some((d) => d.id === e.document_id))).slice(0, 2) ?? [], [finding, ws])
  const comparing = params.get('compare') === '1' && finding && compareEv.length === 2

  const selectFinding = (f: Finding) => {
    setSelFinding(f.id)
    const e = f.evidence.find((x) => x.document_id && ws?.groups.some((g) => g.documents.some((d) => d.id === x.document_id)))
    if (e?.document_id) { setSelDoc(e.document_id); setPage(e.page || 1) }
  }
  const submit = async (f: Finding, action: 'accept' | 'dismiss' | 'clarify', note = '') => {
    await api(`/findings/${f.id}/action`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, note, role: localStorage.getItem('role') ?? 'Scrutiny officer' }) })
    setDialog(null)
    load()
  }

  if (!id) return <Navigate to="/workspace/EoA-DEMO-0417" replace />
  if (!ws) return <><PageHeader title={id} subtitle="Loading…" /><Card><div className="h-40 animate-pulse rounded-lg bg-slate-50" /></Card></>

  const docs = ws.groups.flatMap((g) => g.documents)
  const cur = docs.find((d) => d.id === selDoc) ?? null
  const boxes: Box[] = finding && cur
    ? finding.evidence.filter((e) => e.document_id === cur.id && e.bbox.length === 4).map((e) => ({ bbox: e.bbox, color: colorOf(finding.status), label: e.value, page: e.page } as Box))
    : []
  const tabTypes = TABS.find((t) => t.key === tab)!.types
  const list = ws.findings.filter((f) => !tabTypes || tabTypes.includes(f.check_type))
  const open = ws.findings.filter((f) => f.officer_action === 'none').length
  const canCompare = (f: Finding) => f.evidence.filter((e) => e.document_id).length >= 2
  const startCompare = (f: Finding) => { setSelFinding(f.id); setParams({ compare: '1' }) }
  const viewW = Math.max(240, Math.min(vsize.w - 8, ((vsize.h || 560) - 90) / 1.414 * 1.9))

  return (
    <div className="flex flex-col h-[calc(100vh-26px-64px-64px)] min-h-[520px]">
      <div className="flex items-start justify-between gap-6 mb-4 shrink-0">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="truncate">{ws.application.id}</h1>
            {ws.application.risk_lane && <RiskPill lane={ws.application.risk_lane} />}
            {ws.is_archive && <span className="rounded-full bg-purple-50 px-2.5 py-0.5 text-[12px] font-medium text-purple-800">{ws.application.cycle_label}</span>}
          </div>
          <p className="meta mt-1 truncate">{ws.institution.name} (#{ws.institution.permanent_id}) · {ws.application.category} · Session {ws.application.academic_session} · {open} open flag{open === 1 ? '' : 's'}</p>
        </div>
        <Link to="/queue" className="meta shrink-0 mt-2 hover:text-navy">← Application queue</Link>
      </div>

      <div className={`grid flex-1 min-h-0 grid-rows-[minmax(0,1fr)] gap-4 ${comparing ? 'grid-cols-[70fr_30fr]' : 'grid-cols-[25fr_45fr_30fr]'}`}>
        {comparing ? (
          <Compare ws={ws} finding={finding!} left={compareEv[0]} right={compareEv[1]} onClose={() => setParams({})} />
        ) : (
          <>
            <Card className="overflow-y-auto !p-4"><h2 className="mb-3 !text-[15px]">Documents</h2><DocList ws={ws} selected={selDoc} onSelect={(d) => { setSelDoc(d.id); setPage(1) }} /></Card>
            <Card className="overflow-auto !p-4 flex flex-col">
              <div className="flex items-center justify-between mb-2 shrink-0">
                <h2 className="!text-[15px] truncate">{cur ? cur.label : 'Evidence viewer'}</h2>
                {cur && <span className="meta truncate ml-2">{cur.filename}</span>}
              </div>
              <div ref={viewer} className="flex-1 min-h-0 overflow-auto flex justify-center">
                {cur ? <DocViewer key={cur.id} docId={cur.id} kind={cur.kind} pages={cur.pages} page={page} onPage={setPage} width={viewW} boxes={boxes} />
                  : <EmptyState title="No document selected" hint="Pick a document or a finding." />}
              </div>
            </Card>
          </>
        )}
        <Card className="overflow-y-auto !p-4">
          <div className="flex gap-1 mb-3 border-b border-[#E5E7EB] -mx-1 overflow-x-auto">
            {TABS.map((t) => {
              const n = ws.findings.filter((f) => !t.types || t.types.includes(f.check_type)).length
              return (
                <button key={t.key} onClick={() => setTab(t.key)}
                  className={`px-2 py-2 text-[12px] font-medium whitespace-nowrap border-b-2 ${tab === t.key ? 'border-navy text-navy' : 'border-transparent text-slate-500'}`}>
                  {t.label} <span className="text-slate-400">{n}</span>
                </button>
              )
            })}
          </div>
          {list.length === 0 ? <EmptyState compact title="No flags here" hint={ws.findings.length ? 'Nothing in this category.' : 'All checks passed for this application.'} />
            : list.map((f) => (
              <FindingCard key={f.id} f={f} active={f.id === selFinding} onSelect={() => selectFinding(f)} onCompare={canCompare(f) ? () => startCompare(f) : undefined}
                onAction={(a) => (a === 'accept' ? submit(f, 'accept') : setDialog({ f, kind: a }))} />
            ))}
        </Card>
      </div>
      {dialog && <ActionDialog kind={dialog.kind} onCancel={() => setDialog(null)} onSubmit={(n) => submit(dialog.f, dialog.kind, n)} />}
      {void nav}
    </div>
  )
}
