import { fileUrl } from '../api/client'
import type { SceneVisualResult } from '../api/types'
import { relativeToRunDir } from '../lib/assetPath'
import { useSettings } from '../state/settings'

const VIDEO_EXTENSIONS = ['.mp4', '.mov', '.webm']

function isVideoPath(path: string): boolean {
  return VIDEO_EXTENSIONS.some((ext) => path.toLowerCase().endsWith(ext))
}

function SceneThumbnail({
  jobId,
  runDir,
  scene,
}: {
  jobId: string
  runDir: string | null | undefined
  scene: SceneVisualResult
}) {
  const { settings } = useSettings()
  if (!scene.path) {
    return (
      <div className="flex aspect-video items-center justify-center rounded-md bg-slate-100 text-xs text-slate-400 dark:bg-slate-900">
        no asset
      </div>
    )
  }
  const src = fileUrl(settings, jobId, relativeToRunDir(scene.path, runDir))
  if (isVideoPath(scene.path)) {
    return <video muted className="aspect-video w-full rounded-md object-cover" src={src} />
  }
  return (
    <img
      src={src}
      alt={`Scene ${scene.scene_index + 1} (${scene.visual_type})`}
      className="aspect-video w-full rounded-md object-cover"
    />
  )
}

export function SceneGallery({
  jobId,
  runDir,
  scenes,
}: {
  jobId: string
  runDir: string | null | undefined
  scenes: SceneVisualResult[]
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
      {scenes.map((scene) => (
        <div key={scene.scene_index} className="space-y-1">
          <SceneThumbnail jobId={jobId} runDir={runDir} scene={scene} />
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Scene {scene.scene_index + 1} · {scene.status}
            {scene.method ? ` · ${scene.method}` : ''}
          </p>
          {(scene.provider || scene.confidence != null) && (
            <p className="text-xs text-slate-400 dark:text-slate-500">
              {scene.provider ?? '—'}
              {scene.confidence != null ? ` · confidence ${scene.confidence.toFixed(2)}` : ''}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}
