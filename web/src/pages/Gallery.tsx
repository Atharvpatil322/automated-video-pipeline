import { useDeleteJob, useJobs } from '../api/queries'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { JobCard } from '../components/JobCard'
import { LoadingState } from '../components/LoadingState'

export function Gallery() {
  const jobs = useJobs()
  const deleteJob = useDeleteJob()

  if (jobs.isLoading) return <LoadingState label="Loading jobs…" />
  if (jobs.error) return <ErrorState message="Could not load jobs." />
  if (!jobs.data || jobs.data.length === 0) {
    return <EmptyState label="No jobs yet" hint="Create one from the home page." />
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4">
      <h1 className="text-2xl font-bold">Jobs</h1>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
        {jobs.data.map((job) => (
          <JobCard key={job.id} job={job} onDelete={(id) => deleteJob.mutate(id)} />
        ))}
      </div>
    </div>
  )
}
