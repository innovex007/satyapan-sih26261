import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card, EmptyState, PageHeader, StatusChip } from '../components/ui'

interface Doc { document_id: number; application_id: string; filename: string; flagged: boolean; label: string }
interface Detail {
  document_id: number; application_id: string; filename: string
  metadata: { field: string; value: string | null }[]
  signature: 'none' | 'valid' | 'modified_after_signing' | 'broken'
  timeline: { revision: number; label: string; bytes: number; after_signing: boolean }[]
  indicators: string[]; summary: string; flagged: boolean; ela: string | null
}

const SIG: Record<Detail['signature'], { text: string; fg: string; bg: string }> = {
  valid: { text: 'Signature valid', fg: '#1E7B3A', bg: '#E3F5E8' },
  modified_after_signing: { text: 'Modified after signing', fg: '#6A3FB5', bg: '#EFE6FB' },
  broken: { text: 'Signature broken', fg: '#C62828', bg: '#FDE3E3' },
  none: { text: 'Not signed', fg: '#555555', bg: '#EEEEEE' },
}

export function Forensics() {
  const [docs, setDocs] = useState<Doc[]>([])
  const [sel, setSel] = useState<number | null>(null)
  const [d, setD] = useState<Detail | null>(null)

  useEffect(() => {
    api<Doc[]>('/forensics/documents').then((r) => { setDocs(r); if (r.length) setSel(r[0].document_id) }).catch(() => setDocs([]))
  }, [])
  useEffect(() => { if (sel != null) api<Detail>(`/forensics/${sel}`).then(setD).catch(() => setD(null)) }, [sel])

  const sig = d ? SIG[d.signature] : null
  return (
    <>
      <PageHeader tight title="Forensics lab" subtitle="Preliminary indicators on PDF integrity · officer review required" actions={
        <select value={sel ?? ''} onChange={(e) => setSel(Number(e.target.value))} className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-[14px] max-w-[360px]">
          {docs.map((x) => <option key={x.document_id} value={x.document_id}>{x.flagged ? '⚑ ' : ''}{x.label}</option>)}
        </select>} />
      {!d ? <Card><EmptyState title="Loading…" hint="Reading the PDF structure." /></Card> : (
        <>
          <div className={`mb-6 rounded-xl border px-5 py-4 text-[15px] font-medium ${d.flagged ? 'border-[#D9C8F3] bg-[#EFE6FB] text-[#6A3FB5]' : 'border-[#CFE9D6] bg-[#E3F5E8] text-[#1E7B3A]'}`}>
            {d.summary}
            <span className="ml-3 font-normal opacity-80">{d.application_id} · {d.filename}</span>
          </div>
          <div className="grid grid-cols-2 gap-6 mb-6">
            <Card dense title="Metadata">
              <table className="w-full text-[13px]"><tbody>
                {d.metadata.map((m) => (
                  <tr key={m.field} className="border-b border-slate-100 last:border-0">
                    <td className="py-1.5 text-slate-500 w-32">{m.field}</td>
                    <td className={`py-1.5 break-words ${m.field === 'Producer' && /editor/i.test(m.value ?? '') ? 'font-medium text-[#6A3FB5]' : ''}`}>{m.value ?? 'not recorded'}</td>
                  </tr>
                ))}
                <tr><td className="py-1.5 text-slate-500">Signature</td><td className="py-1.5">
                  {sig && <span className="rounded-full px-2.5 py-0.5 text-[12px] font-medium" style={{ color: sig.fg, background: sig.bg }}>{sig.text}</span>}</td></tr>
              </tbody></table>
            </Card>
            <Card dense title="Incremental-save timeline">
              <ol className="space-y-3">
                {d.timeline.map((t) => (
                  <li key={t.revision} className="flex gap-3">
                    <span className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full text-[12px] font-semibold text-white ${t.after_signing ? 'bg-[#6A3FB5]' : 'bg-navy'}`}>{t.revision}</span>
                    <div>
                      <p className="text-[13px] font-medium text-slate-800">Revision {t.revision}: {t.label}</p>
                      <p className="meta">file ends at byte {t.bytes.toLocaleString()}</p>
                    </div>
                  </li>
                ))}
              </ol>
              {d.timeline.length === 1 && <p className="meta mt-3">Single revision: nothing was saved after the document was created.</p>}
            </Card>
          </div>
          <Card dense title="Indicators found">
            {d.indicators.length === 0 ? <p className="meta">None. The file structure, metadata and fonts are consistent.</p> : (
              <ul className="space-y-2">
                {d.indicators.map((i) => (
                  <li key={i} className="flex items-start gap-3 text-[13px]"><StatusChip status="Manual review required" /><span className="pt-0.5">{i}</span></li>
                ))}
              </ul>
            )}
            {d.ela && <img src={d.ela} alt="ELA heat map" className="mt-4 rounded-lg border border-[#E5E7EB]" />}
            <p className="meta mt-3">These are preliminary indicators for the officer, not a finding of forgery.</p>
          </Card>
        </>
      )}
    </>
  )
}
