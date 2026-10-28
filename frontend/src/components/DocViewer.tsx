import { useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import { ChevronLeft, ChevronRight } from 'lucide-react'

// copied from react-pdf's bundled pdfjs-dist into public/ (same version as the renderer)
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'

export interface Box {
  bbox: number[]
  color: string
  tag?: string // data-hl value, used by compare mode to draw the connector line
  label?: string
}

interface Props {
  docId: number
  kind: 'text' | 'scan' | 'image'
  pages: number
  page: number
  onPage?: (p: number) => void
  width: number
  boxes: Box[]
  onReady?: () => void
}

function Overlay({ boxes }: { boxes: Box[] }) {
  return (
    <div className="absolute inset-0 pointer-events-none">
      {boxes.filter((b) => b.bbox.length === 4).map((b, i) => (
        <div key={i} data-hl={b.tag} title={b.label}
          style={{ position: 'absolute', left: `${b.bbox[0] * 100}%`, top: `${b.bbox[1] * 100}%`, width: `${(b.bbox[2] - b.bbox[0]) * 100}%`,
            height: `${(b.bbox[3] - b.bbox[1]) * 100}%`, background: `${b.color}1A`, border: `2px solid ${b.color}`, borderRadius: 3 }} />
      ))}
    </div>
  )
}

export function DocViewer({ docId, kind, pages, page, onPage, width, boxes, onReady }: Props) {
  const url = `/api/documents/${docId}/file`
  const [err, setErr] = useState(false)
  return (
    <div>
      {pages > 1 && onPage && (
        <div className="flex items-center justify-center gap-3 mb-2 meta">
          <button className="p-1 rounded hover:bg-slate-100 disabled:opacity-30" disabled={page <= 1} onClick={() => onPage(page - 1)}><ChevronLeft className="h-4 w-4" /></button>
          Page {page} of {pages}
          <button className="p-1 rounded hover:bg-slate-100 disabled:opacity-30" disabled={page >= pages} onClick={() => onPage(page + 1)}><ChevronRight className="h-4 w-4" /></button>
        </div>
      )}
      <div className="relative inline-block border border-[#E5E7EB] bg-white shadow-card" style={{ width }}>
        {kind === 'image' ? (
          <img src={url} alt="" style={{ width, display: 'block' }} onLoad={onReady} />
        ) : err ? (
          <p className="meta p-6">Could not render this PDF.</p>
        ) : (
          <Document file={url} loading={<div style={{ width, height: width * 1.414 }} className="animate-pulse bg-slate-50" />} onLoadError={() => setErr(true)}>
            <Page pageNumber={page} width={width} renderTextLayer={false} renderAnnotationLayer={false} onRenderSuccess={onReady} />
          </Document>
        )}
        <Overlay boxes={boxes.filter((b) => (b as Box & { page?: number }).page === undefined || (b as Box & { page?: number }).page === page)} />
      </div>
      {kind === 'image' && <p className="meta mt-1.5 text-center">Sample photo</p>}
    </div>
  )
}
