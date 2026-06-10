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
| Cristiano Ronaldo | Team of the Season (TOTS) | 95 | ST | **93** | 96 | 87 | 93 | 45 | 88 | Controlled | 5★/5★ | **Rapid, Quick Step**, Finesse Shot, Power Shot, Trickster, Technical |
| Rodri | Festival of Football: Path to Glory | 96 | CDM/CM | 90 | 88 | 96 | 95 | 94 | 92 | Controlled | 5★/5★ | Intercept, Anticipate, Pinged Pass, Tiki Taka |

> Full PlayStyle lists:
> - **Ronaldo (TOTS):** Finesse Shot, Low Driven, Quick Step, Power Shot, Precision
>   Header, Game Changer, Incisive Pass, Technical, Rapid, Trickster.
>   (187cm · Portugal · Al Nassr · ROSHN Saudi League.)
> - **Rodri (PTG):** PlayStyles+ are the four bolded in the table (Intercept,
>   Anticipate, Pinged Pass, Tiki Taka); plain PlayStyles: Power Shot, Incisive
>   Pass, Long Ball, Aerial Fortress, Technical, Press Proven, Bruiser.
>   (190cm · Spain · Manchester City · Premier League · Age 30.)
>   *Corrected 2026-06-10 against the live fut.gg card page — an earlier crawl
>   wrongly listed Incisive Pass and Press Proven as PlayStyles+.*

---

## Fast special cards — ranked by PAC
Special cards with a pace-relevant profile, sorted by Pace (the fast-meta list).

| Rank | Player | Card | OVR | Pos | PAC | AcceleRATE | Pace PlayStyles+ |
|---:|---|---|---:|:--:|---:|:--:|---|
| 1 | Cristiano Ronaldo | TOTS | 95 | ST | 93 | Controlled | Rapid, Quick Step |

> **Read:** 93 PAC with **Rapid+ + Quick Step+** makes Ronaldo TOTS play faster than
> his raw number on the ball and off the first step. The one knock is **Controlled**
> AcceleRATE (height 187cm) — he won't have the instant burst of an Explosive winger,
> but Quick Step+ narrows that gap. Elite as an Advanced Forward / Poacher (`04`).

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
