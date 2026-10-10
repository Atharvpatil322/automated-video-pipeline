import { fileUrl } from '../api/client'
import { useSettings } from '../state/settings'

export function VideoPlayer({ jobId }: { jobId: string }) {
  const { settings } = useSettings()
  const src = fileUrl(settings, jobId, 'final.mp4')
  return (
    <div className="space-y-2">
      <video controls className="w-full max-w-sm rounded-lg bg-black" src={src}>
        Your browser does not support the video tag.
      </video>
      <a
        href={src}
        download
        className="inline-block rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-900"
      >
        Download final.mp4
      </a>
    </div>
  )
}
