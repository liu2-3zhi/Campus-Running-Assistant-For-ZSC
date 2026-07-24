import DOMPurify from 'dompurify'

let purifier = null

function getPurifier() {
  if (purifier) return purifier
  if (DOMPurify && typeof DOMPurify.sanitize === 'function') {
    purifier = DOMPurify
    return purifier
  }
  if (
    typeof DOMPurify === 'function' &&
    typeof window !== 'undefined' &&
    window.document
  ) {
    purifier = DOMPurify(window)
    return purifier
  }
  return null
}

export function sanitizeSvg(svg) {
  if (!svg || typeof svg !== 'string') return ''
  const activePurifier = getPurifier()
  if (!activePurifier) return ''
  return activePurifier.sanitize(svg, {
    USE_PROFILES: { svg: true, svgFilters: true },
    FORBID_TAGS: ['script', 'foreignObject', 'iframe', 'object', 'embed'],
    FORBID_ATTR: ['style'],
    ALLOW_DATA_ATTR: false,
  })
}
