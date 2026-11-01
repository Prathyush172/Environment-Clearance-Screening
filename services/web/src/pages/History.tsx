import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  History as HistoryIcon,
  RefreshCw,
  ExternalLink,
  Clock,
  AlertTriangle,
  CheckCircle2,
  FileText,
  AlertCircle,
  PlusCircle,
  Database
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface ScreeningItem {
  run_id: string;
  project_name: string;
  status: string;
  route: string | null;
  created_at: string | null;
  completed_at: string | null;
  client_id: string;
  cost_usd?: number;
  verification_status?: string | null;
  verification_passed?: boolean | null;
}

export const History: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [screenings, setScreenings] = useState<ScreeningItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem("eia_auth_token");
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch("/api/v1/screenings?limit=50", {
        headers,
        credentials: "include",
      });

      if (res.status === 401) {
        throw new Error("Authentication session expired. Please log in again.");
      }
      if (!res.ok) {
        throw new Error(`Failed to load screening history (HTTP ${res.status})`);
      }

      const data = await res.json();
      setScreenings(data.items || []);
    } catch (err: any) {
      setError(err.message || "Failed to load screening records from server.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const getStatusBadge = (run: ScreeningItem) => {
    const status = run.status;
    switch (status) {
      case "COMPLETED":
        if (run.verification_passed === true || run.verification_status === "PASSED") {
          return (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
              <CheckCircle2 className="w-3 h-3" /> Completed (Verified)
            </span>
          );
        } else if (run.verification_status === "ERROR" || run.verification_passed === false) {
          return (
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-900 border border-amber-300">
              <AlertTriangle className="w-3 h-3 text-amber-600" /> Completed (Unverified)
            </span>
          );
        }
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
            <CheckCircle2 className="w-3 h-3" /> Completed
          </span>
        );
      case "ESCALATED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-900 border border-amber-200">
            <AlertTriangle className="w-3 h-3 text-amber-600" /> Escalated
          </span>
        );
      case "RUNNING":
      case "VERIFYING":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 animate-pulse">
            <Clock className="w-3 h-3" /> Processing
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800">
            <AlertCircle className="w-3 h-3" /> Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
            {status || "Queued"}
          </span>
        );
    }
  };

  const getRouteBadge = (route: string | null) => {
    if (!route) {
      return <span className="text-gray-400 italic text-xs">Pending</span>;
    }
    switch (route) {
      case "CATEGORY_A_CENTRAL":
        return (
          <span className="px-2 py-0.5 bg-red-100 text-red-800 font-bold rounded text-xs">
            Category A (Central)
          </span>
        );
      case "CATEGORY_B_STATE":
        return (
          <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 font-bold rounded text-xs">
            Category B (State)
          </span>
        );
      case "NO_CLEARANCE_REQUIRED":
        return (
          <span className="px-2 py-0.5 bg-blue-100 text-blue-800 font-bold rounded text-xs">
            No Clearance
          </span>
        );
      case "ESCALATED_TO_HUMAN":
        return (
          <span className="px-2 py-0.5 bg-amber-100 text-amber-900 border border-amber-300 font-semibold rounded text-xs">
            Escalated to Human
          </span>
        );
      default:
        return <span className="text-xs font-mono text-gray-700">{route}</span>;
    }
  };

  const formatDate = (isoString: string | null) => {
    if (!isoString) return "—";
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <HistoryIcon className="w-6 h-6 text-emerald-800" />
            <h1 className="text-xl font-bold text-gray-900">Screening History</h1>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Persisted clearance classification records for organization: <strong className="text-emerald-900">{user?.client_id || "All Tenants"}</strong>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchHistory(true)}
            disabled={refreshing || loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-white border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50 transition shadow-sm disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin text-emerald-700" : ""}`} />
            Refresh
          </button>
          <Link
            to="/"
            className="flex items-center gap-1.5 px-3.5 py-2 bg-emerald-800 hover:bg-emerald-900 text-white rounded-lg text-xs font-semibold transition shadow-sm"
          >
            <PlusCircle className="w-3.5 h-3.5" />
            New Screening
          </Link>
        </div>
      </div>

      {/* Main Container */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        {/* Loading State */}
        {loading && (
          <div className="py-16 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600 mx-auto mb-3"></div>
            <p className="text-xs text-gray-500 font-medium">Loading persisted screening records...</p>
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div className="p-8 text-center bg-red-50/50">
            <AlertCircle className="w-10 h-10 text-red-600 mx-auto mb-2" />
            <h3 className="text-sm font-bold text-red-900">Error Loading Screening Records</h3>
            <p className="text-xs text-red-700 mt-1 max-w-md mx-auto">{error}</p>
            <button
              onClick={() => fetchHistory(false)}
              className="mt-4 px-4 py-1.5 bg-red-700 text-white rounded-lg text-xs font-semibold hover:bg-red-800 transition"
            >
              Retry Connection
            </button>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && screenings.length === 0 && (
          <div className="py-16 px-4 text-center">
            <div className="w-12 h-12 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-3 border border-emerald-100">
              <FileText className="w-6 h-6 text-emerald-600" />
            </div>
            <h3 className="text-base font-bold text-gray-900">No Screening Records Yet</h3>
            <p className="text-xs text-gray-500 max-w-sm mx-auto mt-1">
              You haven't submitted any environmental clearance proposals yet. Start a new screening to classify your project under EIA 2006.
            </p>
            <div className="mt-5">
              <Link
                to="/"
                className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-800 hover:bg-emerald-900 text-white rounded-lg text-xs font-semibold shadow-sm transition"
              >
                <PlusCircle className="w-4 h-4" /> Start New Screening
              </Link>
            </div>
          </div>
        )}

        {/* Table of Persisted Screenings */}
        {!loading && !error && screenings.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-gray-50/80 border-b border-gray-200 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Project Name</th>
                  <th className="py-3 px-4">Run ID</th>
                  <th className="py-3 px-4">Submitted</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Clearance Route</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-xs">
                {screenings.map((run) => (
                  <tr
                    key={run.run_id}
                    onClick={() => navigate(`/runs/${run.run_id}`)}
                    className="hover:bg-emerald-50/30 cursor-pointer transition"
                  >
                    <td className="py-3.5 px-4 font-semibold text-gray-900 max-w-xs truncate">
                      {run.project_name || "Untitled Screening"}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-gray-500 text-[11px]">
                      {run.run_id.substring(0, 8)}...
                    </td>
                    <td className="py-3.5 px-4 text-gray-600 whitespace-nowrap">
                      {formatDate(run.created_at)}
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {getStatusBadge(run)}
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {getRouteBadge(run.route)}
                    </td>
                    <td className="py-3.5 px-4 text-right whitespace-nowrap">
                      <Link
                        to={`/runs/${run.run_id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-emerald-800 hover:text-emerald-950 font-semibold text-[11px] hover:bg-emerald-100 rounded transition"
                      >
                        View Result
                        <ExternalLink className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Footer info bar */}
        {!loading && !error && screenings.length > 0 && (
          <div className="bg-gray-50 border-t border-gray-200 px-4 py-2.5 flex items-center justify-between text-[11px] text-gray-500">
            <span className="flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-gray-400" />
              Showing {screenings.length} persisted records from database
            </span>
            <span>Click any record to inspect complete legal basis & citations</span>
          </div>
        )}
      </div>
    </div>
  );
};
