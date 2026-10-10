import type { Scene } from '../api/types'

export function SceneTable({ scenes }: { scenes: Scene[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] text-left text-sm">
        <caption className="sr-only">Scene plan</caption>
        <thead>
          <tr className="border-b text-muted-foreground">
            <th scope="col" className="py-1 pr-2">#</th>
            <th scope="col" className="py-1 pr-2">Visual</th>
            <th scope="col" className="py-1 pr-2">Motion</th>
            <th scope="col" className="py-1 pr-2">Narration</th>
            <th scope="col" className="py-1 pr-2">Transition</th>
          </tr>
        </thead>
        <tbody>
          {scenes.map((scene, i) => (
            <tr key={i} className="border-b border-border/60 align-top">
              <td className="py-2 pr-2">{i + 1}</td>
              <td className="py-2 pr-2">{scene.visual_type}</td>
              <td className="py-2 pr-2">{scene.motion}</td>
              <td className="py-2 pr-2">{scene.script_line}</td>
              <td className="py-2 pr-2">{scene.transition ?? 'none'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
