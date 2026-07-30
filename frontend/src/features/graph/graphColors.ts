type GraphTheme = 'dark' | 'light'

type Palette = Record<string, string[]>

const darkPalettes: Palette = {
  document: ['#E6A86C', '#F0B978', '#D99252', '#F2C98D'],
  chunk: ['#8EA5B9', '#A6BBCB', '#7694AA'],
  organization: ['#E6A86C', '#E9B77A', '#D99455', '#F0C894'],
  'organization-unit': ['#E9B77A', '#D99455', '#F0C894', '#C9814B'],
  person: ['#A994FF', '#B9A8FF', '#8D79E8', '#C6B8FF'],
  country: ['#6CA8FF', '#82B5FF', '#4D8FE8', '#A0C9FF'],
  region: ['#8DC7FF', '#A5D3FF', '#6BA9DF', '#B8DEFF'],
  place: ['#7BE2D4', '#91E9DD', '#59C9BA', '#B0F1E8'],
  technology: ['#73D6C8', '#8BE0D4', '#50BDAF', '#A7ECE3'],
  equipment: ['#F39A6B', '#F5AD82', '#D9794D', '#F7C1A0'],
  system: ['#8C86FF', '#9D98FF', '#716BE2', '#BDB9FF'],
  project: ['#D78BE8', '#E19BEE', '#BB6CCC', '#EDB9F4'],
  policy: ['#69D49A', '#80DEA9', '#4DBA7D', '#A4EAC0'],
  event: ['#FF8B72', '#FF9D88', '#E66D56', '#FFC0B1'],
}

const lightPalettes: Palette = {
  document: ['#A85E20', '#B86F2B', '#914B18', '#C17B37'],
  chunk: ['#49647B', '#5F7890', '#38566F'],
  organization: ['#A85E20', '#B86F2B', '#914B18', '#C17B37'],
  'organization-unit': ['#B86F2B', '#914B18', '#C17B37', '#7D3F17'],
  person: ['#6653C7', '#7563D2', '#5140AE', '#8978DF'],
  country: ['#2868A8', '#377AB9', '#1B578F', '#4A8CC9'],
  region: ['#2B729B', '#3B83AC', '#205E84', '#5799BA'],
  place: ['#147A74', '#238D86', '#0C655F', '#43A79F'],
  technology: ['#168C83', '#279D93', '#0D716A', '#4BB5AA'],
  equipment: ['#B04F24', '#C26131', '#963D1A', '#D17A4B'],
  system: ['#5F54B7', '#7065C7', '#4B419D', '#887BD8'],
  project: ['#904AA4', '#A05BB4', '#78378C', '#B675C5'],
  policy: ['#147A4F', '#258B5F', '#0D633F', '#4BA776'],
  event: ['#B64735', '#C75A46', '#96392B', '#D47B6A'],
}

function normalizeToken(token: string) {
  return token.replace(/^graph\./, '').replace(/_/g, '-').toLowerCase()
}

function stableIndex(value: string, length: number) {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) hash = (hash * 31 + value.charCodeAt(index)) | 0
  return Math.abs(hash) % length
}

export function graphColor(token: string, theme: GraphTheme = 'dark', seed?: string | number) {
  const normalized = normalizeToken(token)
  const key = normalized === 'project-program' ? 'project' : normalized === 'policy-law' ? 'policy' : normalized
  const palettes = theme === 'light' ? lightPalettes : darkPalettes
  const palette = palettes[key] ?? palettes.chunk
  return palette[stableIndex(`${normalized}:${seed ?? ''}`, palette.length)]
}
