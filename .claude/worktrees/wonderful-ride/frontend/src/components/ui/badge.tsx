import React from 'react'

function cn(...classes: (string | undefined | false)[]) {
  return classes.filter(Boolean).join(' ')
}

export function Badge({
  className,
  variant = 'default',
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { variant?: string }) {
  const variants: Record<string, string> = {
    default: 'border-transparent bg-white/10 text-white',
    secondary: 'border-transparent bg-white/5 text-white/70',
    outline: 'border border-white/20 text-white/80',
    destructive: 'border-transparent bg-red-500/20 text-red-300',
  }
  return (
    <div
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors',
        variants[variant] || variants.default,
        className,
      )}
      {...props}
    />
  )
}
