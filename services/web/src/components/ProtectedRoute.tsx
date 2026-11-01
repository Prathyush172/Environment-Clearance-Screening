import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ShieldAlert } from 'lucide-react';

interface ProtectedRouteProps {
  children: React.ReactElement;
  allowedRoles?: string[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, allowedRoles }) => {
  const { user, isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-[50vh] flex flex-col items-center justify-center text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600 mb-3"></div>
        <p className="text-xs text-gray-500 font-medium">Verifying security session...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return (
      <div className="max-w-md mx-auto my-12 p-6 bg-red-50 border border-red-200 rounded-xl text-center">
        <ShieldAlert className="w-10 h-10 text-red-600 mx-auto mb-2" />
        <h2 className="text-base font-bold text-red-900">Access Restricted</h2>
        <p className="text-xs text-red-700 mt-1">
          Your current role (<strong>{user.role}</strong>) does not have permission to access this administrative resource.
        </p>
      </div>
    );
  }

  return children;
};
