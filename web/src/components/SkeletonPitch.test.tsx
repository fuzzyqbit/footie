import { render } from '@testing-library/react'
import SkeletonPitch from './SkeletonPitch'

test('renders animated placeholder tiles', () => {
  const { container } = render(<SkeletonPitch />)
  // 1 + 4 + 2 + 3 + 1 = 11 placeholder tiles
  expect(container.querySelectorAll('.animate-pulse')).toHaveLength(11)
})
