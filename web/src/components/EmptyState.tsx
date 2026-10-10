export function EmptyState({ label, hint }: { label: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center gap-1 rounded-lg border border-dashed border-slate-300 p-10 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
      <p className="font-medium">{label}</p>
      {hint && <p className="text-sm">{hint}</p>}
    </div>
  )
}
