import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server, MOCK_CHEM } from '../test/handlers'
import BuildPage from './BuildPage'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <BuildPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

test('renders formation and budget inputs', async () => {
  renderPage()
  expect(await screen.findByLabelText(/formation/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/budget/i)).toBeInTheDocument()
})

test('Build button fires POST /api/build and shows pitch', async () => {
  const user = userEvent.setup()
  let buildCalled = false
  server.use(
    http.post('http://localhost:8026/api/build', () => {
      buildCalled = true
      return HttpResponse.json({ ok: true, data: {
        formation: '4-2-3-1', seed_cost: 100000, total_cost: 500000, team_chem: 33,
        xi: [], squad: { name: 'built', formation: '4-2-3-1', starting_xi: {} },
      }, error: null })
    })
  )
  renderPage()
  await user.type(await screen.findByLabelText(/budget/i), '500K')
  await user.click(screen.getByRole('button', { name: /^build$/i }))
  await waitFor(() => expect(buildCalled).toBe(true))
})

test('shows error when build fails', async () => {
  server.use(
    http.post('http://localhost:8026/api/build', () =>
      HttpResponse.json({ ok: false, data: null, error: 'Budget too low' }))
  )
  const user = userEvent.setup()
  renderPage()
  await user.type(await screen.findByLabelText(/budget/i), '1K')
  await user.click(screen.getByRole('button', { name: /^build$/i }))
  expect(await screen.findByText(/Budget too low/i)).toBeInTheDocument()
})

test('Save squad button appears after build result', async () => {
  const user = userEvent.setup()
  renderPage()
  await user.type(await screen.findByLabelText(/budget/i), '500K')
  await user.click(screen.getByRole('button', { name: /^build$/i }))
  expect(await screen.findByRole('button', { name: /save squad/i })).toBeInTheDocument()
})

test('swapping a slot fires chem and saving fires PUT', async () => {
  const user = userEvent.setup()
  let chemCalled = false
  let putCalled = false
  server.use(
    http.post('http://localhost:8026/api/chem', () => {
      chemCalled = true
      return HttpResponse.json({ ok: true, data: MOCK_CHEM, error: null })
    }),
    http.put('http://localhost:8026/api/squads/:name', () => {
      putCalled = true
      return HttpResponse.json({ ok: true, data: { name: 'built-squad', path: '' }, error: null })
    }),
  )
  renderPage()
  await user.type(await screen.findByLabelText(/budget/i), '500K')
  await user.click(screen.getByRole('button', { name: /^build$/i }))
  await screen.findAllByText('91')
  await user.click(screen.getAllByText('GK')[0])
  await user.click(await screen.findByText('Haaland'))
  await waitFor(() => expect(chemCalled).toBe(true))
  await user.click(screen.getByRole('button', { name: /save squad/i }))
  await waitFor(() => expect(putCalled).toBe(true))
})
