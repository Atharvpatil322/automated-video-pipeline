import { ProviderKeysForm } from '../components/ProviderKeysForm'
import { useSettings } from '../state/settings'

export function Settings() {
  const { settings, setSettings } = useSettings()

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-4">
      <h1 className="text-2xl font-bold">Settings</h1>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">API connection</h2>
        <label className="flex flex-col gap-1 text-sm">
          <span>API base URL</span>
          <input
            type="text"
            placeholder="(relative - same origin)"
            value={settings.apiBaseUrl}
            onChange={(e) => setSettings((prev) => ({ ...prev, apiBaseUrl: e.target.value }))}
            className="rounded-md border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>API token (optional)</span>
          <input
            type="password"
            autoComplete="off"
            value={settings.apiToken}
            onChange={(e) => setSettings((prev) => ({ ...prev, apiToken: e.target.value }))}
            className="rounded-md border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
          />
        </label>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Provider keys (BYOK)</h2>
        <ProviderKeysForm />
      </section>
    </div>
  )
}
