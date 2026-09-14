import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext";
import { RegionProvider } from "./context/RegionContext";
import Overview from "./pages/Overview";
import Alerts from "./pages/Alerts";
import Incidents from "./pages/Incidents";
import HighwayCorridors from "./pages/HighwayCorridors";
import EmergencyContacts from "./pages/EmergencyContacts";
import AuthorityContacts from "./pages/AuthorityContacts";
import ZoneDetail from "./pages/ZoneDetail";
import DataObservations from "./pages/DataObservations";
import DataMethodology from "./pages/DataMethodology";
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
 * light/dark theme — see src/context/ThemeContext.jsx. RegionProvider does
 * the same for the selected NER state (all 8 real NER states — see
 * NER_STATES) — see src/context/RegionContext.jsx.
 */
export default function App() {
  return (
    <ThemeProvider>
      <RegionProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/incidents" element={<Incidents />} />
            <Route path="/highway-corridors" element={<HighwayCorridors />} />
            <Route path="/emergency-contacts" element={<EmergencyContacts />} />
            <Route path="/authority-contacts" element={<AuthorityContacts />} />
            <Route path="/zones/:zoneId" element={<ZoneDetail />} />
            <Route path="/data-observations" element={<DataObservations />} />
            <Route path="/data-methodology" element={<DataMethodology />} />
            <Route path="/citizen-reports" element={<CitizenReports />} />
            <Route path="/help" element={<HelpDocs />} />
          </Routes>
        </BrowserRouter>
      </RegionProvider>
    </ThemeProvider>
  );
}
