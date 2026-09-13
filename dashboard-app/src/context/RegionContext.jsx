import { createContext, useContext, useState } from "react";

/**
 * ============================================================================
 *  REGION CONTEXT — selected NER state (NER expansion, phase 1)
 * ============================================================================
 * Sikkim is the only state with real populated zones right now (Assam and
 * Mizoram exist as valid values with zero rows until their own data
 * pipeline runs -- see CLAUDE.md). "All States" and "Sikkim" are therefore
 * functionally identical today; this exists so every screen that reads
 * zones/corridors is already state-aware, not bolted on later once a
 * second state's data actually lands.
 * ============================================================================
 */

export const NER_STATES = ["Sikkim", "Assam", "Mizoram"];

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
