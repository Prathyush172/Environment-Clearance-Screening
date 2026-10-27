import React from 'react';
import { AlertTriangle } from 'lucide-react';

export const DisclaimerBanner: React.FC = () => {
  return (
    <div className="bg-amber-500 text-slate-900 px-4 py-2.5 shadow-sm font-medium text-xs sm:text-sm flex items-center justify-center gap-2">
      <AlertTriangle className="w-4 h-4 text-slate-950 flex-shrink-0" />
      <span>
        <strong>SCREENING OPINION ONLY:</strong> This service generates automated pre-screening opinions under India's EIA Notification 2006. It does not constitute a legal determination. An accredited environmental consultant must make the final determination.
      </span>
    </div>
  );
};
