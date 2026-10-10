import type { Scene } from '../api/types'

export function SceneTable({ scenes }: { scenes: Scene[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] text-left text-sm">
        <caption className="sr-only">Scene plan</caption>
        <thead>
          <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-800 dark:text-slate-400">
            <th scope="col" className="py-1 pr-2">#</th>
            <th scope="col" className="py-1 pr-2">Visual</th>
            <th scope="col" className="py-1 pr-2">Motion</th>
            <th scope="col" className="py-1 pr-2">Narration</th>
            <th scope="col" className="py-1 pr-2">Transition</th>
          </tr>
        </thead>
        <tbody>
          {scenes.map((scene, i) => (
            <tr key={i} className="border-b border-slate-100 align-top dark:border-slate-900">
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
