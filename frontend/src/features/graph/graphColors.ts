const tokenColors: Record<string, string> = {
  'graph.document': '#E6A86C', 'graph.organization': '#E6A86C', 'graph.org-unit': '#F0C894', 'graph.person': '#A994FF', 'graph.country': '#6CA8FF', 'graph.region': '#8DC7FF', 'graph.place': '#7BE2D4', 'graph.technology': '#73D6C8', 'graph.equipment': '#F39A6B', 'graph.system': '#8C86FF', 'graph.project': '#D78BE8', 'graph.policy': '#69D49A', 'graph.event': '#FF8B72',
}

export function graphColor(token: string) { return tokenColors[token] ?? '#8EA5B9' }
