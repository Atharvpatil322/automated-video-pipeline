export function OfflineBanner() {
  return (
    <div
      role="status"
      className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200"
    >
      OFFLINE mode — the server is using deterministic local fakes for every provider. No
      real API keys are used and nothing is billed.
    </div>
  )
}
