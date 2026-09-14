import { createContext, useContext, useState } from "react";

/**
 * ============================================================================
 *  REGION CONTEXT — selected NER state (NER expansion, phase 1)
 * ============================================================================
 * All 8 real North Eastern Region states are valid selections (migrations/
 * 008_ner_all_states.sql widened the backend's zones.state CHECK to match).
 * Sikkim is the only one with real populated zones right now -- every other
 * state exists as a real, valid value with zero rows until its own data
 * pipeline runs (see CLAUDE.md, scripts/ml/ml_config.py's STATE_CONFIGS).
 * "All States" and "Sikkim" are therefore functionally identical today;
 * this exists so every screen that reads zones/corridors is already
 * state-aware for all 8, not bolted on one at a time as each state's real
 * data actually lands.
 * ============================================================================
 */

export const NER_STATES = [
  "Sikkim",
  "Assam",
  "Arunachal Pradesh",
  "Manipur",
  "Meghalaya",
  "Mizoram",
  "Nagaland",
  "Tripura",
];

const RegionContext = createContext({ state: "", setState: () => {} });

export function RegionProvider({ children }) {
  // "" means "All States" -- getRiskZones/getCorridors treat empty/undefined
  // the same as no filter, matching the backend's optional `state` query param.
  const [state, setState] = useState("");

  return (
    <RegionContext.Provider value={{ state, setState }}>
      {children}
    </RegionContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useRegion() {
  return useContext(RegionContext);
}
