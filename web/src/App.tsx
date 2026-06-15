import { Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import CardsPage from './pages/CardsPage'
import SquadsPage from './pages/SquadsPage'
import BuildPage from './pages/BuildPage'
import UpgradePage from './pages/UpgradePage'
import UpdatesPage from './pages/UpdatesPage'
import ValuePage from './pages/ValuePage'
import WatchlistPage from './pages/WatchlistPage'
import ComparePage from './pages/ComparePage'
import ObjectivesPage from './pages/ObjectivesPage'

export default function App() {
  return (
    <div className="flex h-screen bg-navy text-white overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">
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
        </Routes>
      </main>
    </div>
  )
}
