import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Send, Sparkles, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const INDIAN_STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
  "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
  "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
  "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
  "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
  "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
];

const PRESETS = [
  {
    title: "Reference Case: Mining near National Park (2 km)",
    desc: "Triggers General Condition upgrading Category B to Category A (Central Level)",
    data: {
      client_id: "demo-client-01",
      project_name: "Kudremukh Buffer Iron Ore Project",
      description: "Proposed open cast iron ore mining project over a lease area of 45 hectares with production capacity of 0.8 MTPA.",
      sector_hint: "Mining of minerals",
      capacity: { value: 0.8, unit: "MTPA" },
      area_ha: 45.0,
      location: { state: "Karnataka", district: "Chikkamagaluru", latitude: 13.21, longitude: 75.25 },
      proximity: [{ feature_type: "national_park", distance_km: 2.0, name: "Kudremukh National Park" }]
    }
  },
  {
    title: "Standard Mining Project (12 km from protected area)",
    desc: "Beyond 5 km threshold - remains Category B (State Level)",
    data: {
      client_id: "demo-client-01",
      project_name: "Sandur Commercial Bauxite Mine",
      description: "Establishment of new bauxite mining operations across an area of 35 hectares with modern dust suppression.",
      sector_hint: "Mining of minerals",
      capacity: { value: 0.5, unit: "MTPA" },
      area_ha: 35.0,
      location: { state: "Karnataka", district: "Ballari", latitude: 15.08, longitude: 76.54 },
      proximity: [{ feature_type: "wildlife_sanctuary", distance_km: 12.0, name: "Daroji Bear Sanctuary" }]
    }
  },
  {
    title: "Thermal Power Plant (8 km from boundary)",
    desc: "Item 1(d) enhanced 10 km GC threshold triggers Category A upgrade",
    data: {
      client_id: "demo-client-02",
      project_name: "Raichur Super Thermal Power Extension",
      description: "Expansion of coal-based thermal power plant by 250 MW with supercritical boiler technology.",
      sector_hint: "Thermal Power Plants",
      capacity: { value: 250.0, unit: "MW" },
      area_ha: 120.0,
      location: { state: "Karnataka", district: "Raichur", latitude: 16.20, longitude: 77.34 },
      proximity: [{ feature_type: "inter_state_boundary", distance_km: 8.0, name: "Telangana Border" }]
    }
  }
];

