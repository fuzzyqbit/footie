import { render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../test/handlers'
import { MOCK_CARD, MOCK_HAALAND } from '../test/handlers'
import GeneratorPage from './GeneratorPage'

// Two frames across two versions so the background picker has something to show.
const ICON = { ...MOCK_CARD, id: 'icon', version: 'Icon', bg_url: 'https://x/icon.png', image_url: 'https://x/p.png' }
const TOTS = { ...MOCK_HAALAND, id: 'tots', version: 'TOTS', bg_url: 'https://x/tots.png', image_url: 'https://x/p2.png' }

function withFrames() {
  server.use(
    http.get('http://localhost:8026/api/cards', () =>
      HttpResponse.json({ ok: true, data: { total: 2, cards: [ICON, TOTS] }, error: null })),
  )
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <GeneratorPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

test('stat labels switch to GK set when position is GK', async () => {
  const user = userEvent.setup()
  renderPage()
  // outfield default
  expect(screen.getByLabelText('PAC')).toBeInTheDocument()
  await user.selectOptions(screen.getByRole('combobox', { name: 'Position' }), 'GK')
  // GK labels replace outfield ones
  expect(screen.getByLabelText('DIV')).toBeInTheDocument()
  expect(screen.queryByLabelText('PAC')).not.toBeInTheDocument()
})

test('name input updates the live preview', async () => {
  const user = userEvent.setup()
  renderPage()
  await user.type(screen.getByPlaceholderText(/mbappe/i), 'Zlatan')
  // appears in the card overlay (uppercased via CSS, raw text in DOM)
  expect(screen.getByText('Zlatan')).toBeInTheDocument()
})

test('background picker lists one labelled frame per version', async () => {
  withFrames()
  renderPage()
  const icon = await screen.findByRole('button', { name: /Icon/ })
  const tots = screen.getByRole('button', { name: /TOTS/ })
  expect(icon).toBeInTheDocument()
  expect(tots).toBeInTheDocument()
  // first available frame is selected by default
  expect(within(icon).getByRole('img')).toHaveAttribute('src', ICON.bg_url)
})
