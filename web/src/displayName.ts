// The scraped data labels some Icons by their legal/birth name. Show the common
// name players actually know instead. Keyed on the exact full name (not a
// fragment) so e.g. "Wesley Vinícius França Lima" is never mistaken for Vini Jr.
const ALIASES: Record<string, string> = {
  'de Assis Moreira': 'Ronaldinho',
  'dos Santos Leite': 'Kaká',
  'da Silva Rocha': 'Roberto Carlos',
  'Nazário de Lima': 'Ronaldo (R9)',
  'Vinícius José de Oliveira Júnior': 'Vinícius Júnior',
}

export function displayName(name: string): string {
  return ALIASES[name] ?? name
}
