import { Wand2 } from 'lucide-react'

import { archetypeIcon, formatLabel } from '../lib/icons'

const LET_DIRECTOR_CHOOSE = ''

export function ArchetypePicker({
  archetypes,
  value,
  onChange,
}: {
  archetypes: string[]
  value: string
  onChange: (archetype: string) => void
}) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Archetype">
      <ArchetypeOption
        label="Let the director choose"
        Icon={Wand2}
        selected={value === LET_DIRECTOR_CHOOSE}
        onClick={() => onChange(LET_DIRECTOR_CHOOSE)}
      />
      {archetypes.map((archetype) => (
        <ArchetypeOption
          key={archetype}
          label={formatLabel(archetype)}
          Icon={archetypeIcon(archetype)}
          selected={value === archetype}
          onClick={() => onChange(archetype)}
        />
      ))}
    </div>
  )
}

function ArchetypeOption({
  label,
  Icon,
  selected,
  onClick,
}: {
  label: string
  Icon: typeof Wand2
  selected: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onClick}
      className={`flex flex-col items-center gap-1.5 rounded-lg border p-3 text-center text-sm transition-colors ${
        selected
          ? 'border-primary bg-accent text-accent-foreground'
          : 'border-border text-muted-foreground hover:border-primary/50 hover:text-foreground'
      }`}
    >
      <Icon className="h-5 w-5" aria-hidden="true" />
      {label}
    </button>
  )
}
