import { formatLabel, platformIcon } from '../lib/icons'

export function PlatformPicker({
  platforms,
  value,
  onChange,
}: {
  platforms: string[]
  value: string
  onChange: (platform: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Platform">
      {platforms.map((platform) => {
        const Icon = platformIcon(platform)
        const selected = platform === value
        return (
          <button
            key={platform}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(platform)}
            className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
              selected
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-border text-muted-foreground hover:border-primary/50 hover:text-foreground'
            }`}
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
            {formatLabel(platform)}
          </button>
        )
      })}
    </div>
  )
}
