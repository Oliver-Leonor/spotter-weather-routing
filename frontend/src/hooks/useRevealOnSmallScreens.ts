import { useEffect, useRef } from 'react'

const SMALL_SCREEN = '(max-width: 1023px)' // below the two-column layout

/**
 * On a small screen the page is one long column, so new content can appear out of view. This
 * scrolls the returned element into view whenever `key` changes to a new non-null value.
 */
export function useRevealOnSmallScreens<T extends HTMLElement>(key: string | null) {
  const ref = useRef<T>(null)
  useEffect(() => {
    if (key === null || !window.matchMedia?.(SMALL_SCREEN).matches) return
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ref.current?.scrollIntoView?.({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' })
  }, [key])
  return ref
}
