import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Status } from '../lib/status'
import { Card, EmptyState, PageHeader, StatusChip } from '../components/ui'

interface Active { name: string; version: number; modified: string; file: string; yaml_text: string; rules: { id: string; checks: string; threshold: string; status: Status }[] }

function Line({ text }: { text: string }) {
  if (/^\s*#/.test(text)) return <span className="text-slate-400">{text}</span>
  const m = text.match(/^(\s*-?\s*)([\w\-.]+)(:)(.*)$/)
  if (!m) return <span>{text}</span>
  const [, indent, key, colon, rest] = m
  const [val, comment] = rest.split(/(\s+#.*)$/).filter((x) => x !== undefined)
  const hl = (v: string) => v.split(/(\b\d[\d.\-]*\b|\btrue\b|\bfalse\b)/).map((p, i) => (/^(\d[\d.\-]*|true|false)$/.test(p) ? <span key={i} className="text-amber-600">{p}</span> : <span key={i}>{p}</span>))
  return <><span>{indent}</span><span className="text-[#1F3864] font-medium">{key}</span><span>{colon}</span>{hl(val ?? '')}{comment && <span className="text-slate-400">{comment}</span>}</>
}

export function Rules() {
  const [r, setR] = useState<Active | null>(null)
  useEffect(() => { api<Active>('/rules/active').then(setR).catch(() => setR(null)) }, [])
  if (!r) return <><PageHeader title="Rule files (APH)" subtitle="Checklist and tolerances per application category" /><Card><EmptyState title="Loading…" hint="Reading the active rule file." /></Card></>
  return (
    <>
      <PageHeader tight title="Rule files (APH)" subtitle={`${r.name} · version ${r.version} · last modified ${r.modified.replace('T', ' ')} · ${r.file} (read-only)`} actions={
        <button disabled title="Editing in next version" className="rounded-lg border border-[#E5E7EB] bg-white px-4 py-2 text-[14px] font-medium text-slate-400 cursor-not-allowed">Edit</button>} />
      <Card dense title="Rules in force" className="mb-6">
        <table className="w-full table-fixed text-left text-[13px]">
          <colgroup><col className="w-[170px]" /><col /><col className="w-[260px]" /><col className="w-[190px]" /></colgroup>
          <thead><tr className="meta">{['Rule ID', 'What it checks', 'Threshold', 'Status produced'].map((h) => <th key={h} className="border-b border-[#E5E7EB] px-2 py-2 font-medium">{h}</th>)}</tr></thead>
          <tbody>
            {r.rules.map((x) => (
              <tr key={x.id} className="border-b border-slate-100 last:border-0 align-top">
                <td className="px-2 py-2 font-medium text-navy">{x.id}</td><td className="px-2 py-2">{x.checks}</td>
                <td className="px-2 py-2 text-slate-600">{x.threshold}</td><td className="px-2 py-2"><StatusChip status={x.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card dense title={r.file}>
        <pre className="max-h-[420px] overflow-auto rounded-lg bg-slate-50 p-4 text-[12px] leading-5 font-mono">
          {r.yaml_text.split('\n').map((l, i) => <div key={i}><Line text={l} /></div>)}
        </pre>
      </Card>
    </>
  )
}
