import { FlaskConical } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

export function OfflineBanner() {
  return (
    <Alert className="border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
      <FlaskConical aria-hidden="true" />
      <AlertTitle>Offline mode</AlertTitle>
      <AlertDescription className="text-amber-700 dark:text-amber-300">
        The server is using deterministic local fakes for every provider — no real API keys are
        used and nothing is billed.
      </AlertDescription>
    </Alert>
  )
}
