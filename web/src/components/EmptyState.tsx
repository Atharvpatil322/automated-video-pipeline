import type { LucideIcon } from 'lucide-react'

export function EmptyState({
  icon: Icon,
  label,
  hint,
}: {
  icon?: LucideIcon
  label: string
  hint?: string
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed p-10 text-center text-muted-foreground">
      {Icon && <Icon className="h-8 w-8 text-muted-foreground/50" aria-hidden="true" />}
      <p className="font-medium text-foreground">{label}</p>
      {hint && <p className="text-sm">{hint}</p>}
    </div>
  )
}
