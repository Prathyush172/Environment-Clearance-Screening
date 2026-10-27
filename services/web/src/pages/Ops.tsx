import React from 'react';
import { Activity } from 'lucide-react';

export const Ops: React.FC = () => {
  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
        <Activity className="w-12 h-12 text-emerald-600 mx-auto mb-3" />
        <h2 className="text-lg font-bold text-gray-900">System Operations & Monitoring</h2>
        <p className="text-sm text-gray-500 max-w-md mx-auto mt-1">
          Prometheus metrics are scraped on port 9090 and Grafana dashboards are served on port 3001. Distributed Jaeger tracing runs on port 16686.
        </p>
      </div>
    </div>
  );
};
