import { useRegion, NER_STATES } from "../context/RegionContext";

/**
 * Filters the map, stat cards, and Highway Corridors by NER state. Sikkim is
 * the only state with real zones right now -- "All States" and "Sikkim"
 * show identical results until Assam/Mizoram's own data pipeline runs (see
 * CLAUDE.md, NER expansion phase 1).
 */
export default function StateSelector() {
  const { state, setState } = useRegion();

  return (
    <select
      value={state}
      onChange={(e) => setState(e.target.value)}
      aria-label="Filter by NER state"
      className="rounded-lg border border-paper-200 bg-white px-2.5 py-1.5 text-xs font-medium text-paper-700 hover:bg-paper-50 dark:border-night-700 dark:bg-night-800 dark:text-paper-300 dark:hover:bg-night-700"
    >
      <option value="">All States</option>
      {NER_STATES.map((s) => (
        <option key={s} value={s}>
          {s}
        </option>
      ))}
    </select>
  );
}
