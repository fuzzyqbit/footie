import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PlayerDropdown from './PlayerDropdown'
import { MOCK_CARD, MOCK_HAALAND } from '../test/handlers'

const cards = [MOCK_CARD, MOCK_HAALAND]

test('shows search input on render', () => {
  render(<PlayerDropdown slot="ST" cards={cards} onSwap={() => {}} onClose={() => {}} />)
  expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument()
})

test('lists available cards', () => {
  render(<PlayerDropdown slot="ST" cards={cards} onSwap={() => {}} onClose={() => {}} />)
  expect(screen.getByText('Mbappe')).toBeInTheDocument()
  expect(screen.getByText('Haaland')).toBeInTheDocument()
})

test('filters list by search term', async () => {
  const user = userEvent.setup()
  render(<PlayerDropdown slot="ST" cards={cards} onSwap={() => {}} onClose={() => {}} />)
  await user.type(screen.getByPlaceholderText(/search/i), 'haa')
  expect(screen.queryByText('Mbappe')).not.toBeInTheDocument()
  expect(screen.getByText('Haaland')).toBeInTheDocument()
})

test('clicking a player calls onSwap with slot and card id', async () => {
  const user = userEvent.setup()
  const onSwap = vi.fn()
  render(<PlayerDropdown slot="ST" cards={cards} onSwap={onSwap} onClose={() => {}} />)
  await user.click(screen.getByText('Haaland'))
  expect(onSwap).toHaveBeenCalledWith('ST', 'haaland--base')
})

test('Escape key calls onClose', async () => {
  const user = userEvent.setup()
  const onClose = vi.fn()
  render(<PlayerDropdown slot="ST" cards={cards} onSwap={() => {}} onClose={onClose} />)
  await user.keyboard('{Escape}')
  expect(onClose).toHaveBeenCalled()
})
