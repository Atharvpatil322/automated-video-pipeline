import {
  BookOpen,
  Film,
  type LucideIcon,
  MonitorPlay,
  Palette,
  Smartphone,
  Sparkles,
  Video,
} from 'lucide-react'

const PLATFORM_ICONS: Record<string, LucideIcon> = {
  youtube: MonitorPlay,
  tiktok: Smartphone,
  instagram: Smartphone,
}

export function platformIcon(platform: string): LucideIcon {
  return PLATFORM_ICONS[platform] ?? Video
}

const ARCHETYPE_ICONS: Record<string, LucideIcon> = {
  infographic: BookOpen,
  cinematic_documentary: Film,
  warm_editorial: Palette,
}

export function archetypeIcon(archetype: string): LucideIcon {
  return ARCHETYPE_ICONS[archetype] ?? Sparkles
}

export function formatLabel(id: string): string {
  return id
    .split('_')
    .map((word) => word[0]?.toUpperCase() + word.slice(1))
    .join(' ')
}
