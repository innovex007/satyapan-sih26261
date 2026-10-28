import { NavLink, Outlet } from 'react-router-dom'
import { Search, ShieldCheck } from 'lucide-react'
import { useState } from 'react'

const NAV = [
  { group: 'Overview', items: [{ to: '/', label: 'Dashboard' }] },
  { group: 'Scrutiny', items: [{ to: '/queue', label: 'Application queue' }, { to: '/workspace', label: 'Application workspace' }] },
  { group: 'Intelligence', items: [{ to: '/twins', label: 'Twin search' }, { to: '/forensics', label: 'Forensics lab' }] },
  { group: 'Verification', items: [{ to: '/sources', label: 'Source checks' }] },
  { group: 'Configuration', items: [{ to: '/rules', label: 'Rule files (APH)' }] },
  { group: 'Governance', items: [{ to: '/audit', label: 'Audit log' }, { to: '/evaluation', label: 'Evaluation' }] },
]
const ROLES = ['Scrutiny officer', 'EVC expert', 'Admin']

function Banner() {
  return (
    <div className="bg-slate-100 border-b border-slate-200 text-center meta py-1">
      Prototype · synthetic data · simulated sources
    </div>
  )
}

export function Layout() {
  const [role, setRole] = useState(ROLES[0])
  return (
    <div className="h-screen flex flex-col">
      <Banner />
      <div className="flex flex-1 min-h-0">
        <aside className="w-64 shrink-0 bg-navy text-white flex flex-col overflow-y-auto">
          <div className="flex items-center gap-2 px-6 h-16 shrink-0">
            <ShieldCheck className="h-5 w-5 text-amber-brand" />
            <span className="font-semibold tracking-[0.18em]">SATYAPAN</span>
          </div>
          <nav className="flex-1 px-3 pb-4">
            {NAV.map((g) => (
              <div key={g.group} className="mb-5">
                <p className="px-3 mb-1 text-[11px] uppercase tracking-wider text-slate-300/70">{g.group}</p>
                {g.items.map((i) => (
                  <NavLink
                    key={i.to}
                    to={i.to}
                    end={i.to === '/'}
                    className={({ isActive }) =>
                      `block rounded-lg px-3 py-2 text-[14px] border-l-[3px] ${
                        isActive ? 'bg-white/10 text-white border-amber-brand' : 'text-slate-200 hover:bg-white/5 border-transparent'
                      }`
                    }
                  >
                    {i.label}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
          <div className="border-t border-white/10 p-3 shrink-0">
            <NavLink to="/self-check" className="block rounded-lg px-3 py-2 text-slate-200 hover:bg-white/5">
              Institution self-check
            </NavLink>
          </div>
        </aside>
        <div className="flex-1 flex flex-col min-w-0">
          <header className="h-16 shrink-0 bg-white border-b border-[#E5E7EB] px-8 flex items-center gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                placeholder="Search application ID or institution"
                className="w-full rounded-lg border border-[#E5E7EB] bg-canvas pl-9 pr-3 py-2 text-[14px] outline-none focus:border-navy"
              />
            </div>
            <div className="ml-auto flex items-center gap-4">
              <select
                value={role}
                onChange={(e) => { setRole(e.target.value); try { localStorage.setItem('role', e.target.value) } catch { /* ignore */ } }}
                className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-[14px]"
              >
                {ROLES.map((r) => <option key={r}>{r}</option>)}
              </select>
              <div className="h-8 w-8 rounded-full bg-navy text-white grid place-items-center text-[12px] font-medium">SO</div>
            </div>
          </header>
          <main className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-[1440px] p-8"><Outlet /></div>
          </main>
        </div>
      </div>
    </div>
  )
}

export function SelfCheckLayout() {
  return (
    <div className="h-screen flex flex-col">
      <Banner />
      <header className="h-16 shrink-0 bg-teal-700 text-white px-8 flex items-center justify-between">
        <span className="font-semibold">Satyapan · Institution self-check</span>
        <NavLink to="/" className="text-[14px] text-teal-100 hover:text-white">Officer portal</NavLink>
      </header>
      <main className="flex-1 overflow-y-auto"><div className="mx-auto max-w-[960px] p-8"><Outlet /></div></main>
    </div>
  )
}
