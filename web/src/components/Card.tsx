import type { HTMLAttributes, ReactNode } from 'react'

import { Card as ShadcnCard } from '@/components/ui/card'
import { cn } from '@/lib/utils'

/** Thin wrapper so call sites can keep using <Card as="section" ...> for
 * semantic landmarks - shadcn's own Card is always a <div>.
 */
export function Card({
  children,
  className = '',
  as: As,
  ...rest
}: {
  children: ReactNode
  className?: string
  as?: 'div' | 'section'
} & HTMLAttributes<HTMLElement>) {
  if (As === 'section') {
    return (
      <section className={cn('rounded-xl border bg-card p-4 shadow-xs sm:p-5', className)} {...rest}>
        {children}
      </section>
    )
  }
  return (
    <ShadcnCard className={cn('p-4 sm:p-5', className)} {...rest}>
      {children}
    </ShadcnCard>
  )
}
