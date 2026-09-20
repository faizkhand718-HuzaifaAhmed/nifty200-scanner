# NIFTY 200 Opportunity Scanner — Frontend (Phases 8–9, 11, 13)

## Running it

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000 (redirects to `/dashboard`).

## What's real vs. mocked

Every number on this dashboard is currently **mock data** (`lib/mockData.ts`),
shaped to match the real backend's actual output fields (see the comments in
`lib/types.ts` pointing at the specific Python source). No FastAPI HTTP layer
exists yet — only the underlying Python engines (Phases 2–13) do. `lib/api.ts`
has a `TODO` at every function marking exactly what real call replaces the
mock, so wiring up the backend later is a fetch-call swap, not a rewrite.

"Ranking must automatically update when new data arrives" is currently a
15-second client-side poll (`subscribeToLiveRankings`), not a live push —
it's structured so a real WebSocket subscription can replace the polling
loop with no change to any calling code.

## Verification status — please read before trusting this

This sandbox has no network access, so I could not `npm install` or run a
real Next.js dev server here. What I *did* verify:

1. **Every pure `.ts` logic file** (`types.ts`, `format.ts`, `mockData.ts`,
   `candles.ts`, `mockChartData.ts`, `alerts.ts`, `mockAlerts.ts`,
   `paperTrading.ts`, `mockPaperTrading.ts`) — type-checked cleanly with the
   real TypeScript compiler (`tsc --strict`), no shims needed since none of
   these touch React. Several were also **actually executed** via `ts-node`
   with real assertions on the output (see the phase sections below).
2. **Every `.tsx` component and page** — type-checked cleanly against
   hand-written minimal shims for React/Next's API (not the real
   `@types/react`/`next` packages, which aren't installable here without
   network). This confirms correct JSX syntax, prop usage, imports, and
   `@/...` path-alias resolution, but a simplified shim can't catch every
   edge case the real type packages would. The shim itself needed several
   small fixes along the way (`useRef<T>(null)`, `JSX.IntrinsicAttributes`
   for `key`, `ChangeEvent`) — each one was a gap in my shim, not a bug in
   the actual component code, but flagged in each phase's notes below since
   the distinction matters.
3. **The visual design** — built and iterated as a standalone
   `preview.html` (plain HTML/CSS/JS, same design tokens, no build step),
   screenshotted with Playwright at both desktop (1440px) and mobile
   (390px) widths, and revised based on what the screenshots showed (the
   first mobile table pass was too dense — 17 stacked fields per row — and
   was replaced with the compact 2-line card list you see now).

**Please run `npm install && npm run dev` and look at it yourself before
treating this as done.** The individual pieces are verified; the whole
assembled app, rendered by a real Next.js server, is not.

## Files

```
frontend/
├── app/
│   ├── layout.tsx              root layout
│   ├── page.tsx                redirects to /dashboard
│   ├── globals.css             design tokens, base styles
│   ├── dashboard/page.tsx      main dashboard (client component)
│   ├── stocks/[symbol]/page.tsx  detail page (server component)
│   └── paper-trading/page.tsx  open/closed positions + summary metrics
├── components/
│   ├── Badges.tsx               DirectionBadge, StatusBadge
│   ├── MarketStatusBar.tsx      top status strip
│   ├── OpportunityCard.tsx      Top Long / Top Short hero cards
│   ├── Top5Column.tsx           Top 5 Long/Short lists
│   ├── FilterBar.tsx            filter chips + view-size toggle
│   ├── RankingTable.tsx         main table (desktop) / card list (mobile)
│   ├── CandlestickChart.tsx     lightweight-charts wrapper (render-only)
│   ├── ChartSection.tsx         timeframe + overlay state, loads chart data
│   ├── TimeframeSelector.tsx    1m/3m/5m/10m/15m/30m/Daily buttons
│   ├── OverlayToggles.tsx       VWAP/EMA/PDH/PDL/S/R visibility chips
│   ├── AlertCenter.tsx          orchestrates the alert subscription + 3 channels
│   ├── AlertBell.tsx            header bell icon, unread badge, history panel
│   ├── AlertToast.tsx           transient toast stack (the "dashboard alert" channel)
│   └── PaperTradeButton.tsx     "allow the user to create a virtual position"
├── lib/
│   ├── types.ts                 data contracts, mapped to backend fields
│   ├── format.ts                price/percent/volume formatting
│   ├── mockData.ts              placeholder ranking data
│   ├── candles.ts                chart data contracts + the no-client-side-
│   │                             indicator-math rule (read this one first)
│   ├── mockChartData.ts         QUARANTINED mock chart generator - delete
│   │                             once the real /api/chart endpoint exists
│   ├── alerts.ts                 alert types, mapped to backend fields
│   ├── mockAlerts.ts             mock alert stream generator
│   ├── browserNotifications.ts  Notification API wrapper
│   ├── soundAlert.ts             Web Audio oscillator tone generator
│   ├── paperTrading.ts           paper-position types, mapped to backend fields
│   ├── mockPaperTrading.ts       mock in-memory position store
│   └── api.ts                   API client (mocked, TODO-marked for real wiring)
├── preview.html                 standalone visual preview, no build needed
├── package.json / tsconfig.json / tailwind.config.js / next.config.js / postcss.config.js
```

