import React, { useEffect, useState } from 'react';
import { ShieldAlert } from 'lucide-react';

export const Quarantine: React.FC = () => {
  const [items, setItems] = useState<any[]>([]);

  useEffect(() => {
    const token = localStorage.getItem("eia_auth_token");
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    fetch('/api/v1/quarantine?limit=10', { headers, credentials: "include" })
      .then(res => res.json())
      .then(data => setItems(data.items || []))
      .catch(() => {});
  }, []);

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center gap-3 border-b border-gray-200 pb-4 mb-4">
          <ShieldAlert className="w-6 h-6 text-red-600" />
          <div>
            <h2 className="text-lg font-bold text-gray-900">Quarantined Requests</h2>
            <p className="text-xs text-gray-500">Rejected submissions that failed schema or cross-field safety guardrails.</p>
          </div>
        </div>

        {items.length === 0 ? (
          <div className="text-center py-8 text-gray-400 text-sm">No quarantined submissions recorded yet.</div>
        ) : (
          <div className="space-y-3">
            {items.map((item, idx) => (
              <div key={idx} className="p-4 border border-red-100 bg-red-50/30 rounded-lg text-xs space-y-2">
                <div className="flex justify-between font-mono text-gray-600">
                  <span>Correlation: {item.correlation_id}</span>
                  <span>{item.created_at}</span>
                </div>
                <div className="font-semibold text-red-700">Errors:</div>
                <pre className="bg-white p-2 rounded border border-red-200 text-red-900 overflow-x-auto">
                  {JSON.stringify(item.field_errors, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
