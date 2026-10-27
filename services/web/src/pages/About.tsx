import React from 'react';
import { Info, AlertTriangle } from 'lucide-react';

export const About: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 space-y-6">
        <div className="flex items-center gap-3 border-b border-gray-200 pb-4">
          <Info className="w-6 h-6 text-emerald-700" />
          <h2 className="text-xl font-bold text-gray-900">About the EIA Pre-Screening System</h2>
        </div>

        <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-3 text-amber-900 text-sm">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 text-amber-600 mt-0.5" />
          <div>
            <strong>DISCLAIMER:</strong> SCREENING OPINION ONLY: This is not a legal determination of environmental clearance requirements. An accredited environmental consultant must make the final determination. This system performs pre-screening only and does not constitute environmental impact assessment.
          </div>
        </div>

        <div className="space-y-4 text-sm text-gray-700 leading-relaxed">
          <h3 className="font-bold text-base text-gray-900">Statutory Framework</h3>
          <p>
            This system references the Environment Impact Assessment Notification, 2006 (S.O. 1533(E)) notified by the Ministry of Environment, Forest and Climate Change (MoEFCC), Government of India, along with all gazetted amendments through March 2025.
          </p>
          <h3 className="font-bold text-base text-gray-900">Key Screening Mechanisms</h3>
          <ul className="list-disc pl-5 space-y-1">
            <li><strong>Schedule Thresholds:</strong> Classification of activities into Category A (Central Level appraisal) or Category B (State SEIAA appraisal).</li>
            <li><strong>General Condition (GC):</strong> Mandatory modifier upgrading Category B projects to Category A if located within 5 km (or 10 km for specified heavy sectors) of Protected Areas, Eco-Sensitive Zones, Critically Polluted Areas, or Inter-State/International Boundaries.</li>
            <li><strong>Independent Verification:</strong> Secondary verifier agent cross-examining every citation and entailment claim before result finalization.</li>
          </ul>
        </div>
      </div>
    </div>
  );
};
