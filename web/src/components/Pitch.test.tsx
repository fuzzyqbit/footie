import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Pitch from './Pitch'
import { MOCK_CARD, MOCK_CHEM, SLOTS_4231 } from '../test/handlers'
import type { Card } from '../types'

const slotCards: Record<string, Card> = Object.fromEntries(
  SLOTS_4231.map(s => [s, MOCK_CARD])
)

test('renders 11 slot cards', () => {
  render(
    <Pitch
      formationSlots={[...SLOTS_4231]}
      slotCards={slotCards}
      chemReport={MOCK_CHEM}
      selectedSlot={null}
      onSlotClick={() => {}}
    />
  )
  expect(screen.getAllByText('91')).toHaveLength(11)
})

test('GK slot appears in the document', () => {
  render(
    <Pitch
      formationSlots={[...SLOTS_4231]}
      slotCards={slotCards}
      chemReport={MOCK_CHEM}
      selectedSlot={null}
      onSlotClick={() => {}}
    />
  )
  expect(screen.getAllByText('GK').length).toBeGreaterThan(0)
})

test('clicking a slot calls onSlotClick with slot name', async () => {
  const user = userEvent.setup()
  const onSlotClick = vi.fn()
  render(
    <Pitch
      formationSlots={[...SLOTS_4231]}
      slotCards={slotCards}
      chemReport={MOCK_CHEM}
      selectedSlot={null}
      onSlotClick={onSlotClick}
    />
  )
  await user.click(screen.getAllByText('GK')[0])
  expect(onSlotClick).toHaveBeenCalledWith('GK')
})

test('selected slot has highlighted border class', () => {
  const { container } = render(
    <Pitch
      formationSlots={[...SLOTS_4231]}
      slotCards={slotCards}
      chemReport={MOCK_CHEM}
      selectedSlot="ST"
      onSlotClick={() => {}}
    />
  )
  const selected = container.querySelector('[data-slot="ST"]')
  expect(selected).toHaveClass('border-gold')
})
