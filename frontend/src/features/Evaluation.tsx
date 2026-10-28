import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card, EmptyState, Kpi, PageHeader } from '../components/ui'

interface Part { found: number; total: number }
interface Results {
  planted_found: number; planted_total: number; per_type: Record<string, Part>; clean_applications: number; false_alarms_on_clean: number
  false_alarms_per_100_clean_docs: number; precision: number; recall: number
  ocr_scanned_facts: { tp: number; expected: number; f1: number }; text_layer_facts: { tp: number; expected: number; f1: number }
  classification: { correct: number; total: number; accuracy: number }; avg_seconds_per_application: number
  risk_lanes: Record<string, number>; hero_cases: Record<string, boolean>
  twins?: { detected: number; planted: number; by_type: Record<string, { detected: number; total: number; stage: string[]; min_inliers: number }>
    false_matches: number; unplanted_pairs: number; threshold_min_inliers: number; max_inliers_non_twin: number; min_inliers_reshot: number | null
    hard_negatives: { flagged: boolean }[] }
}

export function Evaluation() {
  const [r, setR] = useState<Results | null>(null)
  useEffect(() => { api<Results>('/eval/results').then(setR).catch(() => setR(null)) }, [])
  if (!r || r.planted_total === undefined) return <><PageHeader title="Evaluation" subtitle="Measured on synthetic data" /><Card><EmptyState title="No results yet" hint="Run make eval to compute metrics." /></Card></>
  const pct = (x: number) => `${(x * 100).toFixed(1)}%`
  return (
    <>
      <PageHeader title="Evaluation" subtitle="Measured on synthetic data · simulated sources" />
      <div className="grid grid-cols-3 gap-6 mb-6">
        <Kpi label="Planted anomalies flagged" value={`${r.planted_found} / ${r.planted_total}`} hint={`recall ${pct(r.recall)} · precision ${pct(r.precision)}`} />
        <Kpi label="False alarms on clean applications" value={`${r.false_alarms_on_clean}`} hint={`${r.clean_applications} clean applications · ${r.false_alarms_per_100_clean_docs} per 100 documents`} />
        <Kpi label="Scanned-document fact accuracy (OCR)" value={`${r.ocr_scanned_facts.tp} / ${r.ocr_scanned_facts.expected}`} hint={`F1 ${r.ocr_scanned_facts.f1.toFixed(3)} · text layer ${r.text_layer_facts.tp}/${r.text_layer_facts.expected}`} />
        <Kpi label="Document classification" value={pct(r.classification.accuracy)} hint={`${r.classification.correct} of ${r.classification.total} documents`} />
        <Kpi label="Average time per application" value={`${r.avg_seconds_per_application} s`} hint="pipeline, CPU only" />
        <Kpi label="Risk lanes (30 applications)" value={`${r.risk_lanes.Green} · ${r.risk_lanes.Amber} · ${r.risk_lanes.Red}`} hint="Green · Amber · Red" />
      </div>
      <div className="grid grid-cols-2 gap-6">
        <Card dense title="Recall by defect type">
          <table className="w-full text-[13px]"><tbody>
            {Object.entries(r.per_type).map(([k, v]) => (
              <tr key={k} className="border-b border-slate-100 last:border-0"><td className="py-1.5">{k}</td><td className="py-1.5 text-right tabular-nums text-slate-600">{v.found} / {v.total}</td></tr>
            ))}
          </tbody></table>
        </Card>
        {r.twins && (
          <Card dense title="Twin detection (pHash, then keypoints)">
            <table className="w-full text-[13px]"><tbody>
              {Object.entries(r.twins.by_type).map(([k, v]) => (
                <tr key={k} className="border-b border-slate-100"><td className="py-1.5">{k}</td>
                  <td className="py-1.5 text-slate-500">{v.stage.map((x) => (x === 'copy' ? 'pHash' : x === 'reshot' ? 'keypoints' : x)).join(' + ')}</td>
                  <td className="py-1.5 text-right tabular-nums text-slate-600">{v.detected} / {v.total}</td></tr>
              ))}
              <tr className="border-b border-slate-100"><td className="py-1.5">Hard negatives flagged</td><td /><td className="py-1.5 text-right tabular-nums text-slate-600">{r.twins.hard_negatives.filter((h) => h.flagged).length} / {r.twins.hard_negatives.length}</td></tr>
              <tr><td className="py-1.5">False matches</td><td className="py-1.5 text-slate-500">{r.twins.unplanted_pairs.toLocaleString()} unplanted pairs</td><td className="py-1.5 text-right tabular-nums text-slate-600">{r.twins.false_matches}</td></tr>
            </tbody></table>
            <p className="meta mt-2">Keypoint threshold {r.twins.threshold_min_inliers} inliers · highest non-twin {r.twins.max_inliers_non_twin} · lowest re-shot twin {r.twins.min_inliers_reshot}</p>
          </Card>
        )}
        <Card dense title="Demo hero cases">
          <ul className="space-y-1.5 text-[13px]">
            {Object.entries(r.hero_cases).map(([k, ok]) => (
              <li key={k} className="flex items-center justify-between"><span>{k}</span>
                <span className={`rounded-full px-2.5 py-0.5 text-[12px] font-medium ${ok ? 'bg-[#E3F5E8] text-[#1E7B3A]' : 'bg-[#FDE3E3] text-[#C62828]'}`}>{ok ? 'reproduces' : 'miss'}</span></li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  )
}
