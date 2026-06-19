import { Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import Sidebar from './components/Sidebar'
import SkeletonGrid from './components/SkeletonGrid'

// Pages are lazy-loaded at module top level (never inside the component — that
// would reset state every render) so each becomes its own chunk and the heavy
// GeneratorPage graph (@imgly WASM/ML) stays out of the initial download.
const CardsPage = lazy(() => import('./pages/CardsPage'))
const SquadsPage = lazy(() => import('./pages/SquadsPage'))
const BuildPage = lazy(() => import('./pages/BuildPage'))
const UpgradePage = lazy(() => import('./pages/UpgradePage'))
const UpdatesPage = lazy(() => import('./pages/UpdatesPage'))
const ValuePage = lazy(() => import('./pages/ValuePage'))
const WatchlistPage = lazy(() => import('./pages/WatchlistPage'))
const ComparePage = lazy(() => import('./pages/ComparePage'))
const ObjectivesPage = lazy(() => import('./pages/ObjectivesPage'))
const SbcsPage = lazy(() => import('./pages/SbcsPage'))
const GeneratorPage = lazy(() => import('./pages/GeneratorPage'))

export default function App() {
  return (
    <div className="flex h-screen bg-navy text-fg overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">
        <Suspense fallback={<SkeletonGrid />}>
          <Routes>
            <Route path="/" element={<Navigate to="/cards" replace />} />
            <Route path="/cards" element={<CardsPage />} />
            <Route path="/squads" element={<SquadsPage />} />
            <Route path="/build" element={<BuildPage />} />
            <Route path="/upgrade" element={<UpgradePage />} />
            <Route path="/updates" element={<UpdatesPage />} />
            <Route path="/value" element={<ValuePage />} />
            <Route path="/watchlist" element={<WatchlistPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/objectives" element={<ObjectivesPage />} />
            <Route path="/sbcs" element={<SbcsPage />} />
            <Route path="/create" element={<GeneratorPage />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  )
}
