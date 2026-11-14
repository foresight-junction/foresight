import { createRef } from 'react'

// drei <Html> re-creates its React root when its target element changes (the canvas parent swaps to the
// events-connected element after mount). Giving every label one stable DOM layer avoids that churn.
export const sceneLabelLayer = createRef<HTMLDivElement>()
