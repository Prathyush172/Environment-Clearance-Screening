import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom';
import { DisclaimerBanner } from './components/DisclaimerBanner';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AuthProvider, useAuth } from './context/AuthContext';
import { NewScreening } from './pages/NewScreening';
import { RunView } from './pages/RunView';
import { History } from './pages/History';
import { Quarantine } from './pages/Quarantine';
import { Ops } from './pages/Ops';
import { About } from './pages/About';
import { Login } from './pages/Login';
import {
  Trees,
  FileText,
  History as HistoryIcon,
  ShieldAlert,
  Activity,
  Info,
  LogOut,
  User as UserIcon,
  LogIn
} from 'lucide-react';

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
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

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

          {/* Navigation Links */}
          <nav className="flex items-center gap-1 sm:gap-2">
            <NavLink to="/" icon={<FileText className="w-4 h-4" />}>New Screening</NavLink>
            <NavLink to="/history" icon={<HistoryIcon className="w-4 h-4" />}>History</NavLink>
            {user?.role === "admin" && (
              <>
                <NavLink to="/quarantine" icon={<ShieldAlert className="w-4 h-4" />}>Quarantine</NavLink>
                <NavLink to="/ops" icon={<Activity className="w-4 h-4" />}>Ops</NavLink>
              </>
            )}
            <NavLink to="/about" icon={<Info className="w-4 h-4" />}>About</NavLink>
          </nav>

          {/* User Account / Auth Status */}
          <div className="flex items-center gap-3">
            {isAuthenticated && user ? (
              <div className="flex items-center gap-2.5 bg-emerald-950/60 border border-emerald-800/80 px-3 py-1.5 rounded-lg text-xs">
                <UserIcon className="w-3.5 h-3.5 text-emerald-300" />
                <div className="text-left">
                  <div className="font-semibold text-emerald-100 leading-none">
                    {user.username}
                  </div>
                  <div className="text-[10px] text-emerald-400 mt-0.5">
                    {user.role.toUpperCase()} &bull; {user.client_id}
                  </div>
                </div>
                <button
                  onClick={handleLogout}
                  className="ml-2 p-1 text-emerald-300 hover:text-white hover:bg-emerald-800 rounded transition"
                  title="Sign Out"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white rounded-lg text-xs font-semibold shadow-sm transition"
              >
                <LogIn className="w-3.5 h-3.5" />
                Sign In
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <NewScreening />
              </ProtectedRoute>
            }
          />
          <Route
            path="/runs/:id"
            element={
              <ProtectedRoute>
                <RunView />
              </ProtectedRoute>
            }
          />
          <Route
            path="/history"
            element={
              <ProtectedRoute>
                <History />
              </ProtectedRoute>
            }
          />
          <Route
            path="/quarantine"
            element={
              <ProtectedRoute allowedRoles={["admin", "auditor"]}>
                <Quarantine />
              </ProtectedRoute>
            }
          />
          <Route
            path="/ops"
            element={
              <ProtectedRoute allowedRoles={["admin", "auditor"]}>
                <Ops />
              </ProtectedRoute>
            }
          />
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
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </Router>
  );
};

export default App;
