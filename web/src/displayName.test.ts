import { displayName } from './displayName'

test('maps birth-name icons to common names', () => {
  expect(displayName('de Assis Moreira')).toBe('Ronaldinho')
  expect(displayName('dos Santos Leite')).toBe('Kaká')
  expect(displayName('da Silva Rocha')).toBe('Roberto Carlos')
  expect(displayName('Vinícius José de Oliveira Júnior')).toBe('Vinícius Júnior')
})

test('passes through unknown names unchanged', () => {
  expect(displayName('Harry Kane')).toBe('Harry Kane')
  // a different player who merely shares a name fragment must not be aliased
  expect(displayName('Wesley Vinícius França Lima')).toBe('Wesley Vinícius França Lima')
})
