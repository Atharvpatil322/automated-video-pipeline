import { ChevronDown } from 'lucide-react'
import type { ReactNode } from 'react'

export function CollapsibleSection({
  title,
  description,
  defaultOpen = false,
  children,
}: {
  title: string
  description?: string
  defaultOpen?: boolean
  children: ReactNode
}) {
  return (
    <details className="group rounded-xl border bg-card p-4 text-card-foreground shadow-xs sm:p-5" open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2">
        <span>
          <span className="font-medium">{title}</span>
          {description && <span className="block text-sm text-muted-foreground">{description}</span>}
        </span>
        <ChevronDown
          aria-hidden="true"
          className="h-5 w-5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
        />
      </summary>
      <div className="mt-4 space-y-4">{children}</div>
    </details>
  )
}
