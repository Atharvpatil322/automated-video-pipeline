import { Clapperboard, LayoutGrid, Plus, Settings as SettingsIcon } from 'lucide-react'
import { NavLink, Route, Routes } from 'react-router-dom'

import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { Gallery } from './pages/Gallery'
import { Home } from './pages/Home'
import { Job } from './pages/Job'
import { Settings } from './pages/Settings'

const NAV_LINKS = [
  { to: '/', label: 'New job', icon: Plus },
  { to: '/gallery', label: 'Gallery', icon: LayoutGrid },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
]

function linkClass({ isActive }: { isActive: boolean }) {
  return cn(
    buttonVariants({ variant: isActive ? 'default' : 'ghost' }),
    'rounded-full',
  )
}

export function App() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
        <nav className="mx-auto flex max-w-5xl items-center justify-between gap-4 p-3">
          <NavLink to="/" end className="flex items-center gap-2 font-semibold">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Clapperboard className="h-4 w-4" aria-hidden="true" />
            </span>
            Reel Studio
          </NavLink>
          <div className="flex gap-1">
            {NAV_LINKS.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} end={to === '/'} className={linkClass}>
                <Icon aria-hidden="true" />
                {label}
              </NavLink>
            ))}
          </div>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl">
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
