import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Loader2, CornerDownLeft } from "lucide-react";
import { searchAll } from "../services/api";

/**
 * ============================================================================
 *  GLOBAL SEARCH  (NEW IN DRAFT 5)
 * ============================================================================
 * Searches zones, alerts, incidents and citizen reports from the top bar.
 *
 * Everything visible here is finished: the dropdown, grouping by result type,
 * keyboard navigation (arrow keys, Enter, Escape), the loading state, the
 * "no results" state, click-outside-to-close, and the Ctrl+K / Cmd+K shortcut.
 *
 * LINK SPOT M (src/services/api.js → searchAll)
 *   Today it filters the local `searchIndex`. To go live, the backend team
 *   replaces that function body with a fetch to GET /api/search?q=...
 *   NOTHING IN THIS FILE CHANGES when that happens.
 *
 * Why the delay: typing "mangan" would fire six searches, one per letter.
 * We wait 200 ms after the last keystroke before asking — this is called
 * debouncing, and it is what stops the backend being hammered.
 * ============================================================================
 */

const DEBOUNCE_MS = 200;

// The order result groups appear in the dropdown.
const TYPE_ORDER = ["Zone", "Alert", "Incident", "Citizen report"];

const typeStyle = {
  Zone: "bg-risk-highSoft text-risk-high dark:bg-risk-high/20 dark:text-risk-highOn",
  Alert: "bg-risk-moderateSoft text-risk-moderate dark:bg-risk-moderate/20 dark:text-risk-moderateOn",
  Incident: "bg-paper-100 text-paper-600 dark:bg-night-800 dark:text-paper-400",
  "Citizen report": "bg-teal-50 text-teal-600 dark:bg-teal-600/20 dark:text-teal-100",
};

/** Bold the part of the text that matched what was typed. */
function Highlight({ text, query }) {
  const i = text.toLowerCase().indexOf(query.toLowerCase());
  if (!query || i === -1) return text;
  return (
    <>
      {text.slice(0, i)}
      <mark className="bg-transparent font-semibold text-ink-900 dark:text-paper-100">
        {text.slice(i, i + query.length)}
      </mark>
      {text.slice(i + query.length)}
    </>
  );
}

export default function SearchBox() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0); // which row the arrow keys are on

  const boxRef = useRef(null);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  // Typing is what starts a search, so the loading flag is set here rather
  // than inside the effect below.
  const handleChange = (value) => {
    setQuery(value);
    setOpen(true);
    if (value.trim()) {
      setLoading(true);
    } else {
      setResults([]);
      setLoading(false);
    }
  };

  // ---- run the search, 200 ms after typing stops -------------------------
  useEffect(() => {
    if (!query.trim()) return undefined;
    const timer = setTimeout(() => {
      searchAll(query).then((hits) => {
        setResults(hits);
        setActive(0);
        setLoading(false);
      });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  // ---- close when clicking anywhere else ---------------------------------
  useEffect(() => {
    const onClickAway = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onClickAway);
    return () => document.removeEventListener("mousedown", onClickAway);
  }, []);

  // ---- Ctrl+K / Cmd+K jumps into the search box --------------------------
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Flat list in display order, so the arrow keys move the way the eye does.
  const ordered = TYPE_ORDER.flatMap((t) => results.filter((r) => r.type === t));

  const goTo = (item) => {
    if (!item) return;
    setOpen(false);
    setQuery("");
    inputRef.current?.blur();
    navigate(item.to);
  };

  const onKeyDown = (e) => {
    if (e.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
      return;
    }
    if (!ordered.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => (i + 1) % ordered.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (i - 1 + ordered.length) % ordered.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      goTo(ordered[active]);
    }
  };

  return (
    <div ref={boxRef} className="relative hidden sm:block">
      <Search
        size={16}
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-paper-500"
      />
      <input
        ref={inputRef}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls="search-results"
        aria-label="Search locations, alerts, incidents and citizen reports"
        autoComplete="off"
        value={query}
        onChange={(e) => handleChange(e.target.value)}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder="Search locations, alerts, reports..."
        className="w-72 rounded-lg border border-paper-200 bg-paper-50 py-2 pl-9 pr-12 text-sm text-paper-700 placeholder:text-paper-500 focus:outline-none focus:ring-2 focus:ring-teal-600/30 dark:border-night-700 dark:bg-night-800 dark:text-paper-300"
      />
      {!query && (
        <kbd className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 rounded border border-paper-200 px-1.5 py-0.5 text-[10px] font-medium text-paper-500 dark:border-night-700">
          ⌘K
        </kbd>
      )}
      {loading && (
        <Loader2
          size={14}
          className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-paper-500"
        />
      )}

      {open && query.trim() !== "" && (
        <div
          id="search-results"
          role="listbox"
          className="absolute right-0 top-full mt-2 max-h-[26rem] w-[26rem] overflow-y-auto rounded-xl border border-paper-200 bg-white py-2 shadow-xl dark:border-night-700 dark:bg-night-900"
        >
          {!loading && ordered.length === 0 && (
            <p className="px-4 py-6 text-center text-sm text-paper-500">
              Nothing found for “{query}”.
            </p>
          )}

          {TYPE_ORDER.map((type) => {
            const group = results.filter((r) => r.type === type);
            if (!group.length) return null;
            return (
              <div key={type} className="pb-1">
                <p className="px-4 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-paper-500">
                  {type}
                  {group.length > 1 ? "s" : ""}
                </p>
                {group.map((item) => {
                  // Position in the flat `ordered` list, so the arrow-key
                  // highlight lines up with what is on screen.
                  const myIndex = ordered.findIndex((o) => o.id === item.id);
                  const isActive = myIndex === active;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      role="option"
                      aria-selected={isActive}
                      onMouseEnter={() => setActive(myIndex)}
                      onClick={() => goTo(item)}
                      className={`flex w-full items-start gap-3 px-4 py-2 text-left ${
                        isActive ? "bg-paper-100 dark:bg-night-800" : ""
                      }`}
                    >
                      <span
                        className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${typeStyle[item.type]}`}
                      >
                        {item.type}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm text-ink-800 dark:text-paper-200">
                          <Highlight text={item.title} query={query.trim()} />
                        </span>
                        <span className="block truncate text-xs text-paper-500">
                          {item.subtitle}
                        </span>
                      </span>
                      {isActive && (
                        <CornerDownLeft
                          size={13}
                          className="mt-1 shrink-0 text-paper-500"
                        />
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })}

          {ordered.length > 0 && (
            <p className="mt-1 border-t border-paper-200 px-4 pt-2 text-[10px] text-paper-500 dark:border-night-700">
              ↑ ↓ to move · Enter to open · Esc to close
            </p>
          )}
        </div>
      )}
    </div>
  );
}
