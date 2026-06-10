# 11 — Special Cards Tracker (crawled from fut.gg)

**This is the special-card data that the list pages couldn't give us.** While
`fut.gg`'s *list* page is a JavaScript app (no data to a fetcher), its **individual
player-card pages are server-rendered** and crawl cleanly — full stats, PlayStyles,
and AcceleRATE.

### How to add a card
Paste a `fut.gg` player-card URL (the per-card link, e.g.
`https://www.fut.gg/players/231866-rodri/26-84117946/`) and I'll extract it into the
table below and commit it. For **fast players**, send the speedsters' special cards
and they'll slot into the pace ranking.

---

## Tracked special cards

| Player | Card Version | OVR | Pos | PAC | SHO | PAS | DRI | DEF | PHY | AcceleRATE | SM/WF | Key PlayStyles+ |
|---|---|---:|:--:|---:|---:|---:|---:|---:|---:|:--:|:--:|---|
| Rodri | Festival of Football: Path to Glory | 96 | CDM/CM | 90 | 88 | 96 | 95 | 94 | 92 | Controlled | 5★/5★ | Intercept, Anticipate, Pinged Pass, Tiki Taka, Incisive Pass, Press Proven |

> Full PlayStyle list for Rodri: Intercept, Anticipate, Pinged Pass, Tiki Taka,
> Power Shot, Incisive Pass, Long Ball, Aerial Fortress, Technical, Press Proven,
> Bruiser. (190cm · Spain · Manchester City · Premier League · Age 30.)

---

## Notes for the fast-player focus
- **Rodri** here is a control/passing monster, not a pace card (90 PAC, **Controlled**
  AcceleRATE) — elite as a Holding/DLP anchor (see `04`), but not part of the speed
  meta.
- To build the **fast special-card list**, send cards for the speedsters from the
  master list in `docs/10` (Mbappé, Adeyemi, Vini Jr., Frimpong, Doku, Openda, etc.)
  — their special versions are the ones that turn into meta monsters.
- Remember the `09` rule: a special card's **AcceleRATE flip to Explosive/Lengthy**
  matters more than raw +PAC. I'll flag each card's archetype as it's added.
