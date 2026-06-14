import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from '../test/handlers'
import UpgradePage from './UpgradePage'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <UpgradePage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

test('renders squad selector and budget input', async () => {
  renderPage()
  expect(await screen.findByLabelText(/squad/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/budget/i)).toBeInTheDocument()
})

test('Find upgrades button fires POST /api/upgrade', async () => {
  let called = false
  server.use(
    http.post('http://localhost:8026/api/upgrade', () => {
      called = true
      return HttpResponse.json({ ok: true, data: {
        swaps: [], spent: 0, budget: 500000,
        score_before: 10, score_after: 10, chem_before: 33, chem_after: 33, warnings: [],
      }, error: null })
    })
  )
  const user = userEvent.setup()
  renderPage()
  const squadSelect = await screen.findByLabelText(/squad/i)
  await screen.findByRole('option', { name: 'test-squad' })
  await user.selectOptions(squadSelect, 'test-squad')
  await user.type(screen.getByLabelText(/budget/i), '500K')
  await user.click(screen.getByRole('button', { name: /find upgrades/i }))
  await waitFor(() => expect(called).toBe(true))
})

test('shows swap suggestions', async () => {
  const user = userEvent.setup()
  renderPage()
  const squadSelect = await screen.findByLabelText(/squad/i)
  await screen.findByRole('option', { name: 'test-squad' })
  await user.selectOptions(squadSelect, 'test-squad')
  await user.type(screen.getByLabelText(/budget/i), '500K')
  await user.click(screen.getByRole('button', { name: /find upgrades/i }))
  expect(await screen.findByText('Haaland')).toBeInTheDocument()
  expect(screen.getByText('ST')).toBeInTheDocument()
})

test('shows "No upgrades found" when swaps is empty', async () => {
  server.use(
    http.post('http://localhost:8026/api/upgrade', () =>
      HttpResponse.json({ ok: true, data: {
        swaps: [], spent: 0, budget: 100000,
        score_before: 10, score_after: 10, chem_before: 33, chem_after: 33, warnings: [],
      }, error: null }))
  )
  const user = userEvent.setup()
  renderPage()
  const squadSelect = await screen.findByLabelText(/squad/i)
  await screen.findByRole('option', { name: 'test-squad' })
  await user.selectOptions(squadSelect, 'test-squad')
  await user.type(screen.getByLabelText(/budget/i), '100K')
  await user.click(screen.getByRole('button', { name: /find upgrades/i }))
  expect(await screen.findByText(/no upgrades found/i)).toBeInTheDocument()
})