## Known gaps / things to review

- **Charts**: `lightweight-charts` has never actually been installed or
  rendered here (no network for `npm install`) — please verify the chart
  renders correctly, resizes properly, and markers land on the right bars
  once you run it.
- **Alerts**: browser Notification permission flow, real Web Audio
  playback, and toast stack timing/appearance are all unverified — need a
  real browser.
- **Paper trading**: `closePaperPositionManually` uses a plain
  `window.prompt()` for the exit price — functional but crude; a real
  modal/form would be a quick upgrade before this feels production-ready.
- **Mobile table columns**: only Symbol/Price/Change%/Direction/Score/Status
  show on mobile; Volume/RSI/ADX/Entry/SL/Target/R:R require tapping through
  to the detail page. Confirm this tradeoff matches how you'll actually use
  it on a phone.
- **Detail page score breakdown** shows all 9 scoring categories (Trend,
  Volume, VWAP, Momentum, EMA Structure, Breakout/Breakdown, Market
  Confirmation, Relative Strength, Risk/Volatility) even though the summary
  table only carries Trend/Volume/VWAP forward, per the Phase 7 spec.
- **Market regime/strength labels** ("Trending"/"Ranging", "Weak"/
  "Moderate"/"Strong") are display-only derivations with no backend field
  behind them yet — see the comment in `lib/types.ts`.

## Phase 9: charts

`components/CandlestickChart.tsx` wraps `lightweight-charts` (TradingView's
library) and renders candles, overlays, setup markers, and trade-plan
levels. **It performs no indicator calculation of any kind** — see the
header comment in `lib/candles.ts` for the hard rule this project follows:
every overlay value must come from the backend's `IndicatorEngine` output,
never recomputed in the browser. `lib/mockChartData.ts` is the one
deliberate, loudly-commented exception: it fakes a plausible backend
response shape (including EMA/VWAP math) purely so there's something to
render before the real `/api/chart` endpoint exists. **Delete that file
entirely** once the real endpoint is wired up — it is not a fallback.

### Verification performed for Phase 9

- `lib/candles.ts`, `lib/mockChartData.ts` — clean real `tsc --strict`
  pass (no shims needed, no React/Next dependency).
- **Actually executed** `generateMockChartData()` via `ts-node` and
  checked the output: correct candle counts per timeframe (180 intraday,
  90 daily), zero OHLC invariant violations across every candle, correct
  overlay point counts, sensible markers, correctly-wired trade-plan
  values pulled from the ranking mock data.
- Every `.tsx` file including the new chart components — clean `tsc`
  pass against hand-written shims, now including a `lightweight-charts`
  shim (that package isn't installed here either — no network for
  `npm install`). This caught one real shim gap worth knowing about: my
  first `useRef` shim didn't support the standard `useRef<T>(null)`
  pattern used for DOM refs, which real `@types/react` handles via an
  overload — fixed in the shim, not a bug in the component code.
- **Not verified**: the chart actually rendering in a browser via
  `lightweight-charts`' real runtime behavior (chart creation, resize
  handling, marker positioning). That needs `npm install && npm run dev`
  and eyes on it — please do that before trusting this.

## Phase 11: alerts

Backend (`backend/app/alerts/`): `AlertEngine.evaluate()` checks all 11
alert types per bar per symbol, edge-triggered (fires on transitions, not
on a condition merely being true this bar) and deduped via `AlertHistory`
keyed on `(symbol, alert_type, direction, candle_timestamp)`. VWAP
reclaim/rejection reuse Phase 10's own crossing-detection functions
rather than reimplementing them.

