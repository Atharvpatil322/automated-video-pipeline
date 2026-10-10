import { NavLink, Route, Routes } from 'react-router-dom'

import { Gallery } from './pages/Gallery'
import { Home } from './pages/Home'
import { Job } from './pages/Job'
import { Settings } from './pages/Settings'

const NAV_LINKS = [
  { to: '/', label: 'New job' },
  { to: '/gallery', label: 'Gallery' },
  { to: '/settings', label: 'Settings' },
]

function linkClass({ isActive }: { isActive: boolean }) {
  return `rounded-md px-3 py-1.5 text-sm font-medium ${
    isActive
      ? 'bg-brand text-white'
      : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-900'
  }`
}

export function App() {
  return (
    <div className="min-h-screen">
      <nav className="flex gap-2 border-b border-slate-200 p-3 dark:border-slate-800">
        {NAV_LINKS.map(({ to, label }) => (
          <NavLink key={to} to={to} end={to === '/'} className={linkClass}>
            {label}
          </NavLink>
        ))}
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/jobs/:jobId" element={<Job />} />
          <Route path="/gallery" element={<Gallery />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}
