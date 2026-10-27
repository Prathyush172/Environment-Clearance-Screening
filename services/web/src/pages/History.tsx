import React from 'react';
import { History as HistoryIcon } from 'lucide-react';

export const History: React.FC = () => {
  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
        <HistoryIcon className="w-12 h-12 text-gray-400 mx-auto mb-3" />
        <h2 className="text-lg font-bold text-gray-900">Screening History</h2>
        <p className="text-sm text-gray-500 max-w-md mx-auto mt-1">
          Historical screening runs for your client ID are stored and persisted in PostgreSQL. Full table view arriving in Milestone 4.
        </p>
      </div>
    </div>
  );
};
