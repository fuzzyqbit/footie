import { statColor, tierColor } from './statColor'

test('statColor ramps red -> green by value', () => {
  expect(statColor(95)).toBe('#16a34a')
  expect(statColor(85)).toBe('#4caf50')
  expect(statColor(72)).toBe('#eab308')
  expect(statColor(65)).toBe('#f97316')
  expect(statColor(40)).toBe('#ef4444')
  expect(statColor(null)).toBe('#2a2a3a')
})

test('tierColor reflects rating tier and treats specials as gold', () => {
  expect(tierColor(99, 'TOTS')).toBe('#e2b714')
  expect(tierColor(91, 'base')).toBe('#e2b714')
  expect(tierColor(85, 'base')).toBe('#cbd5e1')
  expect(tierColor(78, 'base')).toBe('#d97706')
  expect(tierColor(70, 'base')).toBe('#6b7280')
})
