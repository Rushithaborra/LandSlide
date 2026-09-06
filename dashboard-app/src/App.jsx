import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext";
import Overview from "./pages/Overview";
import Alerts from "./pages/Alerts";
import Incidents from "./pages/Incidents";
import DataObservations from "./pages/DataObservations";
import CitizenReports from "./pages/CitizenReports";
import HelpDocs from "./pages/HelpDocs";

/**
 * All page routes live here. Match this list against the sidebar links in
 * src/components/Sidebar.jsx if you ever add/remove a page.
 *
 * REMOVED IN DRAFT 3: /live-map, /settings and /reports.
 *  - the map itself still lives on the Overview page (RiskMap component)
 *  - the Reports page's job (downloading a report file) moved to the
 *    Incidents page as a per-incident "Download" button
 *
 * ThemeProvider wraps everything so any component can read or flip the
 * light/dark theme — see src/context/ThemeContext.jsx.
 */
export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/incidents" element={<Incidents />} />
          <Route path="/data-observations" element={<DataObservations />} />
          <Route path="/citizen-reports" element={<CitizenReports />} />
          <Route path="/help" element={<HelpDocs />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
