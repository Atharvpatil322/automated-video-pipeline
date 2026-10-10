import { Download } from 'lucide-react'

import { Button } from '@/components/ui/button'

import { fileUrl } from '../api/client'
import { useSettings } from '../state/settings'

export function VideoPlayer({ jobId }: { jobId: string }) {
  const { settings } = useSettings()
  const src = fileUrl(settings, jobId, 'final.mp4')
  return (
    <div className="space-y-2">
      <video controls className="w-full max-w-sm rounded-lg bg-black shadow-sm" src={src}>
        Your browser does not support the video tag.
      </video>
      <Button variant="outline" size="sm" className="rounded-full" asChild>
        <a href={src} download>
          <Download aria-hidden="true" />
          Download
        </a>
      </Button>
    </div>
  )
}
