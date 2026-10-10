/** visuals.json (app/pipeline/visuals.py) stores each scene's asset path
 * absolute (e.g. "/srv/output/<run>/assets/scene-0-ai.png"), since that's
 * what the pipeline itself needs on disk. The files route
 * (app/server/routes/files.py) instead expects a path relative to the
 * job's run directory, same as "final.mp4" or "visuals.json" themselves.
 * Strip the job's own run_dir prefix (which GET /jobs(/:id) always
 * returns) to get something fileUrl() can serve - no backend change
 * needed, since the client already has both pieces of information.
 */
export function relativeToRunDir(assetPath: string, runDir: string | null | undefined): string {
  if (!runDir) return assetPath
  const normalizedRunDir = runDir.replace(/[\\/]+$/, '')
  const normalizedAsset = assetPath.replace(/\\/g, '/')
  const prefix = normalizedRunDir.replace(/\\/g, '/')
  if (normalizedAsset.startsWith(`${prefix}/`)) {
    return normalizedAsset.slice(prefix.length + 1)
  }
  return assetPath
}