export const NewScreening: React.FC = () => {
  const navigate = useNavigate();
  const [clientId, setClientId] = useState(() => localStorage.getItem("eia_client_id") || "client-" + Math.random().toString(36).substring(2, 7));
  const [projectName, setProjectName] = useState("");
  const [description, setDescription] = useState("");
  const [sectorHint, setSectorHint] = useState("");
  const [capacityValue, setCapacityValue] = useState("");
  const [capacityUnit, setCapacityUnit] = useState("MTPA");
  const [areaHa, setAreaHa] = useState("");
  const [stateName, setStateName] = useState("Karnataka");
  const [district, setDistrict] = useState("");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  
  // Proximity
  const [hasProximity, setHasProximity] = useState(false);
  const [featureType, setFeatureType] = useState("national_park");
  const [distanceKm, setDistanceKm] = useState("");
  const [featureName, setFeatureName] = useState("");

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    localStorage.setItem("eia_client_id", clientId);
  }, [clientId]);

  const loadPreset = (preset: typeof PRESETS[0]) => {
    const d = preset.data;
    setClientId(d.client_id);
    setProjectName(d.project_name);
    setDescription(d.description);
    setSectorHint(d.sector_hint);
    setCapacityValue(d.capacity ? String(d.capacity.value) : "");
    setCapacityUnit(d.capacity ? d.capacity.unit : "MTPA");
    setAreaHa(d.area_ha ? String(d.area_ha) : "");
    setStateName(d.location.state);
    setDistrict(d.location.district || "");
    setLatitude(d.location.latitude ? String(d.location.latitude) : "");
    setLongitude(d.location.longitude ? String(d.location.longitude) : "");

    if (d.proximity && d.proximity.length > 0) {
      setHasProximity(true);
      setFeatureType(d.proximity[0].feature_type);
      setDistanceKm(String(d.proximity[0].distance_km));
      setFeatureName(d.proximity[0].name || "");
    } else {
      setHasProximity(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);

    const payload: any = {
      client_id: clientId,
      project_name: projectName,
      description: description,
      sector_hint: sectorHint || undefined,
      area_ha: areaHa ? parseFloat(areaHa) : undefined,
      location: {
        state: stateName,
        district: district || undefined,
        latitude: latitude ? parseFloat(latitude) : undefined,
        longitude: longitude ? parseFloat(longitude) : undefined,
      }
    };

    if (capacityValue) {
      payload.capacity = {
        value: parseFloat(capacityValue),
        unit: capacityUnit,
      };
    }

    if (hasProximity && distanceKm) {
      payload.proximity = [
        {
          feature_type: featureType,
          distance_km: parseFloat(distanceKm),
          name: featureName || undefined,
        }
      ];
    }

    try {
      const token = localStorage.getItem("eia_auth_token");
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch("/api/v1/screenings", {
        method: "POST",
        headers,
        credentials: "include",
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.status === 202) {
        navigate(`/runs/${data.run_id}`);
      } else {
        setErrorMsg(data.detail || JSON.stringify(data.errors) || "Validation error");
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Network error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
      {/* Form Column */}
      <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-1">New Environmental Clearance Pre-Screening</h2>
        <p className="text-sm text-gray-500 mb-6">Enter project proposal parameters to determine applicable EIA Schedule route.</p>

        {errorMsg && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3 text-red-800 text-sm">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-600 mt-0.5" />
            <div>
              <strong>Validation Failed:</strong>
              <div className="mt-1">{errorMsg}</div>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">Client ID</label>
              <input
                type="text"
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                value={clientId}
                onChange={e => setClientId(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">Project Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Iron Ore Mine Expansion"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                value={projectName}
                onChange={e => setProjectName(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">Project Description (min 20 chars)</label>
            <textarea
              required
              rows={3}
              placeholder="Detailed description of activities, processes, and project scope..."
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              value={description}
              onChange={e => setDescription(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">Sector Hint</label>
              <input
                type="text"
                placeholder="e.g. Mining of minerals"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                value={sectorHint}
                onChange={e => setSectorHint(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">Capacity</label>
              <div className="flex gap-2">
                <input
                  type="number"
                  step="any"
                  placeholder="Value"
                  className="w-2/3 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                  value={capacityValue}
                  onChange={e => setCapacityValue(e.target.value)}
                />
                <select
                  className="w-1/3 border border-gray-300 rounded-lg px-2 py-2 text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                  value={capacityUnit}
                  onChange={e => setCapacityUnit(e.target.value)}
                >
                  <option value="MTPA">MTPA</option>
                  <option value="MW">MW</option>
                  <option value="TPD">TPD</option>
                  <option value="MLD">MLD</option>
                  <option value="ha">ha</option>
                  <option value="km">km</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">Total Area (ha)</label>
              <input
                type="number"
                step="any"
                placeholder="Hectares"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                value={areaHa}
                onChange={e => setAreaHa(e.target.value)}
              />
            </div>
          </div>

          {/* Location */}
          <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
            <h3 className="text-xs font-bold text-gray-800 uppercase tracking-wider mb-3">Location Details</h3>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
              <div>
                <label className="block text-xs text-gray-600 mb-1">State / UT</label>
                <select
                  className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white"
                  value={stateName}
                  onChange={e => setStateName(e.target.value)}
                >
                  {INDIAN_STATES.map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">District</label>
                <input
                  type="text"
                  placeholder="District"
                  className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white"
                  value={district}
                  onChange={e => setDistrict(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">Latitude</label>
                <input
                  type="number"
                  step="any"
                  placeholder="e.g. 13.21"
                  className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white"
                  value={latitude}
                  onChange={e => setLatitude(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">Longitude</label>
                <input
                  type="number"
                  step="any"
                  placeholder="e.g. 75.25"
                  className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white"
                  value={longitude}
                  onChange={e => setLongitude(e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Proximity / Sensitive Areas */}
          <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-bold text-gray-800 uppercase tracking-wider">Proximity to Sensitive Areas / Boundaries</h3>
              <label className="flex items-center gap-2 text-xs text-gray-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={hasProximity}
                  onChange={e => setHasProximity(e.target.checked)}
                  className="rounded text-emerald-600 focus:ring-emerald-500"
                />
                Include Proximity Feature
              </label>
            </div>

            {hasProximity && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3 pt-3 border-t border-gray-200">
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Feature Type</label>
                  <select
                    className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white"
                    value={featureType}
                    onChange={e => setFeatureType(e.target.value)}
                  >
                    <option value="national_park">National Park</option>
                    <option value="wildlife_sanctuary">Wildlife Sanctuary</option>
                    <option value="eco_sensitive_zone">Eco-Sensitive Zone</option>
                    <option value="critically_polluted_area">Critically Polluted Area</option>
                    <option value="inter_state_boundary">Inter-State Boundary</option>
                    <option value="international_boundary">International Boundary</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Distance (km)</label>
                  <input
                    type="number"
                    step="any"
                    required={hasProximity}
                    placeholder="e.g. 2.0"
                    className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white"
                    value={distanceKm}
                    onChange={e => setDistanceKm(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Feature Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Bandipur National Park"
                    className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm bg-white"
                    value={featureName}
                    onChange={e => setFeatureName(e.target.value)}
                  />
                </div>
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-emerald-700 hover:bg-emerald-800 text-white font-medium py-3 px-4 rounded-lg flex items-center justify-center gap-2 shadow-sm transition disabled:opacity-50"
          >
            {loading ? "Submitting screening..." : (
              <>
                <Send className="w-4 h-4" /> Run Environmental Pre-Screening
              </>
            )}
          </button>
        </form>
      </div>

      {/* Presets Sidebar */}
      <div className="space-y-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-3 text-emerald-800 font-bold text-sm">
            <Sparkles className="w-4 h-4" /> Benchmark Test Presets
          </div>
          <p className="text-xs text-gray-500 mb-4">Click any preset to autofill the form with test scenarios from the specification.</p>

          <div className="space-y-3">
            {PRESETS.map((p, i) => (
              <div
                key={i}
                onClick={() => loadPreset(p)}
                className="p-3 border border-gray-200 rounded-lg hover:border-emerald-500 hover:bg-emerald-50/50 cursor-pointer transition text-left"
              >
                <div className="text-sm font-semibold text-gray-900">{p.title}</div>
                <div className="text-xs text-gray-500 mt-1">{p.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
