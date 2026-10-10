import { Key, Plug, Settings as SettingsIcon } from 'lucide-react'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import { Card } from '../components/Card'
import { ProviderKeysForm } from '../components/ProviderKeysForm'
import { useSettings } from '../state/settings'

export function Settings() {
  const { settings, setSettings } = useSettings()

  return (
    <div className="mx-auto max-w-2xl space-y-5 p-4 sm:p-6">
      <h1 className="flex items-center gap-2 text-2xl font-bold">
        <SettingsIcon className="h-6 w-6 text-primary" aria-hidden="true" />
        Settings
      </h1>

      <Card as="section" className="space-y-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Plug className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
          API connection
        </h2>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="api-base-url" className="text-sm font-normal">
            API base URL
          </Label>
          <Input
            id="api-base-url"
            type="text"
            placeholder="(relative - same origin)"
            value={settings.apiBaseUrl}
            onChange={(e) => setSettings((prev) => ({ ...prev, apiBaseUrl: e.target.value }))}
            className="h-9"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="api-token" className="text-sm font-normal">
            API token (optional)
          </Label>
          <Input
            id="api-token"
            type="password"
            autoComplete="off"
            value={settings.apiToken}
            onChange={(e) => setSettings((prev) => ({ ...prev, apiToken: e.target.value }))}
            className="h-9"
          />
        </div>
      </Card>

      <Card as="section" className="space-y-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Key className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
          Your own API keys (BYOK)
        </h2>
        <ProviderKeysForm />
      </Card>
    </div>
  )
}