Frontend: three delivery channels wired to the mock alert stream via
`AlertCenter.tsx`:
- **Dashboard alert** — `AlertToast.tsx`, transient toasts, always on.
- **Browser notification** — `lib/browserNotifications.ts`, requires an
  explicit permission grant (button click, not auto-requested on load).
- **Sound** — `lib/soundAlert.ts`, a Web Audio oscillator tone (no bundled
  audio file — there was no network here to fetch one anyway), starts
  OFF and requires an explicit opt-in toggle.

The alert history panel (`AlertBell.tsx`) shows the last 100 alerts with
type/direction/time.

### Verification performed for Phase 11

- Backend: 32/32 tests pass on real execution, including a full
  duplicate-suppression scenario (same bar processed twice → alert fires
  once). **Caught and fixed a real bug**: `AlertHistory` defines
  `__len__`, which made an *empty* history instance falsy — silently
  breaking the `history or AlertHistory()` constructor pattern used
  throughout this codebase (an empty-but-valid caller-supplied history
  was being discarded and replaced). Fixed with explicit `is None`
  checks. Every other engine's config defaults use this same `x or
  Default()` pattern safely, since none of those other classes define
  `__len__`/`__bool__` — this was specific to `AlertHistory`.
- Frontend: `lib/alerts.ts` and `lib/mockAlerts.ts` — clean `tsc --strict`
  pass, then **actually executed** via `ts-node`: 10 unique mock alerts
  generated with zero duplicate IDs, stream correctly exhausts. Also
  caught and fixed a real conceptual bug in `alertTone()`: my first
  version colored `TARGET`/`STOP_LOSS` by trade direction, which meant a
  SHORT trade hitting its target (a win) would have shown red. Fixed to
  be outcome-based (target=green, stop=red, regardless of direction) and
  verified by execution.
- All `.tsx` files — clean `tsc` pass against the shims, which needed one
  addition this phase: `JSX.IntrinsicAttributes` for the `key` prop on
  mapped list items (a shim gap, not a code bug — real `@types/react`
  handles this automatically).
- **Not verified**: actual browser Notification permission flow, real
  Web Audio playback, or the toast stack's visual appearance/timing —
  all need a real browser, which needs `npm install && npm run dev`.

## Phase 13: paper trading

Backend (`backend/app/paper_trading/`): `PaperTradingEngine` tracks virtual
positions end to end (open → automatic stop/target close, or manual close).
Opening a position is always an explicit caller action — the engine never
opens one on its own just because an entry signal exists elsewhere.
`integration.py` bridges Phase 10's `TradeLifecycle` (at the moment it's in
`ENTRY_TRIGGER`) into a paper position, matching "when an ENTRY signal
occurs, allow the user to create a virtual position" literally. "No real
orders should be sent" is enforced the same way Phase 10 enforced its
scoring-independence rule: an architectural test inspects this package's
actual imports and fails the build if any networking/broker library ever
shows up there.

Frontend: `components/PaperTradeButton.tsx` is the "allow the user" part —
it renders on the stock detail page, prefills quantity/entry/stop/target/
score from the stock's already-computed data, and only acts on click.
`app/paper-trading/page.tsx` shows open positions, closed positions, and
the 4 requested summary metrics (Today's P&L, Win rate, Average R, Max
drawdown).

### Verification performed for Phase 13

- Backend: 33/33 tests pass on real execution on the first run, plus a
  full regression pass across all 13 phases (500+ checks, zero failures).
- Frontend: `lib/paperTrading.ts` and `lib/mockPaperTrading.ts` — clean
  `tsc --strict` pass, then **actually executed** via `ts-node`: opened a
  position, closed it, and confirmed the exact expected P&L
  ((1870-1846.5)×20 = 470), correct win classification, and that
  double-closing an already-closed position is correctly blocked.
- `PaperTradeButton.tsx` needed one more shim fix: an `onChange` handler's
  event parameter had no type to infer from (real `@types/react` would
  provide this via `JSX.IntrinsicElements["input"]`) - added a minimal
  `ChangeEvent` type to the shim and an explicit annotation in the
  component, which is the more defensive way to write it regardless.
- **Not verified**: the paper-trading page rendering in a real browser,
  or the `window.prompt()`-based manual-close flow's actual UX.
