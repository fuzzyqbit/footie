import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Sidebar from './Sidebar'
import { toggleWatch, clearWatchlist } from '../watchlist'
import { MOCK_CARD } from '../test/handlers'

beforeEach(() => clearWatchlist())

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

test('Flagged link shows a count badge when players are flagged', () => {
  toggleWatch(MOCK_CARD)
  renderSidebar()
  const flagged = screen.getByRole('link', { name: /flagged/i })
  expect(within(flagged).getByText('1')).toBeInTheDocument()
})

test('Flagged link has no badge when nothing is flagged', () => {
  renderSidebar()
  const flagged = screen.getByRole('link', { name: /flagged/i })
  expect(within(flagged).queryByText('1')).not.toBeInTheDocument()
})
