import type { HouseholdView, PersonView } from './state/applyEvent'

export const GALLERY_COLUMNS = 5
export const GALLERY_SPACING = 1.05
export const GALLERY_MAX_TOKENS = 25

export interface GalleryToken {
  id: string
  x: number
  z: number
}

export interface GalleryLink {
  key: string
  from: string
  to: string
  householdId: string
}

export interface GalleryDome {
  householdId: string | null
  memberIds: string[]
  hidden: boolean
}

export interface GalleryLayout {
  tokens: GalleryToken[]
  links: GalleryLink[]
  domes: GalleryDome[]
}

export function layoutGallery(
  personOrder: string[],
  persons: Record<string, PersonView>,
  households: Record<string, HouseholdView>,
): GalleryLayout {
  const recent = [...personOrder]
    .sort((a, b) => (persons[b]?.lastSeenSeq ?? 0) - (persons[a]?.lastSeenSeq ?? 0))
    .slice(0, GALLERY_MAX_TOKENS)
  const visible = new Set(recent)

  const groups: string[][] = []
  const placed = new Set<string>()
  const householdList = Object.values(households).sort((a, b) => a.seq - b.seq)
  for (const household of householdList) {
    const members = household.memberIds.filter((id) => visible.has(id) && !placed.has(id))
    if (members.length === 0) continue
    members.forEach((id) => placed.add(id))
    groups.push(members)
  }
  for (const id of personOrder) {
    if (visible.has(id) && !placed.has(id)) {
      placed.add(id)
      groups.push([id])
    }
  }

  const cells: string[] = []
  for (const group of groups) {
    const column = cells.length % GALLERY_COLUMNS
    if (group.length > 1 && column !== 0 && column + group.length > GALLERY_COLUMNS) {
      while (cells.length % GALLERY_COLUMNS !== 0) cells.push('')
    }
    cells.push(...group)
  }

  const rows = Math.max(1, Math.ceil(cells.length / GALLERY_COLUMNS))
  const tokens: GalleryToken[] = []
  cells.forEach((id, index) => {
    if (id === '') return
    const row = Math.floor(index / GALLERY_COLUMNS)
    const column = index % GALLERY_COLUMNS
    tokens.push({
      id,
      x: (column - (GALLERY_COLUMNS - 1) / 2) * GALLERY_SPACING,
      z: (row - (rows - 1) / 2) * GALLERY_SPACING,
    })
  })

  const links: GalleryLink[] = []
  const domes: GalleryDome[] = []
  for (const household of householdList) {
    const members = household.memberIds.filter((id) => visible.has(id))
    for (let i = 1; i < members.length; i++) {
      links.push({
        key: `${household.id}:${members[i - 1]}:${members[i]}`,
        from: members[i - 1],
        to: members[i],
        householdId: household.id,
      })
    }
    const shielded = members.filter((id) => persons[id]?.sno === 'ACTIVE')
    if (shielded.length > 0 && members.length > 1) {
      domes.push({ householdId: household.id, memberIds: members, hidden: shielded.every((id) => persons[id]?.snoHidden) })
    }
  }
  const inHouseholdDome = new Set(domes.flatMap((d) => d.memberIds))
  for (const id of recent) {
    const person = persons[id]
    if (person?.sno === 'ACTIVE' && !inHouseholdDome.has(id)) {
      domes.push({ householdId: null, memberIds: [id], hidden: person.snoHidden })
    }
  }

  return { tokens, links, domes }
}
