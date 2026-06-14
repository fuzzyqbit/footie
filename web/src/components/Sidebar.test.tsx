import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Sidebar from './Sidebar'

function renderSidebar(path = '/cards') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar />
    </MemoryRouter>
  )
}

test('renders four nav links', () => {
  renderSidebar()
  expect(screen.getByRole('link', { name: /cards/i })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /squads/i })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /build/i })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /upgrade/i })).toBeInTheDocument()
})

test('active link has gold styling', () => {
  renderSidebar('/squads')
  const squadsLink = screen.getByRole('link', { name: /squads/i })
  expect(squadsLink).toHaveClass('text-gold')
})
