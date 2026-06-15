import { render, screen } from '@testing-library/react'
import StatRadar from './StatRadar'

test('renders an svg radar with a value polygon and one dot per stat', () => {
  const { container } = render(<StatRadar values={[97, 90, 85, 95, 36, 78]} />)
  expect(screen.getByRole('img', { name: /face stat radar/i })).toBeInTheDocument()
  // 3 grid rings + 1 value polygon
  expect(container.querySelectorAll('polygon')).toHaveLength(4)
  // one vertex dot per stat
  expect(container.querySelectorAll('circle')).toHaveLength(6)
})

test('treats null stats as zero without crashing', () => {
  const { container } = render(<StatRadar values={[null, null, null, null, null, null]} />)
  expect(container.querySelectorAll('circle')).toHaveLength(6)
})
