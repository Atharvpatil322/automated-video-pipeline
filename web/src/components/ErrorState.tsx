export function ErrorState({ title = 'Something went wrong', message }: { title?: string; message: string }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
    >
      <p className="font-medium">{title}</p>
      <p className="text-sm">{message}</p>
    </div>
  )
}
