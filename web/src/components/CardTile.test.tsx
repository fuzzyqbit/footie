import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CardTile from './CardTile'
import { MOCK_CARD } from '../test/handlers'

test('shows OVR, name, position, price', () => {
  render(<CardTile card={MOCK_CARD} />)
  expect(screen.getByText('91')).toBeInTheDocument()
  expect(screen.getByText('Mbappe')).toBeInTheDocument()
  expect(screen.getByText('ST')).toBeInTheDocument()
  expect(screen.getByText('1.2M')).toBeInTheDocument()
})

test('click expands to show face stats', async () => {
  const user = userEvent.setup()
  render(<CardTile card={MOCK_CARD} />)
  expect(screen.queryByText('PAC')).not.toBeInTheDocument()
  await user.click(screen.getByText('Mbappe'))
  expect(screen.getByText('PAC')).toBeInTheDocument()
  expect(screen.getByText('97')).toBeInTheDocument()
})

test('click again collapses stats', async () => {
  const user = userEvent.setup()
  render(<CardTile card={MOCK_CARD} />)
  await user.click(screen.getByText('Mbappe'))
  await user.click(screen.getByText('Mbappe'))
  expect(screen.queryByText('PAC')).not.toBeInTheDocument()
})

test('shows null price as —', () => {
  render(<CardTile card={{ ...MOCK_CARD, price: null }} />)
  expect(screen.getByText('—')).toBeInTheDocument()
})
