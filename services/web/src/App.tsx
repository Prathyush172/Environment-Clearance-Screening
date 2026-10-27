import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { DisclaimerBanner } from './components/DisclaimerBanner';
import { NewScreening } from './pages/NewScreening';
import { RunView } from './pages/RunView';
import { History } from './pages/History';
import { Quarantine } from './pages/Quarantine';
import { Ops } from './pages/Ops';
import { About } from './pages/About';
import { Trees, FileText, History as HistoryIcon, ShieldAlert, Activity, Info } from 'lucide-react';

const NavLink: React.FC<{ to: string; children: React.ReactNode; icon: React.ReactNode }> = ({ to, children, icon }) => {
  const location = useLocation();
  const isActive = location.pathname === to || (to !== '/' && location.pathname.startsWith(to));
  return (
    <Link
      to={to}
      className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs sm:text-sm font-medium transition ${
        isActive ? 'bg-emerald-800 text-white' : 'text-emerald-100 hover:bg-emerald-800/60 hover:text-white'
      }`}
    >
      {icon}
      {children}
    </Link>
  );
};

export const AppContent: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <DisclaimerBanner />
      
      {/* Header / Navigation */}
      <header className="bg-emerald-900 border-b border-emerald-950 text-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2">
            <Trees className="w-6 h-6 text-emerald-400" />
            <div>
              <div className="font-bold text-base leading-tight tracking-tight">EIA Pre-Screening</div>
              <div className="text-[10px] text-emerald-300">MoEFCC Notification 2006 Classification</div>
            </div>
          </Link>

          <nav className="flex items-center gap-1 sm:gap-2">
            <NavLink to="/" icon={<FileText className="w-4 h-4" />}>New Screening</NavLink>
            <NavLink to="/history" icon={<HistoryIcon className="w-4 h-4" />}>History</NavLink>
            <NavLink to="/quarantine" icon={<ShieldAlert className="w-4 h-4" />}>Quarantine</NavLink>
            <NavLink to="/ops" icon={<Activity className="w-4 h-4" />}>Ops</NavLink>
            <NavLink to="/about" icon={<Info className="w-4 h-4" />}>About</NavLink>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<NewScreening />} />
          <Route path="/runs/:id" element={<RunView />} />
          <Route path="/history" element={<History />} />
          <Route path="/quarantine" element={<Quarantine />} />
          <Route path="/ops" element={<Ops />} />
          <Route path="/about" element={<About />} />
        </Routes>
      </main>

      <footer className="border-t border-gray-200 bg-white py-4 text-center text-xs text-gray-500">
        Environmental Clearance Pre-Screening Service &copy; 2026. Automated screening opinion only.
      </footer>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <Router>
      <AppContent />
    </Router>
  );
};

export default App;
