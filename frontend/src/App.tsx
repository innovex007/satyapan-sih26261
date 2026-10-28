import { Route, Routes } from 'react-router-dom'
import { Layout, SelfCheckLayout } from './components/Layout'
import { Dashboard } from './features/Dashboard'
import { Forensics } from './features/Forensics'
import { SourceChecks } from './features/SourceChecks'
import { Rules } from './features/Rules'
import { AuditLog } from './features/AuditLog'
import { SelfCheck } from './features/SelfCheck'
import { Queue } from './features/Queue'
import { Workspace } from './features/Workspace'
import { TwinSearch } from './features/TwinSearch'
import { Evaluation } from './features/Evaluation'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="queue" element={<Queue />} />
        <Route path="workspace" element={<Workspace />} />
        <Route path="workspace/:id" element={<Workspace />} />
        <Route path="twins" element={<TwinSearch />} />
        <Route path="forensics" element={<Forensics />} />
        <Route path="sources" element={<SourceChecks />} />
        <Route path="rules" element={<Rules />} />
        <Route path="audit" element={<AuditLog />} />
        <Route path="evaluation" element={<Evaluation />} />
      </Route>
      <Route element={<SelfCheckLayout />}>
        <Route path="self-check" element={<SelfCheck />} />
      </Route>
    </Routes>
  )
}
