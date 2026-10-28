import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Workspace } from '../lib/types'
import { Card, EmptyState, StatusChip } from '../components/ui'

const SAMPLE = 'EoA-DEMO-0417'

export function SelfCheck() {
  const [ws, setWs] = useState<Workspace | null>(null)
  useEffect(() => { api<Workspace>(`/applications/${SAMPLE}/workspace`).then(setWs).catch(() => setWs(null)) }, [])
  if (!ws) return <Card><EmptyState title="Loading the sample checklist…" hint="Reading a sample institution's application." /></Card>
  const open = ws.findings.filter((f) => f.officer_action !== 'dismissed')
  return (
    <>
      <h1 className="text-teal-800">Check your application before submitting</h1>
      <p className="meta mt-1 mb-6">Sample institution: {ws.institution.name} · {ws.application.category} · session {ws.application.academic_session}. This is what an officer would see, and how to fix it first.</p>
      <div className="grid grid-cols-2 gap-6">
        <Card dense title="Your documents">
          <ul className="divide-y divide-slate-100">
            {ws.groups.flatMap((g) => g.documents).filter((d) => d.kind !== 'image' || d.doc_type !== 'lab_video_frame').map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-3 py-2 text-[13px]"><span className="truncate">{d.label}</span><StatusChip status={d.status} /></li>
            ))}
            {ws.missing.map((m) => (
              <li key={m.doc_type} className="flex items-center justify-between gap-3 py-2 text-[13px]"><span>{m.label}</span><StatusChip status="Verification pending" /></li>
            ))}
          </ul>
        </Card>
        <Card dense title={`To fix before you submit (${open.length})`}>
          {open.length === 0 ? <p className="meta">Nothing to fix: every check passed.</p> : (
            <ul className="space-y-4">
              {open.map((f) => (
                <li key={f.id}>
                  <StatusChip status={f.status} />
                  <p className="mt-1.5 text-[13px] leading-5 text-slate-800">{f.reason}</p>
                  <p className="mt-1 text-[12px] leading-[18px] text-slate-600"><span className="font-medium text-slate-700">How to clear: </span>{f.how_to_clear}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  )
}
